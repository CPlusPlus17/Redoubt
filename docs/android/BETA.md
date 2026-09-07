# Closed beta (LW-M7-06)

Owner: LW-M7-06. This file is written **before** the beta starts, as the task's
first acceptance line requires. It fixes the entry criteria, the device spread,
what is collected, the exit criteria, and holds the go/no-go decision at the end.
Nothing below is a result yet; §6 records results as they arrive and §7 is blank
until the owner signs it.

The beta exists for one reason above all others: the memory cost of site
isolation (LW-M5-01) plus `isolatedProcess` (LW-M5-02) is invisible on a flagship
and decisive on a budget phone. Every design choice here is weighted toward
finding that out on hardware we do not own.

## 1. Entry criteria

The beta does not start until every line below is true and the evidence is
linked. "Green on the maintainer's machine" counts only where the line says so.

| # | Criterion | Evidence | Status |
|---|---|---|---|
| E1 | The build carries all landed Android patches (`assets/patches/android.txt`), compiled from the pinned ESR tarball by `make android-apk TARGETS=android` — not a tree that was patched after the APK was built | `librewolf-android-apk-<v>/build-times.txt`, `logs/` naming the tree | **met 2026-09-06** — buildID `20260905183254`, read off the running app by the harness. Two compile errors in `update-check.patch` had to be fixed first; they had passed every gate. |
| E2 | Both ARM ABIs (`arm64-v8a`, `armeabi-v7a`) are real Gecko builds, not an x86_64 universal APK with empty ARM directories | `unzip -l fenix-universal-release.apk \| grep lib/` shows `libxul.so` under each ABI | **met 2026-09-06.** All three ABIs built into one fat AAR (`buildID 20260906190000`) and the universal APK carries `libxul.so` under `armeabi-v7a`, `arm64-v8a` and `x86_64`. Four APKs: 117/121/127 MB per-ABI plus a 278 MB universal. Note the universal APK gets an `armeabi-v7a` directory from three AndroidX/JNA prebuilts **whether or not that ABI was built**, so a two-ABI build produces a universal APK that installs on 32-bit ARM and has no engine — `android-apk.sh` refuses to emit it, which is why only the per-ABI APKs exist right now. |
| E3 | Smoke suite green on the emulator against the beta build, **except the two checks E12's decision deliberately leaves red** | `docs/android/evidence/lw-m7-06/` | **met 2026-09-06.** Green on the shipping artifact: `--check-search`, `--check-aboutconfig`, `--check-strings` (both halves), `--check-no-suggest`, `--check-update-privacy`, `--check-no-gms`, `--check-no-adjust`. Red *by design*: `--first-run-capture` and `--check-no-remote-settings`, which assert zero Remote Settings traffic that E12 decided to keep — do not weaken them. One gap remains inside a passing check: `--check-update-privacy` proves the store-build path (feature compiled out, no traffic); its opt-in path needs a build carrying a real update-signing key. |
| E4 | Runtime pref audit green (`./scripts/android-pref-audit.sh`, exit 0) with a committed `docs/android/expected-prefs.txt` generated from the beta build | the baseline's commit | **met 2026-09-06** — baseline generated from this build (60 rows) and the audit exits 0. It must be **regenerated** for the actual beta build and the diff read, not carried over. |
| E5 | Fenix unit tests subtract cleanly: `board.py --check-fenix-tests` exit 0 on results from this tree | `docs/android/evidence/lw-m7-06/check-fenix-tests.out` | **met 2026-09-06** — 598 classes / 5,426 tests, 93 failing = 90 environmental + 3 known-real + 0 unexpected. First time the suite has ever been run here. **Note the results directory has since been wiped** by `android-verify-repro.sh`, which clears `obj-*/gradle/build` to force a real rebuild, so re-running the gate today exits 2 for want of input. That is correct fail-closed behaviour, not a regression; the passing output is in the evidence file. Re-run the suite for the actual beta build anyway. |
| E6 | Reproducible: `scripts/android-verify-repro.sh` exit 0 on the beta build's inputs, **with R8 on** | `docs/android/evidence/lw-m6-02/summary.txt` | **met 2026-09-06.** Two independent builds with R8 **on**, from the three-ABI tree at a pinned build date, produced byte-identical unsigned APKs for all four artifacts, and the negative control caught an injected 1-byte change. Same-machine only; cross-machine identity is still not claimed. |
| E7 | Signed with the release key, **v2 + v3**, fingerprint matches `SIGNING.md`; signed offline by a holder, never on the CI runner — and the key no longer readable by that runner | `docs/android/evidence/lw-m6-01/RELEASE-HANDOFF.md` | **not met, and everything except the ceremony is done.** The four release APKs are built with R8 on, verified to carry *no* signature (no v1, no v2/v3 block), with `SHA256SUMS` beside them. `android-verify-signature.sh` checks all four properties in one command and its `--self-test` proves it both accepts a correct signature and rejects a correctly-signed APK bearing the wrong key. What is left needs the passphrase and a machine that is not this one, per custody rule 3. |
| E8 | A second key holder exists, or the single-holder decision is recorded with a date in `SIGNING.md` | `SIGNING.md`, "Decision: Redoubt ships single-holder" | **met 2026-09-06.** The owner decided to ship single-holder rather than block on finding a second, and the consequence is recorded in the file's own words: lose both machines and the passphrase and Redoubt ends under `org.redoubtbrowser`, with every user having to uninstall and reinstall. LW-M6-01's "at least two holders" is knowingly not met. An offline third copy remains available later and does not require re-deciding this. |
| E9 | The parity wording (`PARITY.md` §5) is signed off | `PARITY.md` §5 | **met 2026-09-06.** Approved verbatim by the owner, unsoftened, as LW-M5-06 requires. LW-M7-02 must publish it word for word with a reachable link to the parity table, because the sentence promises "we publish exactly where" and that table is the where. |
| E10 | A triage owner and backup are named (`TRIAGE.md` §0), and the bug-report form (LW-M7-04) exists | `TRIAGE.md` §0, `.github/ISSUE_TEMPLATE/android-bug.yml` | **met 2026-09-06.** Owner named. BACKUP deliberately left empty rather than filled with a name that does not exist, with the two things in `TRIAGE.md` that assume cover called out. The form was already live with all seven required fields. |
| E11 | A first-run network capture taken through a resolver that does **not** sinkhole Mozilla hosts | `docs/android/evidence/lw-m7-06/first-run-capture-honest-dns.*` | **met 2026-09-06.** The build host's LAN resolver answers `incoming.telemetry.mozilla.org` and `ads.mozilla.org` with `0.0.0.0`/`::`, so every earlier capture here understated telemetry by construction. Re-run with the emulator pointed at Quad9 (`--dns-server 9.9.9.9`): **the same six events, all Remote Settings, and not one telemetry, Adjust, ads, crash-reporting or Google endpoint.** The sinkhole was not flattering the result. |
| E12 | The Remote Settings allowlist has been decided **for Android** | `settings/android.cfg`, `docs/android/evidence/lw-m4-08/RESULT.md` | **met 2026-09-06.** Decided by the maintainer: keep the seven collections carrying security state, drop the twenty-six for features Redoubt does not ship. Landed and verified live (the device reads exactly seven). Measured effect: **52% less data received** on first run, and the **same six requests**, because one changes-endpoint poll serves whatever remains. Going to zero would freeze certificate revocation until the next release; that was put and refused. |

E7–E10 are human actions; nothing an agent does can meet them. E1–E6, E11 and
E12 are build-and-measure or decide-and-record work.

**Where this stood at the end of 2026-09-06:** eleven of twelve met. Everything
except **E7**. Outstanding: **E7 alone**, and it is now one offline command rather than a task. The
unsigned artifacts are built and checksummed, the signing invocation is verified, and
the checker that judges the result has been checked in both directions. The step that
remains needs the passphrase and a machine that is not this one — see
`docs/android/evidence/lw-m6-01/RELEASE-HANDOFF.md`.

One open problem is not an entry criterion and outranks several that are: **the keystore
lives on the build host and the Actions runner executes as its owner**, so any workflow
reaching that runner can read it (`SIGNING.md` custody rule 3). Moving it is a
maintainer action. The device evidence is in `docs/android/evidence/lw-m7-06/`, which also
records what each passing check did *not* cover.

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

- **Length:** 14 days from the first install, matching the launch-window rotation
  in `TRIAGE.md` §5, so one calendar drives both.
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
   off (compiled in); `about:config` is not reachable in the release build.
6. **Sites that break** with RFP/ETP strict, listed by URL; whether stock Firefox
   for Android breaks them too.
7. **Anything that says "Firefox" or "Mozilla" in the UI**, with a screenshot —
   `--check-strings` covers the resource table and the deep-linked settings
   screens, not every dialog.
8. **Battery**: subjective only, unless the tester volunteers `dumpsys batterystats`.

How: one issue per finding through the Android bug-report form (LW-M7-04) with the
`beta` label, or one summary message per tester at day 7 and day 14 if the form is
not yet live. `adb logcat` is asked for only on crashes, with the warning that it
contains visited URLs.

## 5. Exit criteria — go / no-go for the public release

**No-go on any one of these:**

- N1. A crash on launch, or an OOM kill within the first minute of ordinary use,
  on any device in slots 1–3 that is not explained and fixed by a second build
  inside the window.
- N2. Any outbound connection in a first-run capture (E11) to a Mozilla telemetry,
  experiments, ads, or crash-reporting host, or to any Google host from the app
  itself. Remote Settings traffic (`firefox.settings.services.mozilla.com`) is a
  no-go too: `rs-blocker-android.patch` exists to stop it, and the 2026-09-02/04
  capture on the maintainer's host showed a real sync from an unknown build.
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
