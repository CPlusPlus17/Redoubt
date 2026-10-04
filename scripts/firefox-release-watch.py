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

Only the latest release is flagged. If two releases land between runs (a
daily schedule makes that rare), the older one gets no issue of its own; the
rebase goes straight to the newer one anyway.

Standard library only. Exit 0 when it did its job (including "nothing to
do" and "tarball not there yet"); exit 1 on a network or API failure, so the
workflow run turns red instead of silently missing a release.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


PRODUCT_DETAILS_URL = 'https://product-details.mozilla.org/1.0/firefox_versions.json'
ARCHIVE_BASE = 'https://archive.mozilla.org/pub/firefox/releases'
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

    def issue_titles(self, label):
        """Titles of every issue with `label`, open and closed."""
        titles, page = [], 1
        while True:
            q = urllib.parse.urlencode({'labels': label, 'state': 'all',
                                        'per_page': 100, 'page': page})
            status, items, _ = self._call('GET', f'/issues?{q}')
            if status != 200 or not isinstance(items, list):
                raise WatchError(f'listing issues labelled {label}: HTTP {status}')
            titles += [i.get('title', '') for i in items]
            if len(items) < 100:
                return titles
            page += 1

    def ensure_label(self, label):
        status, _, _ = self._call('POST', '/labels', {
            'name': label, 'color': LABEL_COLOR, 'description': LABEL_DESCRIPTION})
        # 201 created, 422 already exists. Anything else: creating the issue
        # with the label below still works where the token may set labels.
        return status in (201, 422)

    def create_issue(self, title, body, label):
        status, issue, _ = self._call('POST', '/issues', {
            'title': title, 'body': body, 'labels': [label]})
        if status != 201 or not issue:
            raise WatchError(f'creating issue {title!r}: HTTP {status}')
        return issue.get('html_url', '')


# --------------------------------------------------------------------------

def run(root, versions, exists, github, repo, dry_run=False, log=print, ref='main'):
    """Decide and act. Returns a one-word outcome, also used by the tests:
    'current', 'no-tarball', 'duplicate', 'would-open', 'opened'."""
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

    title = issue_title(latest)
    if github is None:
        if not dry_run:
            raise WatchError('no GitHub access and not a dry run')
        log('dry run without GitHub access: duplicate check skipped')
    elif title in github.issue_titles(LABEL):
        log(f'already flagged: {title!r}')
        return 'duplicate'

    body = issue_body(latest, android, desktop, esr, esr_next, repo, ref)
    if dry_run:
        log(f'dry run: would open {title!r}:\n\n{body}')
        return 'would-open'
    github.ensure_label(LABEL)
    log(f'opened {github.create_issue(title, body, LABEL)}')
    return 'opened'


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1],
                   help='repository root holding version and version.android')
    p.add_argument('--versions-file', type=Path,
                   help='read product-details from this file instead of the network')
    p.add_argument('--product-details-url', default=PRODUCT_DETAILS_URL)
    p.add_argument('--archive-base', default=ARCHIVE_BASE)
    p.add_argument('--api', default=os.environ.get('GITHUB_API_URL', GITHUB_API))
    p.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY', ''),
                   help='owner/name (default: $GITHUB_REPOSITORY)')
    p.add_argument('--ref', default='main', help='branch the issue links REBASE.md on')
    p.add_argument('--dry-run', action='store_true',
                   help='open nothing; without GITHUB_TOKEN, also skip the duplicate check')
    a = p.parse_args(argv)

    token = os.environ.get('GITHUB_TOKEN', '')
    try:
        if a.versions_file:
            versions = json.loads(a.versions_file.read_text())
        else:
            versions = fetch_json(a.product_details_url)
        if not a.dry_run and not (a.repo and token):
            raise WatchError('GITHUB_TOKEN and --repo/$GITHUB_REPOSITORY are required '
                             '(or pass --dry-run)')
        github = GitHub(a.repo, token, a.api) if (a.repo and token) else None
        outcome = run(a.root, versions,
                      lambda u: url_exists(u.replace(ARCHIVE_BASE, a.archive_base, 1)),
                      github, a.repo or 'CPlusPlus17/Redoubt', a.dry_run, ref=a.ref)
    except (WatchError, ValueError, OSError) as e:
        print(f'error: {e}', file=sys.stderr)
        return 1
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as f:
            f.write(f'firefox-release-watch: **{outcome}**\n')
    print(f'outcome: {outcome}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
