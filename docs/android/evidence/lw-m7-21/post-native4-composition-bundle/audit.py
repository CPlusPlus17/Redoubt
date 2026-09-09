#!/usr/bin/env python3
"""Read-only-input composition audit. Writes only a new --output directory; never builds or accesses a guest."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

PATCHES = {
    '30': 'patches/android/no-default-shortcuts.patch',
    '31': 'patches/android/extension-permission-durability.patch',
    '29': 'patches/android/firefox-suggest-data.patch',
    '35': 'patches/android/extension-update-controls.patch',
    '36': 'patches/android/global-privacy-controls.patch',
}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


def safe(name):
    require(name and not name.startswith('/') and '..' not in Path(name).parts, 'unsafe path: ' + name)
    return name


def archive(data):
    result = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as stream:
        for item in stream.getmembers():
            safe(item.name)
            if item.isdir():
                continue
            require(item.isfile() and item.name not in result, 'non-file/duplicate archive member')
            result[item.name] = stream.extractfile(item).read()
    return result


def put(tree, name, data):
    path = tree / safe(name)
    require(not path.exists(), 'refusing to overwrite initial input: ' + name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def contents(tree):
    return {str(path.relative_to(tree)): path.read_bytes() for path in tree.rglob('*') if path.is_file()}


def manifest(data):
    result = {}
    for line in data.decode().splitlines():
        digest, name = line.split('  ', 1)
        safe(name)
        require(re.fullmatch('[0-9a-f]{64}', digest) and name not in result, 'invalid manifest row')
        result[name] = digest
    return result


def binding_text(bindings):
    return ''.join(digest + '  ' + name + '\n' for name, digest in sorted(bindings.items()))


def filtered_patch(data, paths):
    selected = []
    for block in re.split(r'(?=^diff --git |^diff -[^\n]*|^--- (?:a/|/dev/null))', data.decode(), flags=re.M):
        match = re.search(r'^\+\+\+ b/(.+)$', block, re.M)
        if match and match[1] in paths:
            selected.append(block)
    require(selected, 'no scoped patch hunks selected')
    return ''.join(selected)


def apply(repo, tree, patch_path, paths, log):
    patch = filtered_patch((repo / patch_path).read_bytes(), paths)
    steps = []
    for dry in [True, False]:
        args = ['patch', '--batch', '--forward', '--fuzz=0', '-p1'] + (['--dry-run'] if dry else [])
        result = subprocess.run(args, input=patch, cwd=tree, text=True, capture_output=True)
        steps.append({'dry_run': dry, 'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
        require(result.returncode == 0 and not re.search(r'with fuzz|FAILED|malformed', result.stdout + result.stderr, re.I),
                'patch failed: ' + patch_path + '\n' + result.stdout + result.stderr)
    require(not list(tree.rglob('*.rej')), 'patch left rejects')
    # GNU patch preserves .orig backups on offset; discard only these known tool
    # outputs in this newly created scratch source after recording all offsets.
    for path in tree.rglob('*.orig'):
        path.unlink()
    log.append({'patch': patch_path, 'patch_sha256': sha((repo / patch_path).read_bytes()), 'steps': steps,
                'offsets': re.findall(r'Hunk #[^\n]*offset[^\n]*', steps[-1]['stdout'])})


def check_files(tree, rows, side):
    for row in rows:
        path = tree / row['path']
        actual = sha(path.read_bytes()) if path.is_file() else None
        require(actual == row[side + '_sha256'], side + ' source mismatch: ' + row['path'] + ' actual=' + str(actual))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pins', type=Path, default=Path(__file__).with_name('audit-inputs.json'))
    args = parser.parse_args()
    repo, out = args.repo.resolve(), args.output.resolve()
    require(not out.exists() and out != repo and repo not in out.parents, 'output must be a new directory outside input repository')
    pins = read_json(args.pins)
    for name, expected in pins['files'].items():
        data = (repo / safe(name)).read_bytes()
        require(len(data) == expected['bytes'] and sha(data) == expected['sha256'], 'input changed: ' + name)
    out.mkdir(parents=True)
    evidence = repo / 'docs/android/evidence'
    native_capture = read_json(evidence / 'lw-m7-21/native4-success/capture.json')
    native_bytes = (evidence / 'lw-m7-21/native4-success/guest-evidence.tar.gz').read_bytes()
    require(sha(native_bytes) == native_capture['sha256'], 'native4 archive pin differs')
    native = archive(native_bytes)
    original_manifest = native['native4-terminal/driver/source-sha256.txt']
    original = manifest(original_manifest)
    require(len(original) == 164 and sha(original_manifest) == native_capture['result']['source_manifest_sha256'], 'native4 manifest differs')
    for phase in ['before', 'after']:
        checks = native[f'native4-terminal/driver/source-{phase}.txt'].decode().splitlines()
        require(set(checks) == {name + ': OK' for name in original} and len(checks) == 164, 'native4 checks differ')
    (out / 'original-native4-source-sha256.txt').write_bytes(original_manifest)

    overlay = read_json(evidence / 'lw-m7-21/admission-copy-correction/source-overlay.json')
    failed_bytes = (evidence / 'lw-m7-21/native4-apk-failure/guest-evidence.tar.gz').read_bytes()
    require(sha(failed_bytes) == overlay['failed_archive_sha256'], 'failed APK archive differs')
    failed = archive(failed_bytes)
    failed_result = read_json(evidence / 'lw-m7-21/native4-apk-failure/result.json')
    for name, expected in failed_result['files'].items():
        require(sha(failed[name]) == expected['sha256'] and len(failed[name]) == expected['bytes'], 'failed APK evidence differs: ' + name)
    failed_manifest = failed['parity-extended-apk/source-sha256.txt']
    apk_before = manifest(failed_manifest)
    require(len(apk_before) == 165 and sha(failed_manifest) == failed_result['source_manifest_sha256'], 'failed APK manifest differs')
    require(manifest(failed['parity-extended-apk/native-source-sha256.txt']) == original, 'APK native parent differs')
    (out / 'original-failed-apk-source-sha256.txt').write_bytes(failed_manifest)
    current = dict(apk_before)
    overlay_bytes = {}
    overlay_histories = {}
    for row in overlay['files']:
        name = row['path']
        require(current[name] == row['before_sha256'] and sha(failed['source/' + name]) == row['before_sha256'], 'overlay before differs')
        data = (evidence / 'lw-m7-21/admission-copy-correction' / Path(name).name).read_bytes()
        require(sha(data) == row['after_sha256'], 'overlay after differs')
        current[name] = sha(data)
        overlay_bytes[name] = data
        overlay_histories[name] = [{'task': '26-copy-correction', 'before_sha256': row['before_sha256'], 'after_sha256': row['after_sha256']}]
    context_overlay = read_json(evidence / 'lw-m7-21/search-context-correction/source-overlay.json')
    require(context_overlay['old_patch_sha256'] == overlay['patch_sha256'], '26 correction chain differs')
    failed2_bytes = (evidence / 'lw-m7-21/apk-copy-recovery-failure/guest-evidence.tar.gz').read_bytes()
    require(sha(failed2_bytes) == context_overlay['failed_archive_sha256'], 'second failed APK archive differs')
    failed2 = archive(failed2_bytes)
    failed2_result = read_json(evidence / 'lw-m7-21/apk-copy-recovery-failure/result.json')
    for name, expected in failed2_result['files'].items():
        require(sha(failed2[name]) == expected['sha256'] and len(failed2[name]) == expected['bytes'], 'second APK evidence differs: ' + name)
    require(manifest(failed2['parity-extended-apk/source-sha256.txt']) == current, 'second failed APK manifest does not bind first overlay')
    (out / 'original-second-failed-apk-source-sha256.txt').write_bytes(failed2['parity-extended-apk/source-sha256.txt'])
    for row in context_overlay['files']:
        name = row['path']
        require(current[name] == row['before_sha256'] and sha(failed2['source/' + name]) == row['before_sha256'], 'context overlay before differs')
        data = (evidence / 'lw-m7-21/search-context-correction' / Path(name).name).read_bytes()
        require(sha(data) == row['after_sha256'], 'context overlay after differs')
        current[name] = sha(data)
        overlay_bytes[name] = data
        overlay_histories[name] = [{'task': '26-context-correction', 'before_sha256': row['before_sha256'], 'after_sha256': row['after_sha256']}]
    require(sha((repo / 'patches/android/firefox-suggest-policy.patch').read_bytes()) == context_overlay['patch_sha256'], 'corrected26 patch differs')
    permission_overlay = read_json(evidence / 'lw-m7-21/permission-bundle-correction/source-overlay.json')
    failed3_bytes = (evidence / 'lw-m7-21/apk-context-recovery-failure/guest-evidence.tar.gz').read_bytes()
    require(sha(failed3_bytes) == permission_overlay['failed_archive_sha256'], 'third failed APK archive differs')
    failed3 = archive(failed3_bytes)
    failed3_result = read_json(evidence / 'lw-m7-21/apk-context-recovery-failure/result.json')
    for name, expected in failed3_result['files'].items():
        require(sha(failed3[name]) == expected['sha256'] and len(failed3[name]) == expected['bytes'], 'third APK evidence differs: ' + name)
    require(manifest(failed3['parity-extended-apk/source-sha256.txt']) == current, 'third failed APK manifest does not bind preceding overlays')
    (out / 'original-third-failed-apk-source-sha256.txt').write_bytes(failed3['parity-extended-apk/source-sha256.txt'])
    for row in permission_overlay['files']:
        name = row['path']
        require(current[name] == row['before_sha256'] and sha(failed3['source/' + name]) == row['before_sha256'], 'permission overlay before differs')
        data = (evidence / 'lw-m7-21/permission-bundle-correction' / Path(name).name).read_bytes()
        require(sha(data) == row['after_sha256'], 'permission overlay after differs')
        current[name] = sha(data)
        overlay_bytes[name] = data
        overlay_histories[name] = [{'task': '14-bundle-correction', 'before_sha256': row['before_sha256'], 'after_sha256': row['after_sha256']}]
    require(sha((repo / 'patches/android/canvas-webgl-permissions.patch').read_bytes()) == permission_overlay['patch_sha256'], 'corrected14 patch differs')
    # Both admission files are newly introduced by26; derive their exact bytes
    # independently from the latest full26 patch as well as captured overlays.
    correction_tree = out / 'corrected26-new-files'
    correction_tree.mkdir()
    correction_log = []
    apply(repo, correction_tree, 'patches/android/firefox-suggest-policy.patch', {row['path'] for row in overlay['files']}, correction_log)
    for row in overlay['files']:
        require((correction_tree / row['path']).read_bytes() == overlay_bytes[row['path']], '26 patch/overlay bytes differ')
    permission_tree = out / 'corrected14-dialog'
    permission_tree.mkdir()
    apply(repo, permission_tree, 'patches/android/canvas-webgl-permissions.patch', {row['path'] for row in permission_overlay['files']}, correction_log)
    for row in permission_overlay['files']:
        require((permission_tree / row['path']).read_bytes() == overlay_bytes[row['path']], '14 patch/overlay bytes differ')
    (out / 'expected-current165-source-sha256.txt').write_text(binding_text(current))

    # Rebuild each task's exact retained before state and independently prove its
    # complete final state. These scopes remain distinct from actual compiled164.
    replay_logs, task_before, task_rows, manifests = {}, {}, {}, {}
    for task in ['30', '31', '29', '35', '36']:
        here = evidence / ('lw-m7-' + task)
        data = read_json(here / 'source-files.json')
        manifests[task] = data
        tree = out / ('isolated-' + task)
        tree.mkdir()
        rows = data['files'] if task != '30' else [data]
        if task == '31':
            rows = [row for row in rows if row['role'] == 'changed']
        paths = {row['path'] for row in rows if row.get('delivery', 'source_patch') == 'source_patch'}
        task_rows[task] = rows
        log = replay_logs[task] = []
        if task in ['29', '36']:
            raw = (here / 'scoped-pristine.tar.gz').read_bytes()
            require(sha(raw) == data['scoped_pristine_archive_sha256'], 'pristine archive differs')
            retained = archive(raw)
            require(set(retained) == set(data['scoped_pristine_files']), 'pristine inventory differs')
            for name, content in retained.items():
                require(sha(content) == data['scoped_pristine_files'][name], 'pristine content differs')
                put(tree, name, content)
            for predecessor in data['scoped_predecessors']:
                require(sha((repo / predecessor['path']).read_bytes()) == predecessor['sha256'], 'predecessor differs')
                apply(repo, tree, predecessor['path'], paths, log)
        else:
            raw = (here / 'source-baseline.tar.gz').read_bytes()
            expected = data.get('archive_sha256', data.get('baseline_archive_sha256'))
            if expected:
                require(sha(raw) == expected, 'task archive differs: ' + task)
            retained = archive(raw)
            for name, content in retained.items():
                if name in paths:
                    put(tree, name, content)
        check_files(tree, rows, 'before')
        task_before[task] = {row['path']: (tree / row['path']).read_bytes() if (tree / row['path']).is_file() else None for row in rows}
        expected = data.get('patch_sha256')
        if expected:
            require(sha((repo / PATCHES[task]).read_bytes()) == expected, 'task patch differs: ' + task)
        apply(repo, tree, PATCHES[task], paths, log)
        if task == '29':
            result = subprocess.run(['python3', str(repo / 'scripts/package-firefox-suggest.py'), '--source-tree', str(tree)], capture_output=True, text=True)
            require(result.returncode == 0, 'Suggest packaging failed: ' + result.stderr)
            log.append({'generator': 'scripts/package-firefox-suggest.py', 'stdout': result.stdout, 'stderr': result.stderr})
        check_files(tree, rows, 'after')
        require(set(contents(tree)) == {row['path'] for row in rows}, 'unexpected isolated replay files: ' + task)

    resource = manifests['30']
    require({name: digest for name, digest in apk_before.items() if name not in original} == {resource['path']: resource['after_sha256']}, 'APK30 union differs')
    require(all(apk_before[name] == digest for name, digest in original.items()), 'APK30 changed original native inputs')
    require(json.loads((out / 'isolated-30' / resource['path']).read_bytes()) == {'data': []}, 'empty shortcut resource differs')

    # Earliest changed-file before state wins; later tasks must consume its exact
    # composed output, never overwrite it with their standalone baseline.
    registry = [line.split('#', 1)[0].strip() for line in (repo / 'assets/patches/android.txt').read_text().splitlines()]
    tasks = sorted(['31', '29', '35', '36'], key=lambda task: registry.index(PATCHES[task]))
    require(tasks == ['31', '29', '35', '36'], 'review registry order changed')
    tree = out / 'source'
    tree.mkdir()
    starting = {}
    histories = {}
    for task in tasks:
        for row in task_rows[task]:
            name = row['path']
            histories.setdefault(name, []).append({'task': task, 'before_sha256': row['before_sha256'], 'after_sha256': row['after_sha256'], 'delivery': row.get('delivery', 'source_patch')})
            if name not in starting:
                starting[name] = task_before[task][name]
    for name, data in starting.items():
        if name in current:
            require(data is not None and sha(data) == current[name], 'compiled/current baseline differs: ' + name)
        if data is not None:
            put(tree, name, data)
    for name, data in overlay_bytes.items():
        if name in starting:
            require(starting[name] == data, 'later baseline does not include latest26 context correction')
        else:
            put(tree, name, data)
    put(tree, resource['path'], (out / 'isolated-30' / resource['path']).read_bytes())
    composite_log = []
    for task in tasks:
        rows = task_rows[task]
        check_files(tree, rows, 'before')
        paths = {row['path'] for row in rows if row.get('delivery', 'source_patch') == 'source_patch'}
        apply(repo, tree, PATCHES[task], paths, composite_log)
        if task == '29':
            result = subprocess.run(['python3', str(repo / 'scripts/package-firefox-suggest.py'), '--source-tree', str(tree)], capture_output=True, text=True)
            require(result.returncode == 0, 'composed Suggest packaging failed')
            composite_log.append({'generator': 'scripts/package-firefox-suggest.py', 'stdout': result.stdout, 'stderr': result.stderr})
        check_files(tree, rows, 'after')
    final_content = contents(tree)
    require(set(final_content) == set(starting) | set(overlay_bytes) | {resource['path']}, 'composed output scope differs')
    final = dict(current)
    final.update({name: sha(data) for name, data in final_content.items()})
    (out / 'proposed-source-sha256.txt').write_text(binding_text(final))
    (out / 'composed-subset-sha256.txt').write_text(binding_text({name: sha(data) for name, data in final_content.items()}))
    rows = []
    for name, data in sorted(final_content.items()):
        before = sha(starting[name]) if name in starting and starting[name] is not None else current.get(name)
        if name in starting and starting[name] is None:
            before = None
        rows.append({'path': name, 'original_native4_sha256': original.get(name), 'expected_before_staging_sha256': before,
                     'after_sha256': sha(data), 'after_bytes': len(data),
                     'action': 'retain-bound-input' if before == sha(data) else 'create-if-absent' if before is None else 'replace-if-before-matches',
                     'baseline_binding': 'current165-manifest' if name in current else 'retained-task-baseline-requires-live-preflight',
                     'lineage': overlay_histories.get(name, []) + histories.get(name, [] if name in overlay_histories else [{'task': '30', 'before_sha256': before, 'after_sha256': sha(data)}])})
    staging = {'scope': 'PROPOSED, NOT STAGED. Preflight all current165 hashes and every additional before/absence before any guest mutation.',
               'original_native4_manifest_sha256': sha(original_manifest), 'failed165_manifest_sha256': sha(failed_manifest),
               'second_failed165_manifest_sha256': sha(failed2['parity-extended-apk/source-sha256.txt']),
               'third_failed165_manifest_sha256': sha(failed3['parity-extended-apk/source-sha256.txt']),
               'expected_current165_manifest_sha256': sha(binding_text(current).encode()),
               'final_manifest_sha256': sha(binding_text(final).encode()), 'final_count': len(final), 'files': rows,
               'untouched_original_bindings': {name: digest for name, digest in original.items() if name not in final_content},
               'retention_rule': 'Keep original native4 compiled evidence/manifest and failed APK165 receipt immutable. Bind the full union, not only changed files. This source subset is not a complete Gecko source tree.'}
    (out / 'proposed-staging.json').write_text(json.dumps(staging, indent=2) + '\n')
    (out / 'overlapping-lineages.json').write_text(json.dumps({name: history for name, history in sorted(histories.items()) if len(history) > 1}, indent=2) + '\n')
    (out / 'replay-logs.json').write_text(json.dumps({'corrected26_and14_new_files': correction_log, 'isolated': replay_logs, 'composed': composite_log}, indent=2) + '\n')
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w') as retained:
        for name, data in sorted(final_content.items()):
            item = tarfile.TarInfo(name); item.size = len(data); item.mode = 0o644; item.mtime = 0
            retained.addfile(item, io.BytesIO(data))
    (out / 'composed-source-subset.tar.gz').write_bytes(gzip.compress(raw.getvalue(), mtime=0))
    receipt = {'status': 'PASS local source composition; no target acceptance', 'repository_input_commit': pins['repository_commit'],
               'audit_script_sha256': sha(Path(__file__).read_bytes()),
               'input_pins_sha256': sha(args.pins.read_bytes()), 'original_native4_count': len(original), 'retained_base_with30_count': len(apk_before),
               'base_kotlin_overlay_count': len(overlay_bytes), 'registry_order': [PATCHES[task] for task in tasks],
               'materialized_subset_count': len(final_content), 'final_union_count': len(final), 'original_files_without_local_body': len(staging['untouched_original_bindings']),
               'generated_suggest_count': sum(row.get('delivery') == 'packager' for row in task_rows['29']),
               'shared_later_patch_paths': len([history for history in histories.values() if len(history) > 1]),
               'additional_before_or_absence_preflights_required': sum(name not in current for name in starting),
               'fuzz': 0, 'composite_offsets': [offset for log in composite_log for offset in log.get('offsets', [])],
               'scope_limit': 'All changed-file bodies were reconstructed from retained inputs. Unchanged native4 bodies are preserved as compiled manifest bindings only; future staging must verify their live hashes and all additional inputs before mutation.',
               'target_compilation': 'NOT RUN', 'target_tests': 'NOT RUN', 'APK_runtime': 'NOT RUN',
               'outputs': {name: sha((out / name).read_bytes()) for name in ['proposed-source-sha256.txt', 'proposed-staging.json', 'composed-subset-sha256.txt', 'composed-source-subset.tar.gz', 'overlapping-lineages.json', 'replay-logs.json']}}
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({key: value for key, value in receipt.items() if key not in ['outputs', 'scope_limit']}, indent=2))


if __name__ == '__main__':
    main()
