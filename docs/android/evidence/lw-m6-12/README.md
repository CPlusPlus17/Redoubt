# LW-M6-12 evidence: the Play bundle, built, signed, served and installed (rehearsal)

Measured 2026-10-05 on box A (this build host) with **throwaway keys only**. No real key
was read or used, no account exists, and nothing was uploaded anywhere. Everything here
is a rehearsal of `docs/android/PLAY.md` §3 and §5.

## Inputs, and why this is a 158 build

No Firefox 157 fat GeckoView AAR is left on this host: `find` for `geckoview*157*.aar`
returned nothing. The `target.maven.zip` files under `lw-m6-02-repro` and `lw-m6-08-repro`
are older builds. The rehearsal therefore used the **Firefox 158 local work tree**:

| input | value |
|---|---|
| source tree | `channels/play-build/tree`, Firefox 158 with the Redoubt patches of branch `android/firefox-158` (`cfe1323698fc976cf0ebb5d6b509e51ec7188543`) |
| fat AAR | `ff158/work/build/aar-af`: **x86_64 only**, `geckoview-default-omni-158.0.20261004120000.aar` |
| `MOZ_BUILD_DATE` | `20261004120000` (the AAR's own; see `build-times.txt`) |
| scripts | `scripts/android-apk.sh` and `scripts/android-aab.py` from this branch |
| APK update check | compiled **in** with a throwaway P-256 key (`LW_UPDATE_CHECK_PUBKEY`), so that "compiled out of the bundle" is tested against a build where the APKs carry a key |

The command was `android-apk.sh ... --abis x86_64 --fat-host-abi x86_64 --variant release
--disable-debug-signing --bundle --build-date 20261004120000 --skip-gecko`.

**One rehearsal-only tree change** (`rehearsal-tree.diff`, not in the repo): with a
one-ABI GeckoView, Fenix's third-party native libraries still bring `arm64-v8a` and
`armeabi-v7a` directories into the universal APK and the bundle, and the existing APK
gate correctly fails an ABI directory without `libxul.so`. The rehearsal tree therefore
excludes those two ABIs in `packaging.jniLibs`. A release build has all three
GeckoViews and needs no such change. Two failed attempts on the way are kept in
`play-build/out.fail-*`: `universalApk true` without the exclude fails the APK gate,
and `universalApk false` fails the script's "exactly one UNIVERSAL element" check.
Both failures are the gates working as designed.

## Build (`build-times.txt`)

    apk      967 s   17.91 GB peak   ok
    bundle   215 s   12.74 GB peak   ok     (third Gradle pass, fenix:bundleRelease)

| file | sha256 |
|---|---|
| `apk/fenix-x86_64-release-unsigned.apk` (versionCode 2016188390) | `b5db474ba2c8ad4caebb3c14fce3d21519a3208ad2490c02d693e9548723c434` |
| `apk/fenix-universal-release-unsigned.apk` (versionCode 2016188391) | `b2f92e44eb307d90e3a145f9eb494d6675afadcd8a8a8f334009f3ee1594be71` |
| `aab/fenix-release-unsigned.aab` (versionCode 2016188391) | `685f78454324a4672c0d9a80bf315fdd3089d596cd4be188ea9f8ab41b41a6fe` |

`android-aab.py inspect` (`bundle-metadata.json`) on the unsigned bundle:
`org.redoubtbrowser`, versionCode **2016188391**, equal to `android-aab.py versioncode
--build-date 20261004120000` (the universal code), and **at least** every APK's code
(390 and 391); minSdk 26, targetSdk 37; ABIs `x86_64`; `libxul.so` sha256-identical to the
AAR input (`6d631db281b1abac...`); unsigned; **update check compiled out**.

The update-check key is in the APKs and not in the bundle. This was counted in the
files themselves, not taken from a log. The throwaway key's base64 occurs once in
the dex of each APK (`fenix-x86_64...apk 1`, `fenix-universal...apk 1`) and zero
times in the bundle's dex (`--forbid-key-file`).

## Owner signing, rehearsed (`sign-run.log`, `refusals.log`)

`sign-aab.sh` ran with the throwaway upload key (`1e7f290a...854c1f`) inside the build image
(this host has no `jarsigner`; the image has JDK 17's). It checked the CI sha256 and that
the bundle is unsigned, signed it, verified it and compared the payload: **3285 entries
identical** to the unsigned bundle. Signed bundle:
`e3798bdcd8f1a09d89882b77844dac215f01af6c44b2e2c3ee278aca02f9ee31`.

**Defect found and fixed here:** the first version verified with `jarsigner -verify
-strict`. `-strict` turns "self-signed certificate" into an error (exit 4), and a Play
upload key is self-signed, so the script would have refused **every** correct upload.
It now requires exit 0, `jar verified.`, and no unsigned or modified entries, and leaves
the signer check to `android-aab.py --expect-signer-sha256`.

Refusals, each measured:

- **A.** The expected upload certificate is the app signing key's fingerprint, so the
  script stops before it signs anything (rc 2).
- **B.** The bundle was signed by a key other than the registered upload certificate
  (the throwaway "app signing" key `dd05cee7...`). `android-aab.py` reports
  `signer certificate(s) [dd05...] expected exactly [1e7f...]` and no
  `fenix-release.aab` is left behind.
- **C.** There is no `play-upload-cert.sha256` and no override (rc 2).

## What Play would serve (`scripts/bundletool.sh`, pinned 1.18.3)

Google's part was simulated by `bundletool build-apks` with a throwaway **app signing**
key (`dd05cee78591c15aad3570a9698a9bb13f8d71b18f8801da65298945514a813a`):

- `--mode=universal`: `universal.apk`, 269 MB (the bundle stores native libraries
  uncompressed; the Play download is compressed), sha256
  `c312424176f374ad2d0e1c91771caefd8ff494c10ace243f9463e7d2e873d6b0`, v2 and v3 signed by
  `dd05cee7...`, versionCode 2016188391, targetSdk 37.
- `--connected-device` on the API 34 emulator: `base-master` + `base-x86_64` +
  `base-xxhdpi` splits, installed with `install-apks`.

## Emulator smoke (API 34 google_apis x86_64, `smoke.txt`)

The emulator started only after `channels/EMULATOR-FREE` existed. On the Play-style
install:

- It launches (`am start -W`: `Status: ok`). The first screen is "uBlock Origin was
  added".
- `check-no-gms` PASS, `ubo-first-navigation` PASS, `ubo-preinstalled-signature` PASS.
- **Settings has no "Check for updates" row.** All Settings rows were dumped by
  scrolling through the whole screen. The only rows that mention updates are
  "Update extensions automatically" and its summary.
- `check-aboutconfig` PASS: about:config is reachable, with **52 prefs locked**. The
  curated `pref-dump` (`prefs.txt`) shows `browser.contentblocking.category=strict`,
  the telemetry and datareporting prefs and `librewolf.cfg.version=8.6`, all locked.

The listing screenshots `docs/android/play/screenshots/phone-{1,2,3}.png` were taken from
this install with Android's demo-mode status bar and cropped to 1080x2160. Play's limit
is a long side of at most twice the short side. The UI is the 158 build's. Retake them
from the release build if 157's UI differs visibly.

## Cross-channel updates, both directions (`cross-channel.log`)

The direct APK and the Play splits were signed with the same throwaway key. That stands
in for "one key on every channel".

| step | result |
|---|---|
| install the direct per-ABI APK (390, check compiled **in**), open a tab | Settings shows "Check for updates"; 1 tab |
| install the Play splits (391) over it | **Success**; `firstInstallTime` unchanged, `lastUpdateTime` new; the tab is still there; **0** "Check for updates" rows |
| the same build's direct APK (390) over the Play install | **refused**: `INSTALL_FAILED_VERSION_DOWNGRADE` (390 < 391), as PLAY.md §3 predicts |
| negative control: the Play universal APK re-signed with a **different** key over the Play install | **refused**: `INSTALL_FAILED_UPDATE_INCOMPATIBLE` |

Not measured: Play build N to a direct APK of build N+1. That needed a second build with
a later `MOZ_BUILD_DATE`, which is another 20-minute build. It follows from the arithmetic:
one hour later adds 8 to the code, which beats the low bits (`android-aab.py
versioncode`). Also not reproducible here: the installer of record. `adb` and
`bundletool` installs have no installer, while a real Play install has
`com.android.vending`.

## Owner, after the upload (not done here)

The last acceptance criterion of LW-M6-12 needs the real account and is the owner's:
the Play listing is live, and Play's signed universal APK (App bundle explorer) verifies
with `64:14:EB:33:...:3B:D0` via `scripts/android-verify-signature.sh`.
