#!/usr/bin/env python3
"""Build all native ABIs from an explicitly reviewed, already staged source tree."""
import argparse
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('native_checkpoint_helpers', HERE / 'checkpoint.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
REPO = c.REPO
DEPENDENCIES = (
    'scripts/android-fat-aar.sh', 'assets/mozconfig.android',
    'docs/android/evidence/lw-m7-25/podman-native-bounded.sh',
    'docs/android/evidence/lw-m7-12/candidate5/native.py',
    'docs/android/evidence/lw-m7-12/candidate5/checkpoint.py',
    'docs/android/evidence/lw-m7-12/candidate5/grade.py',
    'docs/android/evidence/lw-m7-12/grade-extended-tests.py',
)


def load(path):
    inputs = json.loads(path.read_text())
    c.require(inputs['schema'] == 1, 'unsupported schema')
    c.require(re.fullmatch('native5-[a-z0-9-]+', inputs['run_id']) is not None,
              'explicit new native5 run ID required')
    c.require(inputs['service_name'] == 'redoubt-' + inputs['run_id'] + '.service',
              'service must match run ID')
    c.require(inputs['reviewed_scope_note'].strip(), 'explicit reviewed source scope required')
    image = inputs['container_image_id']
    c.require(image.startswith('sha256:') and c.sha(image[7:]), 'immutable image digest required')
    dt.datetime.strptime(inputs['build_date'], '%Y%m%d%H%M%S')
    c.require(re.fullmatch('[0-9]{14}', inputs['build_date']) is not None, 'build date must be exact')
    work, source = c.absolute(inputs['work']), c.absolute(inputs['source_dir'])
    c.require(source.is_relative_to(work) and source != work, 'source must be inside work tree')
    destination = work / inputs['run_id']
    c.require(not destination.exists(), 'native output already exists; preserve it')
    c.require(set(inputs['repository_files']) == set(DEPENDENCIES), 'dependency inventory differs')
    for name, value in inputs['repository_files'].items():
        c.require(c.digest(REPO / name) == value, 'dependency changed: ' + name)
    manifest = c.checked_file(inputs['source_manifest'])
    rows = c.source_manifest(manifest, inputs['source_manifest']['count'])
    c.verify_sources(source, rows)
    stage = c.checked_file(inputs['source_staging_receipt'])
    # The complete staging receipt is retained as provenance; the selected
    # reviewed manifest is the authoritative inventory verified above.
    seed = c.absolute(inputs['gradle_home_seed'])
    c.require(seed.is_dir() and seed.is_relative_to(work) and not seed.is_relative_to(destination),
              'existing guest Gradle cache seed required')
    command = [str(REPO / 'scripts/android-fat-aar.sh'), '--srcdir', str(source),
               '--outdir', str(destination / 'aar'), '--engine',
               str(REPO / 'docs/android/evidence/lw-m7-25/podman-native-bounded.sh'),
               '--abis', ','.join(c.ABIS), '--fat-host-abi', 'x86_64',
               '--jobs', '4', '--build-date', inputs['build_date'], '--image', image]
    return inputs, source, destination, manifest, rows, stage, seed, command


def run(path, context):
    inputs, source, destination, manifest, rows, stage, seed, command = context
    c.require(os.getuid() == 1001 and c.query(['id', '-un']) == 'runner', 'requires guest runner')
    os.environ['XDG_RUNTIME_DIR'] = '/run/user/1001'
    c.require(c.query(['systemd-detect-virt', '--vm']) == 'kvm', 'requires KVM guest')
    c.require(not c.query(['podman', '--remote=false', 'ps', '-q']), 'another container is active')
    processes = subprocess.run(['pgrep', '-f', '[e]mulator.*-avd|[q]emu-system'], capture_output=True)
    c.require(processes.returncode == 1, 'emulator active or process inspection failed')
    observed_image = c.query(['podman', '--remote=false', 'image', 'inspect', '--format',
                              '{{.Id}}', inputs['container_image_id']]).removeprefix('sha256:')
    c.require(c.sha(observed_image) and 'sha256:' + observed_image == inputs['container_image_id'],
              'actual image identity differs')
    invocation = os.environ.get('INVOCATION_ID', '')
    c.require(re.fullmatch('[0-9a-f]{32}', invocation) is not None, 'actual service invocation required')
    service = dict(line.split('=', 1) for line in c.query([
        'systemctl', '--user', 'show', inputs['service_name'], '-p', 'InvocationID',
        '-p', 'RemainAfterExit']).splitlines())
    c.require(service == {'InvocationID': invocation, 'RemainAfterExit': 'yes'},
              'launch matching service with RemainAfterExit=yes to preserve terminal identity')
    # Repeat read-only validation immediately before creating any output.
    c.require(load(path) == context, 'inputs changed after preflight')
    destination.mkdir()
    evidence = destination / 'evidence'; evidence.mkdir()
    out = destination / 'aar'; out.mkdir()
    shutil.copy2(path, evidence / 'inputs.json')
    shutil.copy2(manifest, evidence / 'source-sha256.txt')
    shutil.copy2(stage, evidence / 'source-staging-receipt.json')
    (evidence / 'initial-service.json').write_text(json.dumps(service, indent=2) + '\n')
    (evidence / 'boot-id.txt').write_text(Path('/proc/sys/kernel/random/boot_id').read_text())
    (evidence / 'started.txt').write_text(dt.datetime.now(dt.timezone.utc).isoformat() + '\n')
    state = {'schema': 1, 'status': 'RUNNING', 'service_name': inputs['service_name'],
             'invocation_id': invocation, 'source_dir': str(source),
             'build_date': inputs['build_date'], 'container_image_id': inputs['container_image_id'],
             'reviewed_scope_note': inputs['reviewed_scope_note'], 'command': command}

    def save():
        (evidence / 'result.json').write_text(json.dumps(state, indent=2) + '\n')

    def check_sources(name):
        c.verify_sources(source, rows)
        (evidence / name).write_text(''.join(key + ': OK\n' for key in rows))

    save()
    try:
        check_sources('source-before.txt')
        subprocess.run(['cp', '-a', '--reflink=auto', str(seed), str(out / 'gradle-home')], check=True)
        with (evidence / 'native-build.log').open('w') as stream:
            result = subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT)
        (evidence / 'build-exit.txt').write_text(str(result.returncode) + '\n')
        check_sources('source-after.txt')
        for name, value in inputs['repository_files'].items():
            c.require(c.digest(REPO / name) == value, 'dependency changed during build: ' + name)
        c.require(result.returncode == 0, 'native build failed')
        state['aars'] = {abi: c.record(out / abi / 'target.maven.zip') for abi in c.ABIS}
        merged = list(out.glob('geckoview-*.aar'))
        c.require(len(merged) == 1, 'exactly one merged AAR required')
        state['merged'] = c.record(merged[0])
        for abi in (*c.ABIS, 'fat'):
            log = out / 'logs' / (abi + '.log')
            c.require('MACH_EXIT=0' in log.read_text(), 'missing successful native pass: ' + abi)
        state['status'] = 'PASS'
        state['scope'] = 'Three native ABI compilations and actual merge only; APK/unit/native runtime gates pending'
        return 0
    except Exception as error:
        state['status'] = 'FAIL'; state['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        (evidence / 'finished.txt').write_text(dt.datetime.now(dt.timezone.utc).isoformat() + '\n')
        for key, name in {'source_manifest': 'source-sha256.txt', 'build_exit': 'build-exit.txt',
                          'started': 'started.txt', 'finished': 'finished.txt',
                          'build_log': 'native-build.log', 'source_before': 'source-before.txt',
                          'source_after': 'source-after.txt'}.items():
            if (evidence / name).is_file(): state[key] = c.record(evidence / name)
        save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    context = load(args.inputs)
    if not args.run:
        print(json.dumps({'status': 'PLAN ONLY', 'command': context[-1],
                          'source_count': len(context[4]), 'output': str(context[2])}, indent=2))
        return 0
    return run(args.inputs, context)


if __name__ == '__main__':
    raise SystemExit(main())
