#!/usr/bin/env python3
"""Adversarial controls for the source-evidence checker, not Android unit tests."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parents[3]
spec = importlib.util.spec_from_file_location('fixture_lineage', HERE / 'check-fixture-lineage.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
coverage = json.loads((HERE / 'coverage.json').read_bytes())
followup = json.loads((HERE / 'followup-review.json').read_bytes())
review = json.loads((HERE / 'fixture-lineage-followup/review.json').read_bytes())

with tempfile.TemporaryDirectory(prefix='lw-m7-17-lineage-negatives-') as scratch:
    private = Path(scratch)
    local = private / HERE.relative_to(ROOT)
    for name in review['inputs']:
        out = private / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes((ROOT / name).read_bytes())
    for name in ['fixture-lineage-followup/review.json', 'fixture-lineage-followup/before-review.tar.gz', 'fixture-lineage-followup/before-android-registry.txt']:
        out = local / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes((HERE / name).read_bytes())
    module.HERE, module.ROOT = local, private

    def run(c, f):
        with contextlib.redirect_stdout(io.StringIO()):
            module.check(c, f)

    run(coverage, followup)
    print('PASS: exact baseline fixture lineage accepted')

    def reject(label, change, expected):
        c, f, r = copy.deepcopy(coverage), copy.deepcopy(followup), copy.deepcopy(review)
        restore = change(c, f, r)
        (local / 'fixture-lineage-followup/review.json').write_text(json.dumps(r))
        try:
            run(c, f)
        except ValueError as error:
            assert expected in str(error), (label, str(error))
            print(f'PASS: rejected {label}: {error}')
        else:
            raise AssertionError('accepted ' + label)
        finally:
            if restore:
                restore()
            (local / 'fixture-lineage-followup/review.json').write_text(json.dumps(review))

    reject('false target verdict', lambda c, f, r: f['fixture_lineage_followup'].update(compile_verdict='PASS'), 'must not claim target success')
    reject('relabelled original archive', lambda c, f, r: r.update(unchanged_original_source_sha256='0' * 64), 'relabels original archive')
    reject('changed counterpart semantics', lambda c, f, r: c['counterparts']['sync'].update(remaining='None'), 'changes coverage semantics')
    reject('Bundle stage overwritten by current hash', lambda c, f, r: r['graphics_patch_chain'].update(bundle=r['graphics_patch_chain']['coroutine_optin']), 'Bundle graphics lineage differs')
    reject('missing intermediate fixture stage', lambda c, f, r: r['graphics_patch_chain'].update(permission_fixture=r['graphics_patch_chain']['bundle']), 'permission fixture lineage differs')

    def corrupt_body(c, f, r):
        row = next(n for n in r['inputs'] if n.endswith('/OriginBoundPermissionsFeatureTest.kt'))
        path = private / row
        original = path.read_bytes()
        path.write_bytes(original.replace(b'@Test', b'// removed Test', 1))
        return lambda: path.write_bytes(original)

    reject('changed authored test body', corrupt_body, 'fixture input differs')
    run(coverage, followup)
    print('PASS: exact fixture lineage accepted after every negative control')
