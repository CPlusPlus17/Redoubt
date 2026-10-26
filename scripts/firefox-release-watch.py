#!/usr/bin/env python3
"""Flag every new Firefox release with one GitHub issue.

Run hourly by .github/workflows/firefox-release-watch.yaml. Since 2026-10-02 the
Android track follows Firefox release, the same track as desktop
(docs/android/TRACK.md, "Decision reversed"), so every Firefox release is a
rebase for both. Nothing else in the repository watches for one:
scripts/update-version.py only runs when a human types `make check`, and it
never looks at version.android.

What it does, in order:

1. reads LATEST_FIREFOX_VERSION (and, for information only, FIREFOX_ESR and
   FIREFOX_ESR_NEXT) from Mozilla's product-details;
2. compares it to ./version.android and ./version. If it is not newer than
   both, it stops: nothing to do;
3. checks that archive.mozilla.org already carries
   releases/<v>/source/firefox-<v>.source.tar.xz. A release can be announced
   before the source tarball is published; until it is, there is nothing to
   rebase onto, so it stops and the next run tries again;
4. looks for an issue (open OR closed) carrying the watcher label with the
   exact title "Firefox <v> released: rebase Android and desktop". If one
   exists it stops, so a version is flagged once, ever, however often this
   runs and whether or not the issue has since been closed;
5. otherwise opens that issue, with links to the release notes and the
   security advisories and the REBASE.md steps.

Then the same for Firefox for Android, from product-details'
mobile_versions.json (`run_android`). Its `version` is the Firefox for Android
release; Mozilla sometimes ships an Android-only dot release (153.0.2) that
desktop never gets, and that LATEST_FIREFOX_VERSION therefore never shows.
When that `version` is newer than ./version.android, is not the desktop
release above (that issue covers both targets), and is not older than it (the
desktop rebase goes past it), it opens ONE issue, "Firefox for Android <v>
released: rebase Android", deduplicated the same way. It does NOT wait for a
source tarball: an Android-only dot can ship without one. The issue says
whether archive.mozilla.org has firefox-<v>.source.tar.xz and, if not, what to
do instead. The *_beta/alpha/nightly fields of the feed are never read.

If mobile_versions.json cannot be read, the desktop part still runs and the
run turns red; no issue is opened about the failure. If firefox_versions.json
cannot be read, the Android part is skipped too: without the desktop release
it cannot tell an Android-only release from one the desktop issue covers.

`patchcheck` (the workflow's second job, see the section of that name below)
then tests the patch lists against each flagged release that has a source
tarball (both targets for a Firefox release, Android only for a Firefox for
Android one) and comments the result on its issue, once per version and
commit. `--dry-run --patchcheck-version <v>` also queues a check of <v> by
hand, newer than the repository or not, with no issue; it prints the comment
instead of posting it, and without --dry-run it is refused.

Only the latest release is flagged. If two releases land between runs (a
hourly schedule makes that rare), the older one gets no issue of its own; the
rebase goes straight to the newer one anyway.

Since LW-M7-47 (docs/android/RELEASE-WATCH.md) it also: assigns every issue
it opens to --notify (default $RELEASE_WATCH_NOTIFY, else the repository
owner) and @-mentions them, and assigns an open unassigned one; reads Mozilla's
security advisories (section "Mozilla security advisories" below) and puts
the ones the shipped release is behind on the release issue or a new one;
reminds on open `security` issues every 24 h; emits the `autobuild` matrix
(section "autobuild"); and, if RELEASE_WATCH_NTFY_URL is set, pushes each of
those events to an ntfy topic. `--notify-test` only opens and closes one test
issue to check the notification path.

Standard library only. Exit 0 when it did its job (including "nothing to
do" and "tarball not there yet"). A transient failure (TransientError: no
connection, a timeout, HTTP 408/429/5xx from a feed, archive.mozilla.org or
the GitHub API) is a warning and a job-summary line, and the run stays green,
until the same source has failed for more than OUTAGE_HOURS in a row
(--state-file keeps the first failure's time between runs; the workflow keeps
that file in the Actions cache). Then, and on every other failure (a 401/403/
404, a malformed version file or feed entry, a bug), exit 1: the run turns red
instead of silently missing a release, without an e-mail an hour for every
short outage.
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request


PRODUCT_DETAILS_URL = 'https://product-details.mozilla.org/1.0/firefox_versions.json'
MOBILE_PRODUCT_DETAILS_URL = 'https://product-details.mozilla.org/1.0/mobile_versions.json'
ARCHIVE_BASE = 'https://archive.mozilla.org/pub/firefox/releases'
FENIX_ARCHIVE_BASE = 'https://archive.mozilla.org/pub/fenix/releases'
# Mozilla's GitHub mirror of mozilla-release / mozilla-central. Firefox for
# Android releases are tagged FIREFOX-ANDROID_<v>_RELEASE there, Android-only
# dots included (FIREFOX-ANDROID_153_0_2_RELEASE has no FIREFOX_ twin).
FIREFOX_MIRROR = 'https://github.com/mozilla-firefox/firefox'
GITHUB_API = 'https://api.github.com'
LABEL = 'firefox-release'
LABEL_COLOR = 'e66000'
LABEL_DESCRIPTION = 'A new Firefox release to rebase onto (scripts/firefox-release-watch.py)'
USER_AGENT = 'redoubt-firefox-release-watch'
TIMEOUT = 30

# Notification (LW-M7-47). Firefox 157.0.1 was flagged on 2026-10-06 (#3) and
# nobody acted for three days: the issue had no assignee, mentioned nobody and
# said "rebase", not "security". Every issue the watcher opens is now assigned
# to RELEASE_WATCH_NOTIFY (default: the repository owner) and @-mentions them,
# which GitHub delivers as a "participating" notification (web, email, GitHub
# Mobile push, per the owner's notification settings). docs/android/RELEASE-WATCH.md.
SECURITY_LABEL = 'security'
SECURITY_LABEL_COLOR = 'b60205'
SECURITY_LABEL_DESCRIPTION = ('A Mozilla security advisory the shipped Redoubt is behind '
                              '(scripts/firefox-release-watch.py)')
PRIORITY_LABELS = {'critical': 'priority: critical', 'high': 'priority: high'}
PRIORITY_LABEL_COLOR = 'd93f0b'
PRIORITY_LABEL_DESCRIPTION = 'Highest MFSA impact of an advisory the shipped Redoubt is behind'
TEST_LABEL = 'release-watch-test'
# MFSA impact ratings, lowest to highest. "medium" appears in a few old files.
IMPACT_ORDER = {'none': 0, 'low': 1, 'moderate': 2, 'medium': 2, 'high': 3, 'critical': 4}
# A reminder comment on an open security issue at most this often.
REMIND_AFTER_HOURS = 24
# A source (a feed, the archive, the GitHub API calls of one step) may fail
# transiently this long, in a row, before the hourly run turns red.
OUTAGE_HOURS = 6

_VERSION = re.compile(r'^(\d+)\.(\d+)(?:\.(\d+))?(esr)?$')


class WatchError(Exception):
    """A failure that must turn the workflow run red."""


class TransientError(WatchError):
    """A network failure, or an HTTP status that says "try again later"
    (408, 429, 5xx), from a feed, archive.mozilla.org or the GitHub API. The
    hourly run logs it as a warning and stays green until the same source has
    failed for longer than OUTAGE_HOURS (see "Transient failures" in main())."""


# HTTP statuses that mean the other side is down or busy, not that the
# request (or this script) is wrong. 401/403/404/422 stay fatal: those need a
# human (a token, a permission, a renamed path).
TRANSIENT_STATUSES = frozenset({0, 408, 429, 500, 502, 503, 504})


def http_error(message, status):
    """WatchError for `status`, TransientError when the status is one a later
    run may not see."""
    if status in TRANSIENT_STATUSES or (isinstance(status, int) and status >= 500):
        return TransientError(message)
    return WatchError(message)


def parse_version(text):
    """'157.0' -> (157, 0, 0); '157.0.1' -> (157, 0, 1); '153.4.0esr' -> (153, 4, 0).

    Release and ESR versions only. Betas, nightlies and anything else raise
    ValueError: comparing 158.0b3 against 157.0 is not a question this answers.
    """
    m = _VERSION.match(text.strip())
    if not m:
        raise ValueError(f'not a Firefox release or ESR version: {text!r}')
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


def is_newer(candidate, current):
    return parse_version(candidate) > parse_version(current)


def read_track(root, name):
    path = Path(root) / name
    try:
        text = path.read_text().strip()
    except OSError as e:
        raise WatchError(f'cannot read {path}: {e}') from e
    parse_version(text)  # refuse a malformed file loudly
    return text


def issue_title(version):
    return f'Firefox {version} released: rebase Android and desktop'


def android_issue_title(version):
    return f'Firefox for Android {version} released: rebase Android'


def android_tag(version):
    """'157.0.1' -> 'FIREFOX-ANDROID_157_0_1_RELEASE'."""
    parse_version(version)
    return 'FIREFOX-ANDROID_' + version.replace('.', '_') + '_RELEASE'


def tarball_url(version, archive_base=ARCHIVE_BASE):
    return f'{archive_base}/{version}/source/firefox-{version}.source.tar.xz'


def release_notes_url(version):
    return f'https://www.mozilla.org/en-US/firefox/{version}/releasenotes/'


def android_release_notes_url(version):
    return f'https://www.mozilla.org/en-US/firefox/android/{version}/releasenotes/'


ADVISORIES_URL = 'https://www.mozilla.org/en-US/security/advisories/'
KNOWN_VULNERABILITIES_URL = 'https://www.mozilla.org/en-US/security/known-vulnerabilities/firefox/'


def issue_body(version, android, desktop, esr, esr_next, repo, ref='main'):
    """The body of the issue. Pure: everything it says comes from its arguments."""
    rebase = f'https://github.com/{repo}/blob/{ref}/docs/android/REBASE.md'
    behind = []
    if is_newer(version, android):
        behind.append(f'- Android: `version.android` is `{android}`')
    if is_newer(version, desktop):
        behind.append(f'- desktop: `version` is `{desktop}`')
    lines = [
        f'Mozilla released **Firefox {version}** and its source tarball is on '
        f'archive.mozilla.org:',
        f'<{tarball_url(version)}>',
        '',
        'Behind it:',
        *behind,
        '',
        '## Read before rebasing',
        '',
        f'- Release notes (desktop): {release_notes_url(version)}',
        f'- Release notes (Android): {android_release_notes_url(version)}',
        f'- Security advisories (find the MFSA for Firefox {version}, and any '
        f'"Firefox for Android" advisory): {ADVISORIES_URL}',
        f'- Known vulnerabilities fixed, by version: {KNOWN_VULNERABILITIES_URL}',
        '',
        f'For information: current ESR is `{esr or "unknown"}`'
        + (f', next ESR `{esr_next}`' if esr_next else '')
        + '. Redoubt does not track ESR (docs/android/TRACK.md).',
        '',
        f'## Steps ([REBASE.md]({rebase}))',
        '',
        f'1. §1 Decide: read the advisory above; note anything Android-only.',
        f'2. §2 Bump: `printf \'{version}\\n\' > version.android`, '
        f'`printf \'1\\n\' > release.android`; and the same for `version` / '
        f'`release` (desktop). Do not use `make check` for this during an '
        f'Android rebase.',
        f'3. §3 Fetch and verify: `make fetch TARGETS=android` (GPG-verified).',
        '4. §4 Check the patches, both targets: `./scripts/check-patchfail.sh '
        '--targets=android` and `./scripts/check-patchfail.sh`.',
        '5. §5 Fix the rejects (`./scripts/git-patchtree.sh --edit ...`); '
        're-run §4.',
        '6. §6 Pref drift: orphans (6a), moved defaults (6b), `mirror: once` (6c), '
        'Fenix runtime overwrites, landmine L2 (6d).',
        '7. §7 Gates: `lint-patch-scope`, `check-patch-order`, `board.py --check '
        '--check-scope --check-cfg-split`, `--diff-mozconfig --strict`, '
        '`--check-policies`, `scripts/tests`.',
        '8. §8 Build (BUILD.md), then the smoke (SMOKE.md) on the emulator.',
        '9. §9 Sign and publish.',
        '10. §10 Record the rebase in the pull request and close this issue.',
        '',
        f'<sub>Opened by `scripts/firefox-release-watch.py` '
        f'(.github/workflows/firefox-release-watch.yaml). One issue per version: '
        f'it will not reopen or duplicate this one, open or closed. Label: '
        f'`{LABEL}`.</sub>',
    ]
    return '\n'.join(lines) + '\n'


def android_issue_body(version, android, latest, has_tarball, repo, ref='main'):
    """The body of a Firefox for Android issue. Pure, like issue_body."""
    rebase = f'https://github.com/{repo}/blob/{ref}/docs/android/REBASE.md'
    tarball = tarball_url(version)
    lines = [
        f'Mozilla released **Firefox for Android {version}** (`version` in '
        f'<{MOBILE_PRODUCT_DETAILS_URL}>). Desktop Firefox is at `{latest}` '
        f'(`LATEST_FIREFOX_VERSION`), so this is an Android-only release: '
        f'desktop has nothing to rebase.',
        '',
        f'Behind it: Android, `version.android` is `{android}`.',
        '',
        '## Read before rebasing',
        '',
        f'- Release notes (Android): {android_release_notes_url(version)}',
        f'- Security advisories (look for a "Firefox for Android {version}" '
        f'advisory; an Android-only dot often fixes a crash or a site and has '
        f'none): {ADVISORIES_URL}',
        f'- Known vulnerabilities fixed, by version: {KNOWN_VULNERABILITIES_URL}',
        f'- What changed upstream: '
        f'{FIREFOX_MIRROR}/compare/{android_tag(android)}...{android_tag(version)}',
        f'- Mozilla\'s builds of it: {FENIX_ARCHIVE_BASE}/{version}/',
        '',
        '## Source tarball',
        '',
    ]
    if has_tarball:
        lines += [
            f'archive.mozilla.org carries the source tarball for {version}:',
            f'<{tarball}>',
            '',
            'so this is an ordinary rebase, Android only:',
            '',
            f'## Steps ([REBASE.md]({rebase}))',
            '',
            '1. §1 Decide: read the advisory above, if there is one.',
            f'2. §2 Bump: `printf \'{version}\\n\' > version.android`, '
            f'`printf \'1\\n\' > release.android`. Leave `version` / `release` '
            f'(desktop) alone.',
            '3. §3 Fetch and verify: `make fetch TARGETS=android` (GPG-verified).',
            '4. §4 Check the patches: `./scripts/check-patchfail.sh --targets=android`.',
            '5. §5 to §9 as for any rebase: rejects, pref drift, gates, build and '
            'smoke, sign and publish.',
            '6. §10 Record the rebase in the pull request and close this issue.',
        ]
    else:
        lines += [
            f'**archive.mozilla.org has no `firefox-{version}.source.tar.xz`** '
            f'(<{tarball}> was a 404 when this issue was opened). Android dot '
            f'releases can ship without a desktop source tarball (153.0.2 did), '
            f'and then there is nothing for `make fetch` to rebase onto. What to '
            f'do:',
            '',
            f'1. Read what changed: the compare link above, i.e. the '
            f'`{android_tag(version)}` tag in Mozilla\'s Firefox repository '
            f'(mozilla-release) against the tag Redoubt builds now, and the '
            f'advisory.',
            '2. If nothing in it reaches Redoubt (a fix in Fenix code Redoubt '
            'removes, Google services, a crash Redoubt cannot hit), say so here '
            'and close this issue; the next desktop release (`NEXT_RELEASE_DATE` '
            'in firefox_versions.json) carries the change and gets its own issue.',
            '3. If it does (a security fix in Gecko or in Android code Redoubt '
            'ships), take the fix from the release branch as a patch, or wait for '
            'the next desktop release if it is close; record which here '
            '(docs/android/SECURITY.md, "Android-only with no source tarball"). '
            'Building from the tag itself skips §3\'s signature check on the '
            'tarball, so it is not the supported path.',
            '4. If a tarball appears later, the next run notices it while '
            'this issue is open and posts the patch check here.',
        ]
    lines += [
        '',
        f'<sub>Opened by `scripts/firefox-release-watch.py` '
        f'(.github/workflows/firefox-release-watch.yaml) from mobile_versions.json. '
        f'One issue per version: it will not reopen or duplicate this one, open or '
        f'closed. Label: `{LABEL}`.</sub>',
    ]
    return '\n'.join(lines) + '\n'


# --------------------------------------------------------------------------
# I/O. Everything below talks to the network; the tests replace it.
# --------------------------------------------------------------------------

def _request(url, method='GET', data=None, token=None):
    headers = {'User-Agent': USER_AGENT}
    if token:
        headers['Authorization'] = f'Bearer {token}'
        headers['Accept'] = 'application/vnd.github+json'
        headers['X-GitHub-Api-Version'] = '2022-11-28'
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers['Content-Type'] = 'application/json'
    return urllib.request.Request(url, data=body, method=method, headers=headers)


def fetch_json(url):
    try:
        with urllib.request.urlopen(_request(url), timeout=TIMEOUT) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise http_error(f'cannot read {url}: HTTP {e.code}', e.code) from e
    except (urllib.error.URLError, OSError, ValueError) as e:
        # A dead connection, a timeout, or an HTML error page instead of JSON.
        raise TransientError(f'cannot read {url}: {e}') from e


def url_exists(url):
    """True on 200, False on 404. Anything else is an error, not an answer:
    a 5xx from the archive must not read as "no tarball yet" forever."""
    try:
        with urllib.request.urlopen(_request(url, method='HEAD'), timeout=TIMEOUT) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise http_error(f'HEAD {url}: HTTP {e.code}', e.code) from e
    except (urllib.error.URLError, OSError) as e:
        raise TransientError(f'HEAD {url}: {e}') from e


class GitHub:
    def __init__(self, repo, token, api=GITHUB_API):
        self.repo, self.token, self.api = repo, token, api.rstrip('/')

    def _api(self, method, path, data=None):
        """`path` from the API root, e.g. '/repos/o/r/issues' or '/graphql'."""
        url = f'{self.api}{path}'
        try:
            with urllib.request.urlopen(_request(url, method, data, self.token),
                                        timeout=TIMEOUT) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None), r.headers
        except urllib.error.HTTPError as e:
            return e.code, None, e.headers
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise TransientError(f'{method} {url}: {e}') from e

    def _call(self, method, path, data=None):
        return self._api(method, f'/repos/{self.repo}{path}', data)

    def _pages(self, path, params, what):
        out, page = [], 1
        while True:
            q = urllib.parse.urlencode({**params, 'per_page': 100, 'page': page})
            status, items, _ = self._call('GET', f'{path}?{q}')
            if status != 200 or not isinstance(items, list):
                raise http_error(f'{what}: HTTP {status}', status)
            out += items
            if len(items) < 100:
                return out
            page += 1

    def issues(self, label):
        """Every issue with `label` (None: every issue), open and closed, as
        dicts with 'title', 'number', 'state', 'created_at', 'labels' (names),
        'assignees' (logins) and 'node_id'."""
        params = {'state': 'all'} if label is None else {'labels': label, 'state': 'all'}
        items = self._pages('/issues', params,
                            'listing issues' if label is None
                            else f'listing issues labelled {label}')
        return [{'title': i.get('title', ''), 'number': i.get('number'),
                 'state': i.get('state', ''), 'created_at': i.get('created_at', ''),
                 'labels': [l.get('name', '') if isinstance(l, dict) else str(l)
                            for l in i.get('labels') or []],
                 'assignees': [a.get('login', '') for a in i.get('assignees') or []],
                 'node_id': i.get('node_id', '')}
                for i in items if 'pull_request' not in i]

    def issue_titles(self, label):
        """Titles of every issue with `label`, open and closed."""
        return [i['title'] for i in self.issues(label)]

    def comments_full(self, number):
        """Every comment on issue `number` as {'body', 'created_at'}."""
        items = self._pages(f'/issues/{number}/comments', {},
                            f'listing comments on #{number}')
        return [{'body': i.get('body') or '', 'created_at': i.get('created_at', '')}
                for i in items]

    def comments(self, number):
        """Bodies of every comment on issue `number`."""
        return [c['body'] for c in self.comments_full(number)]

    def create_comment(self, number, body):
        status, comment, _ = self._call('POST', f'/issues/{number}/comments',
                                        {'body': body})
        if status != 201 or not comment:
            raise http_error(f'commenting on #{number}: HTTP {status}', status)
        return comment.get('html_url', '')

    def ensure_label(self, label, color=LABEL_COLOR, description=LABEL_DESCRIPTION):
        status, _, _ = self._call('POST', '/labels', {
            'name': label, 'color': color, 'description': description})
        # 201 created, 422 already exists. Anything else: creating the issue
        # with the label below still works where the token may set labels.
        return status in (201, 422)

    def create_issue(self, title, body, label, assignees=()):
        """Returns (html_url, number). GitHub drops an assignee who cannot be
        assigned (no push access) without failing the call."""
        data = {'title': title, 'body': body, 'labels': [label]}
        if assignees:
            data['assignees'] = list(assignees)
        status, issue, _ = self._call('POST', '/issues', data)
        if status != 201 or not issue:
            raise http_error(f'creating issue {title!r}: HTTP {status}', status)
        return issue.get('html_url', ''), issue.get('number')

    def add_assignees(self, number, logins):
        status, _, _ = self._call('POST', f'/issues/{number}/assignees',
                                  {'assignees': list(logins)})
        if status not in (200, 201):
            raise http_error(f'assigning #{number}: HTTP {status}', status)

    def add_labels(self, number, labels):
        status, _, _ = self._call('POST', f'/issues/{number}/labels',
                                  {'labels': list(labels)})
        if status != 200:
            raise http_error(f'labelling #{number}: HTTP {status}', status)

    def edit_issue(self, number, **fields):
        status, _, _ = self._call('PATCH', f'/issues/{number}', fields)
        if status != 200:
            raise http_error(f'editing #{number}: HTTP {status}', status)

    def pin_issue(self, node_id):
        """Pin an issue to the repository's Issues page (GraphQL; at most three
        are pinned). True on success. Best effort: the caller only logs a
        failure, e.g. three already pinned or a token that may not pin."""
        if not node_id:
            return False
        status, data, _ = self._api('POST', '/graphql', {
            'query': 'mutation($id: ID!) { pinIssue(input: {issueId: $id}) '
                     '{ issue { number } } }',
            'variables': {'id': node_id}})
        return status == 200 and bool(data) and not data.get('errors')

    def latest_release(self):
        """The tag of the repository's latest (non-prerelease) release, or ''
        when there is none."""
        status, rel, _ = self._call('GET', '/releases/latest')
        if status == 404:
            return ''
        if status != 200 or not rel:
            raise http_error(f'reading the latest release: HTTP {status}', status)
        return rel.get('tag_name', '')

    def releases(self):
        """Every release of the repository, newest first, as dicts with
        'tag', 'name', 'draft', 'prerelease' and 'body'."""
        items = self._pages('/releases', {}, 'listing releases')
        return [{'tag': r.get('tag_name', ''), 'name': r.get('name') or '',
                 'draft': bool(r.get('draft')), 'prerelease': bool(r.get('prerelease')),
                 'body': r.get('body') or ''}
                for r in items]

    def list_dir(self, repo, path):
        """[{'name', 'download_url'}] of a directory of another (public)
        repository, through the contents API."""
        status, items, _ = self._api('GET', f'/repos/{repo}/contents/{path}')
        if status == 404:
            return []
        if status != 200 or not isinstance(items, list):
            raise http_error(f'listing {repo}/{path}: HTTP {status}', status)
        return [{'name': i.get('name', ''), 'download_url': i.get('download_url', '')}
                for i in items if i.get('type') == 'file']

    # Actions and git data: used by `autobuild` only.

    def workflow_runs(self, workflow, status):
        """[{'id', 'html_url', 'head_branch', 'status'}] of `workflow`'s runs
        in `status` (queued, in_progress, ...)."""
        q = urllib.parse.urlencode({'status': status, 'per_page': 50})
        code, data, _ = self._call('GET', f'/actions/workflows/{workflow}/runs?{q}')
        if code != 200 or not isinstance(data, dict):
            raise http_error(f'listing {workflow} runs ({status}): HTTP {code}', code)
        return [{'id': r.get('id'), 'html_url': r.get('html_url', ''),
                 'head_branch': r.get('head_branch', ''), 'status': r.get('status', '')}
                for r in data.get('workflow_runs') or []]

    def dispatch(self, workflow, ref, inputs):
        code, _, _ = self._call('POST', f'/actions/workflows/{workflow}/dispatches',
                                {'ref': ref, 'inputs': inputs})
        if code != 204:
            raise http_error(f'dispatching {workflow} on {ref}: HTTP {code}', code)

    def branch_sha(self, branch):
        """The commit `branch` points at, or '' when it does not exist."""
        code, data, _ = self._call('GET', f'/git/ref/heads/{branch}')
        if code == 404:
            return ''
        if code != 200 or not data:
            raise http_error(f'reading branch {branch}: HTTP {code}', code)
        return data['object']['sha']

    def commit_files(self, base_sha, files, message):
        """A new commit on top of `base_sha` whose tree is base_sha's with
        `files` ({path: text}) replaced. Returns its sha. Not on any branch
        yet: create_branch points one at it."""
        code, commit, _ = self._call('GET', f'/git/commits/{base_sha}')
        if code != 200 or not commit:
            raise http_error(f'reading commit {base_sha}: HTTP {code}', code)
        code, tree, _ = self._call('POST', '/git/trees', {
            'base_tree': commit['tree']['sha'],
            'tree': [{'path': p, 'mode': '100644', 'type': 'blob', 'content': t}
                     for p, t in sorted(files.items())]})
        if code != 201 or not tree:
            raise http_error(f'creating a tree: HTTP {code}', code)
        code, new, _ = self._call('POST', '/git/commits', {
            'message': message, 'tree': tree['sha'], 'parents': [base_sha]})
        if code != 201 or not new:
            raise http_error(f'creating a commit: HTTP {code}', code)
        return new['sha']

    def create_branch(self, branch, sha):
        code, _, _ = self._call('POST', '/git/refs',
                                {'ref': f'refs/heads/{branch}', 'sha': sha})
        if code != 201:
            raise http_error(f'creating branch {branch}: HTTP {code}', code)


def ntfy_send(url, title, message, click='', priority='default', token='', log=print):
    """Push one message to an ntfy topic (https://ntfy.sh/<topic> or a
    self-hosted server). Optional channel: only when the repository secret
    RELEASE_WATCH_NTFY_URL is set. Never fatal: GitHub's own notification
    (assignment + mention) is the channel of record."""
    headers = {'User-Agent': USER_AGENT, 'Title': title.encode('ascii', 'replace').decode(),
               'Priority': priority, 'Tags': 'warning'}
    if click:
        headers['Click'] = click
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, data=message.encode(), method='POST', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            ok = 200 <= r.status < 300
    except (urllib.error.URLError, OSError) as e:
        log(f'warning: ntfy push failed: {e}')
        return False
    log('ntfy push sent' if ok else 'warning: ntfy push refused')
    return ok


def mention_line(notify, what):
    """The first paragraph of every issue or comment that must reach the
    owner: an @-mention makes it a "participating" notification."""
    return f'@{notify}: {what}\n\n' if notify else ''


def title_matches(actual, base):
    """`actual` is `base`, or `base` behind a "[security: high] " style
    prefix the advisory check adds. The dedup must survive that rename."""
    return actual == base or (actual.startswith('[') and actual.endswith('] ' + base))


def strip_prefix(title):
    if title.startswith('[') and '] ' in title:
        return title.split('] ', 1)[1]
    return title


# --------------------------------------------------------------------------

def run(root, versions, exists, github, repo, dry_run=False, log=print, ref='main',
        found=None, notify=None):
    """Decide and act. Returns a one-word outcome, also used by the tests:
    'current', 'no-tarball', 'duplicate', 'would-open', 'opened'.

    `found`, when given, is a dict filled with what the patch-check job needs:
    'version' (the release, once it has a tarball), 'issue' (its number, when
    one was opened or already exists) and 'state' ('open' or 'closed')."""
    found = {} if found is None else found
    latest = versions.get('LATEST_FIREFOX_VERSION')
    if not latest:
        raise WatchError('product-details has no LATEST_FIREFOX_VERSION')
    parse_version(latest)
    esr = versions.get('FIREFOX_ESR', '')
    esr_next = versions.get('FIREFOX_ESR_NEXT', '')
    android = read_track(root, 'version.android')
    desktop = read_track(root, 'version')

    log(f'Firefox release: {latest}  (ESR {esr or "?"}'
        + (f', next ESR {esr_next}' if esr_next else '') + ')')
    log(f'repo: version.android={android}  version={desktop}')

    if not (is_newer(latest, android) or is_newer(latest, desktop)):
        log(f'up to date: {latest} is not newer than either track')
        return 'current'

    url = tarball_url(latest)
    if not exists(url):
        log(f'{latest} is announced but {url} is not published yet; '
            f'no issue until it is (next run retries)')
        return 'no-tarball'

    found['version'] = latest
    return _flag(issue_title(latest),
                 lambda: issue_body(latest, android, desktop, esr, esr_next, repo, ref),
                 github, dry_run, log, found, notify,
                 f'Mozilla released Firefox {latest}')


def matching_issues(github, title, log=print):
    """Issues whose title is `title` (or `title` behind a "[security: ...]"
    prefix), open or closed. The labelled listing first; when it has none,
    every issue, unfiltered, before anything is opened: on 2026-10-22 the
    labelled listing once came back without #8, and #9 duplicated it."""
    same = [i for i in github.issues(LABEL) if title_matches(i['title'], title)]
    if not same:
        same = [i for i in github.issues(None) if title_matches(i['title'], title)]
        if same:
            log(f'warning: the labelled listing missed {title!r} '
                f'(#{same[0]["number"]}); the unfiltered listing has it')
    return same


def _flag(title, body, github, dry_run, log, found, notify=None, what='new Firefox release'):
    """Open the issue `title` unless one exists, open or closed. `body` is
    called only when the issue is about to be opened (or printed). With
    `notify` (a GitHub login) the issue is assigned to it and mentions it; an
    existing open issue nobody is assigned to is assigned to it too."""
    if github is None:
        if not dry_run:
            raise WatchError('no GitHub access and not a dry run')
        log('dry run without GitHub access: duplicate check skipped')
    else:
        same = matching_issues(github, title, log)
        if same:
            # Prefer an open one, should a human have duplicated it by hand.
            same.sort(key=lambda i: i['state'] != 'open')
            found['issue'], found['state'] = same[0]['number'], same[0]['state']
            found['title'] = same[0]['title']
            log(f'already flagged: {title!r} (#{found["issue"]}, {found["state"]})')
            if (notify and same[0]['state'] == 'open'
                    and not same[0].get('assignees')):
                if dry_run:
                    log(f'dry run: would assign #{found["issue"]} to {notify}')
                else:
                    github.add_assignees(found['issue'], [notify])
                    log(f'assigned #{found["issue"]} to {notify}')
            return 'duplicate'

    text = mention_line(notify, f'{what}; you are assigned. Notification path: '
                                f'docs/android/RELEASE-WATCH.md.') + body()
    if dry_run:
        log(f'dry run: would open {title!r}' + (f' assigned to {notify}' if notify else '')
            + f':\n\n{text}')
        return 'would-open'
    github.ensure_label(LABEL)
    url, found['issue'] = github.create_issue(title, text, LABEL,
                                              assignees=[notify] if notify else ())
    found['state'], found['title'], found['url'] = 'open', title, url
    log(f'opened {url}')
    return 'opened'


def run_android(root, mobile, latest, exists, github, repo, dry_run=False, log=print,
                ref='main', found=None, notify=None):
    """The Firefox for Android half. `mobile` is mobile_versions.json, `latest`
    the desktop LATEST_FIREFOX_VERSION (`run` handles that one). Returns
    'current', 'same-as-desktop', 'superseded', 'ahead-of-desktop',
    'duplicate', 'would-open' or 'opened'. Only a dot release on desktop's
    major (157.0.1 while desktop is 157.0) counts as Android-only.

    `found` gets 'version', 'tarball' (whether firefox-<v>.source.tar.xz is
    on archive.mozilla.org now) and, once there is an issue, 'issue' and
    'state'. Only `version` is read from `mobile`: beta_version, alpha_version,
    nightly_version and the iOS fields are not Android releases."""
    found = {} if found is None else found
    version = mobile.get('version')
    if not version:
        raise WatchError('mobile_versions.json has no version')
    parse_version(version)
    parse_version(latest)
    android = read_track(root, 'version.android')
    log(f'Firefox for Android release: {version}  (desktop {latest}, '
        f'version.android={android})')

    if not is_newer(version, android):
        log(f'Android up to date: {version} is not newer than {android}')
        return 'current'
    if parse_version(version) == parse_version(latest):
        log(f'Firefox for Android {version} is the desktop release: its issue '
            f'covers Android')
        return 'same-as-desktop'
    if is_newer(latest, version):
        log(f'Firefox for Android {version} is older than desktop {latest}: '
            f'the desktop issue\'s rebase goes past it')
        return 'superseded'
    v, d = parse_version(version), parse_version(latest)
    if v[0] != d[0] or v[1:] == (0, 0):
        # A newer major (158.0 while desktop says 157.0) is not an Android-only
        # release: the mobile feed is simply ahead of the desktop one. Flagging
        # it would open a wrong "desktop has nothing to rebase" issue, and a
        # second issue for the same release once desktop catches up.
        log(f'Firefox for Android {version} is a new major ahead of desktop '
            f'{latest}: waiting for the desktop feed to report it')
        return 'ahead-of-desktop'

    found['version'] = version
    found['tarball'] = exists(tarball_url(version))
    log(f'source tarball for {version}: '
        + ('on archive.mozilla.org' if found['tarball'] else 'not on archive.mozilla.org'))
    return _flag(android_issue_title(version),
                 lambda: android_issue_body(version, android, latest, found['tarball'],
                                            repo, ref),
                 github, dry_run, log, found, notify,
                 f'Mozilla released Firefox for Android {version}')


def wants_patchcheck(outcome, found):
    """Whether the patch-check job should run after this outcome: for a newly
    opened issue, for one that is still open (it re-checks only when the
    patches moved; the comment marker makes a repeat a no-op), and in a dry
    run. Never for a closed issue: that rebase is done."""
    if outcome in ('opened', 'would-open'):
        return True
    return outcome == 'duplicate' and found.get('state') == 'open'


def wants_android_patchcheck(outcome, found):
    """As wants_patchcheck, and only when the release has a source tarball to
    check against: an Android-only dot may have none."""
    return bool(found.get('tarball')) and wants_patchcheck(outcome, found)


def patchcheck_jobs(desktop, android):
    """The workflow's patch-check matrix: [{'version', 'issue', 'targets',
    'label'}], one entry per flagged release that wants one. `desktop` and
    `android` are (outcome, found) pairs, either may be None."""
    jobs = []
    if desktop and wants_patchcheck(*desktop):
        f = desktop[1]
        jobs.append({'version': f['version'], 'issue': str(f.get('issue') or ''),
                     'targets': ','.join(PATCHCHECK_TARGETS), 'label': 'release'})
    if android and wants_android_patchcheck(*android):
        f = android[1]
        jobs.append({'version': f['version'], 'issue': str(f.get('issue') or ''),
                     'targets': 'android', 'label': 'android'})
    return jobs


def manual_patchcheck_job(version, targets, dry_run):
    """The matrix entry for a patch check asked for by hand (workflow_dispatch
    input patchcheck_version), so the patchcheck job can be exercised before a
    real new release exists. Checked whether or not `version` is newer than
    the repository, and with no issue: it posts nothing, so it is allowed only
    in a dry run. Raises WatchError (not a dry run, bad targets) or ValueError
    (not a release version: a beta, a nightly, a typo)."""
    if not dry_run:
        raise WatchError('a manual patch check (--patchcheck-version) only runs '
                         'as a dry run: it never posts a comment; pass --dry-run '
                         '(dry_run=true)')
    version = version.strip()
    parse_version(version)
    names = [t.strip() for t in targets.split(',') if t.strip()]
    if not names or any(t not in PATCHCHECK_TARGETS for t in names):
        raise WatchError(f'--patchcheck-targets must be among {PATCHCHECK_TARGETS}, '
                         f'got {targets!r}')
    return {'version': version, 'issue': '', 'targets': ','.join(names),
            'label': 'manual'}


# --------------------------------------------------------------------------
# patchcheck: test both patch lists against the new release, report on the
# issue. Run by the workflow's second job, only after `run` above opened (or
# found open) the issue. Usage:
#
#   firefox-release-watch.py patchcheck --version 158.0 --issue 42 \
#       [--targets desktop,android] [--dry-run]
#
# (--targets android for a Firefox for Android issue: desktop is not rebasing.)
#
# 1. Idempotency first, before an 800 MB download: if the issue already has a
#    comment carrying patchcheck_marker(version, sha) -- sha being the Redoubt
#    commit whose patches are tested -- stop. The same release is re-checked
#    only when the patches moved.
# 2. Download firefox-<v>.source.tar.xz and its .asc; fetch Mozilla's release
#    key from the repository (assets/mozilla-release-key.asc, the same file the
#    Makefile's fetch rule imports) into a throwaway GNUPGHOME; refuse unless the key imported
#    is exactly the pinned fingerprint and gpg reports VALIDSIG whose primary
#    key is that fingerprint.
# 3. Build a scratch root: symlinks to every top-level entry of the checkout
#    except version / version.android (written there as <v>) and the tarball
#    (downloaded there). Nothing in the checkout is modified, nothing is ever
#    committed. Run scripts/check-patchfail.sh in it for --targets=desktop,
#    then --targets=android: one after the other, so one ~5 GB extraction
#    exists at a time (the script removes its own on every exit path; this
#    checks, and removes a leftover, between the two).
# 4. Post ONE comment: per-target pass/fail, failing patches, fuzz counts, a
#    link to the run. --dry-run prints it instead.
# --------------------------------------------------------------------------

MOZILLA_KEY_FINGERPRINT = '14F26682D0916CDD81E37B6D61B7B526D98F0353'
KEY_URL = 'https://keys.openpgp.org/vks/v1/by-fingerprint/{fpr}'
# The pinned key ships in the repository: keys.openpgp.org reset every
# connection from the build network on 2026-10-04, and a build must not depend
# on a keyserver being up. --key-url can still point elsewhere.
KEY_FILE = Path('assets') / 'mozilla-release-key.asc'
PATCHCHECK_TARGETS = ('desktop', 'android')
DOWNLOAD_TIMEOUT = 120
# A GitHub comment is capped at 65536 characters; stay well clear.
COMMENT_LIMIT = 60000
# The tarball plus one extraction, with margin. ubuntu-latest has ~14 GB.
MIN_FREE_BYTES = 8 * 1024 ** 3

_HEADER = re.compile(r'^==> (.+):$')
_FUZZ = re.compile(r'^Hunk #\d+ succeeded at \d+ with fuzz (\d+)')
_OFFSET = re.compile(r'^Hunk #\d+ succeeded at \d+ (?:with fuzz \d+ )?\(offset')
# patch's per-file summary: "1 out of 2 hunks FAILED -- saving rejects to
# file x.rej" (context did not match) or "1 out of 1 hunk ignored -- ..."
# (skipped: missing target file, or a reversed / already applied patch).
_SUMMARY = re.compile(r'^(\d+) out of \d+ hunks? (FAILED|ignored)')
_PATCHES = re.compile(r'^Patches: (\d+)$')


def patchcheck_marker(version, sha):
    return f'<!-- redoubt-patchcheck version={version} sha={sha} -->'


def patchcheck_result_marker(version, sha, results):
    """The second line of a patch-check comment: the per-target verdicts in
    a form `autobuild` reads back (it runs in a later job and cannot see this
    one's outputs). Comments from before LW-M7-47 do not have it."""
    verdicts = ' '.join(f'{t}={r["status"]}' for t, r in results.items())
    return f'<!-- redoubt-patchcheck-result version={version} sha={sha} {verdicts} -->'


_RESULT_MARKER = re.compile(
    r'<!-- redoubt-patchcheck-result version=(\S+) sha=(\S+)((?: [a-z]+=[a-z]+)*) -->')


def patchcheck_results(comments, version, sha):
    """{target: 'pass'|'fail'|'error'} from the newest patch-check comment
    for `version` at `sha`, or None when there is none (or only an old one
    without the result line)."""
    found = None
    for body in comments:
        for m in _RESULT_MARKER.finditer(body):
            if (m.group(1), m.group(2)) == (version, sha):
                found = dict(kv.split('=', 1) for kv in m.group(3).split())
    return found


def already_posted(comments, version, sha):
    marker = patchcheck_marker(version, sha)
    return any(marker in c for c in comments)


def parse_report(text, exit_code):
    """Read check-patchfail.sh's stdout. Returns a dict:

    status   'pass' (exit 0 and the success line), 'fail' (exit 1 with at
             least one failing patch) or 'error' (anything else: the script
             never got to test the patches, e.g. a failed extraction)
    patches  the patch count it announced (None if it never did)
    failing  [(patch, reason)] in list order
    fuzzed   [(patch, hunks, max fuzz)] for patches that applied with fuzz
    fuzz_hunks, offset_hunks   totals over every patch
    """
    sections, current, patches = [], None, None
    tail_lines = []
    for line in text.splitlines():
        m = _HEADER.match(line)
        if m:
            current = {'patch': m.group(1), 'lines': []}
            sections.append(current)
            continue
        m = _PATCHES.match(line)
        if m and patches is None:
            patches = int(m.group(1))
        if line.startswith("Removing '"):
            current = None  # the per-patch part is over
        if current is not None:
            current['lines'].append(line)
        else:
            tail_lines.append(line)

    failing, fuzzed = [], []
    fuzz_hunks = offset_hunks = 0
    for sec in sections:
        lines = sec['lines']
        fuzz = [int(m.group(1)) for m in map(_FUZZ.match, lines) if m]
        fuzz_hunks += len(fuzz)
        offset_hunks += sum(1 for l in lines if _OFFSET.match(l))
        if fuzz:
            fuzzed.append((sec['patch'], len(fuzz), max(fuzz)))
        exited = [l for l in lines if l.startswith('---> patch exited')]
        rejs = [l for l in lines if l.startswith('---[snip]---------- --> ')]
        if not (exited or rejs):
            continue
        failed = ignored = 0
        for m in filter(None, map(_SUMMARY.match, lines)):
            if m.group(2) == 'FAILED':
                failed += int(m.group(1))
            else:
                ignored += int(m.group(1))
        missing = sum(1 for l in lines if "can't find file to patch" in l)
        reversed_ = any(l.startswith('Reversed (or previously applied) patch')
                        for l in lines)
        plural = lambda n, w: f'{n} {w}{"s" if n != 1 else ""}'
        reasons = []
        if failed:
            reasons.append(plural(failed, 'hunk') + ' failed')
        if missing:
            reasons.append(plural(missing, 'target file') + ' missing')
        if reversed_:
            reasons.append('reversed or already applied')
        elif ignored and not missing:
            reasons.append(plural(ignored, 'hunk') + ' ignored')
        if not reasons:
            reasons.append(exited[0][len('---> '):] if exited else '.rej written')
        failing.append((sec['patch'], ', '.join(reasons)))

    # The script's own summary line ("[a] [b]") is the cross-check: a patch
    # it names that the per-section parse missed is still reported.
    named = set()
    for line in tail_lines:
        if line.startswith('[') and line.endswith(']'):
            named.update(re.findall(r'\[([^\]]+)\]', line))
    seen = {p for p, _ in failing}
    failing += [(p, 'reported failing') for p in sorted(named - seen)]

    succeeded = any(l.startswith('success: ') for l in tail_lines)
    if exit_code == 0 and succeeded and not failing:
        status = 'pass'
    elif exit_code == 1 and failing:
        status = 'fail'
    else:
        status = 'error'
    return {'status': status, 'patches': patches, 'failing': failing,
            'fuzzed': fuzzed, 'fuzz_hunks': fuzz_hunks,
            'offset_hunks': offset_hunks, 'exit': exit_code,
            'tail': '\n'.join(text.splitlines()[-15:])}


def run_url(env=None):
    env = os.environ if env is None else env
    server, repo, run_id = (env.get('GITHUB_SERVER_URL', 'https://github.com'),
                            env.get('GITHUB_REPOSITORY'), env.get('GITHUB_RUN_ID'))
    if repo and run_id:
        return f'{server}/{repo}/actions/runs/{run_id}'
    return ''


def patchcheck_comment(version, sha, results, run_link, tarball_sha256='',
                       fingerprint=MOZILLA_KEY_FINGERPRINT):
    """The comment. Pure: everything comes from the arguments. `results` maps
    target -> parse_report() dict, in the order the rows should appear."""
    def row(target, r):
        label = {'pass': 'pass', 'fail': '**FAIL**', 'error': '**ERROR**'}[r['status']]
        fuzz = str(r['fuzz_hunks'])
        if r['fuzzed']:
            n = len(r['fuzzed'])
            fuzz += f' ({n} patch{"es" if n != 1 else ""})'
        patches = '?' if r['patches'] is None else str(r['patches'])
        return (f'| {target} | {label} | {patches} | {len(r["failing"])} '
                f'| {fuzz} | {r["offset_hunks"]} |')

    fpr = ' '.join(fingerprint[i:i + 4] for i in range(0, len(fingerprint), 4))
    lines = [
        patchcheck_marker(version, sha),
        patchcheck_result_marker(version, sha, results),
        f'### Patch check against Firefox {version}',
        '',
        f'`./scripts/check-patchfail.sh --targets=<target>` against '
        f'`firefox-{version}.source.tar.xz`'
        + (f' (sha256 `{tarball_sha256}`)' if tarball_sha256 else '')
        + f', signature verified against Mozilla\'s release key `{fpr}`. '
        f'Patches as of Redoubt `{sha[:12]}`.',
        '',
        '| Target | Result | Patches | Failing | Fuzzed hunks | Offset hunks |',
        '|---|---|---|---|---|---|',
        *(row(t, r) for t, r in results.items()),
        '',
    ]
    if any(r['failing'] for r in results.values()):
        lines += ['#### Failing patches', '']
        for t, r in results.items():
            if r['failing']:
                lines.append(f'**{t}**')
                lines += [f'- `{p}`: {why}' for p, why in r['failing']]
                lines.append('')
    for t, r in results.items():
        if r['status'] == 'error':
            lines += [f'#### {t}: check-patchfail.sh did not finish '
                      f'(exit {r["exit"]})', '', '```', r['tail'], '```', '']
    if any(r['fuzzed'] for r in results.values()):
        lines += ['<details><summary>Patches that applied with fuzz '
                  '(REBASE.md §5a)</summary>', '']
        for t, r in results.items():
            if r['fuzzed']:
                lines.append(f'**{t}**')
                lines += [f'- `{p}`: {h} hunk{"s" if h != 1 else ""}, max fuzz {f}'
                          for p, h, f in r['fuzzed']]
                lines.append('')
        lines += ['</details>', '']
    if run_link:
        lines += [f'Run, with the full reports: {run_link}', '']
    lines.append('<sub>Posted by `scripts/firefox-release-watch.py patchcheck`. '
                 'One comment per Firefox version and Redoubt commit; a new one '
                 'appears only when the patches change. Indicative: REBASE.md §4 '
                 'on the real tree is still the authority.</sub>')
    body = '\n'.join(lines) + '\n'
    if len(body) > COMMENT_LIMIT:
        cut = body[:COMMENT_LIMIT - 200].rsplit('\n', 1)[0]
        body = (cut + '\n\n(truncated; the run has the full reports'
                + (f': {run_link}' if run_link else '') + ')\n')
        if patchcheck_marker(version, sha) not in body:  # cannot happen: it is line 1
            raise WatchError('comment marker lost in truncation')
    return body


def validsig_primary(status_text):
    """From `gpg --status-fd` output, the primary-key fingerprint of a good
    signature, or None. A BADSIG/ERRSIG anywhere means None regardless."""
    primary = None
    for line in status_text.splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[0] != '[GNUPG:]':
            continue
        if parts[1] in ('BADSIG', 'ERRSIG', 'EXPSIG', 'REVKEYSIG'):
            return None
        if parts[1] == 'VALIDSIG' and len(parts) >= 3:
            primary = parts[11] if len(parts) >= 12 else parts[2]
    return primary


def imported_primaries(colons_text):
    """Primary-key fingerprints in `gpg --with-colons --fingerprint` output."""
    out, after_pub = [], False
    for line in colons_text.splitlines():
        f = line.split(':')
        if f[0] == 'pub':
            after_pub = True
        elif f[0] == 'fpr' and after_pub:
            out.append(f[9])
            after_pub = False
        elif f[0] == 'sub':
            after_pub = False
    return out


def _gpg(gnupghome, *args, check=True):
    r = subprocess.run(['gpg', '--batch', '--no-tty', *args],
                       env={**os.environ, 'GNUPGHOME': str(gnupghome)},
                       capture_output=True, text=True)
    if check and r.returncode != 0:
        raise WatchError(f'gpg {" ".join(args)}: {r.stderr.strip()}')
    return r


def download(url, dest, log=print):
    """Stream `url` to `dest`; returns its sha256."""
    h = hashlib.sha256()
    try:
        with urllib.request.urlopen(_request(url), timeout=DOWNLOAD_TIMEOUT) as r, \
                open(dest, 'wb') as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                h.update(chunk)
                f.write(chunk)
    except urllib.error.HTTPError as e:
        raise http_error(f'downloading {url}: HTTP {e.code}', e.code) from e
    except (urllib.error.URLError, OSError) as e:
        raise TransientError(f'downloading {url}: {e}') from e
    log(f'downloaded {url} ({Path(dest).stat().st_size} bytes)')
    return h.hexdigest()


def verify_tarball(tarball, signature, key_url, fingerprint, workdir, log=print):
    """Refuse unless `signature` is a good signature on `tarball` by the key
    whose primary fingerprint is `fingerprint`, fetched from `key_url`."""
    gnupghome = Path(workdir) / 'gnupg'
    gnupghome.mkdir(mode=0o700)
    try:
        _verify(tarball, signature, key_url, fingerprint, workdir, gnupghome, log)
    finally:
        # gpg may have started an agent or keyboxd for this home; do not
        # leave it running against a directory about to be removed.
        subprocess.run(['gpgconf', '--kill', 'all'],
                       env={**os.environ, 'GNUPGHOME': str(gnupghome)},
                       capture_output=True)


def _verify(tarball, signature, key_url, fingerprint, workdir, gnupghome, log):
    key = Path(workdir) / 'release-key.asc'
    if '://' in str(key_url):
        download(key_url, key, log)
    else:
        shutil.copyfile(key_url, key)
        log(f'release key from {key_url}')
    _gpg(gnupghome, '--import', str(key))
    primaries = imported_primaries(
        _gpg(gnupghome, '--with-colons', '--fingerprint').stdout)
    if primaries != [fingerprint]:
        raise WatchError(f'{key_url} imported {primaries or "no key"}, '
                         f'not exactly the pinned {fingerprint}')
    r = _gpg(gnupghome, '--status-fd', '1', '--verify', str(signature), str(tarball),
             check=False)
    got = validsig_primary(r.stdout)
    if r.returncode != 0 or got != fingerprint:
        raise WatchError(f'signature check failed for {tarball} (gpg exit '
                         f'{r.returncode}, VALIDSIG primary {got}):\n{r.stderr.strip()}')
    log(f'signature good: {Path(tarball).name}, primary key {fingerprint}')


def scratch_root(repo_root, scratch, version):
    """A directory check-patchfail.sh can treat as the repository root, with
    `version` and `version.android` both saying `version`. Everything else is
    a symlink into the checkout, which is left untouched."""
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    skip = {'version', 'version.android', '.git'}
    for entry in Path(repo_root).iterdir():
        name = entry.name
        if (name in skip or name.startswith('tmpdir92.')
                or (name.startswith('firefox-') and '.source.tar.xz' in name)):
            continue
        (scratch / name).symlink_to(entry.resolve())
    for name in ('version', 'version.android'):
        (scratch / name).write_text(version + '\n')
    return scratch


def run_check_patchfail(script, root, target, log=print):
    """Run the script for one target in `root`; returns (stdout, exit code).
    Afterwards no extraction may be left behind: the next target needs the
    room."""
    log(f'check-patchfail.sh --targets={target} ...')
    r = subprocess.run(['sh', str(script), f'--targets={target}'], cwd=root,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True)
    for left in Path(root).glob('tmpdir92.*'):
        log(f'removing leftover extraction {left}')
        shutil.rmtree(left, ignore_errors=True)
    if r.stderr.strip():
        log(r.stderr.rstrip())
    return r.stdout, r.returncode


def patchcheck(version, issue, sha, github, repo_root, workdir, *, dry_run=False,
               archive_base=ARCHIVE_BASE, key_url=None,
               fingerprint=MOZILLA_KEY_FINGERPRINT, check_script=None,
               local_tarball=None, run_link='', reports_dir=None, log=print,
               targets=PATCHCHECK_TARGETS, report=None):
    """Returns 'already-posted', 'would-post' or 'posted'. `report`, when
    given, is a dict that gets the comment as 'comment' once it is written."""
    parse_version(version)
    targets = tuple(targets)
    if not targets or any(t not in PATCHCHECK_TARGETS for t in targets):
        raise WatchError(f'targets must be among {PATCHCHECK_TARGETS}, got {targets}')
    if github is not None and issue:
        if already_posted(github.comments(issue), version, sha):
            log(f'#{issue} already has the patch check for {version} at {sha}')
            return 'already-posted'
    elif not dry_run:
        raise WatchError('posting needs GitHub access and --issue')
    else:
        log('dry run without GitHub access or issue: repost check skipped')

    workdir = Path(workdir)
    root = scratch_root(repo_root, workdir / 'root', version)
    free = shutil.disk_usage(root).free
    log(f'free disk at {root}: {free / 1024 ** 3:.1f} GB')
    if free < MIN_FREE_BYTES:
        raise WatchError(f'{free / 1024 ** 3:.1f} GB free, need '
                         f'{MIN_FREE_BYTES / 1024 ** 3:.0f} GB')

    name = f'firefox-{version}.source.tar.xz'
    tarball, signature = root / name, workdir / f'{name}.asc'
    if local_tarball:
        shutil.copyfile(f'{local_tarball}.asc', signature)
        local_tarball = Path(local_tarball).resolve()
        tarball.symlink_to(local_tarball)
        h = hashlib.sha256()
        with open(local_tarball, 'rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                h.update(chunk)
        digest = h.hexdigest()
    else:
        url = tarball_url(version, archive_base)
        download(f'{url}.asc', signature, log)
        digest = download(url, tarball, log)
    verify_tarball(tarball, signature,
                   key_url or str(Path(repo_root) / KEY_FILE), fingerprint, workdir, log)

    script = check_script or Path(repo_root) / 'scripts' / 'check-patchfail.sh'
    results = {}
    for target in targets:
        out, code = run_check_patchfail(script, root, target, log)
        if reports_dir:
            Path(reports_dir).mkdir(parents=True, exist_ok=True)
            (Path(reports_dir) / f'patchfail-{target}.out').write_text(out)
        results[target] = parse_report(out, code)
        log(f'{target}: {results[target]["status"]}, '
            f'{len(results[target]["failing"])} failing, '
            f'{results[target]["fuzz_hunks"]} fuzzed hunks')
        log(f'free disk: {shutil.disk_usage(root).free / 1024 ** 3:.1f} GB')
    tarball.unlink()

    body = patchcheck_comment(version, sha, results, run_link, digest, fingerprint)
    if report is not None:
        report['comment'] = body
    if dry_run:
        log(f'dry run: would comment on #{issue or "?"}:\n\n{body}')
        return 'would-post'
    # Re-read: a concurrent run (the workflow's concurrency group should
    # prevent one) may have posted while this one was patching.
    if already_posted(github.comments(issue), version, sha):
        log(f'#{issue} got the patch check for {version} at {sha} meanwhile')
        return 'already-posted'
    log(f'commented {github.create_comment(issue, body)}')
    return 'posted'


# --------------------------------------------------------------------------
# Mozilla security advisories (LW-M7-47). Source: Mozilla's own repository of
# the MFSA texts, github.com/mozilla/foundation-security-advisories,
# announce/<year>/mfsa<year>-<n>.yml -- the files www.mozilla.org's advisory
# pages are built from, readable through the GitHub API with the workflow's
# GITHUB_TOKEN, no scraping. The newest MFSA_LOOKBACK files are read each run.
#
# An advisory matters when its fixed_in names "Firefox <v>" or "Firefox for
# Android <v>" (not ESR, iOS, Focus, Thunderbird) with <v> newer than the
# Redoubt users run: the latest published GitHub release (android-<v>-<n>),
# or version.android when there is none. Then, once per advisory (a hidden
# marker):
#
#   - the open watcher issue for <v> (release or Firefox for Android) gets a
#     comment with the impact and the CVE list, the `security` label, a
#     `priority: critical|high` label for those impacts, a "[security: <impact>]"
#     title prefix, the owner assigned and mentioned, and a pin for
#     critical/high;
#   - without one (the release issue is closed, or <v> was never flagged
#     because a newer release overtook it) a separate issue opens, titled
#     "Mozilla security advisory MFSA <year>-<n> (fixed in Firefox <v>)",
#     labelled firefox-release + security, assigned, mentioned.
#
# The same run reminds: an open `security` issue whose version is still newer
# than the shipped release gets a comment mentioning the owner once every
# REMIND_AFTER_HOURS.
# --------------------------------------------------------------------------

MFSA_REPO = 'mozilla/foundation-security-advisories'
MFSA_LOOKBACK = 12
ADVISORY_PAGE = 'https://www.mozilla.org/en-US/security/advisories/{id}/'
_MFSA_NAME = re.compile(r'^mfsa(\d{4})-(\d+)\.yml$')
_FIXED_IN = re.compile(r'^Firefox(?: for Android)? (\d+(?:\.\d+){0,2})$')
_RELEASE_TAG = re.compile(r'^android-(\d+\.\d+(?:\.\d+)?)-(\d+)$')
_TITLE_VERSION = re.compile(r'Firefox (?:for Android )?(\d+\.\d+(?:\.\d+)?)\b')

_YAML_KEY = re.compile(r'^( *)([A-Za-z0-9_.-]+):(?:\s+(.*))?$')
_YAML_BLOCK = ('|', '>', '|-', '>-', '|+', '>+')


def _yaml_scalar(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] == "'":
        v = v[1:-1].replace("''", "'")
    elif len(v) >= 2 and v[0] == v[-1] == '"':
        v = v[1:-1].replace('\\"', '"').replace('\\\\', '\\')
    return ' '.join(v.split())


def parse_advisory(text, name=''):
    """The fields this script needs from one announce/*.yml file:
    {'id', 'announced', 'impact', 'title', 'fixed_in': [...],
     'cves': [{'id', 'impact', 'title'}]}.

    Standard library only, so a line reader for the subset of YAML these files
    use (top-level scalars, the fixed_in list, the advisories mapping and its
    block scalars). The test cross-checks it against PyYAML on real files;
    2024-2026 (272 files) read identically on 2026-10-09."""
    out = {'id': name, 'announced': '', 'impact': '', 'title': '', 'fixed_in': [],
           'cves': []}
    section = cve = block = capture = None
    cve_indent = field_indent = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        indent = len(line) - len(line.lstrip(' '))
        if block is not None:
            if indent > block:
                if capture is not None:
                    target, key = capture
                    target[key] = ' '.join((target[key] + ' ' + line).split())
                continue
            block = capture = None
        if section == 'fixed_in' and line.lstrip().startswith('- '):
            out['fixed_in'].append(_yaml_scalar(line.lstrip()[2:]))
            continue
        m = _YAML_KEY.match(line)
        if not m:
            continue
        ind, key, val = len(m.group(1)), m.group(2), m.group(3)
        target = None
        if ind == 0:
            section, cve = key, None
            target = out if key in ('announced', 'impact', 'title') else None
        elif section == 'advisories':
            if cve_indent is None:
                cve_indent = ind
            if ind == cve_indent:
                cve = {'id': key, 'impact': '', 'title': ''}
                out['cves'].append(cve)
                field_indent = None
            elif cve is not None and ind > cve_indent:
                if field_indent is None:
                    field_indent = ind
                if ind == field_indent and key in ('impact', 'title'):
                    target = cve
        if val is not None and val.strip() in _YAML_BLOCK:
            block = ind
            if target is not None:
                target[key] = ''
                capture = (target, key)
        elif target is not None and val is not None:
            target[key] = _yaml_scalar(val)
    return out


def normalize_version(text):
    """'157' -> '157.0' (MFSA spells a major without .0); '157.0.1' unchanged."""
    return text if '.' in text else f'{text}.0'


def advisory_versions(adv):
    """Firefox / Firefox for Android versions in fixed_in, normalized."""
    out = []
    for entry in adv['fixed_in']:
        m = _FIXED_IN.match(entry.strip())
        if m:
            out.append(normalize_version(m.group(1)))
    return out


def advisory_impact(adv):
    """The highest of the advisory's own impact and its CVEs'."""
    impacts = [adv.get('impact', '')] + [c['impact'] for c in adv['cves']]
    return max((i for i in impacts if i in IMPACT_ORDER),
               key=IMPACT_ORDER.get, default='unknown')


def mfsa_label(adv_id):
    """'mfsa2026-104' -> 'MFSA 2026-104'."""
    return adv_id.upper().replace('MFSA', 'MFSA ', 1)


def advisory_marker(adv_id):
    return f'<!-- redoubt-mfsa id={adv_id} -->'


def advisory_issue_title(adv, version):
    return f'Mozilla security advisory {mfsa_label(adv["id"])} (fixed in Firefox {version})'


def security_title(title, impact):
    return f'[security: {impact}] {strip_prefix(title)}'


def shipped_release(tag, android):
    """(version, description) of what Redoubt users run: the latest GitHub
    release's tag, android-<v>-<n>, else version.android."""
    m = _RELEASE_TAG.match(tag or '')
    if m:
        return m.group(1), f'Redoubt {m.group(1)}-{m.group(2)} (release `{tag}`)'
    return android, f'`version.android` {android} (no published release found)'


def _cve_lines(adv, limit=60):
    cves = sorted(adv['cves'], key=lambda c: -IMPACT_ORDER.get(c['impact'], 0))
    lines = [f'- **{c["impact"] or "?"}** `{c["id"]}`: {c["title"]}' for c in cves[:limit]]
    if len(cves) > limit:
        lines.append(f'- ... and {len(cves) - limit} more (see the advisory)')
    return lines


def advisory_text(adv, version, shipped_desc, android):
    """The shared part of the advisory comment and the advisory issue. Pure."""
    impact = advisory_impact(adv)
    counts = {}
    for c in adv['cves']:
        counts[c['impact'] or '?'] = counts.get(c['impact'] or '?', 0) + 1
    tally = ', '.join(f'{n} {i}' for i, n in sorted(
        counts.items(), key=lambda kv: -IMPACT_ORDER.get(kv[0], 0)))
    return [
        f'**{mfsa_label(adv["id"])}**: {adv["title"]} (announced {adv["announced"]}).',
        f'Highest impact: **{impact}**. Fixed in: {", ".join(adv["fixed_in"])}. '
        f'CVEs: {len(adv["cves"])}' + (f' ({tally})' if tally else '') + '.',
        f'Advisory: {ADVISORY_PAGE.format(id=adv["id"])}',
        '',
        f'Users run {shipped_desc}, older than Firefox {version}; '
        + (f'`version.android` on the default branch is `{android}`, older too. '
           if is_newer(version, android) else
           f'`version.android` on the default branch is already `{android}` '
           f'(rebased, not yet released). ')
        + f'Every CVE below that reaches Gecko or Fenix code Redoubt ships is '
        f'open in the published APK until a release at or past {version} is '
        f'signed and published. Response targets: docs/android/SECURITY.md.',
        '',
        '<details><summary>CVEs</summary>',
        '',
        *_cve_lines(adv),
        '',
        '</details>',
    ]


def advisory_comment(adv, version, shipped_desc, android, notify):
    return (advisory_marker(adv['id']) + '\n'
            + mention_line(notify, f'Mozilla published a security advisory for this '
                                   f'release (impact {advisory_impact(adv)}).')
            + '\n'.join(advisory_text(adv, version, shipped_desc, android)) + '\n')


def advisory_issue_body(adv, version, shipped_desc, android, notify, open_issues, repo,
                        ref='main'):
    rebase = f'https://github.com/{repo}/blob/{ref}/docs/android/REBASE.md'
    lines = [advisory_marker(adv['id'])]
    text = mention_line(notify, 'the shipped Redoubt is behind a Mozilla security '
                                'advisory; you are assigned.')
    lines += [text.rstrip('\n'), ''] if text else []
    lines += advisory_text(adv, version, shipped_desc, android)
    lines += ['', '## What to do', '']
    if open_issues:
        lines.append('Open release issues of the watcher: '
                     + ', '.join(f'#{n}' for n in open_issues)
                     + '. Rebasing onto any of them at or past Firefox '
                     + f'{version} closes this.')
    else:
        lines.append(f'No open release issue covers Firefox {version} (it was '
                     f'closed, or a newer release overtook it before it was '
                     f'flagged). Rebase onto the latest Firefox release '
                     f'([REBASE.md]({rebase})); it carries these fixes.')
    lines += ['', 'Close this issue when a signed Redoubt at or past Firefox '
              f'{version} is published.', '',
              '<sub>Opened by `scripts/firefox-release-watch.py` from '
              f'{MFSA_REPO}. One issue per advisory.</sub>']
    return '\n'.join(lines) + '\n'


def fetch_advisories(github, now_year, lookback=MFSA_LOOKBACK, fetch_text=None, log=print):
    """The newest `lookback` advisories, parsed, oldest first. Reads this
    year's directory, and last year's too when this one has fewer."""
    fetch_text = fetch_text or _fetch_text
    files = []
    for year in (now_year, now_year - 1):
        for f in github.list_dir(MFSA_REPO, f'announce/{year}'):
            m = _MFSA_NAME.match(f['name'])
            if m:
                files.append(((int(m.group(1)), int(m.group(2))), f))
        if len(files) >= lookback:
            break
    files.sort(key=lambda x: x[0])
    out = []
    for _, f in files[-lookback:]:
        out.append(parse_advisory(fetch_text(f['download_url']), f['name'][:-len('.yml')]))
    log(f'advisories read: {", ".join(a["id"] for a in out) or "none"}')
    return out


def _fetch_text(url):
    try:
        with urllib.request.urlopen(_request(url), timeout=TIMEOUT) as r:
            return r.read().decode()
    except urllib.error.HTTPError as e:
        raise http_error(f'cannot read {url}: HTTP {e.code}', e.code) from e
    except (urllib.error.URLError, OSError, UnicodeDecodeError) as e:
        raise TransientError(f'cannot read {url}: {e}') from e


def load_advisories_dir(path):
    """Advisories from local files (tests, and --advisories-dir by hand)."""
    files = []
    for f in Path(path).iterdir():
        m = _MFSA_NAME.match(f.name)
        if m:
            files.append(((int(m.group(1)), int(m.group(2))), f))
    return [parse_advisory(f.read_text(), f.name[:-len('.yml')])
            for _, f in sorted(files, key=lambda x: x[0])]


def _upgrade(github, issue, adv, impact, notify, dry_run, log):
    """Labels, title prefix, assignee and pin on an existing issue."""
    labels = [SECURITY_LABEL] + ([PRIORITY_LABELS[impact]] if impact in PRIORITY_LABELS else [])
    title = security_title(issue['title'], impact)
    if dry_run:
        log(f'dry run: would label #{issue["number"]} {labels}, retitle it {title!r}'
            + (f', assign {notify}' if notify else '')
            + (', pin it' if impact in PRIORITY_LABELS else ''))
        return
    github.ensure_label(SECURITY_LABEL, SECURITY_LABEL_COLOR, SECURITY_LABEL_DESCRIPTION)
    if impact in PRIORITY_LABELS:
        github.ensure_label(PRIORITY_LABELS[impact], PRIORITY_LABEL_COLOR,
                            PRIORITY_LABEL_DESCRIPTION)
    github.add_labels(issue['number'], labels)
    # Never downgrade: a later "moderate" advisory leaves "[security: high]".
    old = issue['title']
    old_impact = old[len('[security: '):old.index(']')] if old.startswith('[security: ') else ''
    if IMPACT_ORDER.get(impact, 0) >= IMPACT_ORDER.get(old_impact, -1) and title != old:
        github.edit_issue(issue['number'], title=title)
    if notify and notify not in issue.get('assignees', []):
        github.add_assignees(issue['number'], [notify])
    if impact in PRIORITY_LABELS:
        if github.pin_issue(issue.get('node_id', '')):
            log(f'pinned #{issue["number"]}')
        else:
            log(f'warning: could not pin #{issue["number"]} (three pinned already, '
                f'or the token may not pin); the labels and the mention still stand')


def run_advisories(root, advisories, github, repo, shipped_tag, dry_run=False, log=print,
                   notify=None, events=None, ref='main'):
    """Returns [(advisory id, outcome)]; outcome is 'not-affected',
    'known', 'upgraded'/'would-upgrade' or 'opened'/'would-open'."""
    events = [] if events is None else events
    android = read_track(root, 'version.android')
    shipped, shipped_desc = shipped_release(shipped_tag, android)
    log(f'shipped: {shipped_desc}')
    issues = github.issues(LABEL) if github is not None else []
    results = []
    for adv in advisories:
        newer = sorted((v for v in advisory_versions(adv) if is_newer(v, shipped)),
                       key=parse_version)
        if not newer:
            results.append((adv['id'], 'not-affected'))
            continue
        version, impact = newer[0], advisory_impact(adv)
        log(f'{adv["id"]}: fixed in Firefox {version}, impact {impact}; '
            f'shipped {shipped} is behind')
        bases = (issue_title(version), android_issue_title(version))
        release = [i for i in issues if i['state'] == 'open'
                   and any(title_matches(i['title'], b) for b in bases)]
        if release:
            issue = release[0]
            if github is not None and any(advisory_marker(adv['id']) in c
                                          for c in github.comments(issue['number'])):
                results.append((adv['id'], 'known'))
                continue
            body = advisory_comment(adv, version, shipped_desc, android, notify)
            if dry_run:
                log(f'dry run: would comment on #{issue["number"]}:\n\n{body}')
                _upgrade(github, issue, adv, impact, notify, True, log)
                results.append((adv['id'], 'would-upgrade'))
                continue
            url = github.create_comment(issue['number'], body)
            _upgrade(github, issue, adv, impact, notify, False, log)
            log(f'advisory on {url}')
            events.append({'title': f'{mfsa_label(adv["id"])} ({impact}): Firefox {version}',
                           'message': f'Redoubt {shipped} is behind. #{issue["number"]}',
                           'click': url, 'impact': impact})
            results.append((adv['id'], 'upgraded'))
            continue

        title = advisory_issue_title(adv, version)
        if (any(title_matches(i['title'], title) for i in issues)
                or (github is not None and matching_issues(github, title, log))):
            results.append((adv['id'], 'known'))
            continue
        open_numbers = [i['number'] for i in issues if i['state'] == 'open'
                        and not title_matches(i['title'], title)
                        and _TITLE_VERSION.search(i['title'])
                        and not is_newer(version, _TITLE_VERSION.search(i['title']).group(1))]
        body = advisory_issue_body(adv, version, shipped_desc, android, notify,
                                   open_numbers, repo, ref)
        if dry_run or github is None:
            if not dry_run:
                raise WatchError('no GitHub access and not a dry run')
            log(f'dry run: would open {security_title(title, impact)!r}:\n\n{body}')
            results.append((adv['id'], 'would-open'))
            continue
        github.ensure_label(LABEL)
        url, number = github.create_issue(security_title(title, impact), body, LABEL,
                                          assignees=[notify] if notify else ())
        issues.append({'title': security_title(title, impact), 'number': number,
                       'state': 'open', 'assignees': [notify] if notify else [],
                       'labels': [LABEL], 'node_id': ''})
        _upgrade(github, issues[-1], adv, impact, None, False, log)
        log(f'opened {url}')
        events.append({'title': f'{mfsa_label(adv["id"])} ({impact}): Firefox {version}',
                       'message': f'Redoubt {shipped} is behind. New issue #{number}',
                       'click': url, 'impact': impact})
        results.append((adv['id'], 'opened'))
    return results


def _parse_time(text):
    return datetime.datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ').replace(
        tzinfo=datetime.timezone.utc)


REMINDER_MARKER = '<!-- redoubt-reminder -->'


def run_reminders(root, github, shipped_tag, now, dry_run=False, log=print, notify=None,
                  events=None):
    """Remind on every open `security` watcher issue whose Firefox version
    the shipped release is still behind, once per REMIND_AFTER_HOURS (counted
    from the issue's creation, the last reminder or the last advisory comment). Returns the issue
    numbers reminded (or that would be)."""
    events = [] if events is None else events
    shipped, shipped_desc = shipped_release(shipped_tag, read_track(root, 'version.android'))
    out = []
    for issue in github.issues(LABEL):
        if issue['state'] != 'open' or SECURITY_LABEL not in issue.get('labels', []):
            continue
        m = _TITLE_VERSION.search(issue['title'])
        if not m or not is_newer(m.group(1), shipped):
            continue
        stamps = [issue.get('created_at') or '']
        # Any ping that mentioned the owner counts: a reminder, or an
        # advisory comment (so the run that labels an issue does not also
        # remind on it).
        stamps += [c['created_at'] for c in github.comments_full(issue['number'])
                   if REMINDER_MARKER in c['body'] or '<!-- redoubt-mfsa ' in c['body']]
        stamps = [_parse_time(t) for t in stamps if t]
        if not stamps:
            continue
        age = now - max(stamps)
        if age < datetime.timedelta(hours=REMIND_AFTER_HOURS):
            continue
        opened = _parse_time(issue['created_at']) if issue.get('created_at') else None
        days = f'{(now - opened).days} day(s)' if opened else 'a while'
        body = (REMINDER_MARKER + '\n'
                + mention_line(notify, f'reminder: open for {days}; {shipped_desc} is '
                                       f'still behind Firefox {m.group(1)}.')
                + 'This comment repeats every '
                f'{REMIND_AFTER_HOURS} h while the issue is open and the shipped '
                f'release is behind. Close the issue once a fixed release is out, '
                f'or note here why it does not apply.\n')
        if dry_run:
            log(f'dry run: would remind on #{issue["number"]}:\n\n{body}')
        else:
            url = github.create_comment(issue['number'], body)
            log(f'reminded on {url}')
            events.append({'title': f'Still behind Firefox {m.group(1)}',
                           'message': f'#{issue["number"]} open for {days}', 'click': url,
                           'impact': 'high'})
        out.append(issue['number'])
    return out


def notify_test(github, notify, now, dry_run=False, log=print):
    """Open an issue assigned to `notify` that mentions them, then close it:
    one end-to-end check of the notification path. Returns its URL."""
    title = f'Release watch notification test ({now:%Y-%m-%d %H:%M} UTC)'
    body = (mention_line(notify, 'this is a test of the release watcher\'s '
                                 'notification path. If this reached your email or '
                                 'phone, the path works.')
            + 'Closed right after opening; nothing to do. '
            'docs/android/RELEASE-WATCH.md, "Notification".\n')
    if dry_run:
        log(f'dry run: would open and close {title!r} assigned to {notify}:\n\n{body}')
        return ''
    github.ensure_label(TEST_LABEL, 'cccccc', 'Notification test of the release watcher')
    url, number = github.create_issue(title, body, TEST_LABEL,
                                      assignees=[notify] if notify else ())
    github.edit_issue(number, state='closed', state_reason='not_planned')
    log(f'opened and closed {url}')
    return url


# --------------------------------------------------------------------------
# autobuild (LW-M7-47): a candidate build for a flagged release, so a
# signing bundle is ready when the owner looks. Run by the workflow's third
# job after `patchcheck`, one release at a time. Usage:
#
#   firefox-release-watch.py autobuild --version 157.0.1 --issue 3 \
#       --targets desktop,android --base-sha <main sha> [--dry-run]
#
# 1. Once per version, ever: if the issue already carries an autobuild
#    marker for <v>, stop.
# 2. Read the patch check's verdicts for <v> at --base-sha from the issue
#    (patchcheck_result_marker). No verdict: stop (the check did not finish,
#    or was posted before LW-M7-47; the next run, on a new commit, has one).
#    android not 'pass': comment once which target failed (the patch-check
#    comment above lists the patches), mention the owner, stop.
# 3. Box B builds one thing at a time: if android-release.yaml or
#    android-test.yaml has a run queued or in progress, stop; the next run
#    retries.
# 4. Branch auto/firefox-<v> (created at --base-sha plus one commit setting
#    version.android/release.android, and version/release when desktop is in
#    the targets, to <v> / 1; reused if it already exists).
# 5. Choose build_date (section "Build date and versionCode" below): an
#    hour strictly between the Latest release's build hour and the oldest
#    published release of a newer Firefox major (a beta), read from the
#    releases' notes. If no hour fits, or a bound cannot be read, comment
#    once why, mention the owner (who picks the date and dispatches by hand),
#    and stop; that version is then never built by the watcher.
# 6. Dispatch android-release.yaml on that branch: mode=full,
#    update_check=true, build_date=<5>. The workflow builds and gates
#    UNSIGNED APKs only; nothing here signs, publishes or merges.
# 7. Comment: branch, build date and why, the versionCodes, the runs page,
#    what the owner does next.
#
# Permissions: this job alone gets contents: write (the branch, through the
# git data API) and actions: write (the dispatch). A push or ref made with
# GITHUB_TOKEN starts no workflow, which is why the dispatch is explicit
# (GitHub exempts workflow_dispatch from that rule).
# --------------------------------------------------------------------------

AUTOBUILD_POLICIES = ('dot', 'all', 'off')
BUILD_WORKFLOW = 'android-release.yaml'
BOXB_WORKFLOWS = ('android-release.yaml', 'android-test.yaml')
BUSY_STATUSES = ('queued', 'in_progress', 'waiting', 'requested', 'pending')


# --------------------------------------------------------------------------
# Build date and versionCode. Fenix's versionCode is
#
#   0x78200000 | (hours since 2014-12-28 00:00 UTC) << 3 | ABI bits
#
# (scripts/android-aab.py version_code; ABI bits: armeabi-v7a 0, arm64-v8a 2,
# x86_64 6, universal 7), so it is fixed by the build HOUR of MOZ_BUILD_DATE
# and grows by 8 per hour. Android installs, Obtainium and the update check
# all take a higher versionCode as newer. A dot-release candidate built
# "now" while a beta of the next major is out (158.0-1 Beta 1, built
# 20261007050000) would get a higher code than that beta, and beta testers,
# whose profiles are already 158, could be offered it: a downgrade of Firefox
# under their profile. The precedent is 157.0.1-1
# (docs/android/evidence/lw-m7-01/release-157.0.1/README.md, "Build date and
# versionCodes"): 20261006180000, between 157.0-3 (20261006090000) and 158.0-1
# Beta 1 (20261007050000).
#
# The rule (choose_build_date):
#
#   lower  the build hour of the release GitHub marks Latest (the stable
#          users run). No Latest release at all: no lower bound.
#   upper  the earliest build hour among the published (non-draft)
#          releases, prerelease or not, of a Firefox major newer than the
#          candidate's (158.0-1 Beta 1 for a 157.0.x candidate). None: no
#          upper bound.
#   The candidate's hour must be > lower, < upper, not after this run's hour
#   (no build date in the future), and not one any readable release (or
#   REJECTED_BUILD_DATES) already used.
#   - No upper bound: this run's hour (as build_date=now always did, minus
#     the minutes, so the stated versionCodes are exact).
#   - Otherwise: the middle hour of the open window (rounded down), so a
#     later dot release still finds room on both sides; the nearest unused
#     hour if that one is taken.
#   - Window empty, or a bound release whose build date cannot be read: no
#     dispatch; the issue says why and the owner picks the date.
#
# Where a release's build hour comes from: its notes. Every release since
# 157.0-2 states it in the Provenance section, "with MOZ_BUILD_DATE
# YYYYMMDDHHMMSS"; some also state "versionCodes N-M". The asset names
# (fenix-<abi>-release.apk) carry no code, and reading the APKs would mean
# downloading ~400 MB per release, so the notes are the source. When both are
# stated they must agree (the hour recomputed from the lowest code); if they
# do not, or neither is there, the date is unreadable and only matters if
# that release is one of the two bounds.
# --------------------------------------------------------------------------

FENIX_EPOCH = datetime.datetime(2014, 12, 28, tzinfo=datetime.timezone.utc)
VERSION_CODE_BASE = 0x78200000
ABI_BITS = {'armeabi-v7a': 0, 'arm64-v8a': 2, 'x86_64': 6, 'universal': 7}
# Build dates of builds that were rejected and must never be reused
# (memory and DISTRIBUTION.md: run 37234607054, 2026-10-04).
REJECTED_BUILD_DATES = ('20261004200000',)
_BUILD_DATE = re.compile(r'MOZ_BUILD_DATE[`*\s=:]*(\d{14})\b')
_VERSION_CODES = re.compile(r'versionCodes?[`*\s:]*(\d{10})\b')
_ANY_RELEASE_TAG = re.compile(
    r'^android-(\d+\.\d+(?:\.\d+)?(?:esr)?)-(\d+)(?:-beta\.(\d+))?$')


def build_hour(build_date):
    """'20261006090000' -> hours since Fenix's epoch (minutes ignored, as
    Fenix does)."""
    t = datetime.datetime.strptime(build_date, '%Y%m%d%H%M%S').replace(
        tzinfo=datetime.timezone.utc)
    return int((t - FENIX_EPOCH).total_seconds() // 3600)


def hour_date(hour):
    """Inverse of build_hour: the build date at the start of that hour."""
    return (FENIX_EPOCH + datetime.timedelta(hours=hour)).strftime('%Y%m%d%H%M%S')


def version_codes(hour):
    """{abi: versionCode} for a build hour."""
    return {abi: VERSION_CODE_BASE | (hour << 3) | bits for abi, bits in ABI_BITS.items()}


def code_hour(code):
    """The build hour a versionCode was made from."""
    return (code - VERSION_CODE_BASE) >> 3


def release_build_hour(body):
    """The build hour stated in a release's notes, or None. MOZ_BUILD_DATE
    first; a "versionCodes N" range alone also works; both stated and
    disagreeing is None (unreadable), not a guess."""
    dates = {build_hour(m.group(1)) for m in _BUILD_DATE.finditer(body or '')
             if _valid_date(m.group(1))}
    codes = {code_hour(int(m.group(1))) for m in _VERSION_CODES.finditer(body or '')
             if int(m.group(1)) >= VERSION_CODE_BASE}
    if len(dates) > 1 or len(codes) > 1:
        return None
    if dates and codes and dates != codes:
        return None
    return next(iter(dates or codes), None)


def _valid_date(text):
    try:
        datetime.datetime.strptime(text, '%Y%m%d%H%M%S')
        return True
    except ValueError:
        return False


def release_tag_version(tag):
    """'android-158.0-1-beta.1' -> '158.0'; None for any other tag."""
    m = _ANY_RELEASE_TAG.match(tag or '')
    return m.group(1) if m else None


def _codes_text(hour):
    c = version_codes(hour)
    return f'{c["armeabi-v7a"]}-{c["universal"]}'


def choose_build_date(version, releases, latest_tag, now):
    """(build_date or None, explanation). `releases` as GitHub.releases()
    returns them, `latest_tag` the tag GitHub marks Latest ('' for none),
    `now` this run's time. Pure. The rule is in the section comment above."""
    major = parse_version(version)[0]
    now_hour = int((now - FENIX_EPOCH).total_seconds() // 3600)
    published = [r for r in releases if not r.get('draft')]
    used = {build_hour(d) for d in REJECTED_BUILD_DATES}
    for r in published:
        h = release_build_hour(r.get('body', ''))
        if h is not None:
            used.add(h)

    lower = lower_desc = None
    if latest_tag:
        rel = next((r for r in published if r['tag'] == latest_tag), None)
        lower = release_build_hour(rel['body']) if rel else None
        if lower is None:
            return None, (f'the build date of the Latest release `{latest_tag}` cannot be '
                          f'read from its notes (no "MOZ_BUILD_DATE YYYYMMDDHHMMSS" in its '
                          f'Provenance section), so the lower bound of the versionCode is '
                          f'unknown')
        lower_desc = (f'`{latest_tag}` (Latest), built {hour_date(lower)}, versionCodes '
                      f'{_codes_text(lower)}')

    upper = upper_desc = None
    for r in published:
        v = release_tag_version(r['tag'])
        if not v or parse_version(v)[0] <= major:
            continue
        h = release_build_hour(r['body'])
        if h is None:
            return None, (f'`{r["tag"]}` is a published release of Firefox {v}, a newer '
                          f'major than {version}, and its build date cannot be read from '
                          f'its notes, so the upper bound of the versionCode is unknown')
        if upper is None or h < upper:
            upper = h
            upper_desc = (f'`{r["tag"]}` ({"prerelease" if r.get("prerelease") else "release"}'
                          f' of Firefox {v}), built {hour_date(h)}, versionCodes '
                          f'{_codes_text(h)}')

    lo = lower if lower is not None else -1
    bounds = (f'above {lower_desc}' if lower_desc else 'no Latest release, so no lower bound')
    bounds += (f'; below {upper_desc}' if upper_desc
               else f'; no published release of a Firefox major newer than {major}')
    if upper is None:
        if now_hour > lo and now_hour not in used:
            return hour_date(now_hour), (f'this run\'s hour, {bounds}')
        return None, (f'this run\'s hour {hour_date(now_hour)} is not above the lower bound '
                      f'or is already used ({bounds})')
    hi = min(upper, now_hour + 1)  # exclusive; never a build date in the future
    if lower is None:
        lo = max(lo, hi - 24 * 366)  # no Latest release: look back a year at most
    free = [h for h in range(lo + 1, hi) if h not in used]
    if not free:
        return None, (f'no unused hour lies strictly between the bounds and not after '
                      f'this run ({bounds})')
    mid = lo + (hi - lo) // 2 if lower is not None else hi - 1
    pick = min(free, key=lambda h: (abs(h - mid), h))
    return hour_date(pick), (f'the middle of the free window, {bounds}; it leaves room '
                             f'for another dot release on either side')


def autobuild_branch(version):
    return f'auto/firefox-{version}'


def autobuild_marker(version):
    return f'<!-- redoubt-autobuild version={version} -->'


def autobuild_nodate_marker(version):
    return f'<!-- redoubt-autobuild-nodate version={version} -->'


def autobuild_blocked_marker(version, sha):
    return f'<!-- redoubt-autobuild-blocked version={version} sha={sha} -->'


def autobuild_eligible(version, current, policy):
    """Whether a flagged release gets a candidate build. 'dot': a dot
    release on the major Redoubt is on (157.0.1 while version.android is
    157.0); 'all': also a new major; 'off': never."""
    if policy not in AUTOBUILD_POLICIES:
        raise WatchError(f'autobuild policy must be one of {AUTOBUILD_POLICIES}, '
                         f'got {policy!r}')
    if policy == 'off' or not is_newer(version, current):
        return False
    if policy == 'all':
        return True
    v, c = parse_version(version), parse_version(current)
    return v[0] == c[0] and v[1:] != (0, 0)


def autobuild_jobs(checks, current, policy):
    """The workflow's autobuild matrix: the patch-check entries that get a
    candidate build. Never a manual (dry-run) entry, never one without an
    issue."""
    return [dict(j) for j in checks
            if j.get('label') != 'manual' and j.get('issue')
            and autobuild_eligible(j['version'], current, policy)]


def autobuild_files(version, targets):
    files = {'version.android': f'{version}\n', 'release.android': '1\n'}
    if 'desktop' in targets:
        files.update({'version': f'{version}\n', 'release': '1\n'})
    return files


def autobuild_commit_message(version, base_sha, issue):
    return (f'Firefox {version}: bump the version files (candidate build)\n\n'
            f'Made by scripts/firefox-release-watch.py autobuild for #{issue}, on top '
            f'of {base_sha}. Version files only; the rebase itself (REBASE.md '
            f'§5-§10) and the signed release are still the owner\'s. Not for '
            f'merging as is.\n')


def autobuild_comment(version, branch, commit_sha, build_date, runs_url, repo, notify,
                      targets, why=''):
    return (autobuild_marker(version) + '\n'
            + mention_line(notify, f'a candidate build of Firefox {version} is running.')
            + f'### Candidate build dispatched\n\n'
            f'- Branch: [`{branch}`](https://github.com/{repo}/tree/{branch}) at '
            f'`{commit_sha[:12]}`: `version.android` = `{version}`, `release.android` = `1`'
            + (' (and desktop\'s `version` / `release`)' if 'desktop' in targets else '')
            + '; nothing else changed.\n'
            f'- Workflow: `{BUILD_WORKFLOW}`, `mode=full`, `update_check=true`, '
            f'`build_date={build_date}` (box B). Runs: {runs_url}\n'
            f'- Build date `{build_date}`: {why or "chosen by the watcher"}. versionCodes '
            f'{_codes_text(build_hour(build_date))} (armeabi-v7a to universal; '
            f'scripts/android-aab.py versioncode).\n'
            f'- The artifact is **unsigned** (`redoubt-android-unsigned`: the four APKs, '
            f'output-metadata.json, SHA256SUMS). Nothing was signed, published or merged.\n\n'
            f'Next, by hand: download the artifact, run the acceptance on the emulator '
            f'(docs/android/SMOKE.md), sign offline (docs/android/SIGNING.md, '
            f'DISTRIBUTION.md "Publishing a release with the check"), publish, then '
            f'land the bump on main (signed commits) and close this issue. If the '
            f'build fails, the run log says where; the branch stays for the rebase.\n\n'
            f'<sub>Posted by `scripts/firefox-release-watch.py autobuild`. Once per '
            f'version: to build again, dispatch `{BUILD_WORKFLOW}` on the branch by '
            f'hand.</sub>\n')


def autobuild_nodate_comment(version, why, notify):
    return (autobuild_nodate_marker(version) + '\n'
            + mention_line(notify, f'no candidate build of Firefox {version}: no safe '
                                   f'build date.')
            + f'The patch check passed, but the watcher found no build date it may use: '
            f'{why}.\n\n'
            f'The versionCode comes from the build hour (+8 per hour), so the build must '
            f'sit above the Latest release and below every published build of a newer '
            f'Firefox major (a beta), or beta testers could be offered an older Firefox '
            f'under their newer profile. **The owner must pick the build date** and '
            f'dispatch by hand (precedent: docs/android/evidence/lw-m7-01/release-157.0.1/'
            f'README.md, "Build date and versionCodes"):\n\n'
            f'```\ngh workflow run {BUILD_WORKFLOW} --ref {autobuild_branch(version)} '
            f'-f mode=full -f update_check=true -f build_date=YYYYMMDDHH0000\n```\n\n'
            f'The watcher did not create `{autobuild_branch(version)}`: make it from '
            f'main with `version.android` = `{version}` and `release.android` = `1` '
            f'first. `scripts/android-aab.py versioncode YYYYMMDDHH0000 universal` prints '
            f'the code a date gives. The watcher will not build this version by '
            f'itself any more (once per version, like the build), so a hand dispatch '
            f'never races it.\n')


def autobuild_blocked_comment(version, sha, results, notify):
    bad = ', '.join(f'{t}: {r}' for t, r in results.items() if r != 'pass')
    return (autobuild_blocked_marker(version, sha) + '\n'
            + mention_line(notify, f'no candidate build of Firefox {version}.')
            + f'The patch check at `{sha[:12]}` did not pass ({bad}); the comment '
            f'above lists the failing patches. Fix them on main (REBASE.md §5); '
            f'the next run checks the new commit and builds if it passes. This '
            f'issue stays assigned until then.\n')


def boxb_busy(github, workflows=BOXB_WORKFLOWS):
    """The first queued or running run on box B's workflows, or None."""
    for wf in workflows:
        for status in BUSY_STATUSES:
            runs = github.workflow_runs(wf, status)
            if runs:
                return {**runs[0], 'workflow': wf}
    return None


def autobuild(version, issue, targets, base_sha, github, repo, now, *, dry_run=False,
              notify=None, log=print, events=None):
    """Returns 'already-dispatched', 'no-result', 'blocked',
    'already-blocked', 'busy', 'no-build-date', 'would-dispatch' or
    'dispatched'."""
    events = [] if events is None else events
    parse_version(version)
    comments = github.comments(issue)
    if any(autobuild_marker(version) in c for c in comments):
        log(f'#{issue} already has the candidate build of {version}')
        return 'already-dispatched'
    if any(autobuild_nodate_marker(version) in c for c in comments):
        log(f'#{issue} says no build date fits {version}; the owner picks it')
        return 'no-build-date'
    results = patchcheck_results(comments, version, base_sha)
    if results is None:
        log(f'#{issue} has no patch-check verdict for {version} at {base_sha[:12]}; '
            f'no build')
        return 'no-result'
    log(f'patch check at {base_sha[:12]}: {results}')
    if results.get('android') != 'pass':
        if any(autobuild_blocked_marker(version, base_sha) in c for c in comments):
            return 'already-blocked'
        body = autobuild_blocked_comment(version, base_sha, results, notify)
        if dry_run:
            log(f'dry run: would comment on #{issue}:\n\n{body}')
        else:
            url = github.create_comment(issue, body)
            log(f'commented {url}')
            events.append({'title': f'Firefox {version}: patches fail, no build',
                           'message': f'#{issue}', 'click': url, 'impact': 'high'})
        return 'blocked'
    busy = boxb_busy(github)
    if busy:
        log(f'box B is busy ({busy["workflow"]} run {busy["id"]}, {busy["status"]} on '
            f'{busy["head_branch"]}): not dispatching; the next run retries')
        return 'busy'
    latest_tag = github.latest_release()
    build_date, why = choose_build_date(version, github.releases(), latest_tag, now)
    if build_date is None:
        log(f'no build date for {version}: {why}')
        body = autobuild_nodate_comment(version, why, notify)
        if dry_run:
            log(f'dry run: would comment on #{issue}:\n\n{body}')
        else:
            url = github.create_comment(issue, body)
            log(f'commented {url}')
            events.append({'title': f'Firefox {version}: pick a build date',
                           'message': f'No safe versionCode window. #{issue}',
                           'click': url, 'impact': 'high'})
        return 'no-build-date'
    log(f'build_date {build_date}: {why}')
    branch = autobuild_branch(version)
    runs_url = (f'https://github.com/{repo}/actions/workflows/{BUILD_WORKFLOW}'
                f'?query=branch%3A{urllib.parse.quote(branch, safe="")}')
    files = autobuild_files(version, targets)
    if dry_run:
        log(f'dry run: would create {branch} at {base_sha[:12]} + {sorted(files)}, '
            f'dispatch {BUILD_WORKFLOW} mode=full update_check=true '
            f'build_date={build_date}, and comment on #{issue}')
        return 'would-dispatch'
    sha = github.branch_sha(branch)
    if sha:
        log(f'{branch} exists at {sha[:12]}; building it as it is')
    else:
        sha = github.commit_files(base_sha, files,
                                  autobuild_commit_message(version, base_sha, issue))
        github.create_branch(branch, sha)
        log(f'created {branch} at {sha[:12]}')
    github.dispatch(BUILD_WORKFLOW, branch,
                    {'mode': 'full', 'update_check': 'true', 'build_date': build_date})
    log(f'dispatched {BUILD_WORKFLOW} on {branch}, build_date {build_date}')
    url = github.create_comment(issue, autobuild_comment(version, branch, sha, build_date,
                                                         runs_url, repo, notify, targets, why))
    log(f'commented {url}')
    events.append({'title': f'Firefox {version}: candidate build started',
                   'message': f'{branch}, #{issue}', 'click': url, 'impact': 'default'})
    return 'dispatched'


def send_events(events, env=None, log=print):
    """The optional ntfy channel: one push per event, only when the
    repository secret RELEASE_WATCH_NTFY_URL reaches the step."""
    env = os.environ if env is None else env
    url = env.get('RELEASE_WATCH_NTFY_URL', '').strip()
    if not url or not events:
        return 0
    sent = 0
    for e in events:
        prio = {'critical': 'urgent', 'high': 'high'}.get(e.get('impact'), 'default')
        sent += ntfy_send(url, e['title'], e['message'], e.get('click', ''), prio,
                          env.get('RELEASE_WATCH_NTFY_TOKEN', '').strip(), log)
    return sent


def autobuild_main(argv):
    p = argparse.ArgumentParser(
        prog='firefox-release-watch.py autobuild',
        description='Branch, bump and dispatch an unsigned candidate build of a '
                    'flagged release whose patch check passed.')
    p.add_argument('--version', required=True)
    p.add_argument('--issue', type=int, required=True)
    p.add_argument('--targets', default=','.join(PATCHCHECK_TARGETS))
    p.add_argument('--base-sha', default=os.environ.get('GITHUB_SHA', ''),
                   help='the commit the patch check tested (default: $GITHUB_SHA)')
    p.add_argument('--api', default=os.environ.get('GITHUB_API_URL', GITHUB_API))
    p.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY', ''))
    p.add_argument('--notify', default=default_notify())
    p.add_argument('--now', help=argparse.SUPPRESS)  # tests: YYYYMMDDHHMMSS
    p.add_argument('--dry-run', action='store_true',
                   help='write nothing; print what would be created and dispatched')
    a = p.parse_args(argv)
    token = os.environ.get('GITHUB_TOKEN', '')
    if not (a.repo and token and a.base_sha):
        print('error: autobuild needs GITHUB_TOKEN, --repo and --base-sha (it reads '
              'the issue even in a dry run)', file=sys.stderr)
        return 1
    now = (datetime.datetime.strptime(a.now, '%Y%m%d%H%M%S').replace(
        tzinfo=datetime.timezone.utc) if a.now else
        datetime.datetime.now(datetime.timezone.utc))
    events = []
    try:
        outcome = autobuild(a.version, a.issue, [t for t in a.targets.split(',') if t],
                            a.base_sha, GitHub(a.repo, token, a.api), a.repo, now,
                            dry_run=a.dry_run, notify=a.notify or None, events=events)
    except TransientError as e:
        # Box B's queue, the releases or the issue could not be read. Nothing
        # was dispatched (the dispatch is the last write but the comment), so
        # the next hourly run retries; the watch job's outage tracking turns
        # red if GitHub stays down.
        warn(f'autobuild {a.version}: {e}; the next run retries')
        return 0
    except (WatchError, ValueError) as e:
        print(f'error: {e}', file=sys.stderr)
        return 1
    if not a.dry_run:
        send_events(events)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as f:
            f.write(f'firefox-release-watch autobuild {a.version} (#{a.issue}): '
                    f'**{outcome}**\n')
    print(f'outcome: {outcome}')
    return 0


def warn(message, env=None):
    """A warning that stays green: stderr, an Actions annotation and a line
    in the job summary."""
    env = os.environ if env is None else env
    print(f'warning: {message}', file=sys.stderr)
    if env.get('GITHUB_ACTIONS') == 'true':
        print(f'::warning title=Release watch::{message}')
    summary = env.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as f:
            f.write(f'> [!WARNING]\n> {message}\n\n')


def load_outages(path):
    """{source: ISO time of its first failure in the current streak} from
    --state-file. Missing or unreadable: {} (a streak restarts, it never
    turns red by mistake)."""
    if not path:
        return {}
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}
    out = {}
    for k, v in (data.get('failing_since') or {}).items() if isinstance(data, dict) else ():
        try:
            _parse_time(v)
            out[str(k)] = v
        except (TypeError, ValueError):
            pass
    return out


def update_outages(state, ok, transient, now):
    """The next state: a source that worked ends its streak, one that failed
    transiently starts one (or keeps its start). Sources that did not run
    this time keep theirs. Pure."""
    state = {k: v for k, v in state.items() if k not in ok}
    for what in transient:
        state.setdefault(what, now.strftime('%Y-%m-%dT%H:%M:%SZ'))
    return state


def long_outages(state, transient, now, hours=OUTAGE_HOURS):
    """[(source, since)] among this run's transient failures whose streak is
    longer than `hours`."""
    limit = datetime.timedelta(hours=hours)
    return [(w, state[w]) for w in transient
            if w in state and now - _parse_time(state[w]) > limit]


def save_outages(path, state):
    if path:
        Path(path).write_text(json.dumps({'failing_since': state}, indent=1,
                                         sort_keys=True) + '\n')


def default_notify(env=None):
    env = os.environ if env is None else env
    return (env.get('RELEASE_WATCH_NOTIFY') or env.get('GITHUB_REPOSITORY_OWNER') or '').strip()


def head_sha(repo_root):
    sha = os.environ.get('GITHUB_SHA', '')
    if sha:
        return sha
    r = subprocess.run(['git', '-C', str(repo_root), 'rev-parse', 'HEAD'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise WatchError(f'git rev-parse HEAD: {r.stderr.strip()}')
    return r.stdout.strip()


def patchcheck_main(argv):
    p = argparse.ArgumentParser(
        prog='firefox-release-watch.py patchcheck',
        description='Check both patch lists against a Firefox release and '
                    'comment the result on its issue.')
    p.add_argument('--version', required=True)
    p.add_argument('--issue', type=int, help='issue number to comment on')
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1],
                   help='repository checkout whose patches are tested')
    p.add_argument('--sha', help='commit the patches come from (default: '
                   '$GITHUB_SHA, else git rev-parse HEAD in --root)')
    p.add_argument('--workdir', type=Path,
                   help='scratch space (default: a new directory under $RUNNER_TEMP '
                        'or the system temp dir); removed afterwards unless given')
    p.add_argument('--tarball', type=Path,
                   help='use this local firefox-<v>.source.tar.xz (and <it>.asc) '
                        'instead of downloading; still signature-verified')
    p.add_argument('--archive-base', default=ARCHIVE_BASE)
    p.add_argument('--key-url', help='where to get the release key: a URL or a '
                   'file (default: the repository\'s assets/mozilla-release-key.asc)')
    p.add_argument('--fingerprint', default=MOZILLA_KEY_FINGERPRINT,
                   help=argparse.SUPPRESS)  # tests sign with a throwaway key
    p.add_argument('--check-script', type=Path, help=argparse.SUPPRESS)
    p.add_argument('--reports-dir', type=Path,
                   help='also write each target\'s full report here')
    p.add_argument('--targets', default=','.join(PATCHCHECK_TARGETS),
                   help='comma-separated, in order (default: %(default)s)')
    p.add_argument('--api', default=os.environ.get('GITHUB_API_URL', GITHUB_API))
    p.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY', ''))
    p.add_argument('--dry-run', action='store_true',
                   help='post nothing; print the comment')
    a = p.parse_args(argv)

    token = os.environ.get('GITHUB_TOKEN', '')
    github = GitHub(a.repo, token, a.api) if (a.repo and token) else None
    own_workdir = a.workdir is None
    workdir = a.workdir or Path(tempfile.mkdtemp(
        prefix='redoubt-patchcheck-', dir=os.environ.get('RUNNER_TEMP') or None))
    report = {}
    try:
        sha = a.sha or head_sha(a.root)
        outcome = patchcheck(a.version, a.issue, sha, github, a.root, workdir,
                             dry_run=a.dry_run, archive_base=a.archive_base,
                             key_url=a.key_url, fingerprint=a.fingerprint.upper(),
                             check_script=a.check_script, local_tarball=a.tarball,
                             run_link=run_url(), reports_dir=a.reports_dir,
                             targets=[t for t in a.targets.split(',') if t],
                             report=report)
    except TransientError as e:
        # A download or GitHub call that a later run may not see. The issue
        # stays open, so the next hourly run checks again.
        warn(f'patchcheck {a.version}: {e}; the next run retries')
        return 0
    except (WatchError, ValueError, OSError) as e:
        print(f'error: {e}', file=sys.stderr)
        return 1
    finally:
        if own_workdir:
            shutil.rmtree(workdir, ignore_errors=True)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as f:
            f.write(f'firefox-release-watch patchcheck {a.version}: **{outcome}**\n')
            if outcome == 'would-post':
                # A dry run's comment, rendered as it would appear on the issue.
                f.write(f'\nDry run: the comment it would post on '
                        f'#{a.issue or "?"}:\n\n---\n\n{report["comment"]}\n---\n')
    print(f'outcome: {outcome}')
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1],
                   help='repository root holding version and version.android')
    p.add_argument('--versions-file', type=Path,
                   help='read firefox_versions.json from this file instead of the network')
    p.add_argument('--mobile-versions-file', type=Path,
                   help='read mobile_versions.json from this file instead of the network')
    p.add_argument('--product-details-url', default=PRODUCT_DETAILS_URL)
    p.add_argument('--mobile-product-details-url', default=MOBILE_PRODUCT_DETAILS_URL)
    p.add_argument('--archive-base', default=ARCHIVE_BASE)
    p.add_argument('--api', default=os.environ.get('GITHUB_API_URL', GITHUB_API))
    p.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY', ''),
                   help='owner/name (default: $GITHUB_REPOSITORY)')
    p.add_argument('--ref', default='main', help='branch the issue links REBASE.md on')
    p.add_argument('--dry-run', action='store_true',
                   help='open nothing; without GITHUB_TOKEN, also skip the duplicate check')
    p.add_argument('--patchcheck-version',
                   help='also emit a patch check of this release, newer than the '
                        'repository or not, with no issue (dry run only)')
    p.add_argument('--patchcheck-targets', default=','.join(PATCHCHECK_TARGETS),
                   help='targets of that check (default: %(default)s)')
    p.add_argument('--notify', default=default_notify(),
                   help='GitHub login every issue is assigned to and mentions (default: '
                        '$RELEASE_WATCH_NOTIFY, else $GITHUB_REPOSITORY_OWNER; empty: '
                        'nobody)')
    p.add_argument('--advisories-dir', type=Path,
                   help='read mfsa*.yml from this directory instead of '
                        f'github.com/{MFSA_REPO}')
    p.add_argument('--no-advisories', action='store_true',
                   help='skip the security-advisory check and the reminders')
    p.add_argument('--shipped-tag',
                   help='the release users run, as a tag (android-157.0-3); default: '
                        'the repository\'s latest GitHub release')
    p.add_argument('--autobuild-policy',
                   default=os.environ.get('RELEASE_WATCH_AUTOBUILD', '').strip() or 'dot',
                   choices=AUTOBUILD_POLICIES,
                   help='which flagged releases get a candidate build (default: '
                        '$RELEASE_WATCH_AUTOBUILD, else dot)')
    p.add_argument('--notify-test', action='store_true',
                   help='only open and close one test issue assigned to --notify')
    p.add_argument('--state-file', type=Path,
                   default=os.environ.get('RELEASE_WATCH_STATE') or None,
                   help='JSON file that remembers since when each source has been '
                        'failing (default: $RELEASE_WATCH_STATE; none: a transient '
                        'failure never turns the run red)')
    p.add_argument('--now', help=argparse.SUPPRESS)  # tests: YYYYMMDDHHMMSS
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ['patchcheck']:
        return patchcheck_main(argv[1:])
    if argv[:1] == ['autobuild']:
        return autobuild_main(argv[1:])
    a = p.parse_args(argv)
    now = (datetime.datetime.strptime(a.now, '%Y%m%d%H%M%S').replace(
        tzinfo=datetime.timezone.utc) if a.now else
        datetime.datetime.now(datetime.timezone.utc))
    notify = a.notify.strip().lstrip('@') or None

    def load(path, url):
        if path:
            try:
                return json.loads(path.read_text())
            except (OSError, ValueError) as e:
                raise WatchError(f'cannot read {path}: {e}') from e
        return fetch_json(url)

    manual = None
    if a.patchcheck_version:
        # Refused before anything is read: a bad input is not a feed failure.
        try:
            manual = manual_patchcheck_job(a.patchcheck_version,
                                           a.patchcheck_targets, a.dry_run)
        except (WatchError, ValueError) as e:
            print(f'error: manual patch check: {e}', file=sys.stderr)
            return 1

    token = os.environ.get('GITHUB_TOKEN', '')
    if not a.dry_run and not (a.repo and token):
        print('error: GITHUB_TOKEN and --repo/$GITHUB_REPOSITORY are required '
              '(or pass --dry-run)', file=sys.stderr)
        return 1
    github = GitHub(a.repo, token, a.api) if (a.repo and token) else None
    exists = lambda u: url_exists(u.replace(ARCHIVE_BASE, a.archive_base, 1))
    repo = a.repo or 'CPlusPlus17/Redoubt'
    errors = []      # fatal: the run turns red
    transient = {}   # source -> message: a warning, unless the outage is long
    worked = set()   # sources that answered this time
    events = []

    if a.notify_test:
        try:
            notify_test(github, notify, now, a.dry_run)
        except WatchError as e:
            print(f'error: notification test: {e}', file=sys.stderr)
            return 1
        if not a.dry_run:
            send_events([{'title': 'Release watch notification test',
                          'message': 'If this arrived, the ntfy channel works.',
                          'impact': 'default'}])
        return 0

    # Each feed and each half fails on its own: a dead mobile feed must not
    # stop the desktop issue, and neither may open an issue about a failure.
    def attempt(what, f):
        try:
            result = f()
        except TransientError as e:
            print(f'transient failure: {what}: {e}', file=sys.stderr)
            transient.setdefault(what, str(e))
            return None
        except (WatchError, ValueError, OSError) as e:
            print(f'error: {what}: {e}', file=sys.stderr)
            errors.append(what)
            return None
        worked.add(what)
        return result

    versions = attempt('firefox_versions.json',
                       lambda: load(a.versions_file, a.product_details_url))
    mobile = attempt('mobile_versions.json',
                     lambda: load(a.mobile_versions_file, a.mobile_product_details_url))

    found, outcome = {}, None
    if versions is not None:
        outcome = attempt('Firefox release', lambda: run(
            a.root, versions, exists, github, repo, a.dry_run, ref=a.ref, found=found,
            notify=notify))

    android_found, android_outcome = {}, None
    latest = (versions or {}).get('LATEST_FIREFOX_VERSION') or ''
    try:
        parse_version(latest)
    except ValueError:
        latest = ''
    if mobile is not None and not latest:
        print('Firefox for Android: skipped, no usable desktop release to tell an '
              'Android-only release from', file=sys.stderr)
        if versions is not None:
            # The feed answered with no usable release: not an outage.
            errors.append('Firefox for Android (skipped)')
    elif mobile is not None:
        android_outcome = attempt('Firefox for Android', lambda: run_android(
            a.root, mobile, latest, exists, github, repo, a.dry_run, ref=a.ref,
            found=android_found, notify=notify))
    for f_, o_ in ((found, outcome), (android_found, android_outcome)):
        if o_ == 'opened':
            events.append({'title': f_.get('title', 'New Firefox release'),
                           'message': 'Assigned to you on GitHub.',
                           'click': f_.get('url', ''), 'impact': 'default'})

    # Security advisories, then reminders. Read-only GitHub access is enough
    # for a dry run without a token (the contents API allows 60 calls an hour
    # unauthenticated).
    advisory_results, reminded = None, None
    if not a.no_advisories:
        reader = github or GitHub(a.repo or repo, '', a.api)
        shipped_tag = a.shipped_tag
        if shipped_tag is None:
            shipped_tag = attempt('latest release', reader.latest_release) or ''
        advisories = attempt('security advisories', lambda: (
            load_advisories_dir(a.advisories_dir) if a.advisories_dir
            else fetch_advisories(reader, now.year)))
        if advisories is not None:
            advisory_results = attempt('security advisories', lambda: run_advisories(
                a.root, advisories, github, repo, shipped_tag, a.dry_run, notify=notify,
                events=events, ref=a.ref))
        if github is not None:
            reminded = attempt('reminders', lambda: run_reminders(
                a.root, github, shipped_tag, now, a.dry_run, notify=notify,
                events=events))

    jobs = patchcheck_jobs((outcome, found) if outcome else None,
                           (android_outcome, android_found) if android_outcome else None)
    if manual:
        if any((j['version'], j['targets']) == (manual['version'], manual['targets'])
               for j in jobs):
            print(f'manual patch check of {manual["version"]} ({manual["targets"]}): '
                  f'already in the checks')
        else:
            jobs.append(manual)
            print(f'manual patch check of {manual["version"]} ({manual["targets"]}): '
                  f'queued, dry run')
    current = None
    try:
        current = read_track(a.root, 'version.android')
    except WatchError:
        pass
    builds = autobuild_jobs(jobs, current, a.autobuild_policy) if current else []
    affected = [f'{i} ({o})' for i, o in advisory_results or [] if o != 'not-affected']
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as f:
            f.write(f'firefox-release-watch: **{outcome or "error"}**; '
                    f'Firefox for Android: **{android_outcome or "error"}**\n\n')
            if manual:
                f.write(f'manual patch check (dry run): **{manual["version"]}**, '
                        f'targets {manual["targets"]}\n\n')
            if advisory_results is not None:
                f.write('security advisories the shipped release is behind: '
                        + (', '.join(affected) or 'none') + '\n\n')
            if reminded:
                f.write(f'reminded on: {", ".join(f"#{n}" for n in reminded)}\n\n')
            f.write(f'notify: {"@" + notify if notify else "nobody"}; autobuild policy '
                    f'{a.autobuild_policy}: '
                    + (', '.join(b['version'] for b in builds) or 'nothing to build')
                    + '\n')
    if not a.dry_run:
        send_events(events)
    # For the workflow's patch-check job (needs.watch.outputs.*). Written even
    # after an error, so a desktop issue opened before the Android half failed
    # still gets its check.
    output = os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output, 'a') as f:
            f.write(f'outcome={outcome or "error"}\n'
                    f'version={found.get("version", "")}\n'
                    f'issue={found.get("issue") or ""}\n'
                    f'patchcheck={"true" if outcome and wants_patchcheck(outcome, found) else "false"}\n'
                    f'android_outcome={android_outcome or "error"}\n'
                    f'android_version={android_found.get("version", "")}\n'
                    f'android_issue={android_found.get("issue") or ""}\n'
                    f'checks={json.dumps(jobs, separators=(",", ":"))}\n'
                    f'autobuild={json.dumps(builds, separators=(",", ":"))}\n')
    print(f'outcome: {outcome or "error"}')
    print(f'android outcome: {android_outcome or "error"}')
    if advisory_results is not None:
        print('advisories: ' + (', '.join(affected) or 'none affecting the shipped release'))
    if builds:
        print('autobuild: ' + ', '.join(b['version'] for b in builds))

    # Transient failures: green with a warning, unless the same source has
    # been failing for more than OUTAGE_HOURS (then red every run until it
    # answers again).
    state = update_outages(load_outages(a.state_file), worked, transient, now)
    try:
        save_outages(a.state_file, state)
    except OSError as e:
        print(f'warning: cannot write {a.state_file}: {e}', file=sys.stderr)
    long = long_outages(state, transient, now)
    for what, message in transient.items():
        since = state.get(what, '')
        warn(f'{what} failed (transient, failing since {since or "now"}): {message}'
             + ('' if a.state_file else '; no --state-file, so this never turns red'))
    for what, since in long:
        print(f'error: {what} has been failing since {since}, more than '
              f'{OUTAGE_HOURS} h', file=sys.stderr)
    return 1 if errors or long else 0


if __name__ == '__main__':
    sys.exit(main())
