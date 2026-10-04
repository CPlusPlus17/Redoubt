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


def mobile_fixture(version):
    return json.loads((FIXTURES / f'mobile-versions-{version}.json').read_text())


class FakeGitHub:
    def __init__(self, titles=(), closed=()):
        # [title, number, state]; numbers are 1-based positions
        self.items = [{'title': t, 'number': n, 'state': 'closed' if t in closed else 'open'}
                      for n, t in enumerate(titles, 1)]
        self.created = []
        self.labels = []
        self.posted = {}  # number -> [comment bodies]

    def issues(self, label):
        assert label == watch.LABEL
        return [dict(i) for i in self.items]

    def ensure_label(self, label):
        self.labels.append(label)
        return True

    def create_issue(self, title, body, label):
        self.created.append((title, body, label))
        number = len(self.items) + 1
        self.items.append({'title': title, 'number': number, 'state': 'open'})
        return f'https://github.invalid/issues/{number}', number

    def comments(self, number):
        return list(self.posted.get(number, []))

    def create_comment(self, number, body):
        self.posted.setdefault(number, []).append(body)
        return f'https://github.invalid/issues/{number}#c{len(self.posted[number])}'


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
        self.assertEqual(found, {'version': '158.0', 'issue': 2, 'state': 'open'})
        self.assertTrue(watch.wants_patchcheck('opened', found))

        # The next day: still open, so the check runs again (and the comment
        # marker decides whether anything is posted).
        found = {}
        self.assertEqual(self.go('158.0', gh, found=found), 'duplicate')
        self.assertEqual(found, {'version': '158.0', 'issue': 2, 'state': 'open'})
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
        self.assertEqual(af, {'version': '157.0.1', 'tarball': False, 'issue': 1,
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
           if not k.startswith('GITHUB_') and k not in ('RUNNER_TEMP', 'GNUPGHOME')}
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
        if self.headers.get('Authorization') != 'Bearer test-token':
            return self.reply(401, {'message': 'Bad credentials'})
        if url.path == '/repos/o/r/issues':
            assert q['state'] == ['all'] and q['labels'] == ['firefox-release'], q
            page = int(q['page'][0])
            items = [{'title': t, 'number': n, 'state': 'open'}
                     for n, t in enumerate(self.state['issues'], 1)]
            return self.reply(200, items[(page - 1) * 100:page * 100])
        if url.path.startswith('/repos/o/r/issues/') and url.path.endswith('/comments'):
            number = int(url.path.split('/')[5])
            page = int(q['page'][0])
            items = [{'body': b} for b in self.state['comments'].get(number, [])]
            return self.reply(200, items[(page - 1) * 100:page * 100])
        self.reply(404)

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path == '/repos/o/r/labels':
            if data['name'] in self.state['labels']:
                return self.reply(422, {'message': 'already_exists'})
            self.state['labels'].append(data['name'])
            return self.reply(201, data)
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
        tmp = tempfile.TemporaryDirectory(prefix='redoubt-release-watch-e2e-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'version.android').write_text('157.0\n')
        (self.root / 'version').write_text('157.0')

    def script(self, version, *extra, token='test-token', output=None, mobile='157.0'):
        env = clean_env(token)
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
                         '"targets":"desktop,android","label":"release"}]\n')
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
                         'checks=[]\n')

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

    def test_mobile_feed_down_is_red_without_spam(self):
        out = self.root / 'github-output'
        FakeServer.state['tarballs'].add('158.0')
        for _ in range(3):
            r = self.script('158.0', output=out, mobile=None)
            self.assertEqual(r.returncode, 1)
            self.assertIn('mobile_versions.json', r.stderr)
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
        self.assertEqual(r.returncode, 1)
        self.assertIn('firefox_versions.json', r.stderr)
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
        # A 5xx or a dead connection must fail the run, not read as "no
        # tarball yet" -- that would hide a release for as long as it lasted.
        r = self.script('158.0', '--archive-base', f'{self.base}/broken')
        self.assertEqual(r.returncode, 1)
        self.assertIn('HTTP 503', r.stderr)
        r = self.script('158.0', '--archive-base', 'http://127.0.0.1:9/releases')
        self.assertEqual(r.returncode, 1)
        self.assertIn('HEAD', r.stderr)

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
        self.assertEqual(body.count('<!-- redoubt-patchcheck'), 1)
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

    def patchcheck(self, *extra, sha=SHA, token='test-token', fpr=None):
        env = clean_env(token)
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
