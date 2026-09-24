"""Host-only negative controls. No adb invocation or fixture private-key reads."""
import base64
import copy
import importlib.util
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('lw32_setup_tests', HERE/'emulator-setup.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Inputs(unittest.TestCase):
    def test_retained_public_bytes_and_manifest(self):
        # The real openssl validity/self-signature check is an explicit separate
        # check-inputs command. This test focuses on the fail-closed byte binding.
        with patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=0,stderr='')):
            receipt, encoded = m.public_inputs(HERE/'fixture-ca.pem',HERE/'fixture-public-manifest.json')
        self.assertEqual(m.sha(base64.b64decode(encoded)),receipt['ca_der_sha256'])

    def test_private_material_never_reaches_openssl(self):
        with tempfile.TemporaryDirectory() as directory:
            ca = Path(directory)/'input.pem'
            ca.write_text((HERE/'fixture-ca.pem').read_text() + '\n-----BEGIN PRIVATE KEY-----\nAA==\n-----END PRIVATE KEY-----\n')
            with patch.object(m.subprocess,'run') as execute, self.assertRaises(m.Pending):
                m.public_inputs(ca,HERE/'fixture-public-manifest.json')
            execute.assert_not_called()

    def test_wrong_hash_and_unrelated_names_fail_before_openssl(self):
        for field, value in [('ca_der_sha256','0'*64), ('ca_pem_sha256','0'*64),
                             ('dns_names',['duh.de','unrelated.example'])]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                receipt = json.loads((HERE/'fixture-public-manifest.json').read_text())
                receipt[field] = value
                path = Path(directory)/'manifest.json'; path.write_text(json.dumps(receipt))
                with patch.object(m.subprocess,'run') as execute, self.assertRaises(m.Pending):
                    m.public_inputs(HERE/'fixture-ca.pem',path)
                execute.assert_not_called()

    def test_absent_apk_cannot_return_success_or_invoke_adb(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)/'never-created'
            with patch.object(m,'public_inputs',return_value=({},'')), \
                    patch.object(m.g,'foundation') as protocol, \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = m.main(['run','--adb','not-used','--serial','emulator-5554',
                               '--expected-profile','/data/user/0/org.redoubtbrowser/files/profile',
                               '--fresh-dedicated-profile','--work',str(work)])
            self.assertEqual(code,2)
            protocol.assert_not_called()
            self.assertFalse(work.exists())

    def test_expired_or_invalid_ca_fails(self):
        with patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=2,stderr='expired')):
            with self.assertRaises(m.Pending):
                m.public_inputs(HERE/'fixture-ca.pem',HERE/'fixture-public-manifest.json')

    def test_profile_cannot_escape_selected_app(self):
        m.validate_profile('org.redoubtbrowser','/data/user/0/org.redoubtbrowser/files/profile')
        for path in ['/data/user/0/other.app/files/profile', '/tmp/profile',
                     '/data/user/0/org.redoubtbrowser/../other/profile',
                     '/data/user/0/org.redoubtbrowser/files/profile with space']:
            with self.subTest(path=path), self.assertRaises(m.Pending):
                m.validate_profile('org.redoubtbrowser',path)

    def test_only_explicit_rootable_aosp_emulator(self):
        props = {'qemu':'1','debuggable':'1','type':'userdebug','fingerprint':'generic/aosp/x86',
                 'boot':'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'}
        m.emulator_identity('emulator-5554',props)
        for serial, changes in [('physical-phone',{}),('emulator-5554',{'qemu':'0'}),
                                ('emulator-5554',{'debuggable':'0'}),
                                ('emulator-5554',{'type':'user'}),
                                ('emulator-5554',{'boot':'unknown'})]:
            with self.subTest(serial=serial,changes=changes), self.assertRaises(m.Pending):
                m.emulator_identity(serial,props | changes)


class HostsAndDNS(unittest.TestCase):
    def test_hosts_preserves_original_entries_and_adds_only_allowlist(self):
        original = '127.0.0.1 localhost\n::1 ip6-localhost\n# unchanged\n'
        result = m.hosts_body(original)
        self.assertTrue(result.startswith(original))
        self.assertEqual(result[len(original):],''.join('127.0.0.1 '+n+'\n' for n in m.NAMES))

    def test_existing_controlled_mapping_is_not_overwritten(self):
        for name in m.NAMES:
            with self.subTest(name=name), self.assertRaises(m.Pending):
                m.hosts_body('192.0.2.1 something '+name.upper()+' # comment\n')

    def test_commented_names_are_not_existing_mappings(self):
        self.assertIn('127.0.0.1 duh.de',m.hosts_body('127.0.0.1 localhost # duh.de\n'))

    def test_unmount_requires_exact_bind_inode_and_hash(self):
        entries = m.mount_entries('41 24 253:0 /local/tmp/x/hosts /system/etc/hosts rw - ext4 /dev/a rw\n')
        self.assertTrue(m.owns_mount(entries,'1:2','1:2','a','a','a'))
        for args in [(entries,'1:2','1:3','a','a','a'),
                     (entries,'1:2','1:2','a','b','a'),
                     ([], '1:2','1:2','a','a','a'),
                     (entries*2,'1:2','1:2','a','a','a')]:
            with self.subTest(args=args):
                self.assertFalse(m.owns_mount(*args))

    def test_all_gecko_results_must_be_loopback(self):
        rows = [{'name':name,'status':0,'addresses':['127.0.0.1']} for name in m.NAMES]
        self.assertEqual(m.grade_dns(rows),rows)
        variants = [rows[:-1],rows[:2]+rows[:1]]
        for addresses in [[],['192.0.2.1'],['127.0.0.1','203.0.113.2']]:
            changed = copy.deepcopy(rows); changed[2]['addresses'] = addresses; variants.append(changed)
        changed = copy.deepcopy(rows); changed[0]['status'] = 1; variants.append(changed)
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(m.Pending):
                m.grade_dns(variant)


class FakeAdb:
    def __init__(self, rows):
        self.rows, self.calls = rows, []
    def run(self,*args,**kwargs):
        self.calls.append(args)
        if args[1] == '--list':
            return SimpleNamespace(stdout=self.rows,returncode=0)
        return SimpleNamespace(stdout='',returncode=0)


class Recovery(unittest.TestCase):
    def setup_object(self, rows='', owned=None):
        setup = object.__new__(m.Setup)
        setup.args = SimpleNamespace(serial='emulator-5554',package='org.redoubtbrowser')
        setup.state = {'owned': owned or {},'forwardPort':44444}
        setup.adb = FakeAdb(rows)
        setup.save = lambda: None
        setup.event = lambda *args: None
        setup.client = setup.server = None
        return setup

    def test_preexisting_reverse_is_not_claimed_or_removed(self):
        setup = self.setup_object('UsbFfs tcp:443 tcp:48762\n')
        with self.assertRaises(m.Pending):
            setup.create_reverse('httpsReverse','tcp:443','tcp:48762')
        self.assertEqual(setup.state['owned'],{})
        self.assertEqual(setup.adb.calls,[('reverse','--list')])

    def test_own_reverse_can_be_recovered_without_rebinding(self):
        setup = self.setup_object('UsbFfs tcp:443 tcp:48762\n',{'httpsReverse':True})
        setup.create_reverse('httpsReverse','tcp:443','tcp:48762')
        self.assertEqual(setup.adb.calls,[('reverse','--list')])

    def test_replaced_reverse_is_preserved(self):
        setup = self.setup_object('UsbFfs tcp:443 tcp:12345\n',{'httpsReverse':True})
        with self.assertRaises(m.Pending):
            setup.remove_route('reverse','tcp:443','tcp:48762')
        self.assertEqual(setup.adb.calls,[('reverse','--list')])

    def test_forward_on_other_device_is_preserved(self):
        setup = self.setup_object('emulator-5556 tcp:44444 tcp:2828\n',{'forward':True})
        with self.assertRaises(m.Pending):
            setup.create_forward()
        with self.assertRaises(m.Pending):
            setup.remove_route('forward','tcp:44444','tcp:2828')
        self.assertTrue(all(call[1]=='--list' for call in setup.adb.calls))

    def test_reused_serial_different_boot_cannot_cleanup(self):
        setup = self.setup_object(owned={'hostsMount':True})
        setup.state['identity'] = {'boot':'old'}
        setup.identify = lambda: {'boot':'new'}
        with self.assertRaises(m.Pending):
            setup.cleanup()
        self.assertEqual(setup.adb.calls,[])

    def test_no_mutation_cleanup_does_not_stop_an_app(self):
        setup = self.setup_object()
        setup.identify = lambda: self.fail('No device call should be needed')
        setup.cleanup()
        self.assertTrue(setup.state['cleanupComplete'])
        self.assertEqual(setup.adb.calls,[])

    def test_failed_cert_removal_retains_recovery_transport(self):
        setup = self.setup_object(owned={'cert':True,'config':True,'forward':True,'hostsMount':True})
        setup.bind_identity = lambda: None
        setup.installed = lambda: None
        def unavailable(**kwargs):
            raise m.Pending('Unavailable test transport')
        setup.connect = unavailable
        setup.shell = lambda *args: self.fail('Must retain transport when cert removal fails')
        with self.assertRaises(m.Pending):
            setup.cleanup()
        self.assertFalse(setup.state['cleanupComplete'])
        self.assertTrue(all(setup.state['owned'].values()))

    def test_tampered_journal_cannot_select_arbitrary_path(self):
        encoded = base64.b64encode(b'public-test-bytes').decode()
        state = {'version':1,'run':'a'*24,'package':'org.redoubtbrowser',
                 'profile':'/data/user/0/org.redoubtbrowser/files/profile',
                 'caBase64':encoded,'caSha256':m.sha(b'public-test-bytes'),
                 'remoteDir':'/data/local/tmp/lw-cookie-'+'a'*24,'owned':{'remoteDir':True}}
        m.validate_journal(state)
        for changes in [{'remoteDir':'/data/local/tmp/unrelated'},
                        {'configPath':'/data/user/0/org.redoubtbrowser/files/prefs.js'},
                        {'caSha256':'0'*64}, {'owned':{'arbitrary':True}},
                        {'forwardPort':-1}]:
            with self.subTest(changes=changes), self.assertRaises(m.Pending):
                m.validate_journal(state | changes)


if __name__ == '__main__':
    unittest.main()
