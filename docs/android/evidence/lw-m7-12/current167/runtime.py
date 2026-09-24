#!/usr/bin/env python3
"""Run canonical uBO lifecycle, browsing and pref gates on the new current167 APK."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import common as c

UBO = {'ubo-first-navigation', 'ubo-preinstalled-signature',
       'ubo-disabled-control', 'ubo-disabled-control-state',
       'ubo-disabled-restart', 'ubo-disabled-restart-state',
       'ubo-removed-restart', 'ubo-removed-restart-state',
       'ubo-removed-apk-reinstall', 'ubo-removed-apk-reinstall-state'}
BASELINE = {'https-only-interstitial', 'page-load-http', 'page-load-https',
            'webgl', 'video', 'getusermedia', 'extension', 'pref-dump'}


def checked_build():
    state = json.loads((c.BUILD / 'result.json').read_text())
    c.require(state['schema'] == 1 and state['status'] == 'PASS' and state['kind'] == 'apk',
              'new current167 APK checkpoint is not successful')
    c.require(c.checked(state['source_manifest']) == c.BUILD / 'source-sha256.txt'
              and state['source_manifest']['sha256'] == c.CURRENT, 'new APK source binding differs')
    build_config = json.loads(c.checked(state['inputs']).read_text())
    c.require(build_config['kind'] == 'apk' and build_config['source_sha256'] == c.CURRENT
              and build_config['image'] == c.IMAGE and build_config['build_date'] == c.DATE
              and build_config['selection'] == c.SELECTION
              and build_config['command'] == c.build_command(), 'APK build configuration differs')
    c.require(state['service']['InvocationID'] and state['service']['RemainAfterExit'] == 'yes',
              'APK invocation is missing')
    terminal = c.service(c.SERVICES['apk'], state['service']['InvocationID'], terminal=True)
    c.checked(state['started']); c.checked(state['finished'])
    c.require(state['stages']['build']['exit'] == 0 and (c.BUILD / 'build-exit.txt').read_text().strip() == '0',
              'new APK build did not exit successfully')
    c.require(state['stages']['build']['command'] == c.build_command(), 'APK build used another command')
    c.checked(state['stages']['build']['log'])
    apks = c.apk_set(c.OUTPUT / 'apk')
    c.require(apks == state['apks'] and set(state['resources']) == c.APKS, 'new APK/resource set differs')
    c.require(c.checked(state['metadata']) == c.OUTPUT / 'apk/output-metadata.json', 'APK metadata path differs')
    c.require(json.loads(c.checked(state['metadata']).read_text())['applicationId'] == 'org.redoubtbrowser',
              'APK application ID differs')
    for name in sorted(c.APKS):
        row = state['stages'][name + '-resource']
        c.require(row['exit'] == 0, 'APK resource verifier failed: ' + name)
        receipt = c.resource_receipt(c.checked(row['log']).read_text(), apks[name])
        c.require(receipt == state['resources'][name], 'APK resource verdict changed: ' + name)
    c.require(c.manifest(c.checked(state['apk_manifest'])) ==
              {name: row['sha256'] for name, row in apks.items()}, 'APK checksum manifest differs')
    c.require(set(state['input_checks']) == {'source-before.txt', 'source-after.txt', 'native-before.txt', 'native-after.txt'},
              'APK before/after input checks incomplete')
    for name, row in state['input_checks'].items():
        c.require(c.checked(row) == c.BUILD / name, 'APK input check path differs')
    for name in ('source-before.txt', 'source-after.txt'):
        lines = (c.BUILD / name).read_text().splitlines()
        rows = c.manifest(c.STAGE / 'source-sha256.txt')
        c.require(len(lines) == 167 and set(lines) == {n + ': OK' for n in rows}, 'incomplete build source check')
    return state, terminal


def sdk_inputs():
    # Pin all installed image inputs so the unchanged canonical harness cannot
    # select a different system image between config review and runtime.
    paths = [c.SDK / 'platform-tools/adb', c.SDK / 'emulator/emulator',
             c.SDK / 'emulator/qemu/linux-x86_64/qemu-system-x86_64']
    images = sorted(p for p in (c.SDK / 'system-images').rglob('*') if p.is_file())
    c.require(images and all(p.is_file() and os.access(p, os.X_OK) for p in paths),
              'prepared emulator/adb/system image is incomplete')
    return [c.record(p) for p in paths + images]


def prepare():
    # The new runtime config explicitly retains the successful APK's reviewed
    # input selection. It cannot select a newer stage or another test run.
    build = json.loads((c.BUILD / 'result.json').read_text())
    build_config = json.loads(c.checked(build['inputs']).read_text())
    c.select_inputs(build_config['selection'])
    config = c.base_config('runtime')
    c.require(not c.RUNTIME.exists() and not c.RUNTIME_WORK.exists(), 'fresh runtime namespace required')
    build, terminal = checked_build()
    config.update(build_receipt=c.record(c.BUILD / 'result.json'), apk_service=terminal,
                  apks=build['apks'], metadata=build['metadata'], sdk_inputs=sdk_inputs())
    return config


def validate(path, digest):
    config = c.load_config(path, digest, 'runtime')
    c.require(not c.RUNTIME.exists() and not c.RUNTIME_WORK.exists(), 'fresh runtime namespace required')
    c.require(c.checked(config['build_receipt']) == c.BUILD / 'result.json', 'wrong APK receipt')
    build, terminal = checked_build()
    c.require(build['apks'] == config['apks'] and build['metadata'] == config['metadata']
              and terminal == config['apk_service'], 'APK checkpoint changed')
    c.require(sdk_inputs() == config['sdk_inputs'], 'runtime SDK/image inputs changed')
    return config


def grade_smoke(path, required, apk):
    payload = json.loads(path.read_text())
    c.require(payload.get('status') == 'completed' and payload.get('error') is None
              and payload.get('tainted') is False and payload.get('injected_prefs') == {},
              'smoke report incomplete or configuration was injected')
    artifact = payload['artifact']
    c.require(artifact['sha256'] == apk['sha256'] and artifact['size'] == apk['bytes']
              and artifact['path'] == apk['path']
              and artifact['harness_sha256'] == c.digest(c.REPO / 'scripts/android-smoke.sh'),
              'smoke report refers to another APK/harness')
    rows = payload['checks']
    names = [row['check'] for row in rows]
    c.require(len(names) == len(set(names)) and required <= set(names)
              and all(row['ok'] is True for row in rows), 'required smoke checks missing or failed')
    return c.record(path)


def devices(adb):
    output = c.query([str(adb), 'devices'])
    lines = [line for line in output.splitlines() if line.strip()]
    c.require(lines and lines[0] == 'List of devices attached', 'unrecognized adb device list')
    return output, [line.split() for line in lines[1:]]


def execute(path, digest):
    c.guest_guard()
    config = validate(path, digest)
    c.own_service('runtime')
    adb = c.SDK / 'platform-tools/adb'
    before, attached = devices(adb)
    c.require(not attached, 'runtime requires no preexisting device, including offline/unauthorized devices')
    state = c.initial_state('runtime', path, config, c.RUNTIME)
    (c.RUNTIME / 'devices-before.txt').write_text(before + '\n')
    c.RUNTIME_WORK.mkdir(mode=0o700)
    apk = config['apks']['fenix-x86_64-release.apk']
    env = dict(os.environ, ANDROID_SDK_ROOT=str(c.SDK), ANDROID_HOME=str(c.SDK),
               LW_SMOKE_APK=apk['path'], LW_SMOKE_DNS='9.9.9.9', LW_SMOKE_AAPT2=str(c.AAPT))
    serial = None
    try:
        c.source_check(c.RUNTIME / 'source-before.txt')
        c.native_check(c.RUNTIME / 'native-before.txt')
        command = [str(c.REPO / 'scripts/android-smoke.sh'), '--emulator', '--keep-emulator',
                   '--sdk', str(c.SDK), '--apk', apk['path'], '--work', str(c.RUNTIME_WORK / 'smoke-first-navigation'),
                   '--check-ubo-lifecycle', '--json', str(c.RUNTIME / 'ubo-lifecycle.json')]
        ubo_rc = c.run_stage(state, c.RUNTIME, 'ubo-lifecycle', command, env)
        after, attached = devices(adb)
        (c.RUNTIME / 'devices-after-ubo.txt').write_text(after + '\n')
        c.require(len(attached) == 1 and len(attached[0]) == 2 and attached[0][1] == 'device'
                  and re.fullmatch('emulator-[0-9]+', attached[0][0]), 'one live isolated emulator required')
        serial = attached[0][0]
        state['emulator_serial'] = serial
        env.update(ANDROID_SERIAL=serial, LW_SMOKE_PCAP=str(c.RUNTIME_WORK / 'smoke-first-navigation/capture.pcap'))
        # Complete the independent baseline/pref gates even when the uBO gate
        # fails, retaining every failure in the final result.
        command = [str(c.REPO / 'scripts/android-smoke.sh'), '--serial', serial, '--sdk', str(c.SDK),
                   '--apk', apk['path'], '--work', str(c.RUNTIME_WORK / 'smoke-baseline'),
                   '--json', str(c.RUNTIME / 'baseline.json')]
        baseline_rc = c.run_stage(state, c.RUNTIME, 'baseline', command, env)
        pref_env = dict(env, LW_SMOKE_WORK=str(c.RUNTIME_WORK / 'smoke-pref-audit'))
        pref_rc = c.run_stage(state, c.RUNTIME, 'pref-audit', [str(c.REPO / 'scripts/android-pref-audit.sh')], pref_env)
        c.require(ubo_rc == baseline_rc == pref_rc == 0, 'one or more canonical runtime gates failed')
        state['ubo_lifecycle'] = grade_smoke(c.RUNTIME / 'ubo-lifecycle.json', UBO, apk)
        state['baseline'] = grade_smoke(c.RUNTIME / 'baseline.json', BASELINE, apk)
        state['pref_dump'] = grade_smoke(c.RUNTIME_WORK / 'smoke-pref-audit/result.json', {'pref-dump'}, apk)
        c.source_check(c.RUNTIME / 'source-after.txt')
        c.native_check(c.RUNTIME / 'native-after.txt')
        c.load_config(path, digest, 'runtime')
        c.require(c.record(c.BUILD / 'result.json') == config['build_receipt'], 'APK receipt changed')
        checked_build()
        c.require(sdk_inputs() == config['sdk_inputs'], 'SDK/image inputs changed')
        state['status'] = 'PASS'
        state['scope'] = ('Current167 source-bound debug-signed x86_64 APK: complete canonical uBO lifecycle, '
                          'baseline browsing/graphics/media/extension and must-lock pref audit. Other ABI/device '
                          'runtime, every-settings-screen audit and later native increments remain pending.')
        return 0
    except BaseException as error:
        state.update(status='FAIL', error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        # No device existed before this run. Remove only the one newly created
        # emulator; capture raw AVD/log/pcap files in the fresh runtime workspace.
        try:
            _output, attached = devices(adb)
            owned = [r[0] for r in attached if len(r) == 2 and re.fullmatch('emulator-[0-9]+', r[0])]
            if serial is None and len(owned) == 1:
                serial = owned[0]
            if serial:
                result = subprocess.run([str(adb), '-s', serial, 'emu', 'kill'], capture_output=True, text=True, timeout=60)
                (c.RUNTIME / 'emulator-cleanup.log').write_text(result.stdout + result.stderr)
                state['emulator_cleanup_exit'] = result.returncode
                if result.returncode != 0:
                    state.update(status='FAIL', cleanup_error='emulator cleanup failed')
        except Exception as error:
            state.update(status='FAIL', cleanup_error=str(error))
        c.finish(state, c.RUNTIME)
        if state['status'] != 'PASS' and sys.exc_info()[0] is None:
            raise RuntimeError(state.get('cleanup_error', state.get('final_input_error', 'runtime incomplete')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--print-config', action='store_true')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--config-sha256')
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if args.print_config:
        c.require(not args.run and not args.config and not args.config_sha256, 'capture is separate from execution')
        print(json.dumps(prepare(), indent=2))
        return 0
    c.require(args.config is not None and args.config_sha256, 'explicit config and reviewed digest required')
    if args.run:
        return execute(args.config, args.config_sha256)
    config = validate(args.config, args.config_sha256)
    print(json.dumps({'status': 'PLAN ONLY', 'apk': config['apks']['fenix-x86_64-release.apk'],
                      'source_sha256': c.CURRENT, 'source_count': 167}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
