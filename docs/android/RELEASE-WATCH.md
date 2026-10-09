# Release watch: Firefox releases, Mozilla advisories, candidate builds

Task LW-M7-47. Owner decision 2026-10-09, verbatim: "lets do 1,2,7". Item 1
of the list it answers: never miss a Mozilla security release again. Notify
the owner immediately when a new Firefox (Android) release or Mozilla security
advisory appears. For a Firefox dot release, start the build pipeline
automatically, so that a bundle is ready to sign.

The machinery is `scripts/firefox-release-watch.py`, run by
`.github/workflows/firefox-release-watch.yaml` on GitHub-hosted runners. What
it did before this task (one issue per release, the patch check comment) is
described in `REBASE.md`, "Release-track cadence". This page covers what
LW-M7-47 added and how to operate it.

## Why #3 went unnoticed

Firefox 157.0.1 shipped on 2026-10-06. On that day's run the watcher opened
issue #3, "Firefox 157.0.1 released: rebase Android and desktop", at 14:17
UTC. Its patch check comment (both targets pass) followed at 14:21. On
2026-10-07 a second patch check comment followed for a new commit on main.
Three days later nobody had acted. What was checked on 2026-10-09:

- **Nobody was told.** The issue had no assignee and its body mentioned
  nobody. `github-actions[bot]` opened it. For a repository owner, GitHub
  notifies about a bot-opened issue only if they *watch* the repository.
  `GET /repos/CPlusPlus17/Redoubt/subscription` with the owner's token
  returned **404, "Not Found"**, which means the owner does not watch the
  repository. So #3 produced no notification at all: no email, no push, and
  nothing in the github.com inbox.
- **It did not look urgent.** The title said "rebase", not "security". MFSA
  2026-104 (Firefox 157.0.1, one moderate CVE, CVE-2026-106016) was published
  on the same day, but the watcher did not read advisories, so the issue
  never said that the shipped 157.0-3 was behind one.
- **The schedule was late.** The daily 07:23 UTC cron actually started at
  16:10, 14:16, 14:35, 14:40 and 14:26 UTC on 2026-10-05 to 2026-10-09
  (`gh run list --workflow firefox-release-watch.yaml`). GitHub does not
  promise when a scheduled run starts.

## What it does now

Every hour (`cron: '23 * * * *'`):

1. **Release issues are assigned and mention the owner.** Each issue the
   watcher opens is created with the owner as assignee. Its first line is
   `@<owner>: Mozilla released Firefox <v>; you are assigned. ...`. An open
   watcher issue with no assignee, such as #3, is assigned on the next run.
   Assignment and mention are "participating" notifications. GitHub delivers
   them whether or not the owner watches the repository, unless the
   repository is set to *Ignore*.
2. **Security advisories.** The watcher reads the newest 12 files of
   `announce/<year>/` in
   [mozilla/foundation-security-advisories](https://github.com/mozilla/foundation-security-advisories).
   That repository holds the source of
   <https://www.mozilla.org/en-US/security/advisories/>. The read goes
   through the GitHub API with the workflow's `GITHUB_TOKEN`; there is no
   scraping. An advisory counts when its `fixed_in` names `Firefox <v>` or
   `Firefox for Android <v>` and `<v>` is newer than the release users run:
   the latest GitHub release `android-<v>-<n>` (`version.android` if there
   is none). ESR, iOS, Focus and Thunderbird advisories are ignored. For each
   advisory that counts, once (hidden marker `<!-- redoubt-mfsa id=... -->`):
   - if the watcher's issue for `<v>` is open, it gets a comment with the
     highest impact, the CVE count per impact, the CVE list and a mention.
     It also gets the label `security`, a `priority: critical` or
     `priority: high` label for those impacts, and the title prefix
     `[security: <impact>]`. The prefix is never lowered, and the release
     dedup still recognises the renamed title. Critical and high issues are
     also pinned. Pinning is best effort: GitHub allows three pinned issues;
   - otherwise (that issue is closed, or a newer release overtook `<v>`
     before it was flagged) it opens an issue titled
     `[security: <impact>] Mozilla security advisory MFSA <year>-<n> (fixed in Firefox <v>)`
     with labels `firefox-release` and `security`. The issue is assigned to
     the owner, mentions them, and lists the watcher's open release issues
     that would fix it.
3. **Reminders.** Every open `security` issue whose version the shipped
   release is still behind gets a comment that mentions the owner. It is
   posted once per 24 hours, counted from the issue's creation or the last
   advisory or reminder comment. The reminders stop when the issue is closed
   or the shipped release catches up.
4. **Candidate builds** (job `autobuild`, below).
5. **Optional push channel**, ntfy. It is off unless a secret is set
   (below).

The job summary of each run shows the outcome, the advisories the shipped
release is behind, the reminders sent and what autobuild will do.

## Notification: what the owner must check

GitHub's own notification path needs no new secret. These settings decide
whether it reaches the owner within the hour:

1. <https://github.com/settings/notifications>:
   - **Default notifications email**: an address that is read.
   - **Subscriptions → "Participating, @mentions and custom"**: tick
     **Email**, and **On GitHub** for the web inbox. This one setting covers
     both the assignment and the mention.
   - **Customize email updates**: does not matter here. It covers pull
     request reviews and pushes.
2. **GitHub Mobile** (if installed): app → Profile → Settings →
   Notifications → turn on push for **Assigned** and **Direct mentions**.
   Check the "Working hours" there too; outside them the app holds pushes
   back.
3. **The repository's Watch button** on github.com/CPlusPlus17/Redoubt: any
   setting **except "Ignore"**. "Participating and @mentions" (the current
   state: not watching) is enough. *Custom → Issues* also notifies on every
   new issue, including the ones the watcher opens before it assigns them.
4. Verify end to end: Actions → "Firefox release watch" → Run workflow →
   `notify_test: true`. This opens one issue assigned to the owner that
   mentions them, labelled `release-watch-test`, and closes it at once. Its
   email or push should arrive within minutes. If it does not, check the
   three points above. Check the spam folder for `notifications@github.com`
   too.

The login notified is the repository variable `RELEASE_WATCH_NOTIFY`
(Settings → Secrets and variables → Actions → Variables). If that variable is
unset, it is `GITHUB_REPOSITORY_OWNER`, i.e. `CPlusPlus17`. GitHub silently
drops an assignee without push access to the repository. The mention still
goes out.

**Timing.** The watcher acts at most an hour after Mozilla's
product-details or advisory files change, plus GitHub's scheduling delay.
That delay has been hours for the old daily run. If an hourly run is dropped,
the next one catches up. If the owner wants a timing guarantee, an external
trigger is the fix: for example a cron entry on box A running
`gh workflow run firefox-release-watch.yaml --repo CPlusPlus17/Redoubt`.
That is a token on box A and is not set up by this task.

### Optional: ntfy push

For a push to the phone that does not depend on GitHub's notification
settings, the owner can create the **repository secret**
`RELEASE_WATCH_NTFY_URL`: a topic URL such as
`https://ntfy.sh/redoubt-<32 random characters>`, or one on a self-hosted
ntfy server. If the server requires an access token, also create
`RELEASE_WATCH_NTFY_TOKEN`. Then subscribe to the topic in the ntfy app. With
the secret unset, which is the default, nothing is sent. A failed push only
logs a warning; GitHub's notification is the channel of record.

Privacy of an ntfy.sh topic:

- **The topic name is the only secret.** Anyone who knows or guesses it can
  read the messages and post fake ones. Use a long random name and keep it
  out of the repository. GitHub masks secrets in logs.
- **The operator of ntfy.sh sees every message** and the IP addresses of the
  subscribers. The messages carry only public facts: a Firefox version, an
  MFSA number, an issue link. Nothing about users, keys or builds goes out.
- A self-hosted ntfy with access control and `RELEASE_WATCH_NTFY_TOKEN`
  avoids both points.

Messages: a new release issue, an advisory (priority `high` or `urgent` for
high and critical advisories), a reminder, a candidate build started or
blocked by failing patches. The notification test sends one too.

## Candidate builds (`autobuild` job)

Goal: when Mozilla ships a dot release on Redoubt's current major, an
unsigned build of it is ready by the time the owner looks.

When a watch run flags a release (opened, or still open) that has a source
tarball, and the policy allows it, the release joins the `autobuild` matrix.
The policy is the repository variable `RELEASE_WATCH_AUTOBUILD`:

| value | builds |
|---|---|
| `dot` (default, unset) | a dot release on the major of `version.android` (157.0.1 or 157.1 while on 157.0) |
| `all` | also a new major (158.0 while on 157.0) |
| `off` | nothing |

`dot` is the default because a new major usually needs the work on a local
rebase branch (for 158: `android/firefox-158`). A build of main plus a
version bump would fail or ship without that work, and would hold box B for
hours.

The job runs `scripts/firefox-release-watch.py autobuild` after the patch
check job:

1. **Once per version.** If the issue already has an
   `<!-- redoubt-autobuild version=<v> -->` comment, the job stops. To build
   again, dispatch `android-release.yaml` by hand.
2. **Only on a passing patch check of this commit.** Since LW-M7-47 the
   patch check comment has a second marker,
   `<!-- redoubt-patchcheck-result version=<v> sha=<commit> desktop=pass android=pass -->`.
   If that marker is missing for the run's commit (the check did not finish,
   or the comment is older than this task), nothing happens. If android did
   not pass, one comment says which target failed and mentions the owner;
   the patch check comment above it lists the failing patches. The issue
   stays assigned. A fix on main gets a new check on the next run, and a
   build if the check passes.
3. **One build at a time on box B.** If `android-release.yaml` or
   `android-test.yaml` has a queued, waiting, pending, requested or
   in-progress run, the job stops, for example during a beta acceptance
   build. The next hourly run tries again.
4. **Branch `auto/firefox-<v>`**: the run's commit on main plus one commit
   that sets `version.android` to `<v>` and `release.android` to `1` (also
   `version` and `release` when desktop is among the targets). The commit is
   made through the git data API, so GitHub signs it as
   `github-actions[bot]`. Nothing else changes, and the branch is not for
   merging as it is: the bump lands on main as a signed commit from the
   owner. If the branch already exists, the job builds it as it stands.
5. **Dispatch** `android-release.yaml` on the branch with `mode=full`,
   `update_check=true` and `build_date=<now, UTC>`. A push or ref created
   with `GITHUB_TOKEN` starts no workflow by itself; GitHub exempts
   `workflow_dispatch`, which is why the dispatch is explicit.
6. **Comment**: the branch, the build date, the runs page and the next steps.

**It never signs, publishes or merges.** `android-release.yaml` builds and
gates *unsigned* APKs and uploads them with `output-metadata.json` and
`SHA256SUMS` as the artifact `redoubt-android-unsigned`. That is the bundle
`sign.sh` takes. After a build, by hand:

1. Download the artifact.
2. Run the acceptance on the emulator (`SMOKE.md`).
3. Sign offline (`SIGNING.md`; `DISTRIBUTION.md`, "Publishing a release with
   the check").
4. Publish.
5. Land the bump on main and close the issue.

**Permissions.** The workflow default is `permissions: {}`. `watch` and
`patchcheck` get `contents: read` and `issues: write`. Only `autobuild` gets
`contents: write` (the branch), `actions: write` (the dispatch, and reading
box B's queue) and `issues: write`. No new secret is needed.

## Dry runs and tests

```sh
# Everything read-only. Without a token: no duplicate check, no reminders;
# advisories and the latest release are read without authentication
# (60 API calls an hour).
python3 scripts/firefox-release-watch.py --dry-run --repo CPlusPlus17/Redoubt --notify CPlusPlus17
# With a read token it also sees the issues: "would assign", "would comment", "would label".
GITHUB_TOKEN=$(gh auth token) python3 scripts/firefox-release-watch.py --dry-run \
    --repo CPlusPlus17/Redoubt --notify CPlusPlus17
# Advisories from local files instead of GitHub; pretend a different release is shipped.
python3 scripts/firefox-release-watch.py --dry-run --advisories-dir DIR --shipped-tag android-157.0-3
# What autobuild would do for an issue (reads the issue; needs a token).
GITHUB_TOKEN=... python3 scripts/firefox-release-watch.py autobuild --dry-run \
    --repo CPlusPlus17/Redoubt --version 157.0.1 --issue 3 --base-sha "$(git rev-parse origin/main)"
# Offline tests: fixtures only, fake GitHub/archive/ntfy servers on 127.0.0.1.
python3 scripts/tests/test-firefox-release-watch.py
```

From the Actions tab: `dry_run: true` opens, posts, labels, assigns,
dispatches and pushes nothing. It prints all of it and the autobuild plan.
`notify_test: true` runs the notification test and nothing else.

The advisory fixtures (`scripts/tests/fixtures/firefox-release-watch/mfsa/`)
are unmodified copies of Mozilla's files, fetched 2026-10-09:

- MFSA 2026-104 (Firefox 157.0.1) and 2026-97 (Firefox 157);
- 2026-100, 2026-101 and 2026-89 (ESR, Thunderbird and iOS: ignored);
- 2026-73 (an Android-only dot whose `fixed_in` says "Firefox 153.0.3");
- 2024-45 ("Firefox for Android 130.0.1");
- 2025-25 (an indented `fixed_in`) and 2025-28 (a block-scalar CVE title).

The script parses these files with the standard library. On 2026-10-09 its
reading of every 2024-2026 file (272) was compared with PyYAML's and matched;
the test repeats that comparison on the fixtures when PyYAML is installed.
The workflow passes `actionlint` 1.7.12 (without shellcheck).

## What it does not do

- It does not decide or rebase. The issue, the comments and the candidate
  build are a head start. `REBASE.md` §1 to §10 are still the owner's (or an
  agent's) to do.
- It does not read the advisory pages' prose. If an advisory names a
  version older than the shipped release, the watcher treats it as covered,
  even if a CVE in it was missed upstream.
- It does not build a new major unless `RELEASE_WATCH_AUTOBUILD=all`.
- It does not file anything upstream.

## On merge

The first hourly run on main after the merge acts on the state at that
moment. If Firefox 157.0.1 is still `LATEST_FIREFOX_VERSION`:

- #3 is assigned to the owner.
- #3 gets the MFSA 2026-104 comment, the `security` label and the title
  `[security: moderate] ...`.
- The patch check runs again for the new commit, with the result marker.
- Unless the policy is `off`, the next step is a candidate build of 157.0.1
  on box B, as soon as box B is idle. Set `RELEASE_WATCH_AUTOBUILD=off`
  before merging if box B is needed for 158.0-1 at that time.
