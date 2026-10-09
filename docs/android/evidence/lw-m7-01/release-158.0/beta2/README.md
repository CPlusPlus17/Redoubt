# Redoubt 158.0-1 Beta 2 (from the Firefox 158.0 RC, build2): build configuration

Owner decision, 2026-10-09, verbatim: **"Beta 2 from the RC now"**. Beta 2 is
a GitHub **prerelease** built from Mozilla's 158.0 release candidate
(`candidates/158.0-candidates/build2`, the newest candidate build that day),
with LW-M7-46 (no "Canvas or WebGL was protected" snackbar). The final
158.0-1 follows on 2026-10-13 from Mozilla's official 158.0 source
(`releases/158.0/`). **157.0-3 stays Latest**, and the in-app update check
does **not** announce this build: `site/update/` is untouched. See
`../PREBASE.md` section 11.

## Branch

`android/158-beta2` is a copy of the local-only `android/firefox-158` at
`0f2665fe` (which has `fix/webgl-quiet-notice` merged as `cebb03c6` and the
owner decision recorded), plus this one commit. It exists so that CI on box B
can build it. `android/firefox-158` stays unpushed and keeps `157.0`,
`release.android` `3` and the Makefile's `releases`/`build1` defaults. This
branch is never merged.

## What this commit changes

| file | was | now | why |
|---|---|---|---|
| `version.android` | `157.0` | `158.0` | the Android tree, the tarball and the version string |
| `version` | `157.0` | `158.0` | desktop gates run against the same RC tarball; desktop is not built or released from this branch |
| `release.android` | `3` | `1` | first build of 158 (PREBASE.md section 5, step 2) |
| `Makefile` | `FF_CHANNEL ?= releases`, `FF_BUILD ?= build1` | `FF_CHANNEL ?= candidates`, `FF_BUILD ?= build2` | `make fetch` takes the RC |
| `release-158.0/receipts/` | absent | the six receipts, recaptured on this tree | the receipt tests look up `release-<version.android>` |

- **Why the Makefile defaults.** `android-release.yaml` runs a plain
  `make fetch TARGETS=android` and has no input for `FF_CHANNEL` or
  `FF_BUILD`. Changing the two `?=` defaults on this branch only is the least
  invasive way: no workflow change, and the `android-test.yaml` patch-set job
  that a push of `android/**` starts fetches the same tarball. With them,
  `make fetch` resolves to
  `https://archive.mozilla.org/pub/firefox/candidates/158.0-candidates/build2/source/firefox-158.0.source.tar.xz`
  and checks its `.asc` against the pinned `assets/mozilla-release-key.asc`
  exactly as for a release (`VALIDSIG ... 14F26682D0916CDD81E37B6D61B7B526D98F0353`).
  The values stay overridable on the make command line.
- **Version shown.** `version.android` `158.0` and `release.android` `1` make
  this build report **versionName `158.0-1-default`, the same as the final
  158.0-1.** That follows the 157.0-1 Beta 5 precedent (same versionName,
  higher versionCode).
- **Telling it apart from the final 158.0-1.** By **versionCode and build
  date**, and by the release tag `android-158.0-1-beta.2`. The versionCode is
  Fenix's build-hour code from `build_date`. Beta 2's build date is later than
  Beta 1's `20261007050000` (codes 2016188904-911), so Beta 2 installs over
  Beta 1 and over 157.0-3. The final 158.0-1 is built on or after 2026-10-13
  with a later build date, so its codes are higher and it installs over
  Beta 2. The prerelease notes must state the RC build, the tarball sha256,
  the build date and the versionCodes.

## Source

`candidates/158.0-candidates/build2/source/firefox-158.0.source.tar.xz`,
814889676 bytes, sha256
`fc77f7801d7580a600af683cc367e261eb1ec74647e84a91b4a1e3c1dd5aa2bb`;
`GOODSIG`, `VALIDSIG 827E658608679618CD349F93678E455D76767AA3 …
14F26682D0916CDD81E37B6D61B7B526D98F0353` with a fresh GnuPG home and the
pinned key. build2 was the newest candidate build on 2026-10-09, and
`releases/158.0/` was not published yet (`gates/tarball-158.0-build2.txt`).

## Gates on this commit, against the RC build2 tarball

| check | result |
|---|---|
| `check-patchfail.sh --targets=android` | exit 0, 8 hunks with fuzz, the same profile as on 158.0b4 and in the stopped release attempt (`gates/patchfail-android.out.gz`) |
| `check-patchfail.sh --targets=desktop` | exit 0, 30 hunks with fuzz, same profile (`gates/patchfail-desktop.out.gz`) |
| `check-patch-order.py` | ok: 38/38 constraints, 157 shared-file pairs |
| `lint-patch-scope.py` | OK, 110 patch files |
| `board.py --check`, `--check-scope`, `--check-cfg-split`, `--diff-mozconfig --strict` | ok (130 tasks; 22/44/44; librewolf.cfg regenerates; 0 documented differences) |
| `site-check.py` | PASS, 8 pages |
| receipts `recapture.py` on the `make android-dir` tree | six of six exact at fuzz 0, equal to the stack and the tree (`gates/recapture.log`) |
| `scripts/tests/test-*.py` | all 0 except `test-android-signing.py` and `test-android-version-code.py` (exit 2: they need a built APK and gradle classes; run in acceptance) (`gates/scripts-tests.txt`) |

## Build

On box B, from this branch:

    gh workflow run android-release.yaml -R CPlusPlus17/Redoubt --ref android/158-beta2 \
      -f mode=full -f update_check=true -f build_date=<YYYYMMDDHH0000 UTC>

`bundle` stays false. The run id, head sha and build date are recorded with
the acceptance evidence (`../release-158.0-1-beta.2/`).
