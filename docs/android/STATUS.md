# Status snapshot — 2026-09-06

What is true today, what is merely landed, and what is not started. Replaces the
2026-08-18 snapshot, which had gone 19 days stale and said false things — it
counted 82 tasks (there are 89), 12 android patches (there are 25), and listed
LW-M4-05 as "produced nothing across three attempts" when `no-gms.patch` is
landed and its removal measured on a built APK.

**This file is a snapshot and will go stale the same way.** Re-derive rather than
quote it: the numbers below come from the commands shown, and every one of them
runs in under a minute.

## Milestone state — 67 / 89 done

    M0 15/16 · M1 16/16 · M2 8/9 · M3 9/11 · M4 10/16 · M5 3/7 · M6 2/7 · M7 4/7

Not done (22): LW-M0-07, M2-08\*, M3-05, M3-07, M4-04, M4-06\*, M4-08, M4-10,
M4-11\*, M4-12, M5-01, M5-04, M5-05, M5-06, M6-01, M6-02, M6-03, M6-04, M6-06\*,
M7-02, M7-04, M7-06.

\* M4-06, M4-11, M6-06 and M2-08 landed code on 2026-09-05/06 and are awaiting
device evidence or a CI run; they are counted not-done until their `verify`
passes. The done-set was derived from git log, `docs/android/evidence/<id>/` and
owned files, because **`tasks.yaml` has no status field** — `board.py --done`
takes a hand-typed id list. Re-derive with `board.py --ready --done <ids>`.

## Gates, as measured today

| gate | result |
|---|---|
| `board.py --check` | ok: 89 tasks, 17 waves, 0 warnings |
| `board.py --check-scope` | ok: 85 patch files (24 common / 36 desktop / 25 android); one declared-pending warning, `ubo-preinstall.patch` (LW-M3-07, parked) |
| `board.py --check-cfg-split` | ok: 182 common / 85 desktop / 6 android; `librewolf.cfg` regenerates exactly |
| `board.py --check-policies` | ok: 137 prefs declared by GeckoView, 26 shipped by us, every unlocked one classified. **Needs a tree**: `LW_TREE=librewolf-153.0esr-1` |
| `board.py --diff-mozconfig` | ok: hardening parity holds |
| `lint-patch-scope.py` | ok: 85 files, no violations |
| `check-patch-order.py` | ok: 11/11 constraints, 78 shared-file pairs classified |
| `check-patchfail.sh --targets=android` | exit 0 against the real ESR tarball |
| `board.py --check-fenix-tests` | **exit 2 — never run.** The suite has no results on disk anywhere on this machine, and AGENTS.md makes this gate the Definition of done for every Kotlin change. It used to exit 0 on that. |
| `android-pref-audit.sh` | **exit 2 — no baseline.** `docs/android/expected-prefs.txt` does not exist; LW-M3-05 owns it and it is required "from M3 onward". |
| `make check-fuzz` | A report, not a gate: the recipe is `-`-prefixed so it always succeeds, and `fixfuzz` is the paired repair step. **The report has to be read.** Measured 2026-09-06 with `--fuzz=0 --targets=android`: **15 hunks in 13 patches** only apply because `patch` is allowed to fuzz, and **3 of them are in `webgl-permission-common.patch`** — more than any other patch, and the one landmine L1 is about. A rebase that shifts those three is how WebGL breaks silently. |
| `android-smoke.sh` | needs a device. Static halves (`--check-no-gms`, `--check-no-adjust`) pass on the current APK. |

## The distinction that matters: LANDED is not VERIFIED

Most of the tree is **landed and gated**. Very little is **verified on a running
build**. In-repo device evidence exists for exactly two things: WebGL surviving
landmine L1 (`evidence/lw-m6-07/smoke3/result.json`) and autoconfig loading with
a lock surviving a Fenix toggle (`evidence/lw-m3-09`).

The often-quoted "0 GMS / 0 Adjust / 14 first-run events" figure is **not current**.
It was measured in `~/lw-fresh-2026-08-22/`, 46 commits ago, before the Remote
Settings blocker landed. The current first-run count is unknown.

Two findings worth carrying forward:

- **The gates do not check that code compiles.** `update-check.patch` (LW-M6-06)
  passed scope, order, patchfail and review, and then failed
  `:fenix:compileReleaseKotlin` twice on first build — an import this tree does
  not have, then a deprecated call under `-Werror`. Every gate stayed green. The
  answer is LW-M2-08's build job, added 2026-09-06.
- **Captures taken on this build host under-count.** The LAN resolver returns
  `0.0.0.0` for `incoming.telemetry.mozilla.org` and `ads.mozilla.org`, so only
  the DNS query is ever visible. `firefox.settings.services.mozilla.com` is not
  filtered. A first-run count from here is not publishable — see `BETA.md` E11.

## What is not started

- **LW-M7-04**: `TRIAGE.md` §0 has no OWNER and no BACKUP. That document calls it
  a LAUNCH BLOCKER in its own words.
- **LW-M6-01 acceptance**: one key holder, two copies. `SIGNING.md` records the
  gap rather than papering over it. Every APK built so far is `CN=Android Debug`,
  v2-only; Accrescent needs v3.
- **Sign-offs**: `TRACK.md` §8 (ESR track) and `PARITY.md` §5 (the public wording,
  marked "Do not publish as-is") are both blank.

## Where to start

`docs/android/BETA.md` is the ordered list — eleven entry criteria with their
evidence and status. E7–E10 need a person; the rest is build-and-measure work.
