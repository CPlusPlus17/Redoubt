#!/usr/bin/env python3
"""Flag every new Firefox release with one GitHub issue.

Run daily by .github/workflows/firefox-release-watch.yaml. Since 2026-10-02 the
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
daily schedule makes that rare), the older one gets no issue of its own; the
rebase goes straight to the newer one anyway.

Standard library only. Exit 0 when it did its job (including "nothing to
do" and "tarball not there yet"); exit 1 on a network or API failure, so the
workflow run turns red instead of silently missing a release.
"""

import argparse
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

_VERSION = re.compile(r'^(\d+)\.(\d+)(?:\.(\d+))?(esr)?$')


class WatchError(Exception):
    """A failure that must turn the workflow run red."""


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
            '4. If a tarball appears later, the next daily run notices it while '
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
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise WatchError(f'cannot read {url}: {e}') from e


def url_exists(url):
    """True on 200, False on 404. Anything else is an error, not an answer:
    a 5xx from the archive must not read as "no tarball yet" forever."""
    try:
        with urllib.request.urlopen(_request(url, method='HEAD'), timeout=TIMEOUT) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise WatchError(f'HEAD {url}: HTTP {e.code}') from e
    except (urllib.error.URLError, OSError) as e:
        raise WatchError(f'HEAD {url}: {e}') from e


class GitHub:
    def __init__(self, repo, token, api=GITHUB_API):
        self.repo, self.token, self.api = repo, token, api.rstrip('/')

    def _call(self, method, path, data=None):
        url = f'{self.api}/repos/{self.repo}{path}'
        try:
            with urllib.request.urlopen(_request(url, method, data, self.token),
                                        timeout=TIMEOUT) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None), r.headers
        except urllib.error.HTTPError as e:
            return e.code, None, e.headers
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise WatchError(f'{method} {url}: {e}') from e

    def _pages(self, path, params, what):
        out, page = [], 1
        while True:
            q = urllib.parse.urlencode({**params, 'per_page': 100, 'page': page})
            status, items, _ = self._call('GET', f'{path}?{q}')
            if status != 200 or not isinstance(items, list):
                raise WatchError(f'{what}: HTTP {status}')
            out += items
            if len(items) < 100:
                return out
            page += 1

    def issues(self, label):
        """Every issue with `label`, open and closed, as
        {'title', 'number', 'state'} dicts."""
        items = self._pages('/issues', {'labels': label, 'state': 'all'},
                            f'listing issues labelled {label}')
        return [{'title': i.get('title', ''), 'number': i.get('number'),
                 'state': i.get('state', '')} for i in items]

    def issue_titles(self, label):
        """Titles of every issue with `label`, open and closed."""
        return [i['title'] for i in self.issues(label)]

    def comments(self, number):
        """Bodies of every comment on issue `number`."""
        items = self._pages(f'/issues/{number}/comments', {},
                            f'listing comments on #{number}')
        return [i.get('body') or '' for i in items]

    def create_comment(self, number, body):
        status, comment, _ = self._call('POST', f'/issues/{number}/comments',
                                        {'body': body})
        if status != 201 or not comment:
            raise WatchError(f'commenting on #{number}: HTTP {status}')
        return comment.get('html_url', '')

    def ensure_label(self, label):
        status, _, _ = self._call('POST', '/labels', {
            'name': label, 'color': LABEL_COLOR, 'description': LABEL_DESCRIPTION})
        # 201 created, 422 already exists. Anything else: creating the issue
        # with the label below still works where the token may set labels.
        return status in (201, 422)

    def create_issue(self, title, body, label):
        """Returns (html_url, number)."""
        status, issue, _ = self._call('POST', '/issues', {
            'title': title, 'body': body, 'labels': [label]})
        if status != 201 or not issue:
            raise WatchError(f'creating issue {title!r}: HTTP {status}')
        return issue.get('html_url', ''), issue.get('number')


# --------------------------------------------------------------------------

def run(root, versions, exists, github, repo, dry_run=False, log=print, ref='main',
        found=None):
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
                 github, dry_run, log, found)


def _flag(title, body, github, dry_run, log, found):
    """Open the issue `title` unless one exists, open or closed. `body` is
    called only when the issue is about to be opened (or printed)."""
    if github is None:
        if not dry_run:
            raise WatchError('no GitHub access and not a dry run')
        log('dry run without GitHub access: duplicate check skipped')
    else:
        same = [i for i in github.issues(LABEL) if i['title'] == title]
        if same:
            # Prefer an open one, should a human have duplicated it by hand.
            same.sort(key=lambda i: i['state'] != 'open')
            found['issue'], found['state'] = same[0]['number'], same[0]['state']
            log(f'already flagged: {title!r} (#{found["issue"]}, {found["state"]})')
            return 'duplicate'

    text = body()
    if dry_run:
        log(f'dry run: would open {title!r}:\n\n{text}')
        return 'would-open'
    github.ensure_label(LABEL)
    url, found['issue'] = github.create_issue(title, text, LABEL)
    found['state'] = 'open'
    log(f'opened {url}')
    return 'opened'


def run_android(root, mobile, latest, exists, github, repo, dry_run=False, log=print,
                ref='main', found=None):
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
                 github, dry_run, log, found)


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
#    key the way the Makefile's fetch rule does (keys.openpgp.org, by
#    fingerprint) into a throwaway GNUPGHOME; refuse unless the key imported
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
    except (urllib.error.URLError, OSError) as e:
        raise WatchError(f'downloading {url}: {e}') from e
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
    download(key_url, key, log)
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
                   key_url or KEY_URL.format(fpr=fingerprint), fingerprint, workdir, log)

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
    p.add_argument('--key-url', help='where to fetch the release key '
                   '(default: keys.openpgp.org by --fingerprint)')
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
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ['patchcheck']:
        return patchcheck_main(argv[1:])
    a = p.parse_args(argv)

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
    errors = []

    # Each feed and each half fails on its own: a dead mobile feed must not
    # stop the desktop issue, and neither may open an issue about a failure.
    def attempt(what, f):
        try:
            return f()
        except (WatchError, ValueError, OSError) as e:
            print(f'error: {what}: {e}', file=sys.stderr)
            errors.append(what)
            return None

    versions = attempt('firefox_versions.json',
                       lambda: load(a.versions_file, a.product_details_url))
    mobile = attempt('mobile_versions.json',
                     lambda: load(a.mobile_versions_file, a.mobile_product_details_url))

    found, outcome = {}, None
    if versions is not None:
        outcome = attempt('Firefox release', lambda: run(
            a.root, versions, exists, github, repo, a.dry_run, ref=a.ref, found=found))

    android_found, android_outcome = {}, None
    latest = (versions or {}).get('LATEST_FIREFOX_VERSION') or ''
    try:
        parse_version(latest)
    except ValueError:
        latest = ''
    if mobile is not None and not latest:
        print('Firefox for Android: skipped, no usable desktop release to tell an '
              'Android-only release from', file=sys.stderr)
        errors.append('Firefox for Android (skipped)')
    elif mobile is not None:
        android_outcome = attempt('Firefox for Android', lambda: run_android(
            a.root, mobile, latest, exists, github, repo, a.dry_run, ref=a.ref,
            found=android_found))

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
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as f:
            f.write(f'firefox-release-watch: **{outcome or "error"}**; '
                    f'Firefox for Android: **{android_outcome or "error"}**\n')
            if manual:
                f.write(f'manual patch check (dry run): **{manual["version"]}**, '
                        f'targets {manual["targets"]}\n')
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
                    f'checks={json.dumps(jobs, separators=(",", ":"))}\n')
    print(f'outcome: {outcome or "error"}')
    print(f'android outcome: {android_outcome or "error"}')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
