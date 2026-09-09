#!/usr/bin/env python3
"""Host controls using the exact failed release UI; no device or production edits."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile
import types
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SPEC = importlib.util.spec_from_file_location('graphics_notice_candidate', ROOT / 'scripts/android-graphics-smoke.py')
g = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(g)
with tarfile.open(HERE / 'before-and-source.tar.gz') as archive:
    BODIES = {m.name: archive.extractfile(m).read() for m in archive.getmembers()}
NOTICE = BODIES['actual/0023-before-open-permissions.xml'].decode()
PKG = 'org.redoubtbrowser'
EMPTY = '<hierarchy/>'


def changed(name, **attributes):
    tree = g.parse_ui(NOTICE)
    node = next(n for n in tree.iter('node') if n.get('resource-id') == PKG + ':id/' + name)
    node.attrib.update(attributes)
    return ET.tostring(tree, encoding='unicode')


def control(rid, text='', **extra):
    attrs = {'package': PKG, 'resource-id': PKG + ':id/' + rid, 'text': text,
             'enabled': 'true', 'clickable': 'true', 'bounds': '[10,20][110,80]'}
    attrs.update(extra)
    root = ET.Element('hierarchy')
    ET.SubElement(root, 'node', attrs)
    return ET.tostring(root, encoding='unicode')


def ui():
    return g.UI(Mock(), PKG, Mock(), 'test', timeout=0.1, screenshots=False)


class NoticeIdentificationTests(unittest.TestCase):
    def test_actual_three_captured_hierarchies_identify_same_native_button(self):
        for name in ['0021-quiet-protection.xml', '0023-before-open-permissions.xml', '0025-failure-ui.xml']:
            with self.subTest(name=name):
                button = g.ubo_added_notice(BODIES['actual/' + name].decode(), PKG)
                self.assertEqual(button['centre'], (922, 1815))
                self.assertEqual(button['resource-id'], PKG + ':id/confirm_button')

    def test_other_extension_and_title_prefix_are_not_acknowledged(self):
        for title in ['Another extension was added', 'uBlock Origin', 'uBlock Origin was added?', 'Add uBlock Origin?']:
            with self.subTest(title=title):
                self.assertIsNone(g.ubo_added_notice(changed('title', text=title), PKG))

    def test_description_must_be_exact_post_installation_message(self):
        for text in ['', 'Allow uBlock Origin to access your data?', 'Share technical data', g.UBO_ADDED_DESCRIPTION + ' Allow?']:
            with self.subTest(text=text):
                self.assertIsNone(g.ubo_added_notice(changed('description', text=text), PKG))

    def test_native_package_resource_classes_and_non_choice_shape_required(self):
        for name in ['icon', 'title', 'description', 'confirm_button']:
            for attrs in [{'package': 'org.other'}, {'resource-id': 'other:id/' + name},
                          {'class': 'android.webkit.WebView'}, {'checkable': 'true'},
                          {'enabled': 'false'}, {'visible-to-user': 'false'},
                          {'clickable': 'false' if name == 'confirm_button' else 'true'}]:
                with self.subTest(name=name, attrs=attrs):
                    self.assertIsNone(g.ubo_added_notice(changed(name, **attrs), PKG))

    def test_generic_ok_allow_disabled_or_invalid_bounds_never_tapped(self):
        for xml in [control('confirm_button', 'OK'), control('origin_permission_allow', 'OK'),
                    changed('confirm_button', text='Allow'), changed('confirm_button', bounds='[1,2][1,2]'),
                    changed('confirm_button', bounds='invalid')]:
            with self.subTest(xml=xml[-180:]):
                instance = ui()
                instance.tap = Mock()
                instance.dump = Mock()
                self.assertEqual(instance.acknowledge_ubo_added_notice(xml), xml)
                instance.tap.assert_not_called()
                instance.dump.assert_not_called()

    def test_split_parents_or_additional_choice_controls_are_rejected(self):
        for split in [True, False]:
            tree = g.parse_ui(NOTICE)
            container = next(n for n in tree.iter('node') if n.get('class') == 'android.widget.RelativeLayout')
            if split:
                button = list(container)[-1]
                container.remove(button)
                tree.append(button)
            else:
                ET.SubElement(container, 'node', {'package': PKG, 'class': 'android.widget.CheckBox'})
            self.assertIsNone(g.ubo_added_notice(ET.tostring(tree, encoding='unicode'), PKG))

    def test_duplicate_native_notices_fail_without_tapping(self):
        tree = g.parse_ui(NOTICE)
        tree.append(copy.deepcopy(list(tree)[0]))
        instance = ui()
        instance.tap = Mock()
        with self.assertRaisesRegex(g.Failure, 'Ambiguous'):
            instance.acknowledge_ubo_added_notice(ET.tostring(tree, encoding='unicode'))
        instance.tap.assert_not_called()

    def test_hidden_or_wrong_container_is_rejected(self):
        for attrs in [{'package': 'other'}, {'class': 'android.webkit.WebView'}, {'visible-to-user': 'false'}, {'enabled': 'false'}]:
            tree = g.parse_ui(NOTICE)
            next(n for n in tree.iter('node') if n.get('class') == 'android.widget.RelativeLayout').attrib.update(attrs)
            self.assertIsNone(g.ubo_added_notice(ET.tostring(tree, encoding='unicode'), PKG))


class NoticeFlowTests(unittest.TestCase):
    def test_single_tap_retains_action_then_returns_fresh_hierarchy(self):
        instance = ui()
        fresh = control('mozac_browser_toolbar_site_info_indicator')
        instance.dump = Mock(return_value=fresh)
        self.assertEqual(instance.acknowledge_ubo_added_notice(NOTICE), fresh)
        instance.shell = Mock()  # Actual tap above used mocked adb, never a device.
        instance.adb.run.assert_called_once()
        self.assertIn('input tap 922 1815', instance.adb.run.call_args.args)
        instance.evidence.event.assert_called_once()
        self.assertEqual(instance.evidence.event.call_args.args[1]['label'], 'acknowledge-ubo-installed-notice')
        instance.dump.assert_called_once_with('after-ubo-installed-notice', screenshot=True)
        instance.evidence.check.assert_not_called()

    def test_disappearance_retries_only_reads_and_taps_once(self):
        instance = ui()
        instance.tap = Mock()
        instance.dump = Mock(side_effect=[NOTICE, EMPTY])
        with patch.object(g.time, 'monotonic', return_value=0), patch.object(g.time, 'sleep'):
            self.assertEqual(instance.acknowledge_ubo_added_notice(NOTICE), EMPTY)
        instance.tap.assert_called_once()
        self.assertEqual(instance.dump.call_count, 2)

    def test_timeout_and_partial_title_still_fail_after_one_tap(self):
        for after in [NOTICE, control('title', g.UBO_ADDED_TITLE)]:
            instance = ui()
            instance.tap = Mock()
            instance.dump = Mock(return_value=after)
            with patch.object(g.time, 'monotonic', side_effect=[0, 1]):
                with self.assertRaisesRegex(g.Failure, 'did not close'):
                    instance.acknowledge_ubo_added_notice(NOTICE)
            instance.tap.assert_called_once()
            instance.evidence.check.assert_not_called()

    def test_permission_dialog_after_notice_is_never_acknowledged(self):
        instance = ui()
        permission = control('origin_permission_allow', 'Allow')
        instance.dump = Mock(return_value=permission)
        instance.tap = Mock()
        self.assertEqual(instance.acknowledge_ubo_added_notice(NOTICE), permission)
        self.assertEqual(instance.acknowledge_ubo_added_notice(permission), permission)
        instance.tap.assert_called_once()
        self.assertEqual(instance.tap.call_args.args[0]['resource-id'], PKG + ':id/confirm_button')

    def test_open_permissions_resumes_real_controls_without_selecting_a_decision(self):
        instance = ui()
        instance.dump = Mock(side_effect=[NOTICE, control('mozac_browser_toolbar_site_info_indicator'),
                                         control('origin_permissions_entry'), control('origin_permissions_dialog_list')])
        instance.tap = Mock()
        instance.open_permissions()
        self.assertEqual([c.args[0]['resource-id'] for c in instance.tap.call_args_list],
                         [PKG + ':id/' + s for s in ['confirm_button', 'mozac_browser_toolbar_site_info_indicator', 'origin_permissions_entry']])
        instance.evidence.check.assert_not_called()

    def test_notice_removed_before_probes_and_quiet_check_reads_after_late_notice(self):
        for forbidden in ['origin_permission_allow', 'origin_permissions_dialog_list']:
            runner = g.Runner.__new__(g.Runner)
            runner.fixtures = [Mock(origin='http://localhost:4245')]
            runner.ui = ui()
            # Existing notice before matrix; another arrives during probes.
            runner.ui.dump = Mock(side_effect=[NOTICE, EMPTY, NOTICE, control(forbidden)])
            runner.ui.tap = Mock()
            runner.evidence = Mock()
            runner.matrix = Mock(side_effect=lambda *a, **kw: self.assertEqual(runner.ui.tap.call_count, 1))
            runner.choose = Mock()
            with self.assertRaisesRegex(g.Failure, 'automatically'):
                runner.core()
            self.assertEqual(runner.ui.tap.call_count, 2)
            runner.choose.assert_not_called()
            runner.evidence.check.assert_not_called()


class LineageTests(unittest.TestCase):
    def test_all_retained_input_bytes_match_receipt(self):
        receipt = json.loads((HERE / 'source-inputs.json').read_text())
        self.assertEqual(hashlib.sha256((HERE / 'before-and-source.tar.gz').read_bytes()).hexdigest(), receipt['archive_sha256'])
        self.assertEqual(set(BODIES), {r['path'] for r in receipt['files']})
        for row in receipt['files']:
            self.assertEqual(hashlib.sha256(BODIES[row['path']]).hexdigest(), row['sha256'])
            self.assertEqual(len(BODIES[row['path']]), row['bytes'])

    def test_actual_failure_reproduces_with_frozen_harness(self):
        old = types.ModuleType('frozen_graphics')
        old.__file__ = str(ROOT / 'scripts/android-graphics-smoke.py')
        exec(compile(BODIES['before/scripts/android-graphics-smoke.py'], old.__file__, 'exec'), old.__dict__)
        instance = old.UI(Mock(), PKG, Mock(), 'old')
        instance.dump = Mock(return_value=NOTICE)
        instance.tap = Mock()
        with self.assertRaisesRegex(old.Failure, 'No quiet Review action'):
            instance.open_permissions()
        instance.tap.assert_not_called()

    def test_all_acceptance_check_calls_and_constants_unchanged(self):
        old = ast.parse(BODIES['before/scripts/android-graphics-smoke.py'])
        new = ast.parse((ROOT / 'scripts/android-graphics-smoke.py').read_text())
        def checks(tree):
            return [ast.dump(n, include_attributes=False) for n in ast.walk(tree) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute) and n.func.attr == 'check']
        self.assertEqual(checks(old), checks(new))
        def functions(tree):
            return {n.name: ast.dump(n, include_attributes=False) for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        before, after = functions(old), functions(new)
        self.assertEqual({n for n in before if before[n] != after[n]}, {'core', 'open_permissions'})
        self.assertEqual(set(after) - set(before), {'ubo_added_notice', 'acknowledge_ubo_added_notice'})
        self.assertEqual(BODIES['before/scripts/android-smoke.sh'], (ROOT / 'scripts/android-smoke.sh').read_bytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
