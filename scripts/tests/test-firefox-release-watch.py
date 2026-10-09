#!/usr/bin/env python3
"""Offline checks for scripts/firefox-release-watch.py.

No network: product-details comes from fixtures
(scripts/tests/fixtures/firefox-release-watch/; product-details-157.0.json is
the real document as served on 2026-10-03, the other two are derived from it;
mobile-versions-157.0.json is mobile_versions.json as served on 2026-10-04,
the 157.0.1 and 158.0 ones are derived from it),
and the end-to-end cases run the script as a subprocess against a fake
archive.mozilla.org + GitHub API on 127.0.0.1.

The patchcheck fixtures are real too: patchfail-157.0-desktop.out and
patchfail-153.4.0esr-desktop.out are check-patchfail.sh reports from
2026-10-04 (main at 39d159ca, against the 157.0 and 153.4.0esr tarballs;
scratch paths rewritten), patchfail-error.out is its output with no tarball,
and the gpg-*.txt files are gpg's output for Mozilla's release key and the
157.0 tarball signature. The patchcheck end-to-end case builds a tiny
"Firefox" tarball, signs it with a throwaway key, and runs the real
check-patchfail.sh against it; it needs gpg, xz and patch, and is skipped
without them.
"""

import http.server
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tarfile
import threading
import unittest
import urllib.parse


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts' / 'firefox-release-watch.py'
FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'firefox-release-watch'

spec = importlib.util.spec_from_file_location('firefox_release_watch', SCRIPT)
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


def fixture(version):
    return json.loads((FIXTURES / f'product-details-{version}.json').read_text())


def core(found):
    """`found` without the title and URL _flag records for notifications."""
    return {k: v for k, v in found.items() if k not in ('title', 'url')}


def mobile_fixture(version):
    return json.loads((FIXTURES / f'mobile-versions-{version}.json').read_text())


class FakeGitHub:
    def __init__(self, titles=(), closed=()):
        # [title, number, state]; numbers are 1-based positions
        self.items = [{'title': t, 'number': n, 'state': 'closed' if t in closed else 'open',
                       'labels': [watch.LABEL], 'assignees': [], 'node_id': f'I_{n}',
                       'created_at': '2026-10-06T14:17:40Z'}
                      for n, t in enumerate(titles, 1)]
        self.created = []
        self.labels = []
        self.posted = {}  # number -> [comment bodies]
        self.stamps = {}  # number -> [comment created_at]
        self.assigned = {}  # number -> [logins]
        self.edits = []
        self.pinned = []
        self.release = ''
        self.rels = []  # what releases() returns: [{'tag', 'draft', 'prerelease', 'body'}]
        self.runs = {}  # (workflow, status) -> [runs]
        self.branches = {}
        self.commits = []
        self.dispatched = []
        self.now = '2026-10-09T12:00:00Z'

    def issues(self, label):
        assert label == watch.LABEL
        return [dict(i) for i in self.items]

    def ensure_label(self, label, *a):
        self.labels.append(label)
        return True

    def create_issue(self, title, body, label, assignees=()):
        self.created.append((title, body, label))
        number = len(self.items) + 1
        self.items.append({'title': title, 'number': number, 'state': 'open',
                           'labels': [label], 'assignees': list(assignees),
                           'node_id': f'I_{number}', 'created_at': self.now})
        self.assigned[number] = list(assignees)
        return f'https://github.invalid/issues/{number}', number

    def item(self, number):
        return next(i for i in self.items if i['number'] == number)

    def add_assignees(self, number, logins):
        self.assigned.setdefault(number, []).extend(logins)
        self.item(number)['assignees'] += list(logins)

    def add_labels(self, number, labels):
        self.item(number)['labels'] += [l for l in labels if l not in self.item(number)['labels']]

    def edit_issue(self, number, **fields):
        self.edits.append((number, fields))
        self.item(number).update(fields)

    def pin_issue(self, node_id):
        self.pinned.append(node_id)
        return True

    def latest_release(self):
        return self.release

    def releases(self):
        return [dict(r) for r in self.rels]

    def comments_full(self, number):
        bodies = self.posted.get(number, [])
        stamps = self.stamps.get(number, [])
        return [{'body': b, 'created_at': stamps[k] if k < len(stamps) else self.now}
                for k, b in enumerate(bodies)]

    def comments(self, number):
        return list(self.posted.get(number, []))

    def create_comment(self, number, body):
        self.posted.setdefault(number, []).append(body)
        self.stamps.setdefault(number, []).append(self.now)
        return f'https://github.invalid/issues/{number}#c{len(self.posted[number])}'

    def workflow_runs(self, workflow, status):
        return list(self.runs.get((workflow, status), []))

    def dispatch(self, workflow, ref, inputs):
        self.dispatched.append((workflow, ref, inputs))

    def branch_sha(self, branch):
        return self.branches.get(branch, '')

    def commit_files(self, base_sha, files, message):
        self.commits.append((base_sha, dict(files), message))
        return f'{len(self.commits):040x}'

    def create_branch(self, branch, sha):
        assert branch not in self.branches
        self.branches[branch] = sha


class Versions(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(watch.parse_version('157.0'), (157, 0, 0))
        self.assertEqual(watch.parse_version('157.0.1'), (157, 0, 1))
        self.assertEqual(watch.parse_version('153.4.0esr'), (153, 4, 0))
        self.assertEqual(watch.parse_version('157.0\n'), (157, 0, 0))
        for bad in ('158.0b3', '159.0a1', '157', '', 'v157.0', '157.0.1.2'):
            with self.assertRaises(ValueError, msg=bad):
                watch.parse_version(bad)

    def test_ordering(self):
        self.assertTrue(watch.is_newer('157.0.1', '157.0'))
        self.assertTrue(watch.is_newer('158.0', '157.0'))
        self.assertTrue(watch.is_newer('158.0', '157.0.1'))
        self.assertTrue(watch.is_newer('157.1', '157.0.9'))
        self.assertFalse(watch.is_newer('157.0', '157.0'))
        self.assertFalse(watch.is_newer('157.0', '157.0.1'))
        self.assertFalse(watch.is_newer('157.0.1', '158.0'))
        # numeric, not lexical: 157.10 > 157.9 and 1000.0 > 999.0
        self.assertTrue(watch.is_newer('157.10', '157.9'))
        self.assertTrue(watch.is_newer('1000.0', '999.0'))
        # the old ESR spelling still compares
        self.assertTrue(watch.is_newer('157.0', '153.4.0esr'))


class Run(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='redoubt-release-watch-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.track('157.0', '157.0')
        self.log = []
        self.asked = []

    def track(self, android, desktop):
        (self.root / 'version.android').write_text(android + '\n')
        (self.root / 'version').write_text(desktop)  # update-version.py writes no newline

    def exists(self, answer):
        def f(url):
            self.asked.append(url)
            return answer
        return f

    def go(self, version, gh, tarball=True, dry_run=False, found=None):
        return watch.run(self.root, fixture(version), self.exists(tarball), gh,
                         'CPlusPlus17/Redoubt', dry_run, log=self.log.append,
                         found=found)

    def test_current_is_quiet(self):
        gh = FakeGitHub()
        self.assertEqual(self.go('157.0', gh), 'current')
        self.assertEqual(gh.created, [])
        self.assertEqual(self.asked, [], 'no archive probe when nothing is new')

    def test_repo_ahead_is_quiet(self):
        self.track('157.0.1', '157.0.1')
        self.assertEqual(self.go('157.0', FakeGitHub()), 'current')

    def test_dot_release_opens_one_issue(self):
        gh = FakeGitHub()
        self.assertEqual(self.go('157.0.1', gh), 'opened')
        self.assertEqual(self.asked, [
            'https://archive.mozilla.org/pub/firefox/releases/157.0.1/source/'
            'firefox-157.0.1.source.tar.xz'])
        (title, body, label), = gh.created
        self.assertEqual(title, 'Firefox 157.0.1 released: rebase Android and desktop')
        self.assertEqual(label, 'firefox-release')
        self.assertEqual(gh.labels, ['firefox-release'])
        self.assertIn('https://www.mozilla.org/en-US/firefox/157.0.1/releasenotes/', body)
        self.assertIn('https://www.mozilla.org/en-US/security/advisories/', body)
        self.assertIn('blob/main/docs/android/REBASE.md', body)
        self.assertIn('140.17.0esr', body)  # FIREFOX_ESR, for information
        for step in ('§1', '§2', '§3', '§4', '§5', '§6', '§7', '§8', '§9', '§10'):
            self.assertIn(step, body)
        self.assertIn("printf '157.0.1\\n' > version.android", body)
        self.assertIn('Android: `version.android` is `157.0`', body)
        self.assertIn('desktop: `version` is `157.0`', body)

    def test_major_release(self):
        gh = FakeGitHub()
        self.assertEqual(self.go('158.0', gh), 'opened')
        self.assertEqual(gh.created[0][0],
                         'Firefox 158.0 released: rebase Android and desktop')
        self.assertIn('153.5.0esr', gh.created[0][1])

    def test_only_one_track_behind(self):
        self.track('157.0', '158.0')
        gh = FakeGitHub()
        self.assertEqual(self.go('158.0', gh), 'opened')
        body = gh.created[0][1]
        self.assertIn('Android: `version.android` is `157.0`', body)
        self.assertNotIn('desktop: `version`', body)

    def test_dedup_across_runs(self):
        gh = FakeGitHub()
        self.assertEqual(self.go('158.0', gh), 'opened')
        self.assertEqual(self.go('158.0', gh), 'duplicate')
        self.assertEqual(self.go('158.0', gh), 'duplicate')
        self.assertEqual(len(gh.created), 1)

    def test_dedup_is_exact_title(self):
        # A closed issue for the same version blocks; a different version,
        # or a near-miss title, does not.
        gh = FakeGitHub(['Firefox 158.0 released: rebase Android and desktop'])
        self.assertEqual(self.go('158.0', gh), 'duplicate')
        gh = FakeGitHub(['Firefox 157.0.1 released: rebase Android and desktop',
                         'Firefox 158.0 released',
                         'Firefox 158.0.1 released: rebase Android and desktop'])
        self.assertEqual(self.go('158.0', gh), 'opened')

    def test_found_drives_the_patchcheck_job(self):
        found = {}
        self.assertEqual(self.go('157.0', FakeGitHub(), found=found), 'current')
        self.assertEqual(found, {})
        self.assertFalse(watch.wants_patchcheck('current', found))

        found = {}
        self.assertEqual(self.go('158.0', FakeGitHub(), tarball=False, found=found),
                         'no-tarball')
        self.assertFalse(watch.wants_patchcheck('no-tarball', found))

        gh, found = FakeGitHub(['unrelated']), {}
        self.assertEqual(self.go('158.0', gh, found=found), 'opened')
        self.assertEqual(core(found), {'version': '158.0', 'issue': 2, 'state': 'open'})
        self.assertTrue(watch.wants_patchcheck('opened', found))

        # The next day: still open, so the check runs again (and the comment
        # marker decides whether anything is posted).
        found = {}
        self.assertEqual(self.go('158.0', gh, found=found), 'duplicate')
        self.assertEqual(core(found), {'version': '158.0', 'issue': 2, 'state': 'open'})
        self.assertTrue(watch.wants_patchcheck('duplicate', found))

        # Closed: the rebase is done; no check.
        title = 'Firefox 158.0 released: rebase Android and desktop'
        found = {}
        self.assertEqual(self.go('158.0', FakeGitHub([title], closed=[title]),
                                 found=found), 'duplicate')
        self.assertEqual(found['state'], 'closed')
        self.assertFalse(watch.wants_patchcheck('duplicate', found))

        # A closed and an open copy: the open one wins.
        found = {}
        gh = FakeGitHub([title, title])
        gh.items[0]['state'] = 'closed'
        self.go('158.0', gh, found=found)
        self.assertEqual((found['issue'], found['state']), (2, 'open'))

        found = {}
        self.assertEqual(self.go('158.0', None, dry_run=True, found=found), 'would-open')
        self.assertTrue(watch.wants_patchcheck('would-open', found))
        self.assertNotIn('issue', found)

    def test_tarball_missing_opens_nothing(self):
        gh = FakeGitHub()
        self.assertEqual(self.go('158.0', gh, tarball=False), 'no-tarball')
        self.assertEqual(gh.created, [])
        # ...and the next run, once the tarball lands, does open it.
        self.assertEqual(self.go('158.0', gh, tarball=True), 'opened')

    def test_dry_run(self):
        gh = FakeGitHub()
        self.assertEqual(self.go('158.0', gh, dry_run=True), 'would-open')
        self.assertEqual(gh.created, [])
        self.assertEqual(self.go('158.0', None, dry_run=True), 'would-open')

    def test_beta_latest_is_refused(self):
        with self.assertRaises(ValueError):
            watch.run(self.root, {'LATEST_FIREFOX_VERSION': '158.0b3'},
                      self.exists(True), FakeGitHub(), 'o/r', log=self.log.append)

    def test_malformed_track_file_is_refused(self):
        self.track('garbage', '157.0')
        with self.assertRaises(ValueError):
            self.go('158.0', FakeGitHub())


class RunAndroid(unittest.TestCase):
    """mobile_versions.json: Android-only releases get their own issue."""

    DOT = 'Firefox for Android 157.0.1 released: rebase Android'

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='redoubt-release-watch-android-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.track('157.0', '157.0')
        self.log = []
        self.asked = []

    track = Run.track

    def exists(self, answer):
        def f(url):
            self.asked.append(url)
            return answer
        return f

    def both(self, desktop, mobile, gh, tarball=False, dry_run=False):
        """One daily run: the desktop half, then the Android half, as main()
        does. Returns ((outcome, found), (outcome, found))."""
        df, af = {}, {}
        versions = fixture(desktop) if isinstance(desktop, str) else desktop
        mv = mobile_fixture(mobile) if isinstance(mobile, str) else mobile
        d = watch.run(self.root, versions, self.exists(tarball), gh, 'CPlusPlus17/Redoubt',
                      dry_run, log=self.log.append, found=df)
        a = watch.run_android(self.root, mv, versions['LATEST_FIREFOX_VERSION'],
                              self.exists(tarball), gh, 'CPlusPlus17/Redoubt', dry_run,
                              log=self.log.append, found=af)
        return (d, df), (a, af)

    def test_real_feed_is_quiet(self):
        gh = FakeGitHub()
        (d, _), (a, af) = self.both('157.0', '157.0', gh)
        self.assertEqual((d, a), ('current', 'current'))
        self.assertEqual(gh.created, [])
        self.assertEqual(self.asked, [])
        self.assertEqual(af, {})

    def test_android_only_dot_without_tarball(self):
        gh = FakeGitHub()
        (d, df), (a, af) = self.both('157.0', '157.0.1', gh, tarball=False)
        self.assertEqual((d, a), ('current', 'opened'))
        self.assertEqual(self.asked, [
            'https://archive.mozilla.org/pub/firefox/releases/157.0.1/source/'
            'firefox-157.0.1.source.tar.xz'])
        (title, body, label), = gh.created
        self.assertEqual(title, self.DOT)
        self.assertEqual(label, 'firefox-release')
        self.assertIn('https://www.mozilla.org/en-US/firefox/android/157.0.1/releasenotes/',
                      body)
        self.assertIn('https://www.mozilla.org/en-US/security/advisories/', body)
        self.assertIn('Desktop Firefox is at `157.0`', body)
        self.assertIn('`version.android` is `157.0`', body)
        self.assertIn('**archive.mozilla.org has no `firefox-157.0.1.source.tar.xz`**', body)
        self.assertIn('https://github.com/mozilla-firefox/firefox/compare/'
                      'FIREFOX-ANDROID_157_0_RELEASE...FIREFOX-ANDROID_157_0_1_RELEASE', body)
        self.assertIn('https://archive.mozilla.org/pub/fenix/releases/157.0.1/', body)
        self.assertIn('NEXT_RELEASE_DATE', body)
        self.assertNotIn('make fetch TARGETS', body)
        self.assertEqual(core(af), {'version': '157.0.1', 'tarball': False, 'issue': 1,
                              'state': 'open'})
        # No tarball: nothing to check the patches against.
        self.assertFalse(watch.wants_android_patchcheck(a, af))
        self.assertEqual(watch.patchcheck_jobs((d, df), (a, af)), [])

    def test_android_only_dot_with_tarball(self):
        gh = FakeGitHub()
        (d, df), (a, af) = self.both('157.0', '157.0.1', gh, tarball=True)
        self.assertEqual(a, 'opened')
        body = gh.created[0][1]
        self.assertIn('<https://archive.mozilla.org/pub/firefox/releases/157.0.1/source/'
                      'firefox-157.0.1.source.tar.xz>', body)
        self.assertIn("printf '157.0.1\\n' > version.android", body)
        self.assertIn('Leave `version` / `release`', body)
        self.assertIn('make fetch TARGETS=android', body)
        self.assertIn('check-patchfail.sh --targets=android', body)
        self.assertNotIn('has no `firefox-', body)
        self.assertEqual(watch.patchcheck_jobs((d, df), (a, af)), [
            {'version': '157.0.1', 'issue': '1', 'targets': 'android',
             'label': 'android'}])

    def test_same_version_as_desktop_is_one_issue(self):
        gh = FakeGitHub()
        (d, df), (a, af) = self.both('157.0.1', '157.0.1', gh, tarball=True)
        self.assertEqual((d, a), ('opened', 'same-as-desktop'))
        self.assertEqual([t for t, _, _ in gh.created],
                         ['Firefox 157.0.1 released: rebase Android and desktop'])
        self.assertEqual(len(self.asked), 1, 'only the desktop half probes the archive')
        self.assertEqual(watch.patchcheck_jobs((d, df), (a, af)), [
            {'version': '157.0.1', 'issue': '1', 'targets': 'desktop,android',
             'label': 'release'}])
        # ...and the next day, still one issue.
        self.both('157.0.1', '157.0.1', gh, tarball=True)
        self.assertEqual(len(gh.created), 1)

    def test_older_than_desktop_is_superseded(self):
        gh = FakeGitHub()
        (d, _), (a, af) = self.both('158.0', '157.0.1', gh, tarball=True)
        self.assertEqual((d, a), ('opened', 'superseded'))
        self.assertEqual(len(gh.created), 1)
        self.assertEqual(af, {})

    def test_mobile_major_ahead_of_desktop_waits(self):
        # Mobile feed reports 158.0 while desktop still says 157.0: no
        # Android-only issue, and no second issue once desktop catches up.
        gh = FakeGitHub()
        (d, _), (a, af) = self.both('157.0', '158.0', gh, tarball=True)
        self.assertEqual(a, 'ahead-of-desktop')
        self.assertEqual(gh.created, [])
        self.assertEqual(af, {})
        (d, _), (a, _) = self.both('158.0', '158.0', gh, tarball=True)
        self.assertEqual((d, a), ('opened', 'same-as-desktop'))
        self.assertEqual(len(gh.created), 1)

    def test_android_already_there(self):
        self.track('157.0.1', '157.0')
        gh = FakeGitHub()
        (_, _), (a, _) = self.both('157.0', '157.0.1', gh)
        self.assertEqual(a, 'current')
        self.assertEqual(gh.created, [])

    def test_ahead_of_a_newer_desktop_release_too(self):
        # Desktop 157.0.1 and an Android-only 157.0.2 on the same day: two
        # releases, two issues, two checks.
        gh = FakeGitHub()
        mv = dict(mobile_fixture('157.0'), version='157.0.2')
        (d, df), (a, af) = self.both('157.0.1', mv, gh, tarball=True)
        self.assertEqual((d, a), ('opened', 'opened'))
        self.assertEqual([t for t, _, _ in gh.created], [
            'Firefox 157.0.1 released: rebase Android and desktop',
            'Firefox for Android 157.0.2 released: rebase Android'])
        self.assertEqual([j['targets'] for j in watch.patchcheck_jobs((d, df), (a, af))],
                         ['desktop,android', 'android'])

    def test_dedup(self):
        gh = FakeGitHub()
        self.both('157.0', '157.0.1', gh)
        (_, _), (a, af) = self.both('157.0', '157.0.1', gh)
        self.assertEqual(a, 'duplicate')
        self.assertEqual(len(gh.created), 1)
        # Still open, still no tarball: no check.
        self.assertFalse(watch.wants_android_patchcheck(a, af))
        # The tarball turns up later while the issue is open: now it is checked.
        (_, _), (a, af) = self.both('157.0', '157.0.1', gh, tarball=True)
        self.assertEqual(a, 'duplicate')
        self.assertTrue(watch.wants_android_patchcheck(a, af))
        self.assertEqual(len(gh.created), 1)
        # Closed: done, never reopened, never checked.
        gh = FakeGitHub([self.DOT], closed=[self.DOT])
        (_, _), (a, af) = self.both('157.0', '157.0.1', gh, tarball=True)
        self.assertEqual((a, af['state']), ('duplicate', 'closed'))
        self.assertFalse(watch.wants_android_patchcheck(a, af))
        self.assertEqual(gh.created, [])
        # A desktop issue for the same number does not count, nor the reverse.
        gh = FakeGitHub(['Firefox 157.0.1 released: rebase Android and desktop'])
        (_, _), (a, _) = self.both('157.0', '157.0.1', gh)
        self.assertEqual(a, 'opened')

    def test_beta_value_is_ignored(self):
        gh = FakeGitHub()
        mv = dict(mobile_fixture('157.0'), beta_version='999.0b1',
                  alpha_version='999.0a1', nightly_version='999.0a1',
                  ios_version='999.0', ios_beta_version='999.0b1')
        (_, _), (a, _) = self.both('157.0', mv, gh)
        self.assertEqual(a, 'current')
        self.assertEqual(self.asked, [])
        self.assertEqual(gh.created, [])

    def test_malformed_feed_is_refused(self):
        with self.assertRaises(ValueError):
            self.both('157.0', dict(mobile_fixture('157.0'), version='158.0b3'),
                      FakeGitHub())
        with self.assertRaises(watch.WatchError):
            self.both('157.0', {'beta_version': '158.0b3'}, FakeGitHub())

    def test_dry_run(self):
        (_, _), (a, af) = self.both('157.0', '157.0.1', None, dry_run=True)
        self.assertEqual(a, 'would-open')
        self.assertTrue(any('would open ' + repr(self.DOT) in l for l in self.log))
        self.assertNotIn('issue', af)


def clean_env(token=None):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('GITHUB_', 'RELEASE_WATCH_'))
           and k not in ('RUNNER_TEMP', 'GNUPGHOME')}
    if token:
        env['GITHUB_TOKEN'] = token
    return env


class FakeServer(http.server.BaseHTTPRequestHandler):
    """archive.mozilla.org (HEAD /releases/...) and the GitHub REST API."""
    state = None

    def log_message(self, *a):
        pass

    def reply(self, code, obj=None):
        raw = json.dumps(obj).encode() if obj is not None else b''
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(raw)

    def do_HEAD(self):
        self.state['heads'].append(self.path)
        if self.path.startswith('/broken/'):
            return self.reply(503)
        ok = self.path.split('/')[2] in self.state['tarballs']
        self.reply(200 if ok else 404)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        files = self.state.get('files', {})
        if url.path in files:  # archive.mozilla.org / keys.openpgp.org
            self.state['gets'].append(url.path)
            raw = files[url.path]
            self.send_response(200)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        # Public reads: no token needed (a dry run without one uses them).
        if url.path == '/repos/o/r/releases/latest':
            tag = self.state.get('release')
            return self.reply(200, {'tag_name': tag}) if tag else self.reply(404)
        if url.path == '/repos/o/r/releases':
            page = int(q['page'][0])
            items = [{'tag_name': r['tag'], 'name': r['tag'], 'draft': r.get('draft', False),
                      'prerelease': r.get('prerelease', False), 'body': r['body']}
                     for r in self.state.get('releases', [])]
            return self.reply(200, items[(page - 1) * 100:page * 100])
        prefix = '/repos/mozilla/foundation-security-advisories/contents/announce/'
        if url.path.startswith(prefix):
            year = url.path[len(prefix):]
            names = [n for n in self.state.get('mfsa', {}) if n.startswith(f'mfsa{year}-')]
            if not names:
                return self.reply(404)
            return self.reply(200, [{'name': n, 'type': 'file',
                                     'download_url': f'{self.state["base"]}/raw/{n}'}
                                    for n in sorted(names)])
        if url.path.startswith('/raw/'):
            raw = self.state['mfsa'][url.path[len('/raw/'):]].encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if self.headers.get('Authorization') != 'Bearer test-token':
            return self.reply(401, {'message': 'Bad credentials'})
        if url.path == '/repos/o/r/issues':
            assert q['state'] == ['all'] and q['labels'] == ['firefox-release'], q
            page = int(q['page'][0])
            meta = self.state.setdefault('meta', {})
            items = [{'title': t, 'number': n, 'state': 'open',
                      **meta.get(n, {})}
                     for n, t in enumerate(self.state['issues'], 1)]
            return self.reply(200, items[(page - 1) * 100:page * 100])
        if url.path.startswith('/repos/o/r/actions/workflows/') and url.path.endswith('/runs'):
            wf = url.path.split('/')[6]
            runs = self.state.get('runs', {}).get((wf, q['status'][0]), [])
            return self.reply(200, {'total_count': len(runs), 'workflow_runs': runs})
        if url.path.startswith('/repos/o/r/git/ref/heads/'):
            branch = url.path[len('/repos/o/r/git/ref/heads/'):]
            sha = self.state.get('refs', {}).get(branch)
            return self.reply(200, {'object': {'sha': sha}}) if sha else self.reply(404)
        if url.path.startswith('/repos/o/r/git/commits/'):
            return self.reply(200, {'sha': url.path.rsplit('/', 1)[1], 'tree': {'sha': 'tree0'}})
        if url.path.startswith('/repos/o/r/issues/') and url.path.endswith('/comments'):
            number = int(url.path.split('/')[5])
            page = int(q['page'][0])
            items = [{'body': b, 'created_at': '2026-10-09T12:00:00Z'}
                     for b in self.state['comments'].get(number, [])]
            return self.reply(200, items[(page - 1) * 100:page * 100])
        self.reply(404)

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path == '/repos/o/r/labels':
            if data['name'] in self.state['labels']:
                return self.reply(422, {'message': 'already_exists'})
            self.state['labels'].append(data['name'])
            return self.reply(201, data)
        if self.headers.get('Authorization') != 'Bearer test-token':
            return self.reply(401, {'message': 'Bad credentials'})
        if self.path.startswith('/repos/o/r/issues/') and self.path.endswith('/assignees'):
            number = int(self.path.split('/')[5])
            self.state.setdefault('assigned', {}).setdefault(number, []).extend(
                data['assignees'])
            return self.reply(201, {'number': number})
        if self.path.startswith('/repos/o/r/issues/') and self.path.endswith('/labels'):
            number = int(self.path.split('/')[5])
            self.state.setdefault('issue_labels', {}).setdefault(number, []).extend(
                data['labels'])
            return self.reply(200, [{'name': l} for l in data['labels']])
        if self.path.startswith('/repos/o/r/actions/workflows/') and self.path.endswith('/dispatches'):
            self.state.setdefault('dispatched', []).append((self.path.split('/')[6], data))
            return self.reply(204)
        if self.path == '/repos/o/r/git/trees':
            self.state.setdefault('trees', []).append(data)
            return self.reply(201, {'sha': 'tree1'})
        if self.path == '/repos/o/r/git/commits':
            self.state.setdefault('commits', []).append(data)
            return self.reply(201, {'sha': 'c' * 40})
        if self.path == '/repos/o/r/git/refs':
            self.state.setdefault('refs', {})[data['ref'][len('refs/heads/'):]] = data['sha']
            return self.reply(201, {'ref': data['ref']})
        if self.path == '/graphql':
            self.state.setdefault('pinned', []).append(data['variables']['id'])
            return self.reply(200, {'data': {'pinIssue': {'issue': {'number': 1}}}})
        if self.path == '/repos/o/r/issues':
            self.state['issues'].append(data['title'])
            self.state['bodies'].append(data)
            n = len(self.state['issues'])
            return self.reply(201, {'html_url': f'http://x/{n}', 'number': n})
        if self.path.startswith('/repos/o/r/issues/') and self.path.endswith('/comments'):
            if self.headers.get('Authorization') != 'Bearer test-token':
                return self.reply(401, {'message': 'Bad credentials'})
            number = int(self.path.split('/')[5])
            posted = self.state['comments'].setdefault(number, [])
            posted.append(data['body'])
            return self.reply(201, {'html_url': f'http://x/{number}#c{len(posted)}'})
        self.reply(404)


    def do_PATCH(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.headers.get('Authorization') != 'Bearer test-token':
            return self.reply(401, {'message': 'Bad credentials'})
        number = int(self.path.split('/')[5])
        self.state.setdefault('edits', []).append((number, data))
        if 'title' in data:
            self.state['issues'][number - 1] = data['title']
        return self.reply(200, {'number': number})


class EndToEnd(unittest.TestCase):
    def setUp(self):
        FakeServer.state = {'heads': [], 'gets': [], 'tarballs': set(), 'labels': [],
                            'files': {}, 'comments': {},
                            # 150 unrelated issues forces a second page
                            'issues': [f'Firefox 1.{i} released: rebase Android and desktop'
                                       for i in range(150)],
                            'bodies': []}
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), FakeServer)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f'http://127.0.0.1:{self.server.server_address[1]}'
        FakeServer.state['base'] = self.base
        tmp = tempfile.TemporaryDirectory(prefix='redoubt-release-watch-e2e-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'version.android').write_text('157.0\n')
        (self.root / 'version').write_text('157.0')

    def script(self, version, *extra, token='test-token', output=None, mobile='157.0',
               env_extra=None):
        env = clean_env(token)
        env.update(env_extra or {})
        if output:
            env['GITHUB_OUTPUT'] = str(output)
        # Never the network: without a mobile fixture the URL is a dead port.
        feed = (['--mobile-versions-file', str(FIXTURES / f'mobile-versions-{mobile}.json')]
                if mobile else
                ['--mobile-product-details-url', 'http://127.0.0.1:9/mobile_versions.json'])
        return subprocess.run(
            [sys.executable, str(SCRIPT), '--root', str(self.root),
             '--versions-file', str(FIXTURES / f'product-details-{version}.json'),
             *feed,
             '--archive-base', f'{self.base}/releases', '--api', self.base,
             '--repo', 'o/r', *extra],
            env=env, capture_output=True, text=True, timeout=60)

    def outputs(self, path):
        out = dict(l.split('=', 1) for l in path.read_text().splitlines())
        out['checks'] = json.loads(out['checks'])
        out['autobuild'] = json.loads(out['autobuild'])
        path.unlink()
        return out

    def test_job_outputs(self):
        out = self.root / 'github-output'
        FakeServer.state['tarballs'].add('158.0')
        r = self.script('158.0', output=out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(out.read_text(),
                         'outcome=opened\nversion=158.0\nissue=151\npatchcheck=true\n'
                         'android_outcome=current\nandroid_version=\nandroid_issue=\n'
                         'checks=[{"version":"158.0","issue":"151",'
                         '"targets":"desktop,android","label":"release"}]\n'
                         'autobuild=[]\n')
        out.unlink()
        r = self.script('158.0', output=out)
        o = self.outputs(out)
        self.assertEqual((o['outcome'], o['issue'], o['patchcheck']),
                         ('duplicate', '151', 'true'))
        self.assertEqual(len(o['checks']), 1)
        r = self.script('157.0', output=out)
        self.assertEqual(out.read_text(),
                         'outcome=current\nversion=\nissue=\npatchcheck=false\n'
                         'android_outcome=current\nandroid_version=\nandroid_issue=\n'
                         'checks=[]\nautobuild=[]\n')

    def test_android_only_dot_release(self):
        out = self.root / 'github-output'
        r = self.script('157.0', output=out, mobile='157.0.1')
        self.assertEqual(r.returncode, 0, r.stderr)
        o = self.outputs(out)
        self.assertEqual((o['outcome'], o['android_outcome'], o['android_version'],
                          o['android_issue']), ('current', 'opened', '157.0.1', '151'))
        self.assertEqual(o['checks'], [], 'no tarball, no patch check')
        self.assertEqual(FakeServer.state['issues'][-1], RunAndroid.DOT)
        self.assertIn('has no `firefox-157.0.1.source.tar.xz`',
                      FakeServer.state['bodies'][-1]['body'])
        # The tarball appears: same issue, now checked.
        FakeServer.state['tarballs'].add('157.0.1')
        r = self.script('157.0', output=out, mobile='157.0.1')
        self.assertEqual(r.returncode, 0, r.stderr)
        o = self.outputs(out)
        self.assertEqual(o['android_outcome'], 'duplicate')
        self.assertEqual(o['checks'], [{'version': '157.0.1', 'issue': '151',
                                        'targets': 'android', 'label': 'android'}])
        self.assertEqual(FakeServer.state['issues'].count(RunAndroid.DOT), 1)

    def test_same_version_both_feeds_one_issue(self):
        FakeServer.state['tarballs'].add('158.0')
        r = self.script('158.0', mobile='158.0')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('android outcome: same-as-desktop', r.stdout)
        self.assertEqual(FakeServer.state['issues'][150:],
                         ['Firefox 158.0 released: rebase Android and desktop'])

    def test_mobile_feed_down_is_green_without_spam(self):
        out = self.root / 'github-output'
        summary = self.root / 'summary.md'
        FakeServer.state['tarballs'].add('158.0')
        for _ in range(3):
            r = self.script('158.0', output=out, mobile=None,
                            env_extra={'GITHUB_STEP_SUMMARY': str(summary)})
            # A dead feed is an outage, not a bug: a warning, not a red run.
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('warning: mobile_versions.json failed (transient', r.stderr)
            self.assertIn('[!WARNING]', summary.read_text())
            o = self.outputs(out)
            # The desktop half did its job and its check still runs.
            self.assertIn(o['outcome'], ('opened', 'duplicate'))
            self.assertEqual(o['android_outcome'], 'error')
            self.assertEqual([c['label'] for c in o['checks']], ['release'])
        # One issue over three runs, and none about the failure.
        self.assertEqual(FakeServer.state['issues'][150:],
                         ['Firefox 158.0 released: rebase Android and desktop'])

    def test_desktop_feed_down_skips_android(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPT), '--root', str(self.root),
             '--product-details-url', 'http://127.0.0.1:9/firefox_versions.json',
             '--mobile-versions-file', str(FIXTURES / 'mobile-versions-157.0.1.json'),
             '--archive-base', f'{self.base}/releases', '--api', self.base,
             '--repo', 'o/r'], env=clean_env('test-token'),
            capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)  # transient: a warning
        self.assertIn('warning: firefox_versions.json failed (transient', r.stderr)
        self.assertIn('Firefox for Android: skipped', r.stderr)
        self.assertEqual(FakeServer.state['heads'], [])
        self.assertEqual(len(FakeServer.state['issues']), 150)

    def test_lifecycle(self):
        r = self.script('158.0')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('outcome: no-tarball', r.stdout)
        self.assertEqual(FakeServer.state['heads'],
                         ['/releases/158.0/source/firefox-158.0.source.tar.xz'])

        FakeServer.state['tarballs'].add('158.0')
        r = self.script('158.0')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('outcome: opened', r.stdout)
        self.assertEqual(FakeServer.state['labels'], ['firefox-release'])
        self.assertEqual(FakeServer.state['bodies'][-1]['labels'], ['firefox-release'])
        self.assertIn('blob/main/docs/android/REBASE.md',
                      FakeServer.state['bodies'][-1]['body'])

        r = self.script('158.0')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('outcome: duplicate', r.stdout)
        self.assertEqual(FakeServer.state['issues'].count(
            'Firefox 158.0 released: rebase Android and desktop'), 1)

    def mfsa(self, *names):
        FakeServer.state['mfsa'] = {f'{n}.yml': (MFSA / f'{n}.yml').read_text()
                                    for n in names}

    def test_advisory_upgrades_the_issue_and_queues_a_build(self):
        out = self.root / 'github-output'
        self.mfsa('mfsa2026-97', 'mfsa2026-100', 'mfsa2026-104')
        FakeServer.state['release'] = 'android-157.0-3'
        FakeServer.state['tarballs'].add('157.0.1')
        r = self.script('157.0.1', '--notify', 'owner', output=out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('advisories: mfsa2026-104 (upgraded)', r.stdout)
        n = 151  # the release issue just opened
        self.assertEqual(FakeServer.state['bodies'][-1]['assignees'], ['owner'])
        self.assertTrue(FakeServer.state['bodies'][-1]['body'].startswith('@owner: '))
        self.assertIn(watch.advisory_marker('mfsa2026-104'), FakeServer.state['comments'][n][0])
        self.assertEqual(FakeServer.state['issue_labels'][n], ['security'])
        self.assertEqual(FakeServer.state['issues'][n - 1],
                         '[security: moderate] Firefox 157.0.1 released: rebase Android and desktop')
        o = self.outputs(out)
        self.assertEqual(o['autobuild'], [{'version': '157.0.1', 'issue': str(n),
                                           'targets': 'desktop,android', 'label': 'release'}])
        # Next run: same issue (renamed), no second advisory comment.
        r = self.script('157.0.1', '--notify', 'owner', output=out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('outcome: duplicate', r.stdout)
        self.assertEqual(len(FakeServer.state['comments'][n]), 1)
        self.assertEqual(len(FakeServer.state['issues']), n)

    def test_dry_run_without_token_reads_advisories(self):
        self.mfsa('mfsa2026-104')
        FakeServer.state['release'] = 'android-157.0-3'
        FakeServer.state['tarballs'].add('157.0.1')
        r = self.script('157.0.1', '--dry-run', token='')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("would open '[security: moderate] Mozilla security advisory "
                      "MFSA 2026-104 (fixed in Firefox 157.0.1)'", r.stdout)
        self.assertEqual(len(FakeServer.state['issues']), 150)

    def test_advisory_feed_down_is_red_but_the_release_still_flags(self):
        FakeServer.state['tarballs'].add('158.0')
        r = self.script('158.0', '--api', self.base + '/broken-api')
        self.assertEqual(r.returncode, 1)
        r = self.script('158.0')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('outcome: opened', r.stdout)

    def test_notify_test(self):
        r = self.script('157.0', '--notify-test', '--notify', 'owner')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(FakeServer.state['issues'][-1].startswith(
            'Release watch notification test ('))
        self.assertEqual(FakeServer.state['bodies'][-1]['assignees'], ['owner'])
        self.assertEqual(FakeServer.state['edits'][-1][1],
                         {'state': 'closed', 'state_reason': 'not_planned'})

    def autobuild(self, *extra, token='test-token'):
        return subprocess.run(
            [sys.executable, str(SCRIPT), 'autobuild', '--version', '157.0.1', '--issue', '3',
             '--base-sha', SHA, '--api', self.base, '--repo', 'o/r', '--notify', 'owner',
             '--now', '20261009123456', *extra],
            env=clean_env(token), capture_output=True, text=True, timeout=60)

    def test_autobuild_cli(self):
        # The real situation of 2026-10-09: 157.0-3 is Latest, 158.0-1 Beta 1
        # is out. build_date=now would put 157.0.1 above the beta.
        FakeServer.state['release'] = 'android-157.0-3'
        FakeServer.state['releases'] = [
            {'tag': 'android-158.0-1-beta.1', 'prerelease': True,
             'body': BETA1_NOTES},
            {'tag': 'android-157.0-3', 'body': STABLE_157_3_NOTES}]
        FakeServer.state['comments'][3] = [
            f'<!-- redoubt-patchcheck-result version=157.0.1 sha={SHA} desktop=pass '
            f'android=pass -->']
        r = self.autobuild('--dry-run')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('outcome: would-dispatch', r.stdout)
        self.assertNotIn('dispatched', FakeServer.state)
        FakeServer.state['runs'] = {('android-release.yaml', 'queued'): [
            {'id': 9, 'html_url': 'x', 'head_branch': 'main', 'status': 'queued'}]}
        r = self.autobuild()
        self.assertIn('outcome: busy', r.stdout)
        FakeServer.state['runs'] = {}
        r = self.autobuild()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('outcome: dispatched', r.stdout)
        self.assertEqual(FakeServer.state['refs'], {'auto/firefox-157.0.1': 'c' * 40})
        tree = FakeServer.state['trees'][0]
        self.assertEqual(tree['base_tree'], 'tree0')
        self.assertEqual({e['path']: e['content'] for e in tree['tree']},
                         {'release': '1\n', 'release.android': '1\n',
                          'version': '157.0.1\n', 'version.android': '157.0.1\n'})
        self.assertEqual(FakeServer.state['commits'][0]['parents'], [SHA])
        self.assertEqual(FakeServer.state['dispatched'], [(
            'android-release.yaml', {'ref': 'auto/firefox-157.0.1', 'inputs': {
                'mode': 'full', 'update_check': 'true', 'build_date': '20261006190000'}})])
        self.assertIn('versionCodes 2016188824-2016188831', FakeServer.state['comments'][3][-1])
        r = self.autobuild()
        self.assertIn('outcome: already-dispatched', r.stdout)
        self.assertEqual(len(FakeServer.state['dispatched']), 1)
        r = self.autobuild(token='')
        self.assertEqual(r.returncode, 1)
        # GitHub unreachable: a warning, green; the next hourly run retries.
        r = self.autobuild('--api', 'http://127.0.0.1:9')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('warning: autobuild 157.0.1:', r.stderr)
        # A wrong token is not an outage.
        r = self.autobuild(token='wrong')
        self.assertEqual(r.returncode, 1)

    def test_current_needs_no_network_beyond_fixture(self):
        r = self.script('157.0')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('outcome: current', r.stdout)
        self.assertEqual(FakeServer.state['heads'], [])

    def test_api_failure_is_red(self):
        FakeServer.state['tarballs'].add('158.0')
        r = self.script('158.0', token='wrong')
        self.assertEqual(r.returncode, 1)
        self.assertIn('HTTP 401', r.stderr)

    def test_no_token_refuses_unless_dry_run(self):
        FakeServer.state['tarballs'].add('158.0')
        r = self.script('158.0', token='')
        self.assertEqual(r.returncode, 1)
        self.assertIn('GITHUB_TOKEN', r.stderr)
        r = self.script('158.0', '--dry-run', token='')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('outcome: would-open', r.stdout)

    def test_archive_error_is_not_missing(self):
        # A 5xx or a dead connection must not read as "no tarball yet" -- that
        # would hide a release for as long as it lasted. It is an outage: a
        # warning now, red once it outlasts OUTAGE_HOURS.
        state = self.root / 'state.json'
        for archive, text in ((f'{self.base}/broken', 'HTTP 503'),
                              ('http://127.0.0.1:9/releases', 'HEAD')):
            r = self.script('158.0', '--archive-base', archive, '--state-file', str(state),
                            '--now', '20261009120000')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(text, r.stderr)
            self.assertIn('outcome: error', r.stdout)
            self.assertNotIn('no-tarball', r.stdout)
        r = self.script('158.0', '--archive-base', f'{self.base}/broken',
                        '--state-file', str(state), '--now', '20261009190000')
        self.assertEqual(r.returncode, 1)
        self.assertIn('Firefox release has been failing since 2026-10-09T12:00:00Z', r.stderr)

    def test_outage_turns_red_after_six_hours_and_clears(self):
        state = self.root / 'state.json'
        FakeServer.state['tarballs'].add('158.0')

        def run(now, mobile=None):
            return self.script('158.0', '--state-file', str(state), '--now', now,
                               mobile=mobile)
        for now in ('20261009000000', '20261009030000', '20261009060000'):
            r = run(now)
            self.assertEqual(r.returncode, 0, (now, r.stderr))
        self.assertEqual(json.loads(state.read_text()),
                         {'failing_since': {'mobile_versions.json': '2026-10-09T00:00:00Z'}})
        r = run('20261009060100')  # just over six hours in a row
        self.assertEqual(r.returncode, 1)
        self.assertIn('mobile_versions.json has been failing since 2026-10-09T00:00:00Z',
                      r.stderr)
        r = run('20261009070000', mobile='157.0')  # it answers: the streak ends
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(state.read_text()), {'failing_since': {}})
        r = run('20261009080000')  # a new streak starts from zero
        self.assertEqual(r.returncode, 0, r.stderr)
        # Unreadable state: start over, never red by mistake.
        state.write_text('{not json')
        self.assertEqual(run('20261010080000').returncode, 0)
        # One issue throughout, none about the outage.
        self.assertEqual(FakeServer.state['issues'][150:],
                         ['Firefox 158.0 released: rebase Android and desktop'])

    def test_logic_errors_stay_red(self):
        state = self.root / 'state.json'
        (self.root / 'version.android').write_text('158.0b3\n')
        r = self.script('158.0', '--state-file', str(state))
        self.assertEqual(r.returncode, 1)
        self.assertIn('not a Firefox release or ESR version', r.stderr)
        (self.root / 'version.android').write_text('157.0\n')
        bad = self.root / 'feed.json'
        bad.write_text(json.dumps({'FIREFOX_ESR': '153.4.0esr'}))
        r = subprocess.run(
            [sys.executable, str(SCRIPT), '--root', str(self.root), '--versions-file',
             str(bad), '--mobile-versions-file', str(FIXTURES / 'mobile-versions-157.0.json'),
             '--archive-base', f'{self.base}/releases', '--api', self.base,
             '--repo', 'o/r', '--no-advisories'], env=clean_env('test-token'),
            capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1)
        self.assertIn('no LATEST_FIREFOX_VERSION', r.stderr)

    # A manual patch check (workflow_dispatch patchcheck_version): only in a
    # dry run, whatever the feeds say, and never a beta.

    def test_manual_patchcheck_emitted_in_dry_run(self):
        out = self.root / 'github-output'
        r = self.script('157.0', '--dry-run', '--patchcheck-version', '157.0',
                        token='', output=out)
        self.assertEqual(r.returncode, 0, r.stderr)
        o = self.outputs(out)
        # The repo is at 157.0: the watch itself has nothing to do ...
        self.assertEqual((o['outcome'], o['android_outcome']), ('current', 'current'))
        # ... and the manual check is queued anyway, with no issue.
        self.assertEqual(o['checks'], [{'version': '157.0', 'issue': '',
                                        'targets': 'desktop,android',
                                        'label': 'manual'}])
        r = self.script('157.0', '--dry-run', '--patchcheck-version', '157.0',
                        '--patchcheck-targets', 'android', token='', output=out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outputs(out)['checks'],
                         [{'version': '157.0', 'issue': '', 'targets': 'android',
                           'label': 'manual'}])
        self.assertEqual(len(FakeServer.state['issues']), 150)

    def test_manual_patchcheck_next_to_a_real_release(self):
        out = self.root / 'github-output'
        FakeServer.state['tarballs'].add('158.0')
        # Same release and targets as the real entry: not checked twice.
        r = self.script('158.0', '--dry-run', '--patchcheck-version', '158.0',
                        output=out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([c['label'] for c in self.outputs(out)['checks']], ['release'])
        # An older one: both, the real one first.
        r = self.script('158.0', '--dry-run', '--patchcheck-version', '157.0',
                        output=out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([(c['version'], c['label']) for c in self.outputs(out)['checks']],
                         [('158.0', 'release'), ('157.0', 'manual')])
        self.assertEqual(len(FakeServer.state['issues']), 150, 'a dry run opens nothing')

    def test_manual_patchcheck_refused_without_dry_run(self):
        out = self.root / 'github-output'
        FakeServer.state['tarballs'].add('158.0')
        r = self.script('158.0', '--patchcheck-version', '157.0', output=out)
        self.assertEqual(r.returncode, 1)
        self.assertIn('only runs as a dry run', r.stderr)
        # Refused before anything else: no outputs (so no patch-check job),
        # no archive or GitHub request, no issue.
        self.assertFalse(out.exists())
        self.assertEqual(FakeServer.state['heads'], [])
        self.assertEqual(len(FakeServer.state['issues']), 150)

    def test_manual_patchcheck_refuses_non_releases(self):
        out = self.root / 'github-output'
        for bad in ('158.0b3', '159.0a1', 'latest', '157'):
            r = self.script('157.0', '--dry-run', '--patchcheck-version', bad,
                            token='', output=out)
            self.assertEqual(r.returncode, 1, bad)
            self.assertIn('not a Firefox release or ESR version', r.stderr)
            self.assertFalse(out.exists())
        r = self.script('157.0', '--dry-run', '--patchcheck-version', '157.0',
                        '--patchcheck-targets', 'ios', token='', output=out)
        self.assertEqual(r.returncode, 1)
        self.assertIn('--patchcheck-targets must be among', r.stderr)

    def test_no_manual_patchcheck_without_the_flag(self):
        # The scheduled path: no flag, so nothing manual even in a dry run,
        # and an empty value (an unset dispatch input) is no flag.
        out = self.root / 'github-output'
        for extra in ((), ('--dry-run',), ('--dry-run', '--patchcheck-version', '')):
            r = self.script('157.0', *extra, output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self.outputs(out)['checks'], [], extra)
            self.assertNotIn('manual', r.stdout)


MFSA = FIXTURES / 'mfsa'


def advisory(name):
    return watch.parse_advisory((MFSA / f'{name}.yml').read_text(), name)


def derived_advisory(name, impact, fixed_in, cves=3):
    """A made-up advisory in the real files' shape (for impacts and versions
    no real file has yet)."""
    lines = [f'## {name}.yml', 'announced: October 13, 2026', f'impact: {impact}',
             'fixed_in:', f'- {fixed_in}', f'title: Security Vulnerabilities fixed in {fixed_in}',
             'advisories:']
    for k in range(cves):
        lines += [f'  CVE-2026-9{k:05d}:', f"    title: 'Bug {k}: use-after-free'",
                  f'    impact: {impact if k == 0 else "moderate"}', '    reporter: Mozilla',
                  '    bugs:', f'      - url: {k}']
    return watch.parse_advisory('\n'.join(lines) + '\n', name)


class AdvisoryParse(unittest.TestCase):
    def test_matches_pyyaml_on_real_files(self):
        try:
            import yaml
        except ImportError:
            self.skipTest('PyYAML not installed')
        norm = lambda v: ' '.join(str(v).split())
        for f in sorted(MFSA.glob('*.yml')):
            y = yaml.safe_load(f.read_text())
            got = watch.parse_advisory(f.read_text(), f.stem)
            self.assertEqual(got['fixed_in'], y['fixed_in'], f.name)
            self.assertEqual(got['impact'], y['impact'], f.name)
            self.assertEqual(got['title'], norm(y['title']), f.name)
            self.assertEqual(got['announced'], norm(y['announced']), f.name)
            self.assertEqual([(c['id'], c['impact'], c['title']) for c in got['cves']],
                             [(k, v.get('impact', ''), norm(v.get('title', '')))
                              for k, v in y['advisories'].items()], f.name)

    def test_fields(self):
        a = advisory('mfsa2026-104')
        self.assertEqual(a['fixed_in'], ['Firefox 157.0.1'])
        self.assertEqual(a['impact'], 'moderate')
        self.assertEqual([c['id'] for c in a['cves']], ['CVE-2026-106016'])
        self.assertEqual(a['cves'][0]['title'], 'Mitigation bypass in the File Handling component')
        self.assertEqual(advisory('mfsa2025-25')['fixed_in'], ['Firefox 137.0.2'])  # indented list
        block = [c for c in advisory('mfsa2025-28')['cves'] if c['id'] == 'CVE-2025-4083'][0]
        self.assertEqual(block['title'], 'Process isolation bypass using "javascript:" URI '
                                         'links in cross-origin frames')
        self.assertEqual(len(advisory('mfsa2026-97')['cves']), 76)

    def test_versions_and_impact(self):
        self.assertEqual(watch.advisory_versions(advisory('mfsa2026-97')), ['157.0'])
        self.assertEqual(watch.advisory_versions(advisory('mfsa2026-104')), ['157.0.1'])
        self.assertEqual(watch.advisory_versions(advisory('mfsa2024-45')), ['130.0.1'])
        self.assertEqual(watch.advisory_versions(advisory('mfsa2026-73')), ['153.0.3'])
        for other in ('mfsa2026-100', 'mfsa2026-101', 'mfsa2026-89'):  # ESR, Thunderbird, iOS
            self.assertEqual(watch.advisory_versions(advisory(other)), [], other)
        self.assertEqual(watch.advisory_impact(advisory('mfsa2026-97')), 'high')
        self.assertEqual(watch.advisory_impact(derived_advisory('mfsa2026-105', 'critical',
                                                                'Firefox 158')), 'critical')
        self.assertEqual(watch.mfsa_label('mfsa2026-104'), 'MFSA 2026-104')

    def test_shipped_release(self):
        self.assertEqual(watch.shipped_release('android-157.0-3', '157.0')[0], '157.0')
        self.assertEqual(watch.shipped_release('android-157.0.1-2', '157.0')[0], '157.0.1')
        self.assertEqual(watch.shipped_release('android-158.0-1-beta.1', '157.0')[0], '157.0')
        self.assertEqual(watch.shipped_release('', '157.0'),
                         ('157.0', '`version.android` 157.0 (no published release found)'))

    def test_title_matches(self):
        base = watch.issue_title('157.0.1')
        self.assertTrue(watch.title_matches(base, base))
        self.assertTrue(watch.title_matches('[security: high] ' + base, base))
        self.assertFalse(watch.title_matches('[security: high] ' + base + ' again', base))
        self.assertFalse(watch.title_matches('x ' + base, base))
        self.assertEqual(watch.security_title('[security: low] ' + base, 'high'),
                         '[security: high] ' + base)


class RunAdvisories(unittest.TestCase):
    DOT = 'Firefox 157.0.1 released: rebase Android and desktop'

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='redoubt-release-watch-mfsa-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'version.android').write_text('157.0\n')
        (self.root / 'version').write_text('157.0')
        self.log = []

    def go(self, gh, advisories, tag='android-157.0-3', dry_run=False):
        return watch.run_advisories(self.root, advisories, gh, 'o/r', tag, dry_run,
                                    log=self.log.append, notify='owner')

    def test_upgrades_the_open_release_issue_once(self):
        gh = FakeGitHub([self.DOT])
        advs = [advisory('mfsa2026-97'), advisory('mfsa2026-100'), advisory('mfsa2026-104')]
        self.assertEqual(self.go(gh, advs), [('mfsa2026-97', 'not-affected'),
                                             ('mfsa2026-100', 'not-affected'),
                                             ('mfsa2026-104', 'upgraded')])
        body = gh.posted[1][0]
        self.assertTrue(body.startswith(watch.advisory_marker('mfsa2026-104') + '\n@owner: '))
        self.assertIn('CVE-2026-106016', body)
        self.assertIn('Highest impact: **moderate**', body)
        self.assertIn('Redoubt 157.0-3', body)
        self.assertIn('https://www.mozilla.org/en-US/security/advisories/mfsa2026-104/', body)
        self.assertEqual(gh.item(1)['labels'], [watch.LABEL, 'security'])
        self.assertEqual(gh.item(1)['title'], '[security: moderate] ' + self.DOT)
        self.assertEqual(gh.assigned[1], ['owner'])
        self.assertEqual(gh.pinned, [], 'moderate is not pinned')
        self.assertEqual(self.go(gh, advs)[-1], ('mfsa2026-104', 'known'))
        self.assertEqual(len(gh.posted[1]), 1)
        # The release watcher still recognises its renamed issue.
        found = {}
        self.assertEqual(watch.run(self.root, fixture('157.0.1'), lambda u: True, gh, 'o/r',
                                   log=self.log.append, found=found), 'duplicate')
        self.assertEqual(found['issue'], 1)

    def test_critical_is_labelled_pinned_and_never_downgraded(self):
        gh = FakeGitHub(['Firefox 158.0 released: rebase Android and desktop'])
        crit = derived_advisory('mfsa2026-105', 'critical', 'Firefox 158')
        self.assertEqual(self.go(gh, [crit]), [('mfsa2026-105', 'upgraded')])
        self.assertIn('priority: critical', gh.item(1)['labels'])
        self.assertEqual(gh.pinned, ['I_1'])
        self.assertTrue(gh.item(1)['title'].startswith('[security: critical] '))
        low = derived_advisory('mfsa2026-106', 'low', 'Firefox 158')
        self.assertEqual(self.go(gh, [low]), [('mfsa2026-106', 'upgraded')])
        self.assertTrue(gh.item(1)['title'].startswith('[security: critical] '))

    def test_no_open_issue_opens_an_advisory_issue(self):
        gh = FakeGitHub([self.DOT, 'Firefox 158.0 released: rebase Android and desktop'],
                        closed=[self.DOT])
        self.assertEqual(self.go(gh, [advisory('mfsa2026-104')]),
                         [('mfsa2026-104', 'opened')])
        title, body, label = gh.created[0]
        self.assertEqual(title, '[security: moderate] Mozilla security advisory '
                                'MFSA 2026-104 (fixed in Firefox 157.0.1)')
        self.assertEqual(label, watch.LABEL)
        self.assertIn('@owner: ', body)
        self.assertIn('Open release issues of the watcher: #2', body)
        self.assertEqual(gh.assigned[3], ['owner'])
        self.assertIn('security', gh.item(3)['labels'])
        self.assertEqual(self.go(gh, [advisory('mfsa2026-104')]),
                         [('mfsa2026-104', 'known')])
        self.assertEqual(len(gh.created), 1)

    def test_shipped_at_or_past_is_quiet(self):
        gh = FakeGitHub([self.DOT])
        self.assertEqual(self.go(gh, [advisory('mfsa2026-104')], tag='android-157.0.1-1'),
                         [('mfsa2026-104', 'not-affected')])
        self.assertEqual((gh.posted, gh.created), ({}, []))

    def test_no_release_falls_back_to_version_android(self):
        gh = FakeGitHub([self.DOT])
        self.assertEqual(self.go(gh, [advisory('mfsa2026-104')], tag=''),
                         [('mfsa2026-104', 'upgraded')])
        self.assertIn('`version.android` 157.0 (no published release found)', gh.posted[1][0])

    def test_dry_run_writes_nothing(self):
        gh = FakeGitHub([self.DOT])
        self.assertEqual(self.go(gh, [advisory('mfsa2026-104')], dry_run=True),
                         [('mfsa2026-104', 'would-upgrade')])
        self.assertEqual((gh.posted, gh.edits, gh.assigned), ({}, [], {}))
        self.assertEqual(self.go(None, [advisory('mfsa2026-104')], dry_run=True),
                         [('mfsa2026-104', 'would-open')])


class Reminders(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='redoubt-release-watch-remind-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'version.android').write_text('157.0\n')
        self.gh = FakeGitHub(['[security: moderate] ' + RunAdvisories.DOT,
                              'Firefox 158.0 released: rebase Android and desktop'])
        self.gh.item(1)['labels'].append('security')

    def at(self, stamp, tag='android-157.0-3'):
        now = watch._parse_time(stamp)
        self.gh.now = stamp
        return watch.run_reminders(self.root, self.gh, tag, now, notify='owner',
                                   log=lambda *a: None)

    def test_once_a_day_while_behind(self):
        self.assertEqual(self.at('2026-10-06T20:00:00Z'), [], 'younger than a day')
        self.assertEqual(self.at('2026-10-09T12:00:00Z'), [1])
        self.assertIn('@owner: reminder: open for 2 day(s)', self.gh.posted[1][0])
        self.assertEqual(self.at('2026-10-09T13:00:00Z'), [])
        self.assertEqual(self.at('2026-10-10T12:00:01Z'), [1])
        self.assertEqual(len(self.gh.posted[1]), 2)
        self.assertNotIn(2, self.gh.posted, 'not a security issue')

    def test_an_advisory_comment_counts_as_a_ping(self):
        self.gh.now = '2026-10-09T11:00:00Z'
        self.gh.create_comment(1, watch.advisory_marker('mfsa2026-104') + '\n@owner: x')
        self.assertEqual(self.at('2026-10-09T12:00:00Z'), [])
        self.assertEqual(self.at('2026-10-10T11:00:00Z'), [1])

    def test_quiet_once_shipped(self):
        self.assertEqual(self.at('2026-10-09T12:00:00Z', tag='android-157.0.1-1'), [])


class Notify(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='redoubt-release-watch-notify-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'version.android').write_text('157.0\n')
        (self.root / 'version').write_text('157.0')

    def go(self, gh, found=None, dry_run=False):
        return watch.run(self.root, fixture('157.0.1'), lambda u: True, gh, 'o/r', dry_run,
                         log=lambda *a: None, found=found, notify='owner')

    def test_new_issue_is_assigned_and_mentions(self):
        gh = FakeGitHub()
        found = {}
        self.assertEqual(self.go(gh, found), 'opened')
        self.assertEqual(gh.assigned[1], ['owner'])
        self.assertTrue(gh.created[0][1].startswith('@owner: Mozilla released Firefox 157.0.1'))
        self.assertEqual(found['url'], 'https://github.invalid/issues/1')

    def test_open_unassigned_issue_gets_assigned_once(self):
        gh = FakeGitHub([RunAdvisories.DOT])
        self.assertEqual(self.go(gh), 'duplicate')
        self.assertEqual(gh.assigned, {1: ['owner']})
        self.go(gh)
        self.assertEqual(gh.assigned, {1: ['owner']})

    def test_closed_issue_is_left_alone(self):
        gh = FakeGitHub([RunAdvisories.DOT], closed=[RunAdvisories.DOT])
        self.assertEqual(self.go(gh), 'duplicate')
        self.assertEqual(gh.assigned, {})

    def test_default_notify(self):
        self.assertEqual(watch.default_notify({'GITHUB_REPOSITORY_OWNER': 'CPlusPlus17'}),
                         'CPlusPlus17')
        self.assertEqual(watch.default_notify({'GITHUB_REPOSITORY_OWNER': 'a',
                                               'RELEASE_WATCH_NOTIFY': 'b'}), 'b')
        self.assertEqual(watch.default_notify({}), '')

    def test_notify_test_opens_and_closes(self):
        gh = FakeGitHub()
        now = watch._parse_time('2026-10-09T12:00:00Z')
        watch.notify_test(gh, 'owner', now, log=lambda *a: None)
        self.assertEqual(gh.created[0][2], watch.TEST_LABEL)
        self.assertEqual(gh.assigned[1], ['owner'])
        self.assertEqual(gh.edits, [(1, {'state': 'closed', 'state_reason': 'not_planned'})])


class Ntfy(unittest.TestCase):
    def test_off_without_the_secret(self):
        self.assertEqual(watch.send_events([{'title': 't', 'message': 'm'}], env={}), 0)

    def test_posts_when_configured(self):
        got = []

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                got.append((self.path, dict(self.headers),
                            self.rfile.read(int(self.headers['Content-Length'])).decode()))
                self.send_response(200)
                self.send_header('Content-Length', '0')
                self.end_headers()

        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        url = f'http://127.0.0.1:{srv.server_address[1]}/redoubt-abc'
        n = watch.send_events([{'title': 'MFSA 2026-105 (critical)', 'message': 'behind',
                                'click': 'https://x/1', 'impact': 'critical'}],
                              env={'RELEASE_WATCH_NTFY_URL': url,
                                   'RELEASE_WATCH_NTFY_TOKEN': 'tk'}, log=lambda *a: None)
        self.assertEqual(n, 1)
        path, headers, body = got[0]
        self.assertEqual((path, body), ('/redoubt-abc', 'behind'))
        self.assertEqual(headers['Priority'], 'urgent')
        self.assertEqual(headers['Click'], 'https://x/1')
        self.assertEqual(headers['Authorization'], 'Bearer tk')

    def test_failure_is_not_fatal(self):
        self.assertEqual(watch.send_events(
            [{'title': 't', 'message': 'm'}],
            env={'RELEASE_WATCH_NTFY_URL': 'http://127.0.0.1:9/x'}, log=lambda *a: None), 0)


# Release notes as published (Provenance sections, trimmed).
STABLE_157_3_NOTES = ('## Provenance\n\n- **Source:** tag android-157.0-3.\n'
                      '- **Build:** CI run 37441476096, with MOZ_BUILD_DATE 20261006090000.\n')
BETA1_NOTES = ('## Provenance\n\n- **Build:** CI run 37576802707, with MOZ_BUILD_DATE '
               '20261007050000; versionCodes 2016188904-2016188911.\n')


def rel(tag, date=None, prerelease=False, draft=False, body=None):
    if body is None:
        body = f'## Provenance\n\n- **Build:** with MOZ_BUILD_DATE {date}.\n' if date else ''
    return {'tag': tag, 'name': tag, 'prerelease': prerelease, 'draft': draft, 'body': body}


class BuildDate(unittest.TestCase):
    """The versionCode window (docs: "Build date and versionCode")."""
    NOW = watch._parse_time('2026-10-09T12:34:56Z')
    LATEST = rel('android-157.0-3', body=STABLE_157_3_NOTES)
    BETA1 = rel('android-158.0-1-beta.1', prerelease=True, body=BETA1_NOTES)

    def choose(self, releases, latest='android-157.0-3', version='157.0.1', now=None):
        return watch.choose_build_date(version, releases, latest, now or self.NOW)

    def test_codes_match_android_aab(self):
        spec = importlib.util.spec_from_file_location('android_aab',
                                                      ROOT / 'scripts' / 'android-aab.py')
        aab = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(aab)
        for date in ('20261006090000', '20261006180000', '20261007050000',
                     '20261009160000', '20261009123456'):
            h = watch.build_hour(date)
            self.assertEqual(watch.version_codes(h),
                             {abi: aab.version_code(date, abi) for abi in watch.ABI_BITS})
            self.assertEqual(watch.code_hour(aab.version_code(date, 'universal')), h)
        # The precedent's numbers (release-157.0.1/README.md).
        self.assertEqual(watch._codes_text(watch.build_hour('20261006090000')),
                         '2016188744-2016188751')
        self.assertEqual(watch._codes_text(watch.build_hour('20261007050000')),
                         '2016188904-2016188911')
        self.assertEqual(watch.hour_date(watch.build_hour('20261009123456')),
                         '20261009120000')

    def test_hour_from_notes(self):
        h = watch.release_build_hour
        self.assertEqual(h(STABLE_157_3_NOTES), watch.build_hour('20261006090000'))
        self.assertEqual(h(BETA1_NOTES), watch.build_hour('20261007050000'))
        self.assertEqual(h('MOZ_BUILD_DATE=`20261005000000`'), watch.build_hour('20261005000000'))
        # versionCodes alone are enough ...
        self.assertEqual(h('versionCodes 2016188904-2016188911'),
                         watch.build_hour('20261007050000'))
        # ... but a date and codes that disagree, two dates, or nothing: unreadable.
        self.assertIsNone(h('MOZ_BUILD_DATE 20261007050000; versionCodes 2016188744-751'))
        self.assertIsNone(h('MOZ_BUILD_DATE 20261007050000 and MOZ_BUILD_DATE 20261006090000'))
        self.assertIsNone(h('Beta 5. Signed on Fedora.'))
        self.assertIsNone(h('MOZ_BUILD_DATE 20261399000000'))

    def test_tag_versions(self):
        v = watch.release_tag_version
        self.assertEqual(v('android-158.0-1-beta.1'), '158.0')
        self.assertEqual(v('android-157.0.1-1'), '157.0.1')
        self.assertEqual(v('android-153.4.0esr-1-beta.3'), '153.4.0esr')
        self.assertIsNone(v('v1.0'))

    def test_precedent_window(self):
        # 2026-10-09: 157.0-3 Latest (…09h), Beta 1 out (07 05h). Middle of
        # the 20-hour window: 20261006190000 (the hand-picked 157.0.1-1 used 18h).
        date, why = self.choose([self.BETA1, self.LATEST])
        self.assertEqual(date, '20261006190000')
        self.assertTrue(watch.build_hour('20261006090000') < watch.build_hour(date)
                        < watch.build_hour('20261007050000'))
        self.assertIn('`android-157.0-3` (Latest), built 20261006090000', why)
        self.assertIn('below `android-158.0-1-beta.1` (prerelease of Firefox 158.0), built '
                      '20261007050000, versionCodes 2016188904-2016188911', why)

    def test_next_dot_after_157_0_1(self):
        # 157.0.1-1 (…18h) is Latest now; 157.0.2 lands between it and Beta 1,
        # and below Beta 2 too (the OLDEST newer-major build is the bound).
        latest = rel('android-157.0.1-1', '20261006180000')
        beta2 = rel('android-158.0-1-beta.2', '20261009160000', prerelease=True)
        date, _ = self.choose([beta2, self.BETA1, latest, self.LATEST],
                              latest='android-157.0.1-1', version='157.0.2')
        self.assertEqual(date, '20261006230000')

    def test_no_newer_major_uses_this_hour(self):
        date, why = self.choose([self.LATEST])
        self.assertEqual(date, '20261009120000')
        self.assertIn("this run's hour", why)
        # A superseded beta of the SAME major is no bound.
        b5 = rel('android-157.0-1-beta.5', '20261004090000', prerelease=True)
        self.assertEqual(self.choose([b5, self.LATEST])[0], '20261009120000')
        # Nor is a draft of a newer major (not published).
        draft = rel('android-158.0-1-beta.9', '20261007000000', prerelease=True, draft=True)
        self.assertEqual(self.choose([draft, self.LATEST])[0], '20261009120000')

    def test_never_in_the_future(self):
        # The beta is far ahead; this run is just after the Latest build.
        beta = rel('android-158.0-1-beta.1', '20261020000000', prerelease=True)
        now = watch._parse_time('2026-10-06T12:10:00Z')
        date, _ = self.choose([beta, self.LATEST], now=now)
        # Window (09h, 13h exclusive) -> middle 11h, not some day in between.
        self.assertEqual(date, '20261006110000')

    def test_used_hours_are_skipped(self):
        taken = rel('android-157.0-2', '20261006190000')
        date, _ = self.choose([self.BETA1, self.LATEST, taken])
        self.assertEqual(date, '20261006180000')

    def test_no_fit(self):
        latest = rel('android-157.0-4', '20261007040000')
        date, why = self.choose([self.BETA1, latest], latest='android-157.0-4')
        self.assertIsNone(date)
        self.assertIn('no unused hour lies strictly between', why)
        # One free hour exactly between: it fits.
        latest = rel('android-157.0-4', '20261007030000')
        self.assertEqual(self.choose([self.BETA1, latest], latest='android-157.0-4')[0],
                         '20261007040000')
        # Latest built after the beta: nothing fits.
        latest = rel('android-157.0-4', '20261008000000')
        self.assertIsNone(self.choose([self.BETA1, latest], latest='android-157.0-4')[0])
        # No newer major, but this run's hour is not after Latest's.
        latest = rel('android-157.0-4', '20261009120000')
        self.assertIsNone(self.choose([latest], latest='android-157.0-4')[0])

    def test_unreadable_bounds(self):
        latest = rel('android-157.0-3', body='Signed on Fedora.')
        date, why = self.choose([self.BETA1, latest])
        self.assertIsNone(date)
        self.assertIn('Latest release `android-157.0-3` cannot be read', why)
        beta = rel('android-158.0-1-beta.1', prerelease=True, body='no provenance')
        date, why = self.choose([beta, self.LATEST])
        self.assertIsNone(date)
        self.assertIn('`android-158.0-1-beta.1` is a published release of Firefox 158.0', why)
        # An unreadable release that is no bound does not matter.
        old = rel('android-157.0-1-beta.5', prerelease=True, body='no provenance')
        self.assertEqual(self.choose([self.BETA1, old, self.LATEST])[0], '20261006190000')

    def test_no_latest_release(self):
        self.assertEqual(self.choose([], latest='')[0], '20261009120000')
        self.assertEqual(self.choose([self.BETA1], latest='')[0], '20261007040000')


class Outages(unittest.TestCase):
    T0 = watch._parse_time('2026-10-09T00:00:00Z')

    def test_streaks(self):
        h = lambda n: self.T0 + watch.datetime.timedelta(hours=n)
        s = watch.update_outages({}, set(), {'a': 'x'}, self.T0)
        self.assertEqual(s, {'a': '2026-10-09T00:00:00Z'})
        s = watch.update_outages(s, {'b'}, {'a': 'x'}, h(3))
        self.assertEqual(s, {'a': '2026-10-09T00:00:00Z'}, 'the start is kept')
        self.assertEqual(watch.long_outages(s, {'a': 'x'}, h(6)), [])
        self.assertEqual(watch.long_outages(s, {'a': 'x'}, h(6.1)),
                         [('a', '2026-10-09T00:00:00Z')])
        # Only a source failing NOW counts: one that did not run is not red.
        self.assertEqual(watch.long_outages(s, {}, h(9)), [])
        self.assertEqual(watch.update_outages(s, {'a'}, {}, h(9)), {})

    def test_load(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 's.json'
            self.assertEqual(watch.load_outages(f), {})
            self.assertEqual(watch.load_outages(None), {})
            f.write_text('[]')
            self.assertEqual(watch.load_outages(f), {})
            f.write_text(json.dumps({'failing_since': {'a': 'yesterday',
                                                       'b': '2026-10-09T00:00:00Z'}}))
            self.assertEqual(watch.load_outages(f), {'b': '2026-10-09T00:00:00Z'})
            watch.save_outages(f, {'c': '2026-10-09T01:00:00Z'})
            self.assertEqual(watch.load_outages(f), {'c': '2026-10-09T01:00:00Z'})

    def test_classification(self):
        for status in (0, 408, 429, 500, 502, 503, 504, 520):
            self.assertIsInstance(watch.http_error('x', status), watch.TransientError, status)
        for status in (200, 401, 403, 404, 422):
            e = watch.http_error('x', status)
            self.assertIsInstance(e, watch.WatchError, status)
            self.assertNotIsInstance(e, watch.TransientError, status)


class Autobuild(unittest.TestCase):
    NOW = watch._parse_time('2026-10-09T12:34:56Z')

    def setUp(self):
        self.gh = FakeGitHub([RunAdvisories.DOT])
        self.gh.release = 'android-157.0-3'
        self.gh.rels = [BuildDate.LATEST]
        self.log = []

    def verdict(self, android='pass', sha=None):
        sha = sha or SHA
        self.gh.posted.setdefault(1, []).append(
            watch.patchcheck_marker('157.0.1', sha) + '\n'
            + f'<!-- redoubt-patchcheck-result version=157.0.1 sha={sha} desktop=pass '
              f'android={android} -->\n### Patch check\n')

    def go(self, dry_run=False, targets=('desktop', 'android')):
        return watch.autobuild('157.0.1', 1, list(targets), SHA, self.gh, 'o/r', self.NOW,
                               dry_run=dry_run, notify='owner', log=self.log.append)

    def test_eligibility(self):
        e = watch.autobuild_eligible
        self.assertTrue(e('157.0.1', '157.0', 'dot'))
        self.assertTrue(e('157.0.2', '157.0.1', 'dot'))
        self.assertTrue(e('157.1', '157.0', 'dot'))
        self.assertFalse(e('158.0', '157.0', 'dot'))
        self.assertTrue(e('158.0', '157.0', 'all'))
        self.assertFalse(e('157.0.1', '157.0', 'off'))
        self.assertFalse(e('157.0', '157.0', 'all'))
        self.assertFalse(e('157.0.1', '157.0.1', 'dot'))
        with self.assertRaises(watch.WatchError):
            e('157.0.1', '157.0', 'sometimes')
        checks = [{'version': '157.0.1', 'issue': '3', 'targets': 'desktop,android',
                   'label': 'release'},
                  {'version': '157.0.1', 'issue': '', 'targets': 'android', 'label': 'manual'},
                  {'version': '158.0', 'issue': '4', 'targets': 'desktop,android',
                   'label': 'release'}]
        self.assertEqual(watch.autobuild_jobs(checks, '157.0', 'dot'), checks[:1])
        self.assertEqual(watch.autobuild_jobs(checks, '157.0', 'all'), [checks[0], checks[2]])

    def test_dispatch_once(self):
        self.verdict()
        self.assertEqual(self.go(), 'dispatched')
        base, files, message = self.gh.commits[0]
        self.assertEqual(base, SHA)
        self.assertEqual(files, {'version.android': '157.0.1\n', 'release.android': '1\n',
                                 'version': '157.0.1\n', 'release': '1\n'})
        self.assertIn('#1', message)
        self.assertEqual(self.gh.branches, {'auto/firefox-157.0.1': f'{1:040x}'})
        self.assertEqual(self.gh.dispatched, [('android-release.yaml', 'auto/firefox-157.0.1',
                                               {'mode': 'full', 'update_check': 'true',
                                                'build_date': '20261009120000'})])
        comment = self.gh.posted[1][-1]
        self.assertTrue(comment.startswith(watch.autobuild_marker('157.0.1') + '\n@owner: '))
        self.assertIn('**unsigned**', comment)
        self.assertIn('build_date=20261009120000', comment)
        self.assertIn("Build date `20261009120000`: this run's hour, above `android-157.0-3`",
                      comment)
        self.assertEqual(self.go(), 'already-dispatched')
        self.assertEqual(len(self.gh.dispatched), 1)

    def test_android_only_bumps_android_only(self):
        self.verdict()
        self.go(targets=('android',))
        self.assertEqual(sorted(self.gh.commits[0][1]), ['release.android', 'version.android'])

    def test_existing_branch_is_reused(self):
        self.verdict()
        self.gh.branches['auto/firefox-157.0.1'] = 'b' * 40
        self.assertEqual(self.go(), 'dispatched')
        self.assertEqual(self.gh.commits, [])
        self.assertIn('`bbbbbbbbbbbb`', self.gh.posted[1][-1])

    def test_needs_a_verdict_for_this_commit(self):
        self.assertEqual(self.go(), 'no-result')
        self.verdict(sha='f' * 40)
        self.assertEqual(self.go(), 'no-result')
        # A pre-LW-M7-47 comment has only the first marker.
        self.gh.posted[1].append(watch.patchcheck_marker('157.0.1', SHA))
        self.assertEqual(self.go(), 'no-result')
        self.assertEqual(self.gh.dispatched, [])

    def test_failing_patches_block_and_say_so_once(self):
        self.verdict(android='fail')
        self.assertEqual(self.go(), 'blocked')
        self.assertIn('did not pass (android: fail)', self.gh.posted[1][-1])
        self.assertIn('@owner: no candidate build', self.gh.posted[1][-1])
        self.assertEqual(self.go(), 'already-blocked')
        self.assertEqual(len(self.gh.posted[1]), 2)
        self.assertEqual((self.gh.branches, self.gh.dispatched), ({}, []))

    def test_box_b_busy_waits(self):
        self.verdict()
        for wf, status in (('android-release.yaml', 'in_progress'),
                           ('android-test.yaml', 'queued')):
            self.gh.runs = {(wf, status): [{'id': 7, 'html_url': 'x', 'head_branch':
                                            'android/158-beta2', 'status': status}]}
            self.assertEqual(self.go(), 'busy')
        self.assertEqual((self.gh.branches, self.gh.dispatched), ({}, []))
        self.gh.runs = {}
        self.assertEqual(self.go(), 'dispatched')

    def test_beta_out_dispatches_inside_the_window(self):
        self.verdict()
        self.gh.rels = [BuildDate.BETA1, BuildDate.LATEST]
        self.assertEqual(self.go(), 'dispatched')
        self.assertEqual(self.gh.dispatched[0][2]['build_date'], '20261006190000')
        comment = self.gh.posted[1][-1]
        self.assertIn('the middle of the free window', comment)
        self.assertIn('versionCodes 2016188824-2016188831', comment)

    def test_no_fit_does_not_dispatch_and_says_why_once(self):
        self.verdict()
        self.gh.release = 'android-157.0-4'
        self.gh.rels = [BuildDate.BETA1, rel('android-157.0-4', '20261007040000')]
        self.assertEqual(self.go(), 'no-build-date')
        comment = self.gh.posted[1][-1]
        self.assertTrue(comment.startswith(watch.autobuild_nodate_marker('157.0.1')
                                           + '\n@owner: no candidate build'))
        self.assertIn('no unused hour lies strictly between', comment)
        self.assertIn('**The owner must pick the build date**', comment)
        self.assertIn('-f build_date=YYYYMMDDHH0000', comment)
        self.assertEqual((self.gh.branches, self.gh.dispatched, self.gh.commits), ({}, [], []))
        # Once per version, and never built later by itself, even if a date
        # would fit by then (the owner may have dispatched by hand).
        self.gh.rels = [BuildDate.LATEST]
        self.gh.release = 'android-157.0-3'
        self.assertEqual(self.go(), 'no-build-date')
        self.assertEqual(len(self.gh.posted[1]), 2)
        self.assertEqual(self.gh.dispatched, [])

    def test_no_fit_dry_run_posts_nothing(self):
        self.verdict()
        self.gh.rels = [BuildDate.BETA1, rel('android-157.0-3', body='unsigned notes')]
        self.assertEqual(self.go(dry_run=True), 'no-build-date')
        self.assertEqual(len(self.gh.posted[1]), 1)
        self.assertTrue(any('would comment' in l for l in self.log))

    def test_dry_run(self):
        self.verdict()
        self.assertEqual(self.go(dry_run=True), 'would-dispatch')
        self.assertEqual((self.gh.branches, self.gh.dispatched, self.gh.commits), ({}, [], []))
        self.assertEqual(len(self.gh.posted[1]), 1)


class ManualPatchcheck(unittest.TestCase):
    def test_job(self):
        self.assertEqual(watch.manual_patchcheck_job(' 157.0 ', 'desktop,android', True),
                         {'version': '157.0', 'issue': '', 'targets': 'desktop,android',
                          'label': 'manual'})
        self.assertEqual(watch.manual_patchcheck_job('153.4.0esr', 'android', True)['targets'],
                         'android')

    def test_dry_run_only(self):
        with self.assertRaisesRegex(watch.WatchError, 'only runs as a dry run'):
            watch.manual_patchcheck_job('157.0', 'desktop,android', False)

    def test_beta_rejected(self):
        for bad in ('158.0b3', '159.0a1', '', 'v157.0'):
            with self.assertRaises(ValueError, msg=bad):
                watch.manual_patchcheck_job(bad, 'desktop,android', True)

    def test_targets(self):
        for bad in ('', ',', 'ios', 'desktop,ios'):
            with self.assertRaises(watch.WatchError, msg=bad):
                watch.manual_patchcheck_job('157.0', bad, True)


def report(name):
    return (FIXTURES / name).read_text()


SHA = '0123456789abcdef0123456789abcdef01234567'
RUN = 'https://github.com/o/r/actions/runs/42'


class ParseReport(unittest.TestCase):
    def test_real_pass(self):
        r = watch.parse_report(report('patchfail-157.0-desktop.out'), 0)
        self.assertEqual(r['status'], 'pass')
        self.assertEqual(r['patches'], 68)
        self.assertEqual(r['failing'], [])
        self.assertEqual(r['fuzz_hunks'], 27)
        self.assertEqual(len(r['fuzzed']), 22)
        self.assertIn(('patches/firefox-in-ua.patch', 1, 2), r['fuzzed'])
        self.assertIn(('patches/fullpage-translations-customization.patch', 2, 1),
                      r['fuzzed'])
        self.assertEqual(r['offset_hunks'], 144)

    def test_real_fail(self):
        r = watch.parse_report(report('patchfail-153.4.0esr-desktop.out'), 1)
        self.assertEqual(r['status'], 'fail')
        self.assertEqual(r['patches'], 68)
        failing = dict(r['failing'])
        self.assertEqual(len(failing), 20)
        # in list order, matching the script's own summary line
        self.assertEqual(r['failing'][0][0], 'patches/always-fetch-latest-toolchain-artifact.patch')
        self.assertEqual(failing['patches/remove-openai.patch'], '1 hunk failed')
        self.assertEqual(failing['patches/xdg-dir.patch'], '2 hunks failed')
        self.assertEqual(failing['patches/ui-patches/privacy-preferences.patch'],
                         'reversed or already applied')
        self.assertEqual(r['fuzz_hunks'], 32)

    def test_summary_line_is_a_cross_check(self):
        # A failure the per-section parse cannot see is still reported.
        text = report('patchfail-157.0-desktop.out').replace(
            'success: All patches where applied successfully.',
            '[patches/ghost.patch]\n\nerror: Some patches failed!')
        r = watch.parse_report(text, 1)
        self.assertEqual(r['status'], 'fail')
        self.assertEqual(r['failing'], [('patches/ghost.patch', 'reported failing')])

    def test_missing_target_file(self):
        text = '\n'.join([
            'Patches: 1', '', 'Testing patches...', '', '==> patches/gone.patch:', '',
            "can't find file to patch at input line 3",
            'Perhaps you used the wrong -p or --strip option?',
            'File to patch: ', 'Skip this patch? [y] ', 'Skipping patch.',
            '1 out of 1 hunk ignored',
            '---> patch exited 1', '', "Removing '/x/tmpdir92.a'...", '',
            '[patches/gone.patch]', '', 'error: Some patches failed!'])
        r = watch.parse_report(text, 1)
        self.assertEqual(r['failing'], [('patches/gone.patch', '1 target file missing')])

    def test_error(self):
        r = watch.parse_report(report('patchfail-error.out'), 1)
        self.assertEqual(r['status'], 'error')
        self.assertIsNone(r['patches'])
        self.assertEqual(r['failing'], [])
        self.assertIn('does not exist', r['tail'])
        # exit 0 without the success line is not a pass either
        self.assertEqual(watch.parse_report('', 0)['status'], 'error')


class Comment(unittest.TestCase):
    def results(self):
        return {'desktop': watch.parse_report(report('patchfail-157.0-desktop.out'), 0),
                'android': watch.parse_report(report('patchfail-153.4.0esr-desktop.out'), 1)}

    def test_body(self):
        body = watch.patchcheck_comment('158.0', SHA, self.results(), RUN, 'ab' * 32)
        self.assertTrue(body.startswith(watch.patchcheck_marker('158.0', SHA) + '\n'))
        self.assertEqual(body.count('<!-- redoubt-patchcheck '), 1)
        self.assertEqual(body.splitlines()[1],
                         f'<!-- redoubt-patchcheck-result version=158.0 sha={SHA} '
                         f'desktop=pass android=fail -->')
        self.assertEqual(watch.patchcheck_results([body], '158.0', SHA),
                         {'desktop': 'pass', 'android': 'fail'})
        self.assertIsNone(watch.patchcheck_results([body], '158.0', 'f' * 40))
        self.assertIn('### Patch check against Firefox 158.0', body)
        self.assertIn('| desktop | pass | 68 | 0 | 27 (22 patches) | 144 |', body)
        self.assertIn('| android | **FAIL** | 68 | 20 | 32 (25 patches) | 165 |', body)
        self.assertIn('#### Failing patches', body)
        self.assertIn('- `patches/xdg-dir.patch`: 2 hunks failed', body)
        failing = body.split('#### Failing patches')[1].split('<details>')[0]
        self.assertNotIn('**desktop**', failing)  # nothing failed there
        self.assertIn('- `patches/firefox-in-ua.patch`: 1 hunk, max fuzz 2', body)
        self.assertIn(f'Run, with the full reports: {RUN}', body)
        self.assertIn('14F2 6682 D091 6CDD 81E3 7B6D 61B7 B526 D98F 0353', body)
        self.assertIn('sha256 `' + 'ab' * 32 + '`', body)
        self.assertIn('Redoubt `0123456789ab`', body)

    def test_all_pass_has_no_failing_section(self):
        r = watch.parse_report(report('patchfail-157.0-desktop.out'), 0)
        body = watch.patchcheck_comment('158.0', SHA, {'desktop': r, 'android': r}, RUN)
        self.assertNotIn('Failing patches', body)
        self.assertNotIn('did not finish', body)

    def test_error_row_shows_the_tail(self):
        res = self.results()
        res['android'] = watch.parse_report(report('patchfail-error.out'), 1)
        body = watch.patchcheck_comment('158.0', SHA, res, RUN)
        self.assertIn('| android | **ERROR** | ? | 0 | 0 | 0 |', body)
        self.assertIn('#### android: check-patchfail.sh did not finish (exit 1)', body)
        self.assertIn('make fetch TARGETS=android', body)

    def test_no_run_link_outside_actions(self):
        self.assertEqual(watch.run_url({}), '')
        self.assertEqual(watch.run_url({'GITHUB_REPOSITORY': 'o/r', 'GITHUB_RUN_ID': '42'}),
                         RUN)
        body = watch.patchcheck_comment('158.0', SHA, self.results(), '')
        self.assertNotIn('Run, with', body)

    def test_truncated_keeps_marker(self):
        r = watch.parse_report(report('patchfail-153.4.0esr-desktop.out'), 1)
        r['failing'] = [(f'patches/p{i}.patch', '1 hunk failed') for i in range(3000)]
        body = watch.patchcheck_comment('158.0', SHA, {'desktop': r}, RUN)
        self.assertLessEqual(len(body), watch.COMMENT_LIMIT)
        self.assertTrue(body.startswith(watch.patchcheck_marker('158.0', SHA)))
        self.assertIn('(truncated; the run has the full reports: ' + RUN, body)

    def test_idempotency_marker(self):
        body = watch.patchcheck_comment('158.0', SHA, self.results(), RUN)
        self.assertTrue(watch.already_posted(['hello', body], '158.0', SHA))
        self.assertFalse(watch.already_posted([body], '158.0.1', SHA))
        self.assertFalse(watch.already_posted([body], '158.0', 'f' * 40))
        self.assertFalse(watch.already_posted([], '158.0', SHA))
        # 158.0 is not a prefix match for 158.0.1, nor the reverse
        other = watch.patchcheck_comment('158.0.1', SHA, self.results(), RUN)
        self.assertFalse(watch.already_posted([other], '158.0', SHA))


class Gpg(unittest.TestCase):
    FPR = watch.MOZILLA_KEY_FINGERPRINT

    def test_validsig_is_the_primary(self):
        status = report('gpg-status-157.0.txt')
        # signed by a subkey; the primary is the last VALIDSIG field
        self.assertIn('VALIDSIG 827E658608679618CD349F93678E455D76767AA3', status)
        self.assertEqual(watch.validsig_primary(status), self.FPR)

    def test_bad_signatures(self):
        self.assertIsNone(watch.validsig_primary(''))
        bad = report('gpg-status-157.0.txt').replace(
            '[GNUPG:] GOODSIG', '[GNUPG:] BADSIG')
        self.assertIsNone(watch.validsig_primary(bad))
        self.assertIsNone(watch.validsig_primary(
            '[GNUPG:] ERRSIG 678E455D76767AA3 1 10 00 1790247115 9 -\\n'))

    def test_imported_primaries(self):
        self.assertEqual(watch.imported_primaries(report('gpg-colons-mozilla-key.txt')),
                         [self.FPR])
        self.assertEqual(watch.imported_primaries(''), [])


def have_tools():
    return all(shutil.which(t) for t in ('gpg', 'xz', 'patch', 'sh'))


@unittest.skipUnless(have_tools(), 'needs gpg, xz and patch')
class PatchcheckEndToEnd(unittest.TestCase):
    """The real check-patchfail.sh against a tiny signed "Firefox" tarball."""

    VERSION = '158.0'

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='redoubt-patchcheck-test-')
        base = Path(cls.tmp.name)
        cls.gnupg = base / 'gnupg'
        cls.gnupg.mkdir(mode=0o700)
        cls.fprs = [cls.genkey(f'Redoubt test {i} <test{i}@invalid>') for i in (1, 2)]
        cls.pubkey = {f: cls.gpg('--armor', '--export', f).stdout for f in cls.fprs}

        # The "upstream" tree: three files; b.txt has drifted under fuzz.
        name = f'firefox-{cls.VERSION}'
        cls.tarball = base / f'{name}.source.tar.xz'
        files = {'a.txt': 'one\ntwo\nthree\n',
                 'b.txt': 'l1\nl2\nl3 upstream changed\nl4\nl5\nl6\nl7\nl8\n',
                 'c.txt': 'desktop\n'}
        with tarfile.open(cls.tarball, 'w:xz') as t:
            d = tarfile.TarInfo(name)
            d.type, d.mode = tarfile.DIRTYPE, 0o755
            t.addfile(d)
            for fn, text in files.items():
                info = tarfile.TarInfo(f'{name}/{fn}')
                info.size = len(text.encode())
                t.addfile(info, io.BytesIO(text.encode()))
        cls.sigs = {}
        for f in cls.fprs:
            sig = base / f'sig-{f}.asc'
            cls.gpg('--armor', '--local-user', f, '--output', str(sig),
                    '--detach-sign', str(cls.tarball))
            cls.sigs[f] = sig.read_bytes()

        # The "repository": patch lists and patches.
        cls.repo = base / 'repo'
        (cls.repo / 'assets' / 'patches').mkdir(parents=True)
        (cls.repo / 'patches').mkdir()
        lists = {'common': 'patches/ok.patch\npatches/fuzzy.patch  # inline comment\n',
                 'desktop': 'patches/desktop.patch\n',
                 'android': '# android only\npatches/gone.patch\n'}
        for k, v in lists.items():
            (cls.repo / 'assets' / 'patches' / f'{k}.txt').write_text(v)
        patches = {
            'ok': '--- a/a.txt\n+++ b/a.txt\n@@ -1,3 +1,3 @@\n one\n-two\n+TWO\n three\n',
            'fuzzy': '--- a/b.txt\n+++ b/b.txt\n@@ -2,6 +2,6 @@\n l2\n l3\n l4\n'
                     '-l5\n+l5 redoubt\n l6\n l7\n',
            'desktop': '--- a/c.txt\n+++ b/c.txt\n@@ -1 +1 @@\n-desktop\n+redoubt\n',
            'gone': '--- a/mobile/gone.kt\n+++ b/mobile/gone.kt\n@@ -1 +1 @@\n-x\n+y\n',
        }
        for k, v in patches.items():
            (cls.repo / 'patches' / f'{k}.patch').write_text(v)
        # The checkout's own version files must not matter (nor change).
        (cls.repo / 'version').write_text('1.0\n')
        (cls.repo / 'version.android').write_text('1.0\n')

    @classmethod
    def tearDownClass(cls):
        subprocess.run(['gpgconf', '--kill', 'all'],
                       env={**os.environ, 'GNUPGHOME': str(cls.gnupg)},
                       capture_output=True)
        cls.tmp.cleanup()

    @classmethod
    def gpg(cls, *args):
        r = subprocess.run(['gpg', '--batch', '--no-tty', '--pinentry-mode', 'loopback',
                            '--passphrase', '', *args],
                           env={**os.environ, 'GNUPGHOME': str(cls.gnupg)},
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return r

    @classmethod
    def genkey(cls, uid):
        cls.gpg('--quick-gen-key', uid, 'ed25519', 'sign', 'never')
        colons = cls.gpg('--with-colons', '--fingerprint', uid).stdout
        return watch.imported_primaries(colons)[0]

    def setUp(self):
        FakeServer.state = {'heads': [], 'gets': [], 'tarballs': set(), 'labels': [],
                            'issues': [], 'bodies': [], 'comments': {}, 'files': {}}
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), FakeServer)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f'http://127.0.0.1:{self.server.server_address[1]}'
        work = tempfile.TemporaryDirectory(prefix='redoubt-patchcheck-run-')
        self.addCleanup(work.cleanup)
        self.work = Path(work.name)
        self.serve(signed_by=self.fprs[0], key=self.fprs[0])

    def serve(self, signed_by, key):
        rel = f'/releases/{self.VERSION}/source/firefox-{self.VERSION}.source.tar.xz'
        FakeServer.state['files'] = {
            rel: self.tarball.read_bytes(),
            rel + '.asc': self.sigs[signed_by],
            '/key.asc': self.pubkey[key].encode(),
        }
        self.tarball_path = rel

    def patchcheck(self, *extra, sha=SHA, token='test-token', fpr=None, env_extra=None):
        env = clean_env(token)
        env.update(env_extra or {})
        env.update({'GITHUB_REPOSITORY': 'o/r', 'GITHUB_RUN_ID': '42',
                    'RUNNER_TEMP': str(self.work)})
        return subprocess.run(
            [sys.executable, str(SCRIPT), 'patchcheck', '--version', self.VERSION,
             '--root', str(self.repo), '--sha', sha,
             '--archive-base', f'{self.base}/releases', '--key-url', f'{self.base}/key.asc',
             '--fingerprint', fpr or self.fprs[0],
             '--check-script', str(ROOT / 'scripts' / 'check-patchfail.sh'),
             '--api', self.base, '--repo', 'o/r', *extra],
            env=env, capture_output=True, text=True, timeout=120)

    def test_posts_once_per_version_and_commit(self):
        r = self.patchcheck('--issue', '7')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('outcome: posted', r.stdout)
        body, = FakeServer.state['comments'][7]
        self.assertIn(watch.patchcheck_marker(self.VERSION, SHA), body)
        self.assertIn('| desktop | pass | 3 | 0 | 1 (1 patch) | 0 |', body)
        self.assertIn('| android | **FAIL** | 3 | 1 | 1 (1 patch) | 0 |', body)
        self.assertIn('- `patches/gone.patch`: 1 target file missing', body)
        self.assertIn('- `patches/fuzzy.patch`: 1 hunk, max fuzz 2', body)
        self.assertIn(f'Run, with the full reports: {RUN}', body)
        self.assertEqual(sorted(FakeServer.state['gets']),
                         sorted(['/key.asc', self.tarball_path, self.tarball_path + '.asc']))
        # Nothing in the checkout changed, nothing was left behind.
        self.assertEqual((self.repo / 'version').read_text(), '1.0\n')
        self.assertEqual((self.repo / 'version.android').read_text(), '1.0\n')
        self.assertEqual(sorted(p.name for p in self.repo.iterdir()),
                         ['assets', 'patches', 'version', 'version.android'])
        self.assertEqual(list(self.work.iterdir()), [])

        # Same version, same commit: nothing downloaded, nothing posted.
        FakeServer.state['gets'].clear()
        r = self.patchcheck('--issue', '7')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('outcome: already-posted', r.stdout)
        self.assertEqual(len(FakeServer.state['comments'][7]), 1)
        self.assertEqual(FakeServer.state['gets'], [])

        # A new commit is a new check.
        r = self.patchcheck('--issue', '7', sha='f' * 40)
        self.assertIn('outcome: posted', r.stdout)
        self.assertEqual(len(FakeServer.state['comments'][7]), 2)

    def test_android_only_targets(self):
        r = self.patchcheck('--issue', '7', '--targets', 'android')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        body, = FakeServer.state['comments'][7]
        self.assertIn('| android | **FAIL** | 3 | 1 |', body)
        self.assertNotIn('| desktop |', body)
        r = self.patchcheck('--issue', '8', '--targets', 'ios', '--dry-run')
        self.assertEqual(r.returncode, 1)
        self.assertIn('targets must be among', r.stderr)

    def test_dry_run_prints_and_posts_nothing(self):
        r = self.patchcheck('--dry-run', token='')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('outcome: would-post', r.stdout)
        self.assertIn(watch.patchcheck_marker(self.VERSION, SHA), r.stdout)
        self.assertIn('| android | **FAIL**', r.stdout)
        self.assertEqual(FakeServer.state['comments'], {})

    def test_manual_dry_run_puts_the_comment_in_the_summary(self):
        # The workflow's manual entry: no --issue, --dry-run, token present.
        summary = self.work / 'step-summary.md'
        r = self.patchcheck('--dry-run', '--targets', 'desktop,android',
                            env_extra={'GITHUB_STEP_SUMMARY': str(summary)})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('outcome: would-post', r.stdout)
        self.assertIn('| desktop | pass |', r.stdout)
        text = summary.read_text()
        summary.unlink()
        self.assertIn(f'patchcheck {self.VERSION}: **would-post**', text)
        self.assertIn('the comment it would post on #?', text)
        self.assertIn(watch.patchcheck_marker(self.VERSION, SHA), text)
        self.assertIn('| android | **FAIL** | 3 | 1 |', text)
        self.assertEqual(FakeServer.state['comments'], {})
        self.assertEqual(sorted(FakeServer.state['gets']),
                         sorted(['/key.asc', self.tarball_path, self.tarball_path + '.asc']))

    def test_no_token_refuses_unless_dry_run(self):
        r = self.patchcheck('--issue', '7', token='')
        self.assertEqual(r.returncode, 1)
        self.assertIn('posting needs GitHub access', r.stderr)

    def test_key_must_be_the_pinned_one(self):
        # The key server hands out a different key than the one pinned.
        self.serve(signed_by=self.fprs[1], key=self.fprs[1])
        r = self.patchcheck('--issue', '7')
        self.assertEqual(r.returncode, 1)
        self.assertIn(f'not exactly the pinned {self.fprs[0]}', r.stderr)
        self.assertEqual(FakeServer.state['comments'], {})

    def test_signature_must_be_by_the_pinned_key(self):
        # The pinned key is served, but someone else signed the tarball.
        self.serve(signed_by=self.fprs[1], key=self.fprs[0])
        r = self.patchcheck('--issue', '7')
        self.assertEqual(r.returncode, 1)
        self.assertIn('signature check failed', r.stderr)
        self.assertEqual(FakeServer.state['comments'], {})

    def test_tampered_tarball(self):
        self.serve(signed_by=self.fprs[0], key=self.fprs[0])
        FakeServer.state['files'][self.tarball_path] += b'\\0'
        r = self.patchcheck('--issue', '7')
        self.assertEqual(r.returncode, 1)
        self.assertIn('signature check failed', r.stderr)
        self.assertEqual(FakeServer.state['comments'], {})


if __name__ == '__main__':
    unittest.main()
