# Closed beta (LW-M7-06)

Owner: LW-M7-06. This file is written **before** the beta starts, as the task's
first acceptance line requires. It fixes the entry criteria, the device spread,
what is collected, the exit criteria, and holds the go/no-go decision at the end.
The entry table records preparation evidence. §6 records tester results as they
arrive; §7 stays blank until the owner makes the public-release decision.

The beta exists for one reason above all others: the memory cost of site
isolation (LW-M5-01) plus `isolatedProcess` (LW-M5-02) is invisible on a flagship
and decisive on a budget phone. Every design choice here is weighted toward
finding that out on hardware we do not own.

## 1. Entry criteria

The beta does not start until every line below is true and the evidence is
linked. "Green on the maintainer's machine" counts only where the line says so.

| # | Criterion | Evidence | Status |
|---|---|---|---|
| E1 | The build carries all landed Android patches (`assets/patches/android.txt`), compiled from the pinned ESR tarball by `make android-apk TARGETS=android` | Candidate build log, source/input manifest and `build-times.txt` | **Met 2026-09-08.** `make android-apk TARGETS=android` completed with R8 on (505 s); the isolated candidate source matches all 248 paths touched by the 50 common/Android patches applied to the pinned tarball. See `evidence/lw-m6-08/candidate-build-times.txt` and `patch-source-comparison.json`. Native AARs are the existing three-ABI inputs; the new patch changes Gradle tooling only. |
| E2 | Both ARM ABIs are real Gecko builds; every ABI directory in the universal APK carries its engine | Candidate APK entry list and ELF headers for each `libxul.so` | **Met 2026-09-08.** Inspected all four candidate ZIPs and ELF headers: ARM32, ARM64 and x86_64 are real engines, every native ABI directory is expected, and the universal carries all three. `evidence/lw-m6-08/candidate-native-abis.json` binds this check to each APK hash. |
| E3 | Smoke suite green on the emulator against the beta payload, except the two strict zero-Remote-Settings checks E12 deliberately leaves red | [Candidate audit](evidence/lw-m7-06/beta-audit-2026-09-08/) | **Met 2026-09-08.** Exact x86_64 candidate payload: baseline 7/7; search, branding/UI, suggestions OFF→ON→OFF, update privacy, release `about:config` edit/restart, no-GMS and no-Adjust checks pass. Baseline negative controls and 23 harness regression tests pass. [Final runtime evidence](evidence/lw-m7-06/beta-audit-2026-09-08/final-candidate/README.md). Update checks are compiled out; an enabled update path is untested. The two E12 exceptions remain red. |
| E4 | Runtime pref audit exits 0, with `expected-prefs.txt` generated from the beta build and its diff reviewed | Candidate pref dump, baseline comparison and audit output | **Met 2026-09-08.** Ran the baseline generator against the final candidate: generator, reviewed diff and audit exit 0. All 58 baseline rows are unchanged (SHA-256 `2ac8b4f9…`). The audit reports zero violations and zero other differences. See `final-candidate/pref-baseline-regeneration.json`, archived before/generated baselines and `pref-audit-final.out` in the candidate audit. Of 137 must-lock keys, 20 are covered by this runtime dump; the generated lock/policy gate covers the rest. |
| E5 | `board.py --check-fenix-tests` exits 0 on a full Fenix suite from the candidate's source | Archived JUnit XML, source hashes and subtraction output | **Met 2026-09-08.** Full patched-source run: 598 classes / 5,426 tests; 93 failures = 90 environmental + 3 known-real + 0 unexpected; subtraction exit 0. Final JUnit XML and exact source/candidate linkage are archived in the candidate audit (`fenix-gate.txt`, `fenix-junit-xml.tar.gz`, `fenix-final-candidate.json`). |
| E6 | `scripts/android-verify-repro.sh --r8` exits 0 for the candidate inputs and both outputs match the candidate | Two independent build logs, hashes and negative control | **Met 2026-09-08.** Corrected version and Glean timestamps; `--r8` exits 0 after two independent builds (1,426 s total). All four outputs match each other and the normal candidate byte for byte; the negative control detects its one-byte corruption. [Logs and comparison](evidence/lw-m6-08/repro/README.md). Same-machine APK assembly only; Gecko/AAR and cross-machine reproducibility remain unverified. |
| E7 | Signed with the release key, **v2 + v3, no v1**, fingerprint matches `SIGNING.md`; signed offline by a holder, never on the CI runner, and the key is no longer readable by that runner | [Signing handoff](evidence/lw-m6-01/RELEASE-HANDOFF.md), signed APK verification, custody confirmation | **Not met.** `~/redoubt-signed/` is empty. On 2026-09-08 `~/redoubt-release.p12` still exists, owned by the user running the live Actions runner. The holder must sign the verified candidate elsewhere and remove the build-host copy after confirming the offline copy. |
| E8 | A second key holder exists, or the single-holder decision is recorded with a date in `SIGNING.md` | `SIGNING.md`, “Decision: Redoubt ships single-holder” | **Met.** Manuel Gysin's dated 2026-09-06 decision is recorded in commit `aca09eb`. This does not satisfy LW-M6-01's separate two-holder criterion. |
| E9 | The parity wording (`PARITY.md` §5) is signed off | `PARITY.md` §5, commit `aca09eb` | **Met.** Owner approved the wording verbatim on 2026-09-06. Publication belongs to the public release. |
| E10 | A triage owner and backup are named, or the dated solo-owner decision is recorded, and the Android bug-report form (LW-M7-04) is live | `TRIAGE.md` §0, local form, [live repository audit](evidence/lw-m7-06/beta-audit-2026-09-08/human-criteria.md) | **Met 2026-09-08.** Following user approval, both form files are on default `main` at `c65d2e4` and all eleven labels are verified live. GitHub’s public preview renders the parsed Android form, field controls, required markers and labels. The owner and solo arrangement remain recorded. [Publication evidence](evidence/lw-m6-08/github-publication.md). Authenticated submission validation remains the separate, unperformed LW-M7-04 manual check. |
| E11 | First-run network capture uses a resolver that does **not** sinkhole Mozilla hosts | Candidate pcap, DNS control and parsed events | **Met 2026-09-08.** The final candidate was captured with emulator DNS `9.9.9.9`; direct controls return public addresses for telemetry, ads and security hosts. The authoritative `final-candidate/first-run-capture-final.json` records 11 outbound transport events, including three complete security-host SNI names. Raw pcap and DNS controls are retained. These are transport observations, not decrypted requests or complete app-UID attribution. |
| E12 | The Remote Settings allowlist has been decided **for Android**, and the beta carries that decision | `settings/android.cfg`, `evidence/lw-m4-08/RESULT.md`, candidate pref dump | **Met 2026-09-08.** The final candidate’s effective `librewolf.services.settings.allowedCollections` matches all seven approved entries in `settings/android.cfg`; the eleven local `allowedCollectionsFromDump` entries are unchanged. See the candidate audit’s `final-candidate/prefs-all.json`. The two strict zero-traffic checks remain red and retain their original assertions; hostnames alone cannot establish which encrypted collections were requested. |

**Current result: eleven of twelve entry criteria met. E7 remains open.**

**Audit reopened 2026-09-08.** The previous “eleven of twelve met” summary was
not supported for the final unsigned APKs. Their hashes and version codes differed
from the old reproducibility and runtime evidence, and the bug form was never live
on the default branch. The current audit binds each result to the actual candidate.

Key custody is part of **E7**, not an optional issue outside these criteria.
Signature verification cannot establish where signing occurred or whether the
runner can still read the key. Those facts need separate holder confirmation and
build-host verification. No release key or passphrase is used by this audit.

Preparing entry does not complete the 14-day beta. Device assignments, tester
results, the second-build upgrade and the public-release GO/NO-GO below remain
required at their respective stages.

## 2. Device spread

The task requires at least one device with 4 GB of RAM or less and at least one
running Android 10 or older. That is the floor, not the plan. Target:

| slot | why | who holds it |
|---|---|---|
| 1. ≤ 3 GB RAM, arm64, Android 10–12 | the OOM case the whole beta is weighted toward | _______ |
| 2. 4 GB RAM, arm64, Android 13+ | the common budget phone | _______ |
| 3. Android 9 or 10, any RAM | oldest supported platform behaviour (WebAuthn is lost below 14 with no GMS — see `no-gms.patch`) | _______ |
| 4. 32-bit ARM (`armeabi-v7a`) if any device can be found | the ABI with the weakest hardening (`hardening-flags.md`: no `-fstack-clash-protection`) | _______ |
| 5. flagship, arm64, current Android | the control: if it fails here it is not a memory problem | _______ |
| 6. one device on a network with no DNS filtering | E11, and the only honest first-run count | _______ |

Record the holder next to each slot and copy the table into `TRIAGE.md` §0, which
asks for exactly this ("who holds which device").

## 3. Duration and channel

- **Length:** 14 days from the first install. The public-launch rotation in
  `TRIAGE.md` §5 starts separately when the public download page goes live.
- **Channel:** direct APK only, from a private link, signed with the release key
  (E7). Not the F-Droid repo, not Accrescent: those channels are M6-03/M6-04 and
  come after the beta, and a beta build in a public repo is a public release.
- **Update path test:** at least one **second** beta build is shipped during the
  window, signed with the same key, and every tester installs it over the first.
  A beta that never exercises the upgrade path has not tested the one thing the
  signing key exists for.
- **The in-app update check** (`update-check.patch`) is **compiled out** of beta
  builds unless the update-signing key and the endpoint exist by then; the row is
  absent, which is the store-build shape. If it is compiled in, E3's
  `--check-update-privacy` must have run against that exact build.

## 4. What is collected

Only what a reporter can actually provide (`TRIAGE.md` §3, item 4), and nothing
that identifies a person:

1. Device model, total RAM, Android version, ABI installed (from Settings > About
   or `adb shell getprop`).
2. **Launch:** cold start time to first paint of the home screen (stopwatch is
   fine); whether it launched at all on the first three tries.
3. **Memory:** whether the app was killed in the background during ordinary use;
   `adb shell dumpsys meminfo org.redoubtbrowser` once with five tabs open, if the
   tester can run adb. This is the number the beta is for.
4. **WebGL:** `https://get.webgl.org` loads a spinning cube. This is landmine L1's
   signature and must be checked on every device, every build.
5. **Privacy posture, from the UI:** Settings > Search lists DuckDuckGo (default),
   Startpage, Mojeek, Wikipedia — with icons; "Show search suggestions" is off;
   Settings > About shows no "Check for updates" row (compiled out) or shows it
   off (compiled in); `about:config` is reachable in the release build; privacy locks remain enforced.
6. **Sites that break** with RFP/ETP strict, listed by URL; whether stock Firefox
   for Android breaks them too.
7. **Anything that says "Firefox" or "Mozilla" in the UI**, with a screenshot —
   `--check-strings` covers the resource table and the deep-linked settings
   screens, not every dialog.
8. **Battery**: subjective only, unless the tester volunteers `dumpsys batterystats`.

How: one issue per finding through the Android bug-report form (LW-M7-04) with the
`beta` label. The form must be live before the beta starts (E10). If it becomes
unavailable during the beta, testers may provide summary messages at day 7 and
day 14; this fallback does not waive E10. `adb logcat` is asked for only on
crashes, with the warning that it contains visited URLs.

## 5. Exit criteria — go / no-go for the public release

**No-go on any one of these:**

- N1. A crash on launch, or an OOM kill within the first minute of ordinary use,
  on any device in slots 1–3 that is not explained and fixed by a second build
  inside the window.
- N2. Any outbound connection in a first-run capture (E11) to a Mozilla telemetry,
  experiments, ads, or crash-reporting host, or to any Google host from the app
  itself. Remote Settings sync outside E12's approved Android allowlist is also a no-go.
  The seven entries in `settings/android.cfg` are the recorded exception for
  security updates; log their traffic and verify the effective allowlist. A
  Mozilla hostname alone does not prove the traffic is approved, and the strict
  zero-Remote-Settings harness checks remain unchanged.
- N3. WebGL broken on any device (L1).
- N4. A search from the toolbar carrying a partner or attribution code, or going
  to an engine that is not in `assets/search-config-v2.json`.
- N5. The second beta build failing to install over the first on any device
  (signing-key or `applicationId` mismatch). This one ends the beta on the spot.
- N6. A privacy pref on `must-lock.txt` found unlocked or moved on a tester's
  device (`--pref-dump` from a tester with adb, diffed against the baseline).

**Go requires all of:**

- G1. Every slot 1–3 device completed the 14 days with the app usable for daily
  browsing, in the tester's own words.
- G2. Every N-item above checked and recorded as not triggered, with the evidence
  linked — an unchecked item is a no-go, not a pass.
- G3. Open beta issues triaged; anything left open is labelled `Status Known
  issue` and appears in the release notes.
- G4. The download page (LW-M7-02) carries the parity wording verbatim and the
  fingerprint from `SIGNING.md`.

## 6. Results log

| date | build (commit, MOZ_BUILD_DATE) | slot | finding | issue |
|---|---|---|---|---|
| | | | | |

## 7. Go / no-go

```
DECISION:     ______   (GO / NO-GO)
DATE:         ______
SIGNED BY:    ______________________   (maintainer)
BUILD:        ______________________   (commit + MOZ_BUILD_DATE of the build the decision covers)
NO-GO ITEMS:  every N-item above, each marked "not triggered — <evidence>" or "triggered — <issue>"
```

Until this block is filled in, LW-M7-06 is not done and the public release does
not proceed — the task's third acceptance line is "a written go/no-go decision at
the end", and this is where it goes.
