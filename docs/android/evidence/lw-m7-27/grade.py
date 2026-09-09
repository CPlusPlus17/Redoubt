#!/usr/bin/env python3
"""Fail-closed grading for individually selected native Android test logs."""
import hashlib
import json
from pathlib import Path
import re


class InvalidResult(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InvalidResult(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def bound_log(receipt, directory):
    """A producer receipt must bind successful completion, freshness and exact bytes.

    This detects stale/replaced local evidence; it is not a signature or an
    authenticity claim about a deliberately fabricated receipt.
    """
    require(receipt.get('exit') == 0, 'process did not exit successfully')
    require(re.fullmatch(r'[a-f0-9]{32}', receipt.get('run_id', '')), 'missing run id')
    require(isinstance(receipt.get('started_ns'), int), 'missing start time')
    require(isinstance(receipt.get('finished_ns'), int) and receipt['finished_ns'] > receipt['started_ns'], 'missing/invalid completion time')
    require(re.fullmatch(r'[a-f0-9]{64}', receipt.get('source_binding_sha256', '')), 'missing source binding')
    require(re.fullmatch(r'[a-f0-9]{64}', receipt.get('build_receipt_sha256', '')), 'missing build binding')
    require(receipt.get('log_created_ns', 0) >= receipt['started_ns'], 'log predates this invocation')
    name = receipt.get('log', '')
    require(name and Path(name).name == name, 'log must be a direct child of its fresh run directory')
    path = Path(directory) / name
    require(path.is_file() and path.stat().st_size > 0, 'missing/empty log')
    require(sha(path) == receipt.get('log_sha256'), 'log bytes do not match receipt')
    return path.read_text(encoding='utf-8', errors='strict')


def grade_xpcshell(raw, spec):
    require(raw.endswith('\n'), 'partial final mozlog record')
    events = []
    for line in raw.splitlines():
        require(bool(line.strip()), 'empty mozlog record')
        try:
            value = json.loads(line)
        except (ValueError, TypeError) as error:
            raise InvalidResult('malformed mozlog record') from error
        require(isinstance(value, dict) and isinstance(value.get('action'), str), 'invalid mozlog event')
        events.append(value)
    require(events, 'empty mozlog')
    required = set(spec['tasks'])
    allowed_skips = set(spec.get('allowed_skips', []))
    require(required and not required & allowed_skips, 'invalid required/skip task set')
    def is_file(name):
        return isinstance(name, str) and (name == Path(spec['path']).name or name.replace('\\', '/').endswith(spec['path']))

    running = None
    started = set()
    finished = set()
    skipped = set()
    suites = ends = starts = file_ends = 0
    for event in events:
        action = event['action']
        require(action != 'crash', 'crash diagnostic')
        if action == 'assertion_count':
            require(event.get('count') == 0, 'native assertion diagnostic')
        if action == 'suite_start':
            suites += 1
            require(suites == 1 and not starts and not ends, 'duplicate/out-of-order suite start')
        elif action == 'suite_end':
            ends += 1
            require(suites == 1 and ends == 1 and file_ends == 1 and running is None, 'premature/duplicate suite end')
        elif action == 'test_start':
            starts += 1
            test = event.get('test', '').replace('\\', '/')
            expected = spec['path']
            require(is_file(test), 'unexpected selected test file')
            require(suites == 1 and starts == 1 and not ends, 'duplicate/out-of-order test file')
            running = test
        elif action == 'test_end':
            require(running is not None and event.get('test') == running and not ends, 'unmatched test end')
            require(event.get('status') == 'PASS' and event.get('expected', 'PASS') == 'PASS', 'test file failed/skipped')
            file_ends += 1
            running = None
        elif action == 'test_status':
            require(running is not None and not ends, 'subtest outside selected file')
            require(is_file(event.get('test')), 'subtest belongs to another file')
            status = event.get('status')
            if status == 'SKIP':
                name = event.get('subtest')
                require(name in allowed_skips and name not in required, 'required/unclassified skipped subtest')
                skipped.add(name)
            else:
                require(status == 'PASS' and event.get('expected', 'PASS') == 'PASS', 'failed/unexpected subtest')
        elif action == 'log':
            require(event.get('level') not in {'ERROR', 'CRITICAL'}, 'harness error diagnostic')
            message = event.get('message', '')
            start = re.search(r'^(.*?) \| Starting (?:setup )?([A-Za-z_][A-Za-z_0-9]*)$', message)
            finish = re.search(r'\| test ([A-Za-z_][A-Za-z_0-9]*) finished \(\d+\)$', message)
            if start and start[2] in required:
                require(is_file(start[1]), 'named task log belongs to another file')
                name = start[2]
                require(running is not None and name not in started and not ends, 'duplicate/out-of-scope task start')
                started.add(name)
            if finish and finish[1] in required:
                name = finish[1]
                require(running is not None and name in started and name not in finished and not ends, 'unmatched/duplicate task finish')
                finished.add(name)
    require(suites == ends == starts == file_ends == 1 and running is None, 'incomplete suite/file lifecycle')
    require(started == finished == required and not required & skipped, 'missing/incomplete named tasks')
    return {'file': spec['path'], 'passed_tasks': sorted(finished), 'allowed_skips_observed': sorted(skipped)}


def grade_instrumentation(raw, expected):
    require(raw.endswith('\n'), 'partial instrumentation output')
    require(expected and len(expected) == len(set(expected)), 'invalid expected test list')
    expected = set(expected)
    passed = set()
    active = None
    fields = {}
    completed = False
    final_codes = 0
    for line in raw.splitlines():
        if line.startswith('INSTRUMENTATION_STATUS: '):
            key, separator, value = line[len('INSTRUMENTATION_STATUS: '):].partition('=')
            require(separator, 'malformed instrumentation status')
            require(key not in fields, 'duplicate instrumentation status field')
            fields[key] = value
        elif line.startswith('INSTRUMENTATION_STATUS_CODE: '):
            require(not completed, 'test event after final result')
            try:
                code = int(line.split(': ', 1)[1])
            except ValueError as error:
                raise InvalidResult('malformed status code') from error
            name = fields.get('class', '') + '#' + fields.get('test', '')
            require(name in expected, 'unrequested/missing named instrumented test')
            require(fields.get('numtests') == str(len(expected)), 'instrumentation count differs from selected methods')
            if code == 1:
                require(active is None and name not in passed, 'duplicate/concurrent test start')
                active = name
            elif code == 0:
                require(active == name and name not in passed, 'unmatched test completion')
                passed.add(name)
                active = None
            else:
                raise InvalidResult('failed/skipped/assumption/incomplete instrumented test')
            fields = {}
        elif line.startswith('INSTRUMENTATION_CODE: '):
            final_codes += 1
            require(line == 'INSTRUMENTATION_CODE: -1' and final_codes == 1, 'instrumentation did not finish successfully')
            require(active is None and not fields and passed == expected, 'partial instrumentation suite')
            completed = True
        elif line.startswith(('INSTRUMENTATION_FAILED:', 'INSTRUMENTATION_ABORTED:', 'INSTRUMENTATION_RESULT: shortMsg=', 'INSTRUMENTATION_RESULT: longMsg=')):
            raise InvalidResult('instrumentation aborted/crashed')
    require(completed and final_codes == 1 and passed == expected, 'missing final instrumentation result')
    require(re.search(r'^OK \(' + str(len(expected)) + r' tests?\)\s*$', raw, re.M), 'missing matching JUnit completion summary')
    return {'passed_methods': sorted(passed)}


def grade_run(directory):
    directory = Path(directory)
    load = lambda name: json.loads((directory / name).read_text())
    invocation = load('invocation.json')
    build = load('build-receipt.json')
    binding = load('source-binding.json')
    requirements = load('requirements.json')
    require(build.get('status') == 'PASS', 'test build did not pass')
    require(sha(directory / 'build-receipt.json') == invocation.get('build_receipt_sha256'), 'build receipt changed')
    require(sha(directory / 'source-binding.json') == invocation.get('source_binding_sha256') == build.get('source_binding_sha256'), 'source binding changed')
    require(sha(directory / 'requirements.json') == build.get('requirements_sha256') == binding.get('requirements_sha256'), 'test requirements changed')
    require(load('source-after-tests.json') == binding, 'source changed during tests or completion missing')
    results = []
    names = [f'xpcshell-{i}.raw-receipt.json' for i in range(len(requirements['xpcshell']))] + ['instrumentation.log.receipt.json']
    for name in names:
        receipt = load(name)
        for key in ['run_id', 'source_binding_sha256', 'build_receipt_sha256']:
            require(receipt.get(key) == invocation.get(key), 'receipt belongs to a different run/build/source')
        raw = bound_log(receipt, directory)
        if name.startswith('xpcshell-'):
            index = int(name.split('-')[1].split('.')[0])
            results.append(grade_xpcshell(raw, requirements['xpcshell'][index]))
        else:
            results.append(grade_instrumentation(raw, requirements['instrumentation']))
    return dict(invocation, status='PASS', results=results, scope='separate instrumented test build only; not release APK acceptance')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Regrade a self-contained archived native-test evidence directory')
    parser.add_argument('run_directory', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(grade_run(args.run_directory), indent=2))
    except (InvalidResult, ValueError, OSError) as error:
        parser.exit(1, f'FAIL / NOT ACCEPTED: {error}\n')
