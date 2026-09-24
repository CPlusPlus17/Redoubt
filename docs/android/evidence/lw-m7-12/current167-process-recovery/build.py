#!/usr/bin/env python3
"""Prepare/review or explicitly execute the current167 APK rebuild only."""
import argparse
import json
from pathlib import Path
import sys

import common as c


def prepare(selection):
    c.select_inputs(selection)
    config = c.base_config('apk')
    c.fresh_namespace(c.BUILD); c.fresh_namespace(c.OUTPUT)
    config['command'] = c.build_command()
    return config


def validate(path, digest):
    config = c.load_config(path, digest, 'apk')
    c.require(config['command'] == c.build_command(), 'build command differs')
    c.fresh_namespace(c.BUILD); c.fresh_namespace(c.OUTPUT)
    return config


def execute(path, digest):
    c.guest_guard()
    config = validate(path, digest)
    c.own_service('apk')
    state = c.initial_state('apk', path, config, c.BUILD)
    try:
        c.source_check(c.BUILD / 'source-before.txt')
        c.native_check(c.BUILD / 'native-before.txt')
        code = c.run_stage(state, c.BUILD, 'build', c.build_command())
        c.source_check(c.BUILD / 'source-after.txt')
        c.native_check(c.BUILD / 'native-after.txt')
        c.require(code == 0, 'APK rebuild failed')
        apks = c.apk_set(c.OUTPUT / 'apk')
        state['apks'] = apks
        metadata = c.OUTPUT / 'apk/output-metadata.json'
        c.require(json.loads(metadata.read_text())['applicationId'] == 'org.redoubtbrowser',
                  'unexpected packaged application ID')
        state['metadata'] = c.record(metadata)
        state['resources'] = {}
        c.write_json(c.BUILD / 'result.json', state)
        for name, apk in apks.items():
            label = name + '-resource'
            command = [sys.executable, str(c.REPO / 'docs/android/evidence/lw-m7-30/check-source.py'),
                       '--apk', apk['path'], '--aapt2', str(c.AAPT)]
            c.require(c.run_stage(state, c.BUILD, label, command) == 0,
                      'actual APK resource verifier failed: ' + name)
            state['resources'][name] = c.resource_receipt((c.BUILD / (label + '.log')).read_text(), apk)
            c.write_json(c.BUILD / 'result.json', state)
        c.require(c.apk_set(c.OUTPUT / 'apk') == apks, 'new APKs changed during verification')
        c.require(c.record(metadata) == state['metadata'], 'APK metadata changed')
        c.source_check(c.BUILD / 'source-after.txt')
        c.native_check(c.BUILD / 'native-after.txt')
        c.load_config(path, digest, 'apk')
        sums = ''.join(row['sha256'] + '  ' + name + '\n' for name, row in sorted(apks.items()))
        (c.BUILD / 'SHA256SUMS.development').write_text(sums)
        state['apk_manifest'] = c.record(c.BUILD / 'SHA256SUMS.development')
        state['status'] = 'PASS'
        state['scope'] = ('Current167 debug-signed release-variant APK build and all four actual resource checks only. '
                          'Native4 inputs reused unchanged; runtime and later native increments remain pending.')
        return 0
    except BaseException as error:
        state.update(status='FAIL', error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        c.finish(state, c.BUILD)
        if state['status'] != 'PASS' and sys.exc_info()[0] is None:
            raise RuntimeError(state.get('final_input_error', 'APK checkpoint incomplete'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--print-config', action='store_true', help='Read-only guest capture; review redirected JSON before --run')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--config-sha256')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--source-stage')
    parser.add_argument('--test-evidence')
    parser.add_argument('--source-manifest-sha256')
    parser.add_argument('--test-service-name')
    parser.add_argument('--test-invocation')
    parser.add_argument('--native-manifest')
    args = parser.parse_args()
    if args.print_config:
        c.require(not args.run and not args.config and not args.config_sha256, 'capture is separate from execution')
        selection = {key: getattr(args, key) for key in ('source_stage', 'test_evidence',
                     'source_manifest_sha256', 'test_service_name', 'test_invocation', 'native_manifest')}
        c.require(all(isinstance(value, str) and value for value in selection.values()),
                  'config capture requires all six explicit source/test/native selection arguments')
        print(json.dumps(prepare(selection), indent=2))
        return 0
    c.require(not any(getattr(args, key) for key in ('source_stage', 'test_evidence',
                     'source_manifest_sha256', 'test_service_name', 'test_invocation', 'native_manifest')),
              'execution uses only the reviewed config selection')
    c.require(args.config is not None and args.config_sha256, 'explicit config and reviewed digest required')
    if args.run:
        return execute(args.config, args.config_sha256)
    config = validate(args.config, args.config_sha256)
    print(json.dumps({'status': 'PLAN ONLY', 'command': config['command'],
                      'source_sha256': c.CURRENT, 'source_count': 167}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
