#!/usr/bin/env python3
"""Retry the same successful APK using an isolated, hash-pinned harness capsule."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import common as c

UBO = set(c.original_runtime.UBO)
BASELINE = set(c.original_runtime.BASELINE)


def checked_build():
    return c.checked_build()


def sdk_inputs():
    return c.original_runtime.sdk_inputs()


def prepare():
    # The new runtime config explicitly retains the successful APK's reviewed
    # input selection. It cannot select a newer stage or another test run.
    build = json.loads((c.BUILD / 'result.json').read_text())
    build_config = json.loads(c.checked(build['inputs']).read_text())
    c.select_inputs(build_config['selection'])
    config = c.base_config('runtime')
    c.fresh_namespace(c.RUNTIME); c.fresh_namespace(c.RUNTIME_WORK)
    build, terminal = checked_build()
    config.update(build_receipt=c.record(c.BUILD / 'result.json'), apk_service=terminal,
                  apks=build['apks'], metadata=build['metadata'], sdk_inputs=sdk_inputs())
    return config


def validate(path, digest):
    config = c.load_config(path, digest, 'runtime')
    c.fresh_namespace(c.RUNTIME); c.fresh_namespace(c.RUNTIME_WORK)
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
              and artifact['harness_sha256'] == c.digest(c.CAPSULE / 'scripts/android-smoke.sh'),
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
        command = [str(c.CAPSULE / 'scripts/android-smoke.sh'), '--emulator', '--keep-emulator',
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
        command = [str(c.CAPSULE / 'scripts/android-smoke.sh'), '--serial', serial, '--sdk', str(c.SDK),
                   '--apk', apk['path'], '--work', str(c.RUNTIME_WORK / 'smoke-baseline'),
                   '--json', str(c.RUNTIME / 'baseline.json')]
        baseline_rc = c.run_stage(state, c.RUNTIME, 'baseline', command, env)
        pref_env = dict(env, LW_SMOKE_WORK=str(c.RUNTIME_WORK / 'smoke-pref-audit'))
        pref_rc = c.run_stage(state, c.RUNTIME, 'pref-audit', [str(c.CAPSULE / 'scripts/android-pref-audit.sh')], pref_env)
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
        state['scope'] = ('Same current167 source-bound APK with corrected harness capsule: complete uBO lifecycle, '
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
            raise RuntimeError(state.get('cleanup_error', state.get('recovery_input_error', state.get('final_input_error', 'runtime incomplete'))))


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
