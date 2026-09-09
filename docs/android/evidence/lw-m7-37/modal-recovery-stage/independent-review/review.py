#!/usr/bin/env python3
"""Host-only independent review of the frozen modal245 stage; never runs staging."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = Path('/home/mgysin/redoubt-artifacts/feature-parity/lw-m7-37-modal-stage/repo')
SCOPE = REPO / 'docs/android/evidence/lw-m7-37/modal-recovery-stage'
PARENT = SCOPE.parent / 'harness-recovery-stage'
sha = lambda data: hashlib.sha256(data).hexdigest()


def record(path):
    body = path.read_bytes()
    return {'path': str(path), 'sha256': sha(body), 'bytes': len(body)}


def functions(path):
    source = path.read_text()
    return {n.name: ast.get_source_segment(source, n) for n in ast.parse(source).body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


expected = {
    'stage.py': '7fc7059e7dbd2851fbfbef3bec28e44a0b931d099812411440bd4c9379417d03',
    'version-inputs.json': 'd6c30694e18eaaea510790459ca95d0ab5daa275ab3c49c8c429e18f8ee9d008',
    'test_checkpoint.py': '59f73d448417c52441068ee55cc2f669c5d44c34f0fec10bdb2a9cf6b7de812c',
    'test_stage.py': 'ad7fab3c297f4c8f35b6e44a2f9ade17913b32a7ad324ebd82efe862fca2aa18',
}
for name, digest in expected.items():
    assert record(SCOPE / name)['sha256'] == digest, name
spec = importlib.util.spec_from_file_location('independent_modal_stage', SCOPE / 'stage.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
pins = s.version_inputs()
inputs = s.own_inputs()
assert len(inputs) == 51 and len({row['path'] for row in inputs}) == 51
assert len(pins['checkpoint_files']) == 18 and len(pins['parent_helper_files']) == 39
for row in inputs:
    assert record(Path(row['path'])) == row
actual_paths = {row['path'] for row in inputs}
assert {row['path'] for row in s.c.runtime_inputs().values()} <= actual_paths
assert len(s.c.runtime_inputs()) == 9
for name in pins['parent_helper_files']:
    assert str(REPO / name) in actual_paths

current_functions, old_functions = functions(SCOPE / 'stage.py'), functions(PARENT / 'stage.py')
assert set(current_functions) == set(old_functions)
unchanged = {name: sha(body.encode()) for name, body in current_functions.items()
             if body == old_functions[name]}
assert len(unchanged) == 14
assert set(current_functions) - set(unchanged) == {'version_inputs', 'own_inputs'}
assert (SCOPE / 'test_stage.py').read_bytes() == (PARENT / 'test_stage.py').read_bytes()
assert s.prior_runtime.c is s.c and s.prior_runtime.implementation.c is s.c
assert s.c.original_runtime.c is s.c.base
assert s.c.base.RUNTIME.name == 'account-process-runtime'
assert s.c.RUNTIME.name == 'modal-process-runtime'
runtime_functions = functions(REPO / 'docs/android/evidence/lw-m7-12/harness-process-recovery/runtime.py')
assert len(runtime_functions) == 8
for name in runtime_functions:
    assert getattr(s.prior_runtime, name).__globals__['c'] is s.c

plan = s.v.load_plan()
assert len(plan['final']) == 245 and len(plan['bodies']) == 107
assert sum(value is None for value in plan['before'].values()) == 45
assert s.v.BASE == '4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739'
assert s.v.FINAL == '40da1bf9c42187b1e037fba5b443e4b26fd2758ffa7b07212710df72693eb806'
native_source = REPO / 'docs/android/evidence/lw-m7-12/candidate5/native.py'
constants = {target.id: ast.literal_eval(n.value) for n in ast.parse(native_source.read_text()).body
             if isinstance(n, ast.Assign) for target in n.targets
             if isinstance(target, ast.Name) and target.id in {'STAGE_KIND', 'STAGE_SERVICE'}}
assert constants == {'STAGE_KIND': 'account-process245-source-stage', 'STAGE_SERVICE': s.SERVICE}

command = [sys.executable, '-m', 'unittest', 'discover', '-s', str(SCOPE), '-p', 'test_*.py', '-v']
test = subprocess.run(command, cwd=REPO, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
(HERE / 'host-tests.txt').write_bytes(test.stdout)
assert test.returncode == 0 and b'Ran 29 tests' in test.stdout and b'\nOK\n' in test.stdout
receipt = {
    'schema': 1,
    'verdict': 'NO_CONCRETE_SOURCE_BLOCKER_FOUND',
    'candidate_commit': 'fd186c86',
    'scope': 'Independent host-only source/binding/preservation review. Failed 11a5 runtime blocks staging; no guest commands, source staging, config capture, or native build.',
    'code_inputs': [record(SCOPE / n) for n in expected],
    'source_inputs': inputs,
    'checkpoint_records': 18,
    'parent_helper_records': 39,
    'unique_staging_inputs': 51,
    'unchanged_function_sha256': unchanged,
    'runtime_functions_bound_to_private_modal_adapter': sorted(runtime_functions),
    'original_runtime_base_unchanged': True,
    'product_manifest_sha256': s.v.FINAL,
    'source_count': 245,
    'body_count': 107,
    'native5_stage_constants_match': constants,
    'host_tests': {'count': 29, 'exit': test.returncode, 'log': record(HERE / 'host-tests.txt')},
    'target_execution': 'NOT_RUN',
    'review_script': record(Path(__file__)),
}
(HERE / 'review.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'review': record(HERE / 'review.json'), 'host_tests': 29, 'source_inputs': 51,
                  'unchanged_functions': 14, 'runtime_bindings': 8}, indent=2))
