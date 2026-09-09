#!/usr/bin/env python3
"""Check the real GeckoView private-permission/uninstall completion boundary.

This is the API durability regression paired with the separate real-Fenix UI
runner (LW-M7-28). It calls the same production methods as GeckoView events;
never writes a permission store, flushes it manually, installs, or changes prefs.
Uses the already installed exact release APK and a dedicated initialized profile.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import secrets
import shlex
import shutil
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('addon_ui_acceptance', ROOT/'scripts/android-addon-state-smoke.py')
a = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(a)
g, Pending, Failure, require = a.g, a.Pending, a.Failure, a.require
PASS, FAIL, PENDING = a.PASS, a.FAIL, a.PENDING
MAX_CALLBACK_TO_STOP_MS = 1000
REQUIRED = {'initial-normal'} | {prefix+suffix for prefix in ('grant', 'revoke', 'grant-before-removal', 'remove')
    for suffix in ('-callback', '-normal', '-private')}
MODULES = {
    'toolkit/components/extensions/ExtensionPermissions.sys.mjs': 'modules/ExtensionPermissions.sys.mjs',
    'mobile/shared/modules/geckoview/GeckoViewWebExtension.sys.mjs': 'modules/GeckoViewWebExtension.sys.mjs',
}
CALL_JS = r"""
return (async()=>{
 const [id,action,value,requestId,version]=arguments;
 const {GeckoViewWebExtension}=ChromeUtils.importESModule('resource://gre/modules/GeckoViewWebExtension.sys.mjs');
 if(id!=='uBlock0@raymondhill.net'||!['private','remove'].includes(action)||
    !/^[0-9a-f]{32}$/.test(requestId)||(action==='private'&&typeof value!=='boolean'))
   throw new Error('Invalid scoped production API request');
 const startedAt=Date.now();
 if(action==='private') {
   const result=await GeckoViewWebExtension.setPrivateBrowsingAllowed(id,value);
   if(result.webExtensionId!==id||result.metaData.version!==version||result.metaData.privateBrowsingAllowed!==value)
     throw new Error('Production private-permission completion returned another state');
 } else {
   await GeckoViewWebExtension.uninstallWebExtension(id);
 }
 return {id,action,value,requestId,version,startedAt,completedAt:Date.now(),acknowledged:true,
   boundary:'GeckoViewWebExtension.'+(action==='private'?'setPrivateBrowsingAllowed':'uninstallWebExtension')};
})();
"""


def grade_ack(data, *, request_id, action, value, version):
    require(isinstance(data, dict), 'Missing actual production API completion')
    expected = {'id': a.ADDON_ID, 'action': action, 'value': value, 'requestId': request_id, 'version': version,
                'acknowledged': True, 'boundary': 'GeckoViewWebExtension.' +
                ('setPrivateBrowsingAllowed' if action == 'private' else 'uninstallWebExtension')}
    require(all(data.get(key) == val and type(data.get(key)) is type(val) for key, val in expected.items()),
            'Stale, wrong-ID or unacknowledged production API result')
    times = [data.get('startedAt'), data.get('completedAt')]
    require(all(type(item) is int and item > 0 for item in times) and times == sorted(times),
            'Invalid device completion timestamps')
    return data


def grade_restart(timing, ack):
    require(timing.get('nextDeviceCommand') == 'timestamped am force-stop' and timing.get('stopSucceeded') is True,
            'Force-stop was not the first successful device command after completion')
    times = [ack['completedAt'], timing.get('deviceStopStartedAt'), timing.get('deviceStopCompletedAt')]
    require(all(type(item) is int and item > 0 for item in times) and times == sorted(times),
            'Device clock is missing or reversed across completion and force-stop')
    host = [timing.get('ackObserved'), timing.get('stopIssued'), timing.get('stopCompleted')]
    require(all(type(item) in (int, float) and math.isfinite(item) for item in host) and host == sorted(host),
            'Host monotonic completion timing is invalid')
    elapsed = times[-1] - times[0]
    if elapsed > MAX_CALLBACK_TO_STOP_MS or (host[-1]-host[0])*1000 > MAX_CALLBACK_TO_STOP_MS:
        raise Pending(f'API completion-to-force-stop took {elapsed} ms; <=1000 ms regression checkpoint unproven')
    return {'deviceCallbackToStoppedMs': elapsed, 'hostAckToStoppedMs': (host[-1]-host[0])*1000,
            'maximumMs': MAX_CALLBACK_TO_STOP_MS}


def bundle_modules(apk, baseline=False):
    source = json.loads((ROOT/'docs/android/evidence/lw-m7-31/source-files.json').read_text())
    expected = {item['path']: item['before_sha256' if baseline else 'after_sha256'] for item in source['files']}
    result = {}
    with zipfile.ZipFile(apk) as archive, zipfile.ZipFile(io.BytesIO(archive.read('assets/omni.ja'))) as omni:
        for path, packaged in MODULES.items():
            actual = hashlib.sha256(omni.read(packaged)).hexdigest()
            require(actual == expected[path], 'Installed APK lacks the exact permission durability module: ' + path)
            result[packaged] = actual
    return result


def grade_completion(data):
    require(data.get('transportConfig', {}).get('transportOnly') is True, 'Transport or policy taint was not excluded')
    done = {item['name'] for item in data['checks'] if item.get('status') == 'PASS' and item.get('evidence')}
    missing = sorted(REQUIRED - done)
    if missing or data['pending']:
        raise Pending('Private API durability incomplete: ' + ', '.join(missing))
    return True


class Runner(a.Runner):
    def prerequisite(self):
        super().prerequisite()
        self.evidence.data['permissionModules'] = bundle_modules(self.args.apk, self.args.baseline_source)
        self.evidence.flush()

    def callback_restart(self, action, value, label):
        old_pid = self.shell('pidof', self.args.package).strip()
        require(bool(old_pid), 'No live app process before the production API call')
        request = secrets.token_hex(16)
        raw = self.marionette.script(CALL_JS, [a.ADDON_ID, action, value, request, self.bundle['pin']['version']], chrome=True)
        observed = time.monotonic()
        ack = grade_ack(raw, request_id=request, action=action, value=value, version=self.bundle['pin']['version'])
        issued = time.monotonic()
        # Device timestamps share the production callback's device wall clock.
        # No dump, screenshot, registry read, sleep, or other device command here.
        command = 'date +%s%3N && am force-stop ' + shlex.quote(self.args.package) + ' && date +%s%3N'
        result = self.adb.run('shell', command, timeout=30)
        completed = time.monotonic()
        lines = result.stdout.strip().splitlines()
        numeric = len(lines) == 2 and all(re.fullmatch(r'[0-9]{13,}', line) for line in lines)
        timing = {'nextDeviceCommand': 'timestamped am force-stop', 'stopSucceeded': result.returncode == 0,
            'ackObserved': observed, 'stopIssued': issued, 'stopCompleted': completed,
            'deviceStopStartedAt': int(lines[0]) if numeric else None,
            'deviceStopCompletedAt': int(lines[1]) if numeric else None,
            'stdout': result.stdout, 'stderr': result.stderr}
        self.evidence.event(label+'-raw-completion', {'ack': ack, 'timing': timing})
        try:
            bound = grade_restart(timing, ack)
            self.evidence.check(label+'-callback', {'ack': ack, 'timing': timing, 'bound': bound})
        except Pending as error:
            self.evidence.pending(label+'-callback', str(error))
        self.resume_first_navigation(label, old_pid)

    def run(self):
        self.prerequisite(); self.start_fixtures()
        self.open_case('initial', connect=True); self.facts()
        initial = self.marionette.script(a.STATE_JS, [a.ADDON_ID], chrome=True)
        require(type(initial.get('privatePermission')) is bool, 'Unknown initial private permission')
        require(self.marionette.script(g.PRIVATE_WINDOWS_JS, chrome=True) == 0, 'Dedicated profile already has private tabs')
        self.observe('initial-normal', private_allowed=initial['privatePermission'], first=True)
        # Ensure every measured call changes the actual permission. If necessary,
        # a genuine production revocation is setup, with no measurement claimed.
        if initial['privatePermission']:
            request = secrets.token_hex(16)
            setup = self.marionette.script(CALL_JS, [a.ADDON_ID, 'private', False, request, self.bundle['pin']['version']], chrome=True)
            self.evidence.event('setup-production-revocation', grade_ack(setup, request_id=request,
                action='private', value=False, version=self.bundle['pin']['version']))
        for label, action, value in [('grant','private',True), ('revoke','private',False),
                                     ('grant-before-removal','private',True), ('remove','remove',None)]:
            self.callback_restart(action, value, label)
            installed = action != 'remove'
            allowed = value if installed else False
            self.observe(label+'-normal', installed=installed, enabled=installed, private_allowed=allowed, first=True)
            require(self.marionette.script(g.PRIVATE_WINDOWS_JS, chrome=True) == 0, 'An existing private context invalidates the fresh private probe')
            self.open_case(label+'-private', private=True)
            self.observe(label+'-private', installed=installed, enabled=installed, private_allowed=allowed)
            self.close_private()
        for item in self.evidence.data['installed']['apk']:
            require(self.shell('sha256sum', item['path']).strip().split()[0] == item['sha256'], 'APK changed during regression')
        complete = grade_completion(self.evidence.data)
        self.evidence.data['functionalComplete'] = complete
        if self.args.baseline_source:
            self.evidence.pending('baseline-only', 'Measured the pinned predecessor; candidate acceptance requires a separate candidate run')
            raise Pending('Baseline measurement finished; this is not candidate acceptance')
        self.evidence.finish('PASS', 'Production API private permission/removal durability checkpoints passed; separate UI/update acceptance still applies', True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default=shutil.which('adb')); parser.add_argument('--serial')
    parser.add_argument('--package', default='org.redoubtbrowser'); parser.add_argument('--apk', type=Path)
    parser.add_argument('--work', type=Path, default=Path.home()/'.cache/redoubt-addon-private-durability')
    parser.add_argument('--dedicated-test-profile', action='store_true'); parser.add_argument('--scheme', default='redoubt')
    parser.add_argument('--marionette-port', type=int); parser.add_argument('--device-marionette-port', type=int, default=2828)
    parser.add_argument('--connect-timeout', type=int, default=60); parser.add_argument('--ui-timeout', type=int, default=25)
    parser.add_argument('--no-screenshots', action='store_true')
    parser.add_argument('--baseline-source', action='store_true', help='measure the exact pinned predecessor modules; never candidate acceptance')
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_.]+', args.package) or not re.fullmatch(r'[a-z][a-z0-9+.-]*', args.scheme):
        parser.error('Invalid package or app scheme')
    if min(args.connect_timeout, args.ui_timeout) <= 0 or any(port is not None and not 1 <= port <= 65535
            for port in (args.marionette_port, args.device_marionette_port)): parser.error('Invalid timeout or port')
    run = secrets.token_hex(8); evidence = a.Evidence(args.work/run, run)
    evidence.data['baselineSource'] = args.baseline_source
    evidence.data['scope'] = 'LW-M7-31 production API completion durability; separate real UI acceptance is LW-M7-28'
    evidence.data['inputs'] = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
        ['scripts/android-addon-private-durability-check.py', 'scripts/android-addon-state-smoke.py',
         'scripts/android-graphics-smoke.py', 'docs/android/evidence/lw-m7-31/source-files.json']}
    runner, status = None, PENDING
    try:
        if not args.adb or not shutil.which(args.adb): raise Pending('adb unavailable; no private durability was tested')
        if not args.dedicated_test_profile: raise Pending('Dedicated profile acknowledgment required for real private choices/removal')
        protocol = g.foundation(); adb = protocol.Adb(args.adb, args.serial); devices = adb.devices()
        if args.serial and args.serial not in devices: raise Pending('Requested device is not connected and authorized')
        if not args.serial:
            if len(devices) != 1: raise Pending('Select one connected and authorized device')
            adb.serial = devices[0]
        runner = Runner(args, evidence, protocol, adb); runner.run()
        if evidence.data['status'] != 'PASS' or not evidence.data['acceptanceComplete']:
            raise Pending('Runner returned without complete API durability evidence')
        status = PASS
    except Pending as error: evidence.finish('PENDING', str(error))
    except Exception as error: evidence.finish('FAIL', str(error)); status = FAIL
    except KeyboardInterrupt: evidence.finish('PENDING', 'Interrupted before complete API durability evidence')
    finally:
        if runner:
            if status != PASS: runner.diagnostics()
            try: runner.close()
            except Exception as error:
                evidence.event('cleanup-error', {'error': str(error)})
                if status == PASS: evidence.finish('FAIL', 'Cleanup failed'); status = FAIL
    print(json.dumps({'status': evidence.data['status'], 'acceptanceComplete': evidence.data['acceptanceComplete'],
        'reason': evidence.data['reason'], 'pending': evidence.data['pending'], 'report': str(evidence.path)}))
    return status


if __name__ == '__main__': sys.exit(main())
