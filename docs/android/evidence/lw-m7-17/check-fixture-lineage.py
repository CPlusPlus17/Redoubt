#!/usr/bin/env python3
"""Verify retained compiler/test correction lineage; never execute target code."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent.parent
GRAPHICS = 'patches/android/canvas-webgl-permissions.patch'
COOKIE = 'patches/android/cookie-banner-controls.patch'
SYNC = 'patches/android/sync-opt-in.patch'


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def archive(data):
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as stream:
        members = stream.getmembers()
        require(all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in members), 'invalid retained member')
        require(len({m.name for m in members}) == len(members), 'duplicate retained member')
        return {m.name: stream.extractfile(m).read() for m in members}


def patch_sections(data):
    result = {}
    for block in re.split(rb'(?=^diff --git |^diff -[^\n]*|^--- (?:a/|/dev/null))', data, flags=re.M):
        match = re.search(rb'^\+\+\+ b/(.+)$', block, re.M)
        if match:
            name = match[1].decode()
            require(name not in result, 'duplicate patch source')
            result[name] = block
    require(result, 'empty patch')
    return result


def check(coverage, followup):
    reference = followup['fixture_lineage_followup']
    require(reference['review_receipt'] == 'fixture-lineage-followup/review.json', 'fixture review path differs')
    receipt = json.loads((HERE / reference['review_receipt']).read_bytes())
    require(reference['repository_before_edit'] == receipt['repository_before_edit'], 'fixture review revision differs')
    for item in [reference, receipt]:
        require(item['compile_verdict'].startswith('NOT RUN') and item['runtime_verdict'].startswith('NOT RUN'), 'fixture review must not claim target success')
    raw = (HERE / 'fixture-lineage-followup/before-review.tar.gz').read_bytes()
    require(digest(raw) == receipt['before_review_archive_sha256'], 'fixture previous review archive differs')
    previous = archive(raw)
    old_coverage = json.loads(previous['coverage.json'])
    old_followup = json.loads(previous['followup-review.json'])
    require(receipt['unchanged_original_source_sha256'] == followup['archived_source_sha256'] == old_followup['archived_source_sha256'], 'fixture review relabels original archive')
    for key in old_coverage:
        if key != 'repository_evidence':
            require(coverage[key] == old_coverage[key], 'fixture review changes coverage semantics: ' + key)
    expected_changes = receipt['updated_repository_evidence']
    actual_changes = {name: {'before_sha256': old, 'after_sha256': coverage['repository_evidence'].get(name)}
                      for name, old in old_coverage['repository_evidence'].items()
                      if old != coverage['repository_evidence'].get(name)}
    require(actual_changes == expected_changes and set(coverage['repository_evidence']) == set(old_coverage['repository_evidence']), 'fixture current input changes differ')
    require(set(actual_changes) == {GRAPHICS, SYNC, 'assets/patches/android.txt', 'docs/android/evidence/lw-m7-35/ordering-receipt.json', 'docs/android/evidence/lw-m7-36/source-files.json', 'patches/android/firefox-suggest-policy.patch', 'docs/android/evidence/lw-m7-29/source-files.json'}, 'fixture review scope expanded')
    inputs = {}
    for name, row in receipt['inputs'].items():
        data = (ROOT / name).read_bytes()
        require(len(data) == row['bytes'] and digest(data) == row['sha256'], 'fixture input differs: ' + name)
        inputs[name] = data

    def read(name):
        require(name in inputs, 'unbound fixture input: ' + name)
        return inputs[name]

    def load(name):
        return json.loads(read(name))

    old_registry = (HERE / 'fixture-lineage-followup/before-android-registry.txt').read_bytes()
    require(digest(old_registry) == old_coverage['repository_evidence']['assets/patches/android.txt'], 'historical registry differs')
    require(read('assets/patches/android.txt') == old_registry + receipt['registry_append'].encode(), 'registry changed beyond reviewed append')
    require(receipt['registry_append'].startswith('patches/android/session-cleanup.patch # LW-M7-37:') and receipt['registry_append'].count('\n') == 1, 'registry append scope differs')

    fixture_home = 'docs/android/evidence/lw-m7-21/permission-cookie-fixture-correction/'
    optin_home = 'docs/android/evidence/lw-m7-21/test-optin-correction/'
    boolean_home = 'docs/android/evidence/lw-m7-20/boolean-matcher-correction/'
    routing_home = 'docs/android/evidence/lw-m7-20/customtab-intent-correction/'
    format_home = 'docs/android/evidence/lw-m7-20/customtab-patch-format-correction/'
    nav_home = 'docs/android/evidence/lw-m7-20/navigation-fixture-correction/'
    reload_home = 'docs/android/evidence/lw-m7-21/cookie-settings-reload-correction/'
    metrics_home = 'docs/android/evidence/lw-m7-21/startup-metrics-fixture-correction/'
    fixtures = load(fixture_home + 'inputs.json')
    retained = {}
    for name in ['before-repository.tar.gz', 'before-source.tar.gz', 'test-source-overlay.tar.gz']:
        raw = read(fixture_home + name)
        require(digest(raw) == fixtures['archives'][name], 'fixture archive internal pin differs')
        retained[name] = archive(raw)
    original = retained['before-repository.tar.gz']
    optin = load(optin_home + 'source-overlay.json')
    packed_graphics = read(optin_home + 'original-graphics.patch.gz')
    require(digest(packed_graphics) == optin['original_patch_archive_sha256'], 'intermediate graphics archive differs')
    intermediate = gzip.decompress(packed_graphics)
    bundle = load('docs/android/evidence/lw-m7-21/permission-bundle-correction/source-overlay.json')
    chain = receipt['graphics_patch_chain']
    require(bundle['patch_sha256'] == fixtures['patches'][GRAPHICS]['before_sha256'] == digest(original[GRAPHICS]) == chain['bundle'], 'Bundle graphics lineage differs')
    require(fixtures['patches'][GRAPHICS]['after_sha256'] == optin['old_patch_sha256'] == digest(intermediate) == chain['permission_fixture'], 'permission fixture lineage differs')
    require(optin['patch_sha256'] == digest(read(GRAPHICS)) == coverage['repository_evidence'][GRAPHICS] == chain['coroutine_optin'], 'optin graphics lineage differs')
    reload = load(reload_home + 'source-overlay.json')
    cookie_intermediate = gzip.decompress(read(reload_home + 'original-cookie-banner-controls.patch.gz'))
    require(digest(original[COOKIE]) == fixtures['patches'][COOKIE]['before_sha256'] and digest(cookie_intermediate) == fixtures['patches'][COOKIE]['after_sha256'] == reload['original_patch_sha256'], 'cookie fixture lineage differs')
    require(digest(read(COOKIE)) == reload['patch_sha256'], 'cookie reload lineage differs')
    boolean = load(boolean_home + 'source-overlay.json')
    routing = load(routing_home + 'source-overlay.json')
    sync_intermediate = read(routing_home + 'original-sync-opt-in.patch')
    require(digest(sync_intermediate) == boolean['patch_sha256'] == routing['previous_patch_sha256'], 'Boolean fixture lineage differs')
    format_receipt = load(format_home + 'receipt.json')
    nav = load(nav_home + 'source-overlay.json')
    routing_patch = read(format_home + 'before-sync-opt-in.patch')
    formatted_patch = read(nav_home + 'before-sync-opt-in.patch')
    require(digest(routing_patch) == routing['patch_sha256'] == format_receipt['previous_patch_sha256'], 'Home routing lineage differs')
    require(digest(formatted_patch) == format_receipt['patch_sha256'] == nav['previous_patch_sha256'], 'GNU format lineage differs')
    process20_home = 'docs/android/evidence/lw-m7-20/isolated-process-correction/'
    navigation_patch = gzip.decompress(read(process20_home + 'before-sync-opt-in.patch.gz'))
    require(digest(navigation_patch) == nav['patch_sha256'], 'historical navigation fixture lineage differs')
    old_format = load(format_home + 'before-source-files.json')
    new_format = load(nav_home + 'before-source-files.json')
    navigation20 = load(process20_home + 'before-source-files.json')
    current20 = load('docs/android/evidence/lw-m7-20/source-files.json')
    require(old_format['files'] == new_format['files'], 'format correction changed source bodies')
    old20 = {x['path']: x['after_sha256'] for x in new_format['files']}
    final20 = {x['path']: x['after_sha256'] for x in navigation20['files']}
    require(set(old20) == set(final20) and {n for n in old20 if old20[n] != final20[n]} == {nav['files'][0]['path']}, 'navigation fixture changed other20 outputs')
    require(current20['patch_sha256'] == digest(read(SYNC)), 'current20 source receipt differs')
    require(digest(read(boolean_home + 'original-sync-opt-in.patch')) == old_coverage['repository_evidence'][SYNC], 'historical Sync review differs')
    patch_pairs = [(original[GRAPHICS], intermediate, {x['path'] for x in fixtures['files'] if x['patch'] == GRAPHICS}),
                   (intermediate, read(GRAPHICS), {x['path'] for x in optin['files']}),
                   (original[COOKIE], cookie_intermediate, {x['path'] for x in fixtures['files'] if x['patch'] == COOKIE}),
                   (cookie_intermediate, read(COOKIE), {x['path'] for x in reload['files']}),
                   (read(boolean_home + 'original-sync-opt-in.patch'), sync_intermediate, {x['path'] for x in boolean['files']})]
    for before, after, changed in patch_pairs:
        a, b = patch_sections(before), patch_sections(after)
        require(set(a) == set(b) and {n for n in a if a[n] != b[n]} == changed, 'fixture patch changed unexpected sections')
        require(all('/src/test/' in name for name in changed), 'fixture change touches product source')
    a, b = patch_sections(sync_intermediate), patch_sections(routing_patch)
    require({n for n in a if a[n] != b.get(n)} == {routing['files'][0]['path']} and set(b) - set(a) == {routing['files'][1]['path']}, 'Home routing changed unexpected patch sections')
    home_before = read(routing_home + 'HomeActivity.kt.before')
    home_after = read(routing_home + 'HomeActivity.kt')
    require(digest(home_before) == routing['files'][0]['before_sha256'] and digest(home_after) == routing['files'][0]['after_sha256'], 'Home routing bodies differ')
    prefix = b'    internal fun handleNewIntent(intent: Intent) {\n'
    account = b'        if (intent.getBooleanExtra(AccountServicesPreference.OPEN_SETTINGS, false)) {\n            intent.removeExtra(AccountServicesPreference.OPEN_SETTINGS)\n            navHost.navController.navigate(NavGraphDirections.actionGlobalSettingsFragment())\n            return\n        }\n'
    external = b'        if (this is ExternalAppBrowserActivity) {\n            return\n        }\n'
    require(prefix + account + external in home_before and home_before.replace(prefix + account + external, prefix + external + account) == home_after, 'Home routing changed beyond restored early return')
    home_tests = read(routing_home + 'HomeActivityAccountSettingsTest.kt')
    require(routing['files'][1]['before_sha256'] is None and digest(home_tests) == routing['files'][1]['after_sha256'] and len(re.findall(rb'@Test\b', home_tests)) == 4, 'Home routing regression inventory differs')
    nav_before = read(nav_home + 'HomeActivityAccountSettingsTest.kt.before')
    nav_after = read(nav_home + 'HomeActivityAccountSettingsTest.kt')
    require(nav_before == home_tests and nav_before.split(b'        val intent = Intent().putExtra', 1)[1] == nav_after.split(b'        val intent = Intent().putExtra', 1)[1], 'navigation fixture changed actions or assertions')
    require(final20[nav['files'][0]['path']] == digest(nav_after), 'navigation fixture final body differs')
    a, b = patch_sections(formatted_patch), patch_sections(navigation_patch)
    require(set(a) == set(b) and {n for n in a if a[n] != b[n]} == {nav['files'][0]['path']}, 'navigation fixture changed unexpected patch sections')
    metrics = load(metrics_home + 'source-overlay.json')
    metrics_patch = 'patches/android/firefox-suggest-policy.patch'
    old_metrics = gzip.decompress(read(metrics_home + 'original-patch.gz'))
    require(digest(old_metrics) == metrics['before_patch_sha256'] == old_coverage['repository_evidence'][metrics_patch], 'metrics fixture predecessor differs')
    process26_home = 'docs/android/evidence/lw-m7-26/isolated-process-correction/'
    metrics_stage = gzip.decompress(read(process26_home + 'before-firefox-suggest-policy.patch.gz'))
    require(digest(metrics_stage) == metrics['after_patch_sha256'], 'historical metrics fixture patch differs')
    a, b = patch_sections(old_metrics), patch_sections(metrics_stage)
    require(all(b.get(n) == block for n, block in a.items()) and set(b) - set(a) == {metrics['changed_files'][0]['path']}, 'metrics fixture modified prior patch sections')
    metrics_before = read(metrics_home + 'FenixApplicationTest.kt.before')
    metrics_after = read(metrics_home + 'FenixApplicationTest.kt')
    added_choices = b'        every { settings.showSponsoredSuggestions } returns true\n        every { settings.showNonSponsoredSuggestions } returns true\n'
    require(metrics_after.count(added_choices) == 1 and metrics_after.replace(added_choices, b'') == metrics_before, 'metrics fixture changed beyond two explicit choices')
    rows = []
    for item in fixtures['files']:
        before = retained['before-source.tar.gz'][item['path']]
        after = retained['test-source-overlay.tar.gz'][item['path']]
        count = item['test_count_before']
        require(count == item['test_count_after'], 'fixture test count changed')
        rows.append((item, before, after, count))
    for home, data, count in [(boolean_home, boolean, 8), (optin_home, optin, 8)]:
        require(len(data['files']) == 1, 'single-file correction scope differs')
        item = data['files'][0]
        rows.append((item, read(home + item['source'] + '.before'), read(home + item['source']), count))
    optin_row = rows[-1]
    item = reload['files'][0]
    rows.append((item, read(reload_home + item['source'] + '.before'), read(reload_home + item['source']), 5))
    require(rows[-1][1].split(b'    @Test\n', 1)[1] == rows[-1][2].split(b'    @Test\n', 1)[1], 'reload fixture changed test bodies')
    rows.append((metrics['changed_files'][0], metrics_before, metrics_after, 8))
    rows.append((nav['files'][0], nav_before, nav_after, 4))
    require(len(rows) == len({item['path'] for item, *_ in rows}) == 8, 'eight fixture sources required')
    for item, before, after, count in rows:
        require(digest(before) == item['before_sha256'] and digest(after) == item['after_sha256'], 'fixture source body differs')
        require(len(re.findall(rb'@Test\b', before)) == len(re.findall(rb'@Test\b', after)) == count, 'authored fixture count differs')
    item, before, after, _ = optin_row
    require(after.replace(b'import kotlinx.coroutines.ExperimentalCoroutinesApi\n', b'').replace(b'@OptIn(ExperimentalCoroutinesApi::class)\n', b'') == before, 'optin changed assertions or body')

    manifest36 = load('docs/android/evidence/lw-m7-36/source-files.json')
    current = {x['path']: x['sha256'] for x in manifest36['scoped_predecessors']}
    for name in [GRAPHICS, COOKIE, SYNC]:
        require(current[name] == digest(read(name)), 'Task36 current predecessor differs')
    manifest23 = load('docs/android/evidence/lw-m7-23/source-files.json')
    require(manifest23['predecessors']['canvas-webgl-permissions.patch'] == digest(read(GRAPHICS)), 'Task23 current predecessor differs')
    final23 = {row['path']: row['after_sha256'] for row in manifest23['files']}
    for row in fixtures['files']:
        if row['patch'] == COOKIE:
            require(final23[row['path']] == row['after_sha256'], 'Task23 corrected source receipt differs')
    ordering = load('docs/android/evidence/lw-m7-35/ordering-inputs.json')
    order_receipt = load('docs/android/evidence/lw-m7-35/ordering-receipt.json')
    require(order_receipt['inputs_sha256'] == digest(read('docs/android/evidence/lw-m7-35/ordering-inputs.json')), 'Task35 order receipt binding differs')
    for name in [GRAPHICS, COOKIE, SYNC]:
        require(ordering['patches'][name] == digest(read(name)), 'Task35 current order predecessor differs')
    manifest29 = load('docs/android/evidence/lw-m7-29/source-files.json')
    require(next(row['sha256'] for row in manifest29['scoped_predecessors'] if row['path'] == metrics_patch) == digest(read(metrics_patch)), 'Task29 current26 predecessor differs')
    current26 = load('docs/android/evidence/lw-m7-26/source-files.json')
    require(next(row['sha256'] for row in current26['scoped_predecessors'] if row['path'] == SYNC) == digest(read(SYNC)), 'Task26 current20 predecessor differs')
    check_process(coverage, followup, read, load)
    print('LINEAGE VERIFIED: Bundle114 -> fixtureA8 -> OptInB10; eight historical fixture bodies; Home9f -> GNU28 -> navigationAC0 -> process8ca; metrics86 -> process36e; three new cases and six actual167 bodies; current20/23/26/29/35/36. No target verdict.')


def check_process(coverage, followup, read, load):
    reference = followup['process_lineage_followup']
    require(reference['review_receipt'] == 'process-lineage-followup/review.json', 'process review path differs')
    review_home = 'docs/android/evidence/lw-m7-17/process-lineage-followup/'
    review = load(review_home + 'review.json')
    require(reference['scope'] == review['scope'] and reference['repository_before_edit'] == review['repository_before_edit'], 'process review scope differs')
    for item in [reference, review]:
        require(item['compile_verdict'].startswith('NOT RUN') and item['runtime_verdict'].startswith('NOT RUN'), 'process review must not claim target success')
    before_raw = read(review_home + 'before-review.tar.gz')
    require(digest(before_raw) == review['before_review_archive_sha256'], 'process previous review archive differs')
    before = archive(before_raw)
    require(set(before) == {'coverage.json', 'followup-review.json', 'coverage-map.md', 'README.md', 'check-coverage.py', 'check-fixture-lineage.py', 'fixture-lineage-followup/review.json', 'fixture-lineage-followup/test-checker.py'}, 'process previous review inventory differs')
    prior = json.loads(before['coverage.json'])
    for key in prior:
        if key != 'repository_evidence':
            require(prior[key] == coverage[key], 'process review changes counterpart semantics: ' + key)
    changes = {n: {'before_sha256': h, 'after_sha256': coverage['repository_evidence'].get(n)}
               for n, h in prior['repository_evidence'].items() if h != coverage['repository_evidence'].get(n)}
    require(changes == review['updated_repository_evidence'] and len(changes) == 5, 'process current evidence scope differs')
    home20 = 'docs/android/evidence/lw-m7-20/isolated-process-correction/'
    home26 = 'docs/android/evidence/lw-m7-26/isolated-process-correction/'
    require(set(review['three_new_authored_cases']) == {'AccountServicesTest.kt', 'AccountServicesPreferenceTest.kt', 'FirefoxSuggestPolicyTest.kt'}, 'process regression class scope differs')
    histories = {}
    for task, home, patch, old_archive, expected_count in [
        ('20', home20, SYNC, 'before-sync-opt-in.patch.gz', 5),
        ('26', home26, 'patches/android/firefox-suggest-policy.patch', 'before-firefox-suggest-policy.patch.gz', 3),
    ]:
        change = load(home + 'source-overlay.json')
        old = load(home + 'before-source-files.json')
        current = load(f'docs/android/evidence/lw-m7-{task}/source-files.json')
        require(digest(gzip.decompress(read(home + old_archive))) == old['patch_sha256'] == change['previous_patch_sha256'] == prior['repository_evidence'][patch], 'process historical patch differs')
        require(digest(read(patch)) == current['patch_sha256'] == change['patch_sha256'] == coverage['repository_evidence'][patch], 'process current patch differs')
        old_rows, new_rows = ({r['path']: r for r in receipt['files']} for receipt in [old, current])
        changed_rows = {r['path']: r for r in change['files']}
        require(set(old_rows) == set(new_rows) and len(changed_rows) == expected_count, 'process scoped inventory differs')
        require({n for n in old_rows if old_rows[n]['after_sha256'] != new_rows[n]['after_sha256']} == set(changed_rows), 'process changed output scope differs')
        for name, row in changed_rows.items():
            old_body = read(home + Path(name).name + '.before')
            new_body = read(home + Path(name).name)
            require(digest(old_body) == old_rows[name]['after_sha256'] == row['before_sha256'], 'process scoped before differs')
            require(digest(new_body) == new_rows[name]['after_sha256'] == row['after_sha256'], 'process scoped after differs')
            if Path(name).name in review['three_new_authored_cases']:
                counts = [len(re.findall(rb'@Test\b', body)) for body in [old_body, new_body]]
                require(counts == review['three_new_authored_cases'][Path(name).name] and counts[1] == counts[0] + 1, 'process authored regression count differs')
        histories[task] = new_rows
    combined = load(home26 + 'current167-overlay.json')
    require(combined['patch20_sha256'] == digest(read(SYNC)) and combined['patch26_sha256'] == digest(read('patches/android/firefox-suggest-policy.patch')), 'process combined patch pins differ')
    old_manifest = read(home26 + 'actual-current167-source-sha256.txt')
    require(digest(old_manifest) == combined['previous_source_sha256'] == review['historical_runtime_parent_sha256'], 'process actual parent manifest differs')
    original = {line.split('  ', 1)[1]: line.split('  ', 1)[0] for line in old_manifest.decode().splitlines()}
    require(len(original) == 167, 'process parent source count differs')
    before_raw = read(home26 + 'actual-expanded-source-before.tar.gz')
    require(digest(before_raw) == combined['before_archive_sha256'], 'process actual before archive differs')
    actual = archive(before_raw)
    policy_path = 'mobile/android/fenix/app/src/test/java/org/mozilla/fenix/settings/search/FirefoxSuggestPolicyTest.kt'
    actual[policy_path] = read(home26 + 'actual-FirefoxSuggestPolicyTest.kt.before')
    require(digest(actual[policy_path]) == combined['policy_test_before_sha256'], 'process actual policy fixture differs')
    packed = read(home26 + 'current167-source-overlay.tar.gz')
    require(digest(packed) == combined['overlay_archive_sha256'], 'process combined archive differs')
    output = archive(packed)
    require(len(combined['files']) == len(output) == 6 and set(output) == {r['path'] for r in combined['files']}, 'process six-file overlay scope differs')
    latest = dict(original)
    source = histories['20'] | histories['26']
    for row in combined['files']:
        name = row['path']
        require(digest(actual[name]) == original[name] == row['before_sha256'], 'process actual before binding differs')
        require(digest(output[name]) == row['after_sha256'] == source[name]['after_sha256'], 'process actual after binding differs')
        latest[name] = row['after_sha256']
    derived = ''.join(f'{h}  {n}\n' for n,h in sorted(latest.items())).encode()
    require(derived == read(home26 + 'proposed-current167-source-sha256.txt') and digest(derived) == combined['proposed_source_sha256'] == review['corrected167_manifest_sha256'], 'process corrected manifest differs')
    require(sum(latest[n] == h for n, h in original.items()) == 161, 'process unaffected actual source bindings changed')
    runtime_log = gzip.decompress(read(home20 + 'startup-logcat-20260909T0523.txt.gz'))
    log_receipt = load(home20 + 'source-overlay.json')['actual_runtime_log']
    require(digest(runtime_log) == log_receipt['sha256'] and b'getSharedPreferences' in runtime_log and b'zygoteTab' in runtime_log, 'process original failure evidence differs')


if __name__ == '__main__':
    check(json.loads((HERE / 'coverage.json').read_bytes()), json.loads((HERE / 'followup-review.json').read_bytes()))
