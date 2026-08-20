# Status snapshot — 2026-08-18

Written at a hard stop: the API began returning 529 Overloaded for every subagent
spawn (three consecutive workflow resumes, `subagent_tokens: 0` each time, i.e.
nothing ran). The tree is left in a green, self-consistent state. This file records
what is true, what is merely landed, and what is not started, so the next session
does not have to reconstruct it.

## Gates — all ten green as of this snapshot

    board.py --check            82 tasks, 17 waves, 0 warnings
    board.py --check-scope      72 listed patch files (24 common / 36 desktop / 12 android)
    board.py --check-cfg-split  182 common / 85 desktop / 2 android; librewolf.cfg regenerates exactly
    board.py --check-policies   101 GeckoView-declared prefs, 21 shipped by us, all acknowledged
    board.py --diff-mozconfig   hardening parity holds
    lint-patch-scope            72 patch files, no scope violations
    check-patch-order           7/7 constraints, 40 shared-file pairs classified
    check-patchfail             desktop 0, android (--use-desktop-tarball) 0

## Milestone state

M0 16/16 · M1 16/16 · M2 6/8 · M3 3/8 · M4 5/13 (see caveat) · M5 3/7 · M6 0/6 · M7 3/7

## The caveat that matters: LANDED IS NOT VERIFIED

Batch 7 landed five patches but **every one of its six verifiers died**, as did the
integrate step. So the following are *applied and gate-clean*, and nothing more:

    patches/android/no-glean.patch          LW-M4-01
    patches/android/no-adjust.patch         LW-M4-02
    patches/android/no-onboarding.patch     LW-M4-10
    patches/android/no-nimbus.patch         LW-M4-13 (rewritten, incl. the test-casualty fix)
    patches/android/no-nimbus-toolkit.patch LW-M4-13
    patches/android/autoconfig-resource-fallback.patch  LW-M3-02 (now listed, no longer pending)

What the gates DO prove: the patches apply, are correctly scoped for the android
target, preserve the desktop applied-set, and satisfy the ordering constraints.

What NOTHING has proved yet, and what the M4 acceptance criteria actually demand:
  1. that Glean and Adjust are absent from the BUILT dex, not merely deleted from
     gradle files. Transitive inclusion survives exactly this kind of change.
  2. that a first-run network capture is empty. M4's headline claim — zero outbound
     requests between install and first navigation — has never been measured, and no
     single task could measure it, because each only carries its own patch.

Cheap evidence I did gather by hand, which is encouraging but not proof:
  - `no-adjust` touches `gradle/libs.versions.toml` AND `app/build.gradle` (96 removed
    lines mentioning the SDK), so the version-catalog coordinate is gone, not just its
    usages. `no-glean` touches `app/build.gradle` (175 removed lines).
  - Both touch 3 test files each, and `no-nimbus` touches 1 — so the unit-test
    casualty class that LW-M4-03 shipped blind was handled proactively this time.

## Not started

**LW-M4-05 (strip Play Integrity, Firebase, GMS)** produced nothing across three
attempts. There is no `patches/android/no-gms.patch` and no reference to one in
`assets/patches/android.txt`. It is the only batch-7 task with zero work on disk.

## Resume instructions

    Workflow({scriptPath: ".../librewolf-android-batch7-wf_fcc085c8-382.js",
              resumeFromRunId: "wf_fcc085c8-382"})

Three agents replay from cache. Run LW-M4-05 ALONE first if the API is still
flaky — it is the only task needing fresh implementation work, and a single agent
has a better chance than ten concurrent ones.

## Human decisions still outstanding

  LW-M4-07  the applicationId — irreversible after first release, blocks nothing else technically
  LW-M6-01  signing key generation and custody
  LW-M6-03/04  F-Droid repo and Accrescent accounts
  LW-M7-06  closed-beta go/no-go
