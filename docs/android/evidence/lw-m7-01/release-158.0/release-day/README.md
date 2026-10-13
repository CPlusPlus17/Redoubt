# Redoubt 158.0-1 (Firefox 158.0): release build configuration

Owner go, 2026-10-13, verbatim: **"yes GO"**, for the final 158.0-1 from
Mozilla's official Firefox 158.0 release (PREBASE.md sections 5 and 11).

This commit sits on main directly after the signed merge of the local
`android/firefox-158` branch (tip `0f2665fe`: the 158 rebase with LW-M7-42
autofill in shadow DOM, LW-M7-46 no WebGL/canvas notice, and the 158 texts of
delete-on-quit, uBO and the update check). The only conflict was
`docs/android/tasks.yaml` (LW-M7-46 against LW-M7-47/48/49, all kept in id
order). The isolation work (`feature/isolation-media`,
`release/158.0-2-isolation`) is not in this release.

## What this commit changes

| file | was | now | why |
|---|---|---|---|
| `version.android` | `157.0.1` | `158.0` | the Android tree, the tarball and the version string |
| `version` | `157.0.1` | `158.0` | desktop follows the same Firefox release; `release` stays `1` |
| `release.android` | `1` | `1` | unchanged: 157.0.1-1 already reset it, and 158.0-1 is the first build of 158 |
| `release-158.0/receipts/` | absent on main | the six receipts | the receipt tests look up `release-<version.android>` |

The Makefile keeps its defaults `FF_CHANNEL ?= releases` and
`FF_BUILD ?= build1`, so `make fetch` takes
`releases/158.0/source/firefox-158.0.source.tar.xz`. Beta 2's copy branch
(`android/158-beta2`, never merged) had switched them to
`candidates`/`build2`; that change is not here.

## Source

`releases/158.0/source/firefox-158.0.source.tar.xz`, 814889676 bytes, sha256
`fc77f7801d7580a600af683cc367e261eb1ec74647e84a91b4a1e3c1dd5aa2bb`. A fresh
GnuPG home holding only the pinned `assets/mozilla-release-key.asc` gives
`GOODSIG` and `VALIDSIG 827E658608679618CD349F93678E455D76767AA3 …
14F26682D0916CDD81E37B6D61B7B526D98F0353` for the tarball and for Mozilla's
`releases/158.0/SHA256SUMS`, which lists the same sha256. It is the same file
as `candidates/158.0-candidates/build2`, from which Beta 2 was built
(`gates/tarball-158.0.txt`).

## Gates on the merged tree, against the 158.0 tarball

| check | result |
|---|---|
| `check-patchfail.sh --targets=android` | exit 0, 66 patches; output identical to Beta 2's run on the build2 tarball (`gates/patchfail-android.out.gz`) |
| `check-patchfail.sh --targets=desktop` | exit 0, 66 patches; identical to Beta 2's (`gates/patchfail-desktop.out.gz`) |
| the same, with `--fuzz=0` | the same 10 android and 20 desktop entries reject as in PREBASE.md section 8 (b4) and in a local 2026-10-09 trial on the build2 tarball (`gates/patchfail-*-fuzz0.out.gz`) |
| `make android-dir TARGETS=android` | exit 0, `librewolf-158.0-1`; every fail-closed check in `librewolf-patches.py` passed, including the glean-core hashes |
| receipts: `recapture.py` on that tree | six of six exact at fuzz 0, equal to the stack and to the tree; byte-identical to the Beta 2 capture (`gates/recapture.log`, `../receipts/README.md`) |
| `check-patch-order.py` | ok: 38/38 constraints, 157 shared-file pairs |
| `lint-patch-scope.py` | OK, 110 patch files |
| `board.py --check`, `--check-scope`, `--check-cfg-split`, `--diff-mozconfig --strict` | ok (133 tasks; 22 common / 44 desktop / 44 android; librewolf.cfg regenerates; 0 documented differences) |
| `site-check.py` | PASS, 8 pages |
| `actionlint` on `.github/workflows/*.yaml` | clean apart from the self-hosted runner label `redoubt-boxb`, which actionlint does not know without a config; with that one message ignored, exit 0. The merge changed no workflow |
| `scripts/tests/test-*.py` | all exit 0 except `test-android-signing.py` and `test-android-version-code.py`, which exit 2 because they need a built APK and Gradle classes; they run in acceptance (`gates/scripts-tests.txt`) |

All logs are in `gates/`.

## Build date and versionCodes

The final 158.0-1 has the same versionName as Beta 1 and Beta 2,
`158.0-1-default`; it is told apart by its versionCode, which must be above
Beta 2's so it installs over it.

| build | build_date | armeabi-v7a | arm64-v8a | x86_64 | universal |
|---|---|---|---|---|---|
| 157.0.1-1 (Latest) | 20261006180000 | 2016188816 | 2016188818 | 2016188822 | 2016188823 |
| 158.0-1 Beta 1 | 20261007050000 | 2016188904 | 2016188906 | 2016188910 | 2016188911 |
| 158.0-1 Beta 2 | 20261009160000 | 2016189376 | 2016189378 | 2016189382 | 2016189383 |
| **158.0-1** | **20261013160000** | **2016190144** | **2016190146** | **2016190150** | **2016190151** |

The codes come from `scripts/android-aab.py versioncode`.

## Build

On box B, from main:

    gh workflow run android-release.yaml -R CPlusPlus17/Redoubt --ref main \
      -f mode=full -f update_check=true -f bundle=false -f build_date=20261013160000

The run id and head sha are recorded with the acceptance evidence, as for
157.0.1-1. `site/update/` is not touched here: the update document is
published only after the owner signs and the GitHub release is public
(PREBASE.md section 5, step 10).
