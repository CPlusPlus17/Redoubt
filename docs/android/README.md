# Redoubt

An Android browser that compiles Gecko from source and applies LibreWolf's patch
set and privacy configuration, sharing both with the desktop build rather than
patching a prebuilt Fennec.

**Redoubt is a fork. It is not the LibreWolf project and is not endorsed by it.**
The privacy configuration is LibreWolf's work and the MPL grants their code, not
their name — read [`IDENTITY.md`](IDENTITY.md) before touching anything that names
the project.

This directory is the work plan and the record of what has been done against it.

**Status: M0 and M1 complete, M2 done, M3/M4 well advanced.** Gecko builds from
source for aarch64-linux-android with the full patch set and every hardening flag
intact; a three-ABI fat AAR and an installable APK exist and run *our* GeckoView
(verified from the packaged `omni.ja`, not inferred). Autoconfig works on Android,
so `lockPref` produces real `Preferences::Lock` calls that survive the Fenix
settings screen. Glean, Adjust, Nimbus, Play Integrity and the onboarding flow are
removed. First-run network traffic is **22-24 events over 4 hostnames, down from 59
over 8** — all that remains is Remote Settings and one `ads.mozilla.org` lookup, both
tracked. 76 patch files: 24 common, 36 desktop, 16 android.

Not done: the Android build still ships the *desktop* pref composition (LW-M3-10),
the UI still says "Firefox" (LW-M4-12), and nothing is signed or distributed.

## Read in this order

| file | what it is |
|---|---|
| [`IDENTITY.md`](IDENTITY.md) | **read first** — this is a fork, not the LibreWolf project, and what that constrains |
| [`ROADMAP.md`](ROADMAP.md) | the shape: strategy, milestones, what we can and cannot promise |
| [`AGENTS.md`](AGENTS.md) | the rules: how to claim a task, ownership, the five landmines |
| [`tasks.yaml`](tasks.yaml) | the board: every task with dependencies, acceptance criteria, verify commands |
| [`PATCH-SCOPE.md`](PATCH-SCOPE.md) | which patches reach Android — reviewed, one justification per patch |
| [`BUILD.md`](BUILD.md) | how to reproduce the Android Gecko build |
| [`TRACK.md`](TRACK.md) | the esr153 decision, with the rebase and security-latency numbers |
| [`UPSTREAM-REPORTS.md`](UPSTREAM-REPORTS.md) | three defects found in LibreWolf's build, worth reporting back |
| [`STATUS.md`](STATUS.md) | what is landed versus verified at the last checkpoint |
| [`board.py`](board.py) | validator and query tool for the board |

## Start here

```sh
python3 docs/android/board.py --check        # board integrity — must be green
python3 docs/android/board.py --check-scope  # patch lists vs PATCH-SCOPE.md
python3 docs/android/board.py --diff-mozconfig  # no hardening flag silently dropped
python3 scripts/lint-patch-scope.py          # no patch in a list that cannot build it
./scripts/check-patchfail.sh                 # every patch still applies
python3 docs/android/board.py --ready --done <finished task ids>
```

All five gates above are green on the current tree. `--ready` takes the tasks
already finished and prints what that unblocks.

Two of the completed M0 tasks fix the **desktop** build and are worth landing on
their own, independently of Android: `LW-M0-04` pinned the l10n fetch, which was
pulling an unverified `refs/heads/main` into every release build, and `LW-M0-11`
fixed `check-patchfail`, which silently reported success when a patch's target file
was missing.

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

## Status

See [`STATUS.md`](STATUS.md) for what is landed versus verified. `tasks.yaml` is
the source of truth for the board and should be edited in the same commit as the
work it describes.
