# Roadmap — Redoubt

Strategy, decided 2026-08-14: **build Gecko from source and port everything, one
shared patch set with desktop.** Timeline is explicitly not the constraint.
Maintainer attention is.

The task-level detail lives in [`tasks.yaml`](tasks.yaml); the rules for working on
it live in [`AGENTS.md`](AGENTS.md). This file is the why and the shape.

- **66 tasks, 328–638 hours, 15 dependency waves**
- **13 agents** is the widest useful parallelism (wave 8)
- **171 hours** on the critical path if every task on it runs long
- **5 tasks need a human** — signing keys, the applicationId, distribution channels
- **30 tasks need worktree isolation** — they mutate the ~10GB source tree

---

## What makes this hard

LibreWolf is not a fork. It downloads a GPG-verified Firefox tarball and applies 53
patches on top. Its actual identity — the thing that makes it LibreWolf rather than
a rebuild of Firefox — lives in two places, and **both are compiled out on
Android**:

1. **Autoconfig.** `settings/librewolf.cfg` (763 lines: 178 `defaultPref`, 60
   `lockPref`, 26 bare `pref`, 12 `librewolf.*` prefs) is delivered through
   `general.config.filename`. `nsReadConfig` resolves the `.cfg` relative to
   `NS_GRE_DIR`, and `nsXREDirProvider.cpp` leaves that empty on Android.
2. **Enterprise policies.** `settings/distribution/policies.json` carries
   `DisableTelemetry`, `HttpsOnlyMode`, the uBO preinstall and more.
   `toolkit/components/enterprisepolicies/moz.build` gates the whole engine on
   `MOZ_WIDGET_TOOLKIT != "android"`.

So the port is not "compile the same patches for a different target". It is a
second product that has to arrive at the same configuration through entirely
different plumbing. That is what M3 is, and it is the milestone with no desktop
precedent to copy.

## What we are honestly promising

Full parity is the target and it is *nearly* reachable. Two things are not:

- **The Gecko content-process sandbox.** `MOZ_SANDBOX` is off on Android,
  `toolkit.mozbuild:37` never traverses `security/sandbox`, and every
  `security.sandbox.*` pref is inert. LW-M5-07 is a time-boxed spike to confirm
  whether that is policy or physics; the working assumption is that it stays gone.
  The mitigation is Android's own containment — `isolatedProcess` plus the app
  zygote (LW-M5-02), and a locked `fission.webContentIsolationStrategy`
  (LW-M5-01) — which recovers most, not all, of it.
- **The signing key.** A new `applicationId` means no upgrade path from any
  existing Android browser, and the key we generate in LW-M6-01 cannot be replaced
  later without stranding every install.

Letterboxing is **not** on this list, despite appearing on earlier drafts. Desktop
LibreWolf ships `privacy.resistFingerprinting.letterboxing` as `false`
(`settings/librewolf.cfg:255`, "expose hidden letterboxing pref but do not enable
it for now"), so Android not having it is not a parity loss for our users.

The agreed public wording, which LW-M5-06 must not soften:

> Redoubt ships the same privacy configuration and the same
> Gecko-level security patches as LibreWolf desktop, on a platform whose process
> containment is weaker — and we publish exactly where.

## What we get for free, that stock Android does not have

Two findings worth stating up front because they invert the usual assumption that
the Android build is "Firefox but locked down":

- Android release ships `fission.webContentIsolationStrategy = 0`
  (ISOLATE_NOTHING) from `nimbus.fml.yaml:521-535`, read *unconditionally* at
  `Core.kt:207-208`. Stock Fenix has **no** per-site process isolation.
- `.isolatedProcessEnabled(true)` and `.appZygoteProcessEnabled(true)` are
  available in `GeckoProvider.kt` with no build flag — both service families are
  already in the generated manifest — and stock Fenix does not use them.

Between them that is the single cheapest security win on the board, and it makes
Redoubt meaningfully harder to attack than the browser it is built
from.

---

## Milestones

### M0 — Foundations · 10 tasks · 22–42h

Make the build repo target-aware without changing a byte of the desktop output.
`TARGETS` in the Makefile, a three-way patch list, an Android mozconfig that
carries every desktop hardening flag, a pinned toolchain image, and a CI skeleton.
Two supply-chain fixes land here that help desktop too: the unpinned l10n fetch
(`librewolf-patches.py:161-165` pulls `refs/heads/main` unverified into every
release build) and the out-of-patch OpenAI deletions.

**Exit:** `make dir` with no arguments is byte-identical to today, and
`make dir TARGETS=common,android` produces a tree with no `browser/`-only patches
in it.

### M1 — Patch-set surgery · 11 tasks · 28–52h

Split the 53 patches three ways and cut the 8 straddlers in half. This is the
highest-leverage parallel milestone — 11 tasks run at once, each owning its own
patch files. The scope rule must be file-level, not prefix-level (landmine L3), and
four patch pairs have a mandatory apply order that gets encoded as a test.

**Exit:** `scripts/lint-patch-scope.py` and `scripts/check-patch-order.py` both
green, desktop tree byte-identical to before the split, every straddler split with
its desktop half producing no diff.

### M2 — Build bring-up · 8 tasks · 63–133h

The critical path. Prove the toolchain on an *unpatched* tree first, then add the
common patch set, then fat-AAR across three ABIs, then the Fenix Gradle stage, then
an APK that installs. `--enable-appservices-in-tree` lands here because M4's search
configuration depends on owning those dumps.

The temptation throughout M2 is to fix a compile error by dropping a patch. That is
a parity loss wearing a build fix's clothes; every drop must be recorded.

**Exit:** an APK that installs, loads a page, and whose `about:buildconfig` shows
our mozconfig — plus a smoke-test harness strong enough to catch landmine L1.

### M3 — Pref delivery · 7 tasks · 45–78h

The milestone with no precedent. Split `librewolf.cfg` three ways, compile it into
the two channels that actually work on Android, and get the locking right — see
landmine L2, because the precedence is the opposite of what it looks like.
`MOZ_DEFAULT_PREFS` runs *before* the profile, Fenix's runtime `Pref.commit()` runs
*after*, so `defaultPref` survives startup and then loses to any Fenix write.

**Exit:** every pref we ship is observable at its intended value after the settings
UI has been opened, verified by a checked-in baseline diff that runs in CI.

### M4 — De-Mozilla-ing the Kotlin layer · 11 tasks · 61–120h

Everything above Gecko: Glean, Adjust, Nimbus, Socorro, Play Integrity and
Firebase, the search configuration, onboarding, sponsored tiles, search
suggestions, branding. Highly parallel — 8 of these run simultaneously in wave 8.

The standard here is removal, not configuration. A disabled-by-flag Glean is one
upstream default flip away from shipping data from a privacy browser, and every
acceptance criterion in this milestone is written against a **network capture or a
built APK**, never against source grep.

**Exit:** zero outbound requests between install and the user's first navigation.

### M5 — Security parity · 7 tasks · 40–78h

The point of the project. Lock the isolation strategy, turn on Android's own
process containment, close the hardening-flag gap the M0 mozconfig had to leave
open, and validate that RFP and the network posture actually behave on Android
rather than merely being set. Ends with the parity matrix and the public wording.

**Exit:** `PARITY.md` has a mechanism or an explicit gap in every row, with the
sandbox gap stated plainly rather than buried.

### M6 — Release engineering · 6 tasks · 46–92h

Key custody first, then reproducibility, then the channels: our own F-Droid repo,
Accrescent, direct APK with Obtainium metadata. The Play Store is out of scope —
its signing model conflicts with keeping the key offline.

The structural rule: **CI publishes unsigned artifacts and hashes; a maintainer
signs offline.** The key never exists in CI, in an image, or in a repo. One
convenience commit undoes the whole model.

**Exit:** two machines produce byte-identical unsigned APKs, and every channel
publishes the same fingerprint.

### M7 — Launch and sustain · 6 tasks · 23–43h

The rebase runbook, the website pages, the FAQ reversal (it currently points
Android users at IronFox), triage labels, the disclosure process, and a closed beta
weighted toward low-RAM devices — because the memory cost of fission plus
`isolatedProcess` is invisible on a flagship and decisive on a budget phone.

**Exit:** a maintainer who did not write the runbook can complete a dot-release
rebase from it alone.

---

## Release track

Decision, upheld by LW-M0-07 after checking the numbers: **Android tracks esr153
while desktop stays on release.** Full evidence in [`TRACK.md`](TRACK.md).

Three of the four figures this section originally carried were wrong. Corrected:

| | desktop (release) | android (esr153) |
|---|---|---|
| **hard rebases** per year | 26 | **1** |
| releases we cut per year | ~46 | ~27 |
| adoption cost today | — | **not zero** — a second source tree |
| co-maintainers of the same base | — | Tor Browser *Stable* only |

- **The current tarball is NOT esr153.** `browser/config/version_display.txt` reads
  `153.0.4` with no `esr` suffix, and `init.configure:1151` computes
  `is_esr = app_version_display.endswith("esr")`, so `MOZ_ESR` is unset. ESR 153 is
  a separate 767 MB artifact at `releases/153.0esr/source/`. The "zero adoption
  cost" claim was false; Android needs its own tree.
- **`MOZ_ESR` is not inert.** It changes seven sites, two of which hit board work:
  `SearchUtils.sys.mjs:361` and `RustSharedRemoteSettingsService.sys.mjs:44` both
  select an `"esr"` channel — relevant to LW-M2-05 and LW-M4-06.
- **ESR barely reduces how many releases we cut** (~26/yr of ESR dots, not ~12 —
  the calendar schedules an ESR 153 dot on every release date). What it reduces is
  **hard rebases: 26 a year to 1.** That is the entire argument, and it is stronger
  than the version it replaces.
- **Mozilla moved to a two-week major cadence** from Firefox 155 on 2026-09-01. The
  "26 majors" figure is right going forward; it was 13.5 when this was first written.

**The cost, stated plainly.** ESR ships security fixes later: of ten release-channel
security dots in 2026, six had no same-day ESR counterpart — median lag **14 days**,
max **21**. The worst case was MFSA 2026-67 (Critical, exploit code public) reaching
ESR seven days later.

**And the one that matters most here: there is no Firefox for Android ESR.**
MFSA 2026-73 is an Android-only advisory with no ESR counterpart and no reason to
acquire one. Tracking ESR on Android means inheriting that gap and backporting
Android-specific security fixes by hand. This does not reverse the decision — 26
hard rebases a year is unsurvivable for this team and one advisory stream is not —
but it converts into a standing **watch obligation** that needs a named owner
(LW-M7-05), and it belongs on the download page rather than in a footnote.

**Reversal is asymmetric.** release→ESR is cheap (wait for the next cut). ESR→release
gets more expensive every month, because there is no intermediate green build to step
through. Keep the track decision uncoupled from the applicationId and signing key
(LW-M4-07, LW-M6-01) so it stays a one-line change.

## Forge

Everything stays on **Codeberg**. Forgejo Actions, the `epsilon` runner, the
package registry and the issue tracker are already there, and none of them have a
GitHub dependency. Upstream is read *from* `github.com/mozilla-firefox/firefox`
(canonical since `mozilla/gecko-dev` was archived) — reading is not hosting.

## Running the board

```sh
python3 docs/android/board.py --check    # CI runs this; keep it green
python3 docs/android/board.py --waves    # what can run in parallel
python3 docs/android/board.py --ready --done LW-M0-01,LW-M0-04
python3 docs/android/board.py --show LW-M1-08
python3 docs/android/board.py --stats
```

## Wave shape

```
wave  0   5 tasks   ████████
wave  1   4 tasks   ██████
wave  2   1 task    ██                  <- LW-M0-02, the serialization point
wave  3   2 tasks   ███
wave  4   1 task    ██                  <- LW-M1-01, gates all patch surgery
wave  5  11 tasks   ██████████████████  <- straddler splits, all parallel
wave  6   7 tasks   ███████████
wave  7   4 tasks   ██████
wave  8  13 tasks   █████████████████████  <- widest; most of M4
wave  9   5 tasks   ████████
wave 10   4 tasks   ██████
wave 11   3 tasks   █████
wave 12   3 tasks   █████
wave 13   2 tasks   ███
wave 14   1 task    ██
```

Two single-task waves gate everything downstream: **LW-M0-02** (the target-aware
patch lists) and **LW-M1-01** (the authoritative scope split). Both are cheap.
Neither should sit in a queue — if only one person is available at the start of the
project, they should be doing these.
