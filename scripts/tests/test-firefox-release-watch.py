#!/usr/bin/env python3
"""Offline checks for scripts/firefox-release-watch.py.

No network: product-details comes from fixtures
(scripts/tests/fixtures/firefox-release-watch/; product-details-157.0.json is
the real document as served on 2026-10-03, the other two are derived from it),
and the end-to-end cases run the script as a subprocess against a fake
archive.mozilla.org + GitHub API on 127.0.0.1.
"""

import http.server
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
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


class FakeGitHub:
    def __init__(self, titles=()):
        self.titles = list(titles)
        self.created = []
        self.labels = []

    def issue_titles(self, label):
        assert label == watch.LABEL
        return list(self.titles)

    def ensure_label(self, label):
        self.labels.append(label)
        return True

    def create_issue(self, title, body, label):
        self.created.append((title, body, label))
        self.titles.append(title)
        return f'https://github.invalid/issues/{len(self.created)}'


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

    def go(self, version, gh, tarball=True, dry_run=False):
        return watch.run(self.root, fixture(version), self.exists(tarball), gh,
                         'CPlusPlus17/Redoubt', dry_run, log=self.log.append)

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
        if self.headers.get('Authorization') != 'Bearer test-token':
            return self.reply(401, {'message': 'Bad credentials'})
        if url.path == '/repos/o/r/issues':
            assert q['state'] == ['all'] and q['labels'] == ['firefox-release'], q
            page = int(q['page'][0])
            items = [{'title': t} for t in self.state['issues']]
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
            return self.reply(201, {'html_url': f'http://x/{len(self.state["issues"])}'})
        self.reply(404)


class EndToEnd(unittest.TestCase):
    def setUp(self):
        FakeServer.state = {'heads': [], 'tarballs': set(), 'labels': [],
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

    def script(self, version, *extra, token='test-token'):
        env = {k: v for k, v in os.environ.items()
               if k not in ('GITHUB_TOKEN', 'GITHUB_REPOSITORY', 'GITHUB_STEP_SUMMARY',
                            'GITHUB_API_URL')}
        if token:
            env['GITHUB_TOKEN'] = token
        return subprocess.run(
            [sys.executable, str(SCRIPT), '--root', str(self.root),
             '--versions-file', str(FIXTURES / f'product-details-{version}.json'),
             '--archive-base', f'{self.base}/releases', '--api', self.base,
             '--repo', 'o/r', *extra],
            env=env, capture_output=True, text=True, timeout=60)

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

if __name__ == '__main__':
    unittest.main()
