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
| E2 | Both ARM ABIs (`arm64-v8a`, `armeabi-v7a`) are real Gecko builds, not an x86_64 universal APK with empty ARM directories | `unzip -l fenix-universal-release.apk \| grep lib/` shows `libxul.so` under each ABI | **partly met.** `arm64-v8a` and `x86_64` each carry a `libxul.so` byte-identical to their AAR input (`a5a5900c` / `43ffa61d`). `armeabi-v7a` building 2026-09-06. Note the universal APK gets an `armeabi-v7a` directory from three AndroidX/JNA prebuilts **whether or not that ABI was built**, so a two-ABI build produces a universal APK that installs on 32-bit ARM and has no engine — `android-apk.sh` refuses to emit it, which is why only the per-ABI APKs exist right now. |
| E3 | Smoke suite green on the emulator against the beta build | `docs/android/evidence/lw-m7-06/` (README + per-check JSON) | **partly met, 2026-09-06.** Green: `--check-search` (all three LW-M4-06 lines), `--check-aboutconfig`, `--check-no-gms`, `--check-no-adjust`, `--check-strings` (resource table only). Red: `--first-run-capture` (10 Remote Settings events — see E12) and `--check-no-suggest` (fails its own positive control, not its subject). Half-covered: `--check-update-privacy` (store-build path only; the opt-in path needs a build with a verification key) and `--check-strings` (running-app traversal not run). |
| E4 | Runtime pref audit green (`./scripts/android-pref-audit.sh`, exit 0) with a committed `docs/android/expected-prefs.txt` generated from the beta build | the baseline's commit | **met 2026-09-06** — baseline generated from this build (60 rows) and the audit exits 0. It must be **regenerated** for the actual beta build and the diff read, not carried over. |
| E5 | Fenix unit tests subtract cleanly: `board.py --check-fenix-tests` exit 0 on results from this tree | results dir path in the evidence | not met |
| E6 | Reproducible: `scripts/android-verify-repro.sh` exit 0 on the beta build's inputs, **with R8 on** (the earlier measurement in `REPRODUCIBLE.md` was R8 off) | `docs/android/evidence/lw-m7-06/repro/` | not met |
| E7 | Signed with the release key, **v2 + v3**, fingerprint matches `SIGNING.md`; signed offline by a holder, never on the CI runner — and the key no longer readable by that runner | `apksigner verify --verbose --print-certs` output in the evidence | not met. Every APK built so far is `CN=Android Debug`, **v2 only** (verified 2026-09-06), and Accrescent rejects v2-only. Separately, the keystore is on the build host and the Actions runner runs as its owner, so "never on the CI runner" is not true of the key's *location* either — see `SIGNING.md` custody rule 3. |
| E8 | A second key holder exists, or the single-holder decision is recorded with a date in `SIGNING.md` | `SIGNING.md` custody table | not met (`SIGNING.md`: 1 holder, 2 copies) |
| E9 | The parity wording (`PARITY.md` §5) is signed off, because testers will ask what the sandbox gap means and the answer must be the published one | sign-off line in `PARITY.md` | not met |
| E10 | A triage owner and backup are named (`TRIAGE.md` §0), and the bug-report form (LW-M7-04) exists, because beta reports go through it | `TRIAGE.md` §0 filled | not met |
| E11 | A first-run network capture from a device **on a network whose resolver does not sinkhole Mozilla hosts**; the maintainer's LAN resolver returns `0.0.0.0` for `incoming.telemetry.mozilla.org` and `ads.mozilla.org`, so captures taken there under-count | pcap summary in the evidence, with the resolver named | not met |

| E12 | The Remote Settings allowlist has been decided **for Android** | `LW-M4-08`, and the two prefs at `settings/common.cfg:709`/`:713` | not met. This is the reason `--first-run-capture` is red, and it is a decision rather than a defect: the shared cfg allow-lists 33 collections to sync (tracking-protection lists, addon blocklists, cert revocation) and `common.cfg:715` already says *"LW-M4-08 owns their Android contents"*. Either Android narrows the list, or M4's "zero outbound requests before first navigation" claim is dropped. It cannot be both. |

E7–E10 are human actions; nothing an agent does can meet them. E1–E6, E11 and
E12 are build-and-measure or decide-and-record work.

**Where this stood on 2026-09-06:** E1 and E4 met, E2 and E3 partly, the rest
open. The device evidence is in `docs/android/evidence/lw-m7-06/`, which also
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
