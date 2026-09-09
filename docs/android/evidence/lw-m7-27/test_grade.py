"""Synthetic protocol regressions; these are not native Android test executions."""
import contextlib
import importlib.util
import os
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import driver
from grade import InvalidResult, bound_log, grade_instrumentation, grade_run, grade_xpcshell, sha

SPEC = {'path':'toolkit/example/test_native.js', 'tasks':['first','second'], 'allowed_skips':['desktop_only']}
METHODS = ['org.mozilla.geckoview.test.Example#first', 'org.mozilla.geckoview.test.Example#second']


def events():
    output = [{'action':'suite_start'}, {'action':'test_start','test':SPEC['path']}]
    for task in SPEC['tasks']:
        output.extend([
            {'action':'log','level':'INFO','message':f'{SPEC["path"]} | Starting {task}'},
            {'action':'test_status','test':SPEC['path'],'subtest':'assertion','status':'PASS'},
            {'action':'log','level':'INFO','message':f'(xpcshell/head.js) | test {task} finished (1)'},
        ])
    return output + [{'action':'test_end','test':SPEC['path'],'status':'PASS'}, {'action':'suite_end'}]


def raw(rows):
    return ''.join(json.dumps(row)+'\n' for row in rows)


def instrumented():
    result = ''
    for current, method in enumerate(METHODS, 1):
        klass, name = method.split('#')
        for code in [1,0]:
            result += f'INSTRUMENTATION_STATUS: class={klass}\nINSTRUMENTATION_STATUS: test={name}\nINSTRUMENTATION_STATUS: numtests=2\nINSTRUMENTATION_STATUS: current={current}\nINSTRUMENTATION_STATUS_CODE: {code}\n'
    return result + 'INSTRUMENTATION_RESULT: stream=\nTime: 1.0\n\nOK (2 tests)\n\nINSTRUMENTATION_CODE: -1\n'


class XpcshellGrading(unittest.TestCase):
    def test_complete_named_task_suite(self):
        self.assertEqual(grade_xpcshell(raw(events()), SPEC)['passed_tasks'], ['first','second'])

    def test_empty_partial_or_malformed(self):
        for text in ['', raw(events())[:-1], '{}\n', 'not json\n', '[]\n']:
            with self.subTest(text=text), self.assertRaises(InvalidResult):
                grade_xpcshell(text, SPEC)

    def test_file_pass_cannot_replace_named_tasks(self):
        rows = [x for x in events() if x['action'] != 'log']
        with self.assertRaises(InvalidResult): grade_xpcshell(raw(rows), SPEC)

    def test_start_without_task_finish(self):
        rows = [x for x in events() if 'second finished' not in x.get('message','')]
        with self.assertRaises(InvalidResult): grade_xpcshell(raw(rows), SPEC)

    def test_required_skip_even_when_finish_is_logged(self):
        rows = events()
        rows.insert(3, {'action':'test_status','test':SPEC['path'],'subtest':'first','status':'SKIP'})
        with self.assertRaises(InvalidResult): grade_xpcshell(raw(rows), SPEC)

    def test_only_explicit_unrelated_skips_allowed(self):
        for name, allowed in [('desktop_only',True),('unexpected',False)]:
            rows = events()
            rows.insert(3, {'action':'test_status','test':SPEC['path'],'subtest':name,'status':'SKIP'})
            if allowed:
                self.assertEqual(grade_xpcshell(raw(rows),SPEC)['allowed_skips_observed'], ['desktop_only'])
            else:
                with self.assertRaises(InvalidResult): grade_xpcshell(raw(rows),SPEC)

    def test_unexpected_failures_and_crashes(self):
        for diagnostic in [
            {'action':'test_status','status':'FAIL','expected':'FAIL'},
            {'action':'log','level':'ERROR','message':'failure'},
            {'action':'crash'}, {'action':'assertion_count','count':1},
        ]:
            rows = events(); rows.insert(3,diagnostic)
            with self.subTest(diagnostic=diagnostic), self.assertRaises(InvalidResult): grade_xpcshell(raw(rows),SPEC)

    def test_zero_native_assertions_are_accepted(self):
        rows=events(); rows.insert(3, {'action':'assertion_count','count':0})
        grade_xpcshell(raw(rows),SPEC)

    def test_duplicate_task_or_test_file(self):
        for index in [1,2,4]:
            rows=events(); rows.insert(index, copy.deepcopy(rows[index]))
            with self.subTest(index=index), self.assertRaises(InvalidResult): grade_xpcshell(raw(rows),SPEC)

    def test_missing_suite_or_file_completion(self):
        for action in ['suite_start','suite_end','test_start','test_end']:
            with self.subTest(action=action), self.assertRaises(InvalidResult):
                grade_xpcshell(raw([x for x in events() if x['action'] != action]),SPEC)

    def test_other_file_task_log_or_subtest_is_rejected(self):
        for kind in ['message','test']:
            rows=events()
            if kind=='message': rows[2]['message']='other.js | Starting first'
            else: rows[3]['test']='other.js'
            with self.subTest(kind=kind),self.assertRaises(InvalidResult):grade_xpcshell(raw(rows),SPEC)

    def test_other_file_is_not_evidence(self):
        rows=events();rows[1]['test']='toolkit/other/test_wrong.js'
        with self.assertRaises(InvalidResult):grade_xpcshell(raw(rows),SPEC)


class InstrumentationGrading(unittest.TestCase):
    def test_complete_selected_methods(self):
        self.assertEqual(grade_instrumentation(instrumented(),METHODS)['passed_methods'],METHODS)

    def test_skip_assumption_failure_error(self):
        for code in [-1,-2,-3,-4,2]:
            text=instrumented().replace('INSTRUMENTATION_STATUS_CODE: 0',f'INSTRUMENTATION_STATUS_CODE: {code}',1)
            with self.subTest(code=code), self.assertRaises(InvalidResult):grade_instrumentation(text,METHODS)

    def test_no_final_result_or_summary(self):
        for text in ['', instrumented()[:-1], instrumented().replace('INSTRUMENTATION_CODE: -1\n',''), instrumented().replace('OK (2 tests)','')]:
            with self.subTest(text=text), self.assertRaises(InvalidResult):grade_instrumentation(text,METHODS)

    def test_missing_named_method_despite_success_summary(self):
        text=instrumented(); start=text.index('INSTRUMENTATION_STATUS: class=', text.index('INSTRUMENTATION_STATUS_CODE: 0')+1)
        text=text[:start]+text[text.index('INSTRUMENTATION_RESULT:'):]
        with self.assertRaises(InvalidResult):grade_instrumentation(text,METHODS)

    def test_wrong_name_count_duplicate_or_unmatched_completion(self):
        for text in [instrumented().replace('test=first','test=unrequested'),instrumented().replace('numtests=2','numtests=1'),instrumented().replace('test=second','test=first'),instrumented().replace('STATUS_CODE: 1','STATUS_CODE: 0',1)]:
            with self.subTest(text=text), self.assertRaises(InvalidResult):grade_instrumentation(text,METHODS)

    def test_crash_or_bad_final_code(self):
        for text in [instrumented()+'INSTRUMENTATION_FAILED: crashed\n',instrumented().replace('INSTRUMENTATION_CODE: -1','INSTRUMENTATION_CODE: 0'),instrumented()+'INSTRUMENTATION_CODE: -1\n']:
            with self.subTest(text=text), self.assertRaises(InvalidResult):grade_instrumentation(text,METHODS)


class EvidenceBinding(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)
        (self.path/'run.log').write_text('fresh\n')
        self.receipt={'run_id':'a'*32,'exit':0,'started_ns':10,'finished_ns':20,'log_created_ns':11,'source_binding_sha256':'b'*64,'build_receipt_sha256':'c'*64,'log':'run.log','log_sha256':sha(self.path/'run.log')}

    def test_bound_fresh_bytes(self):self.assertEqual(bound_log(self.receipt,self.path),'fresh\n')

    def test_stale_incomplete_failed_or_unbound(self):
        for key,value in [('log_created_ns',9),('finished_ns',10),('exit',1),('run_id',''),('source_binding_sha256',''),('build_receipt_sha256',''),('log','../run.log')]:
            receipt=dict(self.receipt,**{key:value})
            with self.subTest(key=key), self.assertRaises(InvalidResult):bound_log(receipt,self.path)

    def test_modified_or_empty_log(self):
        for text in ['changed\n','']:
            (self.path/'run.log').write_text(text)
            with self.subTest(text=text),self.assertRaises(InvalidResult):bound_log(self.receipt,self.path)

    def write(self,name,value):
        (self.path/name).write_text(json.dumps(value)+'\n')

    def make_run(self, pending=None):
        req={'xpcshell':[SPEC],'instrumentation':METHODS}
        if pending:
            req['pending_xpcshell'] = pending
        self.write('requirements.json',req)
        binding={'requirements_sha256':sha(self.path/'requirements.json')}
        self.write('source-binding.json',binding);self.write('source-after-tests.json',binding)
        build={'status':'PASS','source_binding_sha256':sha(self.path/'source-binding.json'),'requirements_sha256':sha(self.path/'requirements.json')}
        self.write('build-receipt.json',build)
        invocation={'run_id':'a'*32,'source_binding_sha256':sha(self.path/'source-binding.json'),'build_receipt_sha256':sha(self.path/'build-receipt.json')}
        self.write('invocation.json',invocation)
        for name,text,receipt_name in [('xpcshell-0.jsonl',raw(events()),'xpcshell-0.raw-receipt.json'),('instrumentation.log',instrumented(),'instrumentation.log.receipt.json')]:
            (self.path/name).write_text(text)
            self.write(receipt_name,dict(self.receipt,**invocation,log=name,log_sha256=sha(self.path/name)))

    def test_archived_run_regrades_without_build_tree(self):
        self.make_run();self.assertEqual(grade_run(self.path)['status'],'PASS')

    def test_upstream_android_exclusion_cannot_become_a_pass(self):
        pending = [{'path':'toolkit/extensions/test_uninstall.js','tasks':['remove'],
                    'reason':'audited upstream Android exclusion'}]
        self.make_run(pending)
        result = grade_run(self.path)
        self.assertEqual(result['status'], 'PENDING')
        self.assertEqual(result['pending_xpcshell'], pending)

    def test_foreign_run_receipt_is_rejected(self):
        self.make_run();p=self.path/'xpcshell-0.raw-receipt.json';x=json.loads(p.read_text());x['run_id']='f'*32;self.write(p.name,x)
        with self.assertRaises(InvalidResult):grade_run(self.path)

    def test_source_after_and_selection_are_bound(self):
        for name in ['source-after-tests.json','requirements.json','build-receipt.json']:
            self.make_run();self.write(name,{})
            with self.subTest(name=name),self.assertRaises(InvalidResult):grade_run(self.path)


class DriverIsolation(unittest.TestCase):
    CONFIG='ac_add_options --enable-application=mobile/android\nac_add_options --target=aarch64-linux-android\nac_add_options --disable-tests\nac_add_options --enable-optimize\nac_add_options --enable-lto=cross\nac_add_options --enable-android-subproject=fenix\nmk_add_options MOZ_OBJDIR=/production/object\n'

    def test_only_test_tools_target_subproject_and_objdir_change(self):
        changed=driver.derive_config(self.CONFIG,Path('/test/obj-x86_64-tests'))
        self.assertIn('--enable-tests',changed);self.assertIn('--target=x86_64-linux-android',changed)
        self.assertIn('--enable-android-subproject=geckoview_example',changed)
        self.assertIn('--enable-optimize\nac_add_options --enable-lto=cross',changed)
        self.assertNotIn('/production/object',changed);self.assertIn('MOZ_OBJDIR=/test/obj-x86_64-tests',changed)

    def test_ambiguous_nonproduction_or_unsafe_config_is_rejected(self):
        for config in [self.CONFIG.replace('mobile/android','browser'),self.CONFIG.replace('--disable-tests','--enable-tests'),self.CONFIG+'ac_add_options --target=x86_64-linux-android\n',self.CONFIG.replace('=fenix','=geckoview_example')]:
            with self.subTest(config=config),self.assertRaises(InvalidResult):driver.derive_config(config,Path('/test/obj'))
        with self.assertRaises(InvalidResult):driver.derive_config(self.CONFIG,Path('/test/$(touch unsafe)'))

    def test_plan_does_not_create_workspace_or_execute(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source=base/'src';source.mkdir();(source/'mach').write_text('')
            config=base/'product.mozconfig';config.write_text(self.CONFIG);workspace=base/'redoubt-native-tests-unit'
            args=['driver.py','plan','--source',str(source),'--source-manifest',str(base/'not-read'),'--product-mozconfig',str(config),'--product-revision','a'*40,'--build-date','20260906190000','--workspace',str(workspace)]
            with mock.patch('sys.argv',args),mock.patch('subprocess.Popen',side_effect=AssertionError('must not execute')),contextlib.redirect_stdout(io.StringIO()) as output:driver.main()
            self.assertEqual(json.loads(output.getvalue())['status'],'NOT RUN');self.assertFalse(workspace.exists())

    def test_manifest_rejects_duplicate_escape_and_mismatched_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'file').write_text('bytes');manifest=root/'manifest'
            row=sha(root/'file')+'  file\n'
            for text in [row+row,'0'*64+'  file\n','0'*64+'  ../escape\n']:
                manifest.write_text(text)
                with self.subTest(text=text),self.assertRaises(InvalidResult):driver.source_binding(root,manifest)


class ContainerIsolation(unittest.TestCase):
    def test_direct_host_execution_is_rejected(self):
        with mock.patch.object(Path,'is_file',return_value=False),self.assertRaisesRegex(InvalidResult,'bounded Podman'):
            driver.container_environment()

    def test_compiler_root_cannot_be_replaced(self):
        image=json.loads(driver.REQUIREMENTS.read_text())['build_image_sha256']
        env={'REDOUBT_NATIVE_TEST_IMAGE':image,'MOZBUILD_STATE_PATH':'/temporary/empty-mozbuild'}
        with mock.patch.dict(os.environ,env,clear=True),mock.patch.object(Path,'is_file',return_value=True),self.assertRaisesRegex(InvalidResult,'compiler/toolchain root'):
            driver.container_environment()

    def test_approved_image_and_bounded_cgroup_required(self):
        image=json.loads(driver.REQUIREMENTS.read_text())['build_image_sha256']
        actual_read=Path.read_text
        env={'REDOUBT_NATIVE_TEST_IMAGE':image,'MOZBUILD_STATE_PATH':'/root/.mozbuild'}
        def read(path,*args,**kwargs):
            if path.name=='memory.max':return 'max'
            if path.name=='memory.swap.max':return 'max'
            if path.name=='cpu.max':return 'max 100000'
            return actual_read(path,*args,**kwargs)
        with mock.patch.dict(os.environ,env,clear=True),mock.patch.object(Path,'is_file',return_value=True),mock.patch.object(Path,'exists',return_value=False),mock.patch.object(Path,'read_text',read),self.assertRaisesRegex(InvalidResult,'memory limit'):
            driver.container_environment()
        with mock.patch.dict(os.environ,{'REDOUBT_NATIVE_TEST_IMAGE':'unapproved'},clear=True),mock.patch.object(Path,'is_file',return_value=True),self.assertRaisesRegex(InvalidResult,'image marker'):
            driver.container_environment()

    def test_vm_wrapper_refuses_host_before_starting_container(self):
        spec=importlib.util.spec_from_file_location('in_vm',Path(driver.__file__).with_name('in-vm.py'))
        wrapper=importlib.util.module_from_spec(spec);spec.loader.exec_module(wrapper)
        args=['in-vm.py','--repo','/unused/repo','build','--source','/unused/src','--source-manifest','/unused/manifest','--product-mozconfig','/unused/config','--product-revision','a'*40,'--build-date','20260906190000','--workspace','/home/runner/native-tests-unit/redoubt-native-tests-unit','--execute']
        with mock.patch('sys.argv',args),mock.patch.object(driver,'query',return_value='none'),mock.patch('subprocess.Popen',side_effect=AssertionError('must not execute')),self.assertRaisesRegex(InvalidResult,'KVM'):
            wrapper.main()


class PermissionNativeSelection(unittest.TestCase):
    @staticmethod
    def specs():
        return [spec for spec in json.loads(driver.REQUIREMENTS.read_text())['xpcshell']
                if Path(spec['path']).name.startswith('test_ext_permissions')]

    @staticmethod
    def rows(spec, prefix=None):
        name = (spec['test_id_prefix'] if prefix is None else prefix) + spec['path']
        rows = [{'action':'suite_start'}, {'action':'test_start','test':name}]
        for task in spec['tasks']:
            rows.extend([
                {'action':'log','level':'INFO','message':f'{name} | Starting {task}'},
                {'action':'test_status','test':name,'subtest':'real assertion','status':'PASS'},
                {'action':'log','level':'INFO','message':f'(xpcshell/head.js) | test {task} finished (1)'},
            ])
        return rows + [{'action':'test_end','test':name,'status':'PASS'}, {'action':'suite_end'}]

    def test_every_named_permission_task_is_required(self):
        for spec in self.specs():
            self.assertEqual(len(grade_xpcshell(raw(self.rows(spec)), spec)['passed_tasks']), len(spec['tasks']))
            for task in spec['tasks']:
                rows = [row for row in self.rows(spec) if f'| test {task} finished' not in row.get('message','')]
                with self.subTest(task=task), self.assertRaises(InvalidResult):
                    grade_xpcshell(raw(rows), spec)

    def test_wrong_manifest_variant_is_not_android_evidence(self):
        for spec in self.specs():
            for prefix in ['xpcshell-remote.toml:', 'xpcshell-legacy-ep.toml:', '']:
                with self.subTest(prefix=prefix), self.assertRaises(InvalidResult):
                    grade_xpcshell(raw(self.rows(spec, prefix)), spec)

    def test_rkv_recovery_is_required_in_the_selected_variant(self):
        spec = next(spec for spec in self.specs() if spec['path'].endswith('/test_ext_permissions.js'))
        task = 'test_permissions_rkv_recovery_rename'
        self.assertIn(task, spec['tasks'])
        rows = self.rows(spec)
        rows.insert(3, {'action':'test_status', 'test':spec['test_id_prefix']+spec['path'],
                        'subtest':task, 'status':'SKIP', 'expected':'SKIP'})
        with self.assertRaises(InvalidResult):
            grade_xpcshell(raw(rows), spec)

    def test_selector_filters_manifest_variants_without_skipping_tasks(self):
        for spec in self.specs():
            self.assertEqual(driver.selection_arguments(spec), ['--tag','in-process-webextensions',spec['path']])
        self.assertEqual(driver.selection_arguments(SPEC), [SPEC['path']])
        with self.assertRaises(InvalidResult):
            driver.selection_arguments(dict(SPEC, tags=['--force']))

    def test_pending_test_sources_are_required_by_the_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'file').write_text('bytes');manifest=root/'manifest'
            manifest.write_text(sha(root/'file')+'  file\n')
            req=root/'requirements.json';req.write_text(json.dumps({'product_paths':[], 'xpcshell':[],
                'pending_xpcshell':[{'path':'missing-test.js','tasks':['remove']}], 'instrumentation':[]}))
            with mock.patch.object(driver, 'REQUIREMENTS', req), self.assertRaisesRegex(InvalidResult,'missing-test.js'):
                driver.source_binding(root,manifest)


if __name__=='__main__':unittest.main()
