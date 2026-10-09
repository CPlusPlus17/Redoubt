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

## Outages: a warning first, red after 6 hours

An hourly run that turned red on every failure would send up to 24 failure
emails a day while product-details, archive.mozilla.org or the GitHub API is
down. So the script tells two kinds of failure apart:

- **Transient** (`TransientError`): no connection, a timeout, a body that is
  not JSON, or HTTP 408, 429 or 5xx, from a feed, the archive, the advisory
  files or the GitHub API. The run logs `warning: <source> failed
  (transient, failing since <time>)`, adds an Actions warning annotation and
  a `[!WARNING]` line to the job summary, and **exits 0**. A 5xx on the
  tarball HEAD is still never read as "no tarball yet": the outcome is
  `error`, not `no-tarball`.
- **Everything else** is red at once: HTTP 401, 403, 404 or 422 (a token, a
  permission or a path that needs a human), a malformed `version.android` or
  feed entry (no `LATEST_FIREFOX_VERSION`), a refused input, a bug.

Each source (the two feeds, "Firefox release", "Firefox for Android",
"latest release", "security advisories", "reminders") keeps its own streak.
`--state-file` (`$RELEASE_WATCH_STATE`) is a JSON file
`{"failing_since": {"<source>": "<UTC time of its first failure>"}}`. A
source that answers ends its streak. When a source that fails now has been
failing for more than `OUTAGE_HOURS` (6 h), the run is red, and stays red
every run until the source answers again. The workflow keeps the file in the
Actions cache: `actions/cache/restore` takes the newest
`release-watch-outages-*` entry, and `actions/cache/save` writes
`release-watch-outages-<run id>` after every run, red ones included (cache
entries cannot be overwritten). A lost or unreadable file only restarts the
count; it can delay a red run, never cause one. Without `--state-file` (by
hand), a transient failure is never red.

The cache was chosen over the alternatives because it needs no write to an
issue (no notification noise) and no extra API calls. Reading the previous
runs' conclusions through the API does not work: those runs are green now.

The `patchcheck` and `autobuild` steps also treat a transient failure as a
warning and exit 0. They write nothing before their last step, so the next
hourly run simply retries. A long outage of the same service turns the
`watch` job red, because it reads the same archive and API.

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
   `<!-- redoubt-autobuild version=<v> -->` comment, or the no-build-date
   comment of step 5, the job stops. To build again, dispatch
   `android-release.yaml` by hand.
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
5. **Build date** (next section). If no hour fits, the job does not create
   the branch or dispatch. It comments once
   (`<!-- redoubt-autobuild-nodate version=<v> -->`), says why, mentions the
   owner and states that **the owner must pick the build date** and dispatch
   by hand. The watcher then never builds that version itself, so a hand
   dispatch cannot race it.
6. **Dispatch** `android-release.yaml` on the branch with `mode=full`,
   `update_check=true` and `build_date=<step 5>`. A push or ref created
   with `GITHUB_TOKEN` starts no workflow by itself; GitHub exempts
   `workflow_dispatch`, which is why the dispatch is explicit.
7. **Comment**: the branch, the build date and why it was chosen, its
   versionCodes, the runs page and the next steps.

### Build date and versionCode

Fenix's versionCode is `0x78200000 | (hours since 2014-12-28 00:00 UTC) << 3`
plus three ABI bits (`scripts/android-aab.py version_code`: armeabi-v7a +0,
arm64-v8a +2, x86_64 +6, universal +7). It follows the **hour** of
`MOZ_BUILD_DATE` and grows by 8 per hour. Android, Obtainium and the update
check all treat a higher versionCode as newer. Before this fix the job used
`build_date=now`. A 157.0.x candidate built on 2026-10-09 would then have got
a higher versionCode than 158.0-1 Beta 1 (built 20261007050000). Beta
testers, whose profiles are already 158, could have been offered it, or moved
down to it by Obtainium: an older Firefox under a newer profile.

The precedent is 157.0.1-1
(`evidence/lw-m7-01/release-157.0.1/README.md`, "Build date and
versionCodes"). Its build date, 20261006180000 (codes 2016188816-823), was
picked by hand between 157.0-3 (20261006090000, 2016188744-751) and Beta 1
(20261007050000, 2016188904-911). The job now applies the same rule itself
(`choose_build_date`):

- **Lower bound**: the build hour of the release GitHub marks *Latest*. With
  no Latest release there is no lower bound.
- **Upper bound**: the earliest build hour among the published (non-draft)
  releases, prerelease or not, of a Firefox **major** newer than the
  candidate's. For 157.0.x that is the oldest 158 beta, because a tester may
  still run Beta 1. A superseded beta of the same major, and any draft, is no
  bound.
- The hour must be strictly between the bounds, not after the run's own
  hour (no build date in the future), and not one any release (or a rejected
  build, `REJECTED_BUILD_DATES`: 20261004200000) already used.
- **No upper bound**: the run's own hour, as before but at the full hour, so
  the versionCodes in the comment are exact.
- **Otherwise**: the middle hour of the free window, rounded down (the
  nearest unused hour if that one is taken). The middle leaves room for
  another dot release on either side. On 2026-10-09 this gives
  20261006190000 (codes 2016188824-831) for 157.0.1, one hour from the hand
  pick. A later 157.0.2, with 157.0.1-1 as Latest, would get 20261006230000.
- **No hour fits**, or a bound release's build date cannot be read: no
  build (step 5).

**Where the build hours come from: the release notes.** The asset names
(`fenix-<abi>-release.apk`) carry no versionCode. Reading the APKs would mean
downloading about 400 MB per release. Every release since 157.0-2 states its
build date in the Provenance section ("CI run N, with MOZ_BUILD_DATE
YYYYMMDDHHMMSS"), and some add "versionCodes N-M". The job reads
`MOZ_BUILD_DATE <14 digits>` and, failing that, the first code of
`versionCodes N`. If both are present they must give the same hour.
Otherwise, or if neither is present, the date is unreadable; that only blocks
a build when the release is one of the two bounds. **So every release's notes
must keep the "MOZ_BUILD_DATE YYYYMMDDHHMMSS" line**, betas included.

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
# Outage tracking by hand: a transient failure is red only with a state file
# whose streak for that source is older than 6 h.
python3 scripts/firefox-release-watch.py --dry-run --state-file /tmp/outages.json
# What autobuild would do for an issue (reads the issue and the releases, and
# prints the build date it would choose and why; needs a token).
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

origin/main is now at ff6e15f7, the 157.0.1-1 rebase: `version` and
`version.android` are `157.0.1`. The Latest GitHub release is still
`android-157.0-3`. While Firefox 157.0.1 is `LATEST_FIREFOX_VERSION`, the
first hourly run on main after the merge does this:

- The release check says `current`: neither track is behind 157.0.1. So
  there is no patch check and **no candidate build**.
- The advisory check finds MFSA 2026-104 (fixed in 157.0.1), and the shipped
  `android-157.0-3` is behind it. #3 is the open issue for 157.0.1. It gets
  the advisory comment, the `security` label and the title
  `[security: moderate] Firefox 157.0.1 released: ...`, and it is
  **assigned** to the owner.
- From then on, #3 gets a **reminder** that mentions the owner every
  24 hours.

This continues until `android-157.0.1-1` is published and marked Latest.
Then the shipped release is no longer behind 157.0.1, so the reminders stop.
The owner closes #3. Firefox 158.0 (due 2026-10-13) gets its own issue and
patch check, but no candidate build under the default `dot` policy.

## Recommended: a ruleset on main (owner action)

The `autobuild` job runs with `contents: write`. It only creates
`auto/firefox-<v>` branches through the git data API, but the token it holds
could also move `main`, as could any other workflow token with
`contents: write`. The owner should add a
**branch ruleset** that lets only the owner update `main`. This task does
not create it:

- Settings → Rules → Rulesets → New ruleset → New branch ruleset.
- Name `main: owner only`, Enforcement **Active**.
- Bypass list: **Repository admin** (the owner), "Always allow". Do not add
  GitHub Actions or any app.
- Target branches: **Include default branch**.
- Rules: **Restrict updates**, **Restrict deletions**, **Block force
  pushes**. Add **Require signed commits** too: main is already signed-only
  by convention.

The `auto/*` branches stay outside the ruleset, so the job keeps working. A
`github-actions[bot]` push to main is then refused. The owner's signed local
merges and pushes go through the bypass.
