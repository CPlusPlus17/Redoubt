# Redoubt: the Android work

Redoubt is a privacy-hardened Android browser built from Firefox's source with
LibreWolf's shared patch set and privacy configuration applied.

**Redoubt is a fork. It is not the LibreWolf project and is not endorsed by it.**
The privacy configuration is LibreWolf's work and the MPL grants their code, not
their name. Read [`IDENTITY.md`](IDENTITY.md) before touching anything that names
the project.

**Current release: Redoubt 158.0-2** (Firefox 158.0, regular release track). Downloads,
fingerprints and install steps are in the [repository README](../../README.md) and on
[GitHub Releases](https://github.com/CPlusPlus17/Redoubt/releases). This directory is the
work plan, the decisions and the evidence behind them.

## For reviewers

| file | what it answers |
|---|---|
| [`PARITY.md`](PARITY.md) | what Redoubt does and does not match against LibreWolf desktop, row by row, measured |
| [`ISOLATION-MEDIA.md`](ISOLATION-MEDIA.md) | isolated content processes on Android 12+ (since 158.0-2) and where media is decoded |
| [`SIGNING.md`](SIGNING.md) | the signing key, its fingerprint and its custody, stated as it is |
| [`YUBIKEY.md`](YUBIKEY.md) | the planned move of the signing keys to a hardware token |
| [`SECURITY.md`](SECURITY.md) | how to report a vulnerability (also without a GitHub account) and what happens next |
| [`REPRODUCIBLE.md`](REPRODUCIBLE.md) | what has been reproduced so far, and what has not |
| [`POSITIONING.md`](POSITIONING.md) | how Redoubt relates to LibreWolf, IronFox and Firefox, and how it is made |
| [`DISTRIBUTION.md`](DISTRIBUTION.md) | the channels (GitHub Releases, the Redoubt F-Droid repository, Obtainium) and the update check |
| [`FDROID.md`](FDROID.md) | the Redoubt F-Droid repository |

## How Redoubt is made

Redoubt has one maintainer. AI coding agents (Claude Code, Codex and local models)
write and check most of the code, patches, tests and documentation, run the gates
(the build, the Fenix unit-test suite, emulator acceptance) and record the evidence
in [`evidence/`](evidence/). The maintainer sets direction, decides the trade-offs,
tests on devices and signs releases.

What you can check without trusting that process:

- the preference configuration (`settings/`, derived from LibreWolf's `librewolf.cfg`)
  and the shared patch set (`assets/patches/common.txt`, LibreWolf's patches split into
  common and desktop halves) are LibreWolf's work; Gecko and Firefox for Android are Mozilla's;
- Redoubt's own changes are the 48 Android patches listed in
  [`assets/patches/android.txt`](../../assets/patches/android.txt) (files in
  [`patches/android/`](../../patches/android/));
- every release names its source commit and the SHA-256 of Mozilla's source tarball;
- the test evidence for every release is in [`evidence/`](evidence/).

## For contributors

| file | what it is |
|---|---|
| [`AGENTS.md`](AGENTS.md) | the working rules: claiming a task, ownership, the landmines |
| [`tasks.yaml`](tasks.yaml) and [`board.py`](board.py) | the board: every task with dependencies, acceptance criteria and verify commands |
| [`REBASE.md`](REBASE.md) | the runbook for a Firefox release rebase |
| [`RELEASE-WATCH.md`](RELEASE-WATCH.md) | how new Firefox releases and Mozilla advisories reach the maintainer |
| [`PATCH-SCOPE.md`](PATCH-SCOPE.md) | which patches reach Android, one justification per patch |
| [`TRACK.md`](TRACK.md) | why Android follows Firefox release (since 157; the earlier ESR 153 decision is kept for the record) |
| [`TRIAGE.md`](TRIAGE.md) | labels, the issue form and canned replies |
| [`UPSTREAM-REPORTS.md`](UPSTREAM-REPORTS.md) | defects found in LibreWolf's build while porting |

[`STATUS.md`](STATUS.md), [`HANDOVER.md`](HANDOVER.md), [`BUILD.md`](BUILD.md) and
[`BETA.md`](BETA.md) describe earlier stages (the ESR 153 builds and the beta) and are
kept as the record; where they disagree with the files above, the files above are current.

Patch lists today: 22 common, 44 desktop, 48 Android.

## Gates

```sh
python3 docs/android/board.py --check        # board integrity — must be green
python3 docs/android/board.py --check-scope  # patch lists vs PATCH-SCOPE.md
python3 docs/android/board.py --diff-mozconfig  # no hardening flag silently dropped
python3 scripts/lint-patch-scope.py          # no patch in a list that cannot build it
./scripts/check-patchfail.sh                 # every patch still applies
python3 docs/android/board.py --ready --done <finished task ids>
```

`--ready` takes the tasks already finished and prints what that unblocks.

## Why the board looks like this

The board is written to be executed by several people or agents at once, so every
task declares which files it owns. `board.py --check` refuses a board where two
tasks in the same dependency wave write the same file, or where two patches in the
same wave edit the same file in the extracted source tree. That check is the reason
the dependency graph has edges that look redundant — several of them exist purely
to serialise writes to `scripts/librewolf-patches.py` and the patch lists.

Every task carries a `verify` command that a fresh agent can run, and acceptance
criteria written against observable behaviour rather than code inspection. In M4
especially, "verify" means a network capture or a dexdump of the built APK, because
a grep over sources does not prove a telemetry SDK is gone.

## The one thing to know before touching anything

Applying `webgl-permission.patch`'s common half to Android compiles
`librewolf.webgl.prompt` as `true`, which makes every WebGL context fail silently —
no crash, no console error — because the code that would answer the prompt lives in
the `browser/` half Android never receives. A build with this bug installs, browses,
and passes any smoke test that does not specifically check for a live WebGL context.

That is landmine L1 in [`AGENTS.md`](AGENTS.md), and it is representative: the
failure modes in this port are quiet ones. The board is built around catching them.
