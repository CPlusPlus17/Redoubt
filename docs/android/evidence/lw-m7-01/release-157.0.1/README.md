# Redoubt 157.0.1-1 (Firefox 157.0.1 security update): build configuration

Owner decision, 2026-10-09, verbatim: **"and then let us the the 157 sec fix we
did not see"**. Redoubt ships **157.0.1-1**, built on Firefox 157.0.1, as the
new Latest stable over 157.0-3.

Firefox 157.0.1 (2026-10-06) fixes **MFSA 2026-104 / CVE-2026-106016**,
"Mitigation bypass in the File Handling component" (moderate, bug 2067465).
The 157.0 to 157.0.1 diff touches `dom/ipc/FilePickerParent.cpp`,
`ContentParent`, the GMP/RDD/Utility IPC code and the Android error-page
strings, so it is treated as relevant to Android. The release watcher's issue
#3 tracked it, and it went unseen for three days (LW-M7-47).

## What this commit changes

| file | was | now | why |
|---|---|---|---|
| `version.android` | `157.0` | `157.0.1` | the Android tree, the tarball and the version string |
| `release.android` | `3` | `1` | first Redoubt build of a new Firefox version |
| `version` | `157.0` | `157.0.1` | desktop follows the same Firefox release; `release` is already `1` (desktop is 157.0.1-1), as for upstream's 156.0.1-1 bump (4372bc87) |
| `release-157.0.1/receipts/` | absent | the six receipts, recaptured on this tree | the receipt tests look up `release-<version.android>` |

### A three-part version

- **Tarball.** The Makefile fetches
  `releases/157.0.1/source/firefox-157.0.1.source.tar.xz`. The tarball
  unpacks to `firefox-157.0.1/`, and the Makefile reads that name from the
  tarball itself. `make android-dir` produced `librewolf-157.0.1-1` (exit 0).
- **Version strings.** `scripts/librewolf-patches.py` writes `157.0.1-1` to
  both `browser/config/version.txt` and `version_display.txt` on Android, as
  checked in the extracted tree.
- **Gecko version code.** `build-fixes.patch` strips `-1`, so `computeVersionCode()`
  parses `157.0.1`. That gives three parts, which it accepts (`parts.size() == 3`),
  and the result is 15700001. The patch's own comment covers the same case for
  `153.0.4-1`.
- **Fenix's APK versionCode** comes from `MOZ_BUILD_DATE` (see below), not from
  the version string.
- **Update manifest.** `scripts/update-manifest.py`'s tag pattern
  `\d+(?:\.\d+)*` accepts `android-157.0.1-1`. In the app, the versionCode
  decides, and `UpdateChecker.isNewer` is only the fallback. It splits off the
  release at the last `-` and compares the digit runs, so `157.0.1-1` sorts
  above `157.0-3`.
- **glean-core checksums.** The pristine `.cargo-checksum.json` hashes that the
  patcher rewrites are unchanged in 157.0.1. Both were found, and the patcher
  ran without the fatal miss.
- **versionName** is `157.0.1-1-default`.

## Build date and versionCodes

Fenix's code is `(hours since its epoch) << 3` plus three ABI bits
(`scripts/android-aab.py versioncode`). The release must sit **above 157.0-3**
and **below 158.0-1 Beta 1**. If it sat above Beta 1, Obtainium or the update
check could move beta testers, whose profiles are already 158, back down to 157.

| build | build_date | armeabi-v7a | arm64-v8a | x86_64 | universal |
|---|---|---|---|---|---|
| 157.0-3 (Latest) | 20261006090000 | 2016188744 | 2016188746 | 2016188750 | 2016188751 |
| **157.0.1-1** | **20261006180000** | **2016188816** | **2016188818** | **2016188822** | **2016188823** |
| 158.0-1 Beta 1 | 20261007050000 | 2016188904 | 2016188906 | 2016188910 | 2016188911 |

20261006180000 lies strictly between the two other dates and has never been
used as a build date. The only rejected date so far is 20261004200000.

## Source

Mozilla's 157.0.1 release tarball is
`releases/157.0.1/source/firefox-157.0.1.source.tar.xz`, 811383348 bytes, sha256
`483bedee9059df2479e4531c443b1073c6ebaed3570bda0c164eb562ee241c4c`. Verifying
it with a fresh GnuPG home and only the pinned `assets/mozilla-release-key.asc`
gives `GOODSIG`, and `VALIDSIG 827E658608679618CD349F93678E455D76767AA3 …
14F26682D0916CDD81E37B6D61B7B526D98F0353` (see `gates/tarball-157.0.1.txt`).

## Gates on this commit, against the 157.0.1 tarball

| check | result |
|---|---|
| `check-patchfail.sh --targets=android` | exit 0; 11 hunks applied with fuzz, none failed (`gates/patchfail-android.out.gz`) |
| `check-patchfail.sh --targets=desktop` | exit 0; 27 hunks applied with fuzz, none failed (`gates/patchfail-desktop.out.gz`) |
| the same, with `--fuzz=0` | Output identical, line for line, to the same run on the 157.0 tarball from main f44de75e for both targets (only the scratch paths differ). 157.0.1 changes no file any patch touches in a way that patch can see, so no patch needed regenerating (`gates/patchfail-*-fuzz0.out.gz`). |
| `check-patch-order.py` | ok: 38/38 constraints, 157 shared-file pairs |
| `lint-patch-scope.py` | OK, 111 patch files |
| `board.py --check`, `--check-scope`, `--check-cfg-split`, `--diff-mozconfig --strict` | ok (128 tasks; 22/46/43; librewolf.cfg regenerates; 0 documented differences) |
| `site-check.py` | PASS, 8 pages |
| `make android-dir TARGETS=android` | exit 0, `librewolf-157.0.1-1` |
| receipts: `recapture.py` on that tree | six of six exact at fuzz 0, equal to the stack and to the tree (`gates/recapture.log`) |
| `scripts/tests/test-*.py` | All exit 0 except `test-android-signing.py` and `test-android-version-code.py`. Both exit 2 because they need a built APK and Gradle classes, so they run in acceptance (`gates/scripts-tests.txt`). |

The static gates and patchfail logs are in `gates/`.

## Build

On box B, from main:

    gh workflow run android-release.yaml -R CPlusPlus17/Redoubt --ref main \
      -f mode=full -f update_check=true -f build_date=20261006180000 -f bundle=false

The run id and head sha are recorded with the acceptance evidence, following
the 157.0-3 procedure (`../release-157.0-3/`, DISTRIBUTION.md).
