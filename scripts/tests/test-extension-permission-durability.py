#!/usr/bin/env python3
"""Replay pinned production-source tests and fail-closed runtime graders (host)."""
import argparse
from contextlib import redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT/'docs/android/evidence/lw-m7-31'
PATCH = ROOT/'patches/android/extension-permission-durability.patch'
SPEC = importlib.util.spec_from_file_location('private_regression', ROOT/'scripts/android-addon-private-durability-check.py')
r = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(r)
SPEC28 = importlib.util.spec_from_file_location('addon_host_tests', ROOT/'docs/android/evidence/lw-m7-28/test-addon-state-smoke.py')
t = importlib.util.module_from_spec(SPEC28); SPEC28.loader.exec_module(t)
t.a = r.a  # Reuse one exception/type identity while retaining the existing fixtures.

def ack():
    return {'id': r.a.ADDON_ID, 'action': 'private', 'value': True, 'requestId': 'a'*32, 'version': t.VERSION,
        'acknowledged': True, 'boundary': 'GeckoViewWebExtension.setPrivateBrowsingAllowed',
        'startedAt': 1000000000000, 'completedAt': 1000000000100}

def timing():
    return {'nextDeviceCommand': 'timestamped am force-stop', 'stopSucceeded': True, 'deviceStopStartedAt': 1000000000120,
            'deviceStopCompletedAt': 1000000000200, 'ackObserved': 10.0, 'stopIssued': 10.01, 'stopCompleted': 10.1}

def grade_ack(value):
    return r.grade_ack(value, request_id='a'*32, action='private', value=True, version=t.VERSION)

class GraderTests(unittest.TestCase):
    def test_actual_bound_and_ack(self):
        self.assertEqual(r.grade_restart(timing(), grade_ack(ack()))['deviceCallbackToStoppedMs'], 100)

    def test_missing_stale_wrong_or_false_ack_rejected(self):
        for key, value in [('requestId', 'b'*32), ('id', 'other'), ('action', 'remove'), ('value', 1),
                           ('version', 'old'), ('acknowledged', False), ('boundary', 'store.put'),
                           ('completedAt', None), ('completedAt', 999)]:
            value_ack=ack();value_ack[key]=value
            with self.subTest(key=key), self.assertRaises(r.Failure): grade_ack(value_ack)

    def test_missing_stop_or_intervening_observer_rejected(self):
        for key, value in [('nextDeviceCommand', 'uiautomator dump'), ('stopSucceeded', False),
                           ('deviceStopStartedAt', None), ('deviceStopCompletedAt', 1),
                           ('stopIssued', float('nan')), ('stopCompleted', 1)]:
            value_timing=timing();value_timing[key]=value
            with self.subTest(key=key), self.assertRaises(r.Failure): r.grade_restart(value_timing, ack())

    def test_slow_callback_checkpoint_is_pending(self):
        for key, value in [('deviceStopCompletedAt', 1000000001200), ('stopCompleted', 12)]:
            value_timing=timing();value_timing[key]=value
            with self.subTest(key=key), self.assertRaises(r.Pending): r.grade_restart(value_timing, ack())

    def test_removed_state_cannot_retain_a_private_permission(self):
        for backend in ['legacy-json', 'rkv']:
            observed=t.state(False, installed=False);observed['permissionBackend']=backend
            t.grade_state(observed, enabled=False, installed=False)
            observed['privatePermission']=True
            with self.assertRaises(r.Failure): t.grade_state(observed, enabled=False, installed=False)

    def test_removed_legacy_disk_grant_or_unknown_backend_rejected(self):
        for key, value in [('privatePermissionDisk', True), ('privatePermissionDisk', None),
                           ('permissionBackend', 'unknown'), ('privatePermission', None)]:
            observed=t.state(False, installed=False);observed[key]=value
            with self.subTest(key=key), self.assertRaises(r.Failure): t.grade_state(observed, enabled=False, installed=False)

    def test_incomplete_or_pending_results_are_not_acceptance(self):
        evidence={'transportConfig':{'transportOnly':True}, 'checks':[], 'pending':[]}
        with self.assertRaises(r.Pending): r.grade_completion(evidence)
        evidence['checks']=[{'name':name,'status':'PASS','evidence':{'observed':True}} for name in r.REQUIRED]
        evidence['pending']=[{'criterion':'grant-callback'}]
        with self.assertRaises(r.Pending): r.grade_completion(evidence)
        evidence['pending']=[];evidence['checks'][0]['status']='FAIL'
        with self.assertRaises(r.Pending): r.grade_completion(evidence)
        evidence['transportConfig']['transportOnly']=False
        with self.assertRaises(r.Failure): r.grade_completion(evidence)

    def test_missing_parser_origin_and_stale_report_are_rejected_by_shared_observer(self):
        rows=t.requests();rows[0]['origin']='http://other.test'
        with self.assertRaises(r.Failure): t.grade_navigation(rows=rows)
        page=t.page();page['documentId']='stale'
        with self.assertRaises(r.Failure): t.grade_navigation(value=page)

    def test_wrong_packaged_permission_module_fails(self):
        with tempfile.TemporaryDirectory() as work:
            omni=io.BytesIO()
            with zipfile.ZipFile(omni,'w') as jar:
                for name in r.MODULES.values():jar.writestr(name,b'old module')
            apk=Path(work)/'wrong.apk'
            with zipfile.ZipFile(apk,'w') as archive:archive.writestr('assets/omni.ja',omni.getvalue())
            with self.assertRaises(r.Failure):r.bundle_modules(apk)

    def test_no_apk_with_connected_fake_adb_cannot_pass(self):
        fake=Mock();fake.devices.return_value=['fake-serial']
        protocol=Mock();protocol.Adb.return_value=fake
        with tempfile.TemporaryDirectory() as work, patch.object(r.g,'foundation',return_value=protocol), \
             patch.object(r.Runner,'diagnostics'),patch.object(r.Runner,'close'),redirect_stdout(io.StringIO()):
            result=r.main(['--adb','/bin/true','--serial','fake-serial','--dedicated-test-profile','--work',work])
            self.assertEqual(result,r.PENDING)
            report=json.loads(next(Path(work).glob('*/addon-results.json')).read_text())
            self.assertFalse(report['acceptanceComplete']);self.assertEqual(report['status'],'PENDING')
            fake.run.assert_not_called()

    def test_first_command_after_real_callback_is_timestamped_force_stop(self):
        runner=object.__new__(r.Runner)
        runner.args=Mock(package='org.redoubtbrowser')
        runner.bundle={'pin':{'version':t.VERSION}}
        runner.evidence=Mock(); trace=[]
        runner.shell=lambda *args: trace.append(('shell',args)) or '42'
        def call(js,args,chrome):
            self.assertEqual(js,r.CALL_JS);self.assertTrue(chrome)
            trace.append(('callback',args))
            result=ack();result['requestId']=args[3];return result
        runner.marionette=Mock();runner.marionette.script.side_effect=call
        def stop(*args,**kwargs):
            trace.append(('stop',args))
            self.assertEqual(args[0],'shell');self.assertIn('am force-stop org.redoubtbrowser',args[1])
            return Mock(returncode=0,stdout='1000000000120\n1000000000200\n',stderr='')
        runner.adb=Mock();runner.adb.run.side_effect=stop
        runner.resume_first_navigation=lambda *args: trace.append(('resume',args))
        runner.callback_restart('private',True,'grant')
        self.assertEqual([event[0] for event in trace],['shell','callback','stop','resume'])
        runner.evidence.check.assert_called_once()

    def test_baseline_binding_is_explicit_and_rejects_candidate_mode(self):
        with tempfile.TemporaryDirectory() as work:
            omni=io.BytesIO()
            with tarfile.open(EVIDENCE/'source-baseline.tar.gz') as baseline, zipfile.ZipFile(omni,'w') as jar:
                for original,packaged in r.MODULES.items():jar.writestr(packaged,baseline.extractfile(original).read())
            apk=Path(work)/'baseline.apk'
            with zipfile.ZipFile(apk,'w') as archive:archive.writestr('assets/omni.ja',omni.getvalue())
            self.assertEqual(len(r.bundle_modules(apk,baseline=True)),2)
            with self.assertRaises(r.Failure):r.bundle_modules(apk)

    def test_api_transport_calls_only_the_production_choice_route(self):
        for banned in ['.put(', '.saveSoon(', 'IOUtils.write', '.flush(', 'Services.prefs.set', 'AddonManager.get']:
            self.assertNotIn(banned,r.CALL_JS)
        self.assertIn('await GeckoViewWebExtension.setPrivateBrowsingAllowed',r.CALL_JS)
        self.assertIn('await GeckoViewWebExtension.uninstallWebExtension',r.CALL_JS)
        self.assertIn('completedAt:Date.now()',r.CALL_JS)


def sha(data): return hashlib.sha256(data).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path);parser.add_argument('--apk',type=Path)
    args=parser.parse_args()
    manifest=json.loads((EVIDENCE/'source-files.json').read_text())
    entries={item['path']:item for item in manifest['files']}
    with tempfile.TemporaryDirectory(prefix='lw-m7-31-source-') as work:
        source=args.source.resolve() if args.source else Path(work)
        if not args.source:
            with tarfile.open(EVIDENCE/'source-baseline.tar.gz') as archive:
                assert {m.name for m in archive}=={name for name,item in entries.items() if item['before_sha256']}
                for member in archive:
                    assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
                    data=archive.extractfile(member).read();assert sha(data)==entries[member.name]['before_sha256']
                    dest=source/member.name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
            result=subprocess.run(['patch','--batch','--forward','--fuzz=0','-p1','-i',str(PATCH)],cwd=source,text=True,capture_output=True,check=True)
            assert 'offset' not in result.stdout and 'fuzz' not in result.stdout,result.stdout
            print('PASS source patch replay: zero fuzz, no offsets',flush=True)
        for name,item in entries.items():
            assert sha((source/name).read_bytes())==item['after_sha256'],name
            if name.endswith(('.js','.mjs')):subprocess.run(['node','--check',str(source/name)],check=True)
        subprocess.run(['node',str(ROOT/'scripts/tests/test-extension-permission-durability.js'),str(source)],check=True,timeout=60)
        # Prove the public-completion tests detect the original delayed write.
        if not args.source:
            ep=source/'toolkit/components/extensions/ExtensionPermissions.sys.mjs';candidate=ep.read_bytes()
            with tarfile.open(EVIDENCE/'source-baseline.tar.gz') as archive: ep.write_bytes(archive.extractfile(entries[next(k for k in entries if k.endswith('/ExtensionPermissions.sys.mjs'))]['path']).read())
            negative=subprocess.run(['node',str(ROOT/'scripts/tests/test-extension-permission-durability.js'),str(source)],text=True,capture_output=True,timeout=60)
            assert negative.returncode != 0 and 'AssertionError' in negative.stderr,negative.stderr
            ep.write_bytes(candidate);print('PASS original delayed-write source is rejected by the same completion test',flush=True)
        if args.apk:print('PASS exact packaged permission modules: '+json.dumps(r.bundle_modules(args.apk)))
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GraderTests))
    if not result.wasSuccessful():raise SystemExit(1)
    print('PASS host source/runner checks; Android xpcshell, target build and real force-stop regression remain pending')

if __name__=='__main__':main()
