# Redoubt 158.0-2 (Firefox 158.0): release build configuration

Owner decision 2026-10-11, verbatim: **"158.0-2, Android 12+ only"**; owner
"go" on 2026-10-14 for 158.0-2 = 158.0-1 plus content isolation on Android 12+,
together with the automatic box B build-cache cleanup.

This commit sits on main directly after

1. the signed `--no-ff` merge of the local branch `release/158.0-2-isolation`
   (tip `f61a83ef`, LW-M7-50; design and device evidence in
   [`../README.md`](../README.md) and `docs/android/ISOLATION-MEDIA.md`), and
2. the box B commit that drops superseded `tree-<version>-<release>` caches
   before the disk gates (`scripts/ci-vm-boxb/prune-tree-cache.py`,
   `docs/android/CI-VM.md`, "Build tree caches").

Merge conflicts: `docs/android/tasks.yaml` (main's LW-M7-47..49 kept, LW-M7-50
appended), `scripts/android-smoke.sh` and `scripts/tests/test-android-smoke.py`
(main's `--check-tls-floor`, `--check-revocation`, `--check-rfp-coherence` kept,
`--check-isolation` added), `docs/android/PARITY.md` (the 158.0-2 process
separation row, with a link to the LW-M7-48 study). `assets/patches/android.txt`
and `docs/android/PATCH-SCOPE.md` merged without conflict: main's entries, then
the four isolation patches at the end.

## What this commit changes

| file | was | now | why |
|---|---|---|---|
| `release.android` | `1` | `2` | second build of Firefox 158.0 for Android |
| `version`, `version.android` | `158.0` | `158.0` | unchanged |
| `release-158.0/receipts/` | present | unchanged | the receipt tests look up `release-<version.android>` = `release-158.0`; they pass on the merged tree without a recapture (`gates/scripts-tests.txt`) |

## What 158.0-2 is

At runtime, `GeckoProvider` decides once: `SDK_INT >= 31` turns isolated content
processes and the app zygote on, and GeckoView passes the locked pref
`media.redoubt-isolation-media.enabled = true`, which sets and locks upstream's
eleven isolated-process media prefs, keeps software codecs in the isolated
content process, sends only H.264/HEVC/AAC to RDD/Utility (which refuse every
other decoder), and enables the drain backport (bug 1987001). Below API 31 the
pref is false and locked, and the build behaves as 158.0-1. The `dev-app`
overlay stays an overlay; this workflow refuses any overlay tree.

## Gates on the merged tree, against the 158.0 tarball

| check | result |
|---|---|
| tarball | the GPG-verified copy used for 158.0-1: 814889676 bytes, sha256 `fc77f780...a2bb`, GOODSIG/VALIDSIG with the pinned key (`gates/tarball-158.0.txt`) |
| `check-patchfail.sh --targets=android` | exit 0, 70 patches; identical to 158.0-1's output apart from the scratch path and the four added isolation patches, which apply (`gates/patchfail-android.out.gz`) |
| `check-patchfail.sh --targets=desktop` | exit 0, 66 patches; identical to 158.0-1's apart from the scratch path (`gates/patchfail-desktop.out.gz`) |
| `check-patch-order.py` | ok: 39/39 constraints, 172 shared-file pairs |
| `lint-patch-scope.py` | OK, 115 patch files |
| `board.py --check`, `--check-scope`, `--check-cfg-split`, `--diff-mozconfig --strict` | ok (134 tasks; 22 common / 44 desktop / 48 android, 1 overlay patch; librewolf.cfg regenerates; 0 documented differences) |
| `site-check.py` | PASS, 8 pages |
| `actionlint` on `.github/workflows/*.yaml` | exit 0 with the self-hosted label `redoubt-boxb` message ignored, as for 158.0-1 |
| `scripts/tests/test-*` | all exit 0 except `test-android-signing.py`, `test-android-version-code.py` and `test-update-check-jvm.sh`, which need a built APK, Gradle classes or a tree (`gates/scripts-tests.txt`) |

All logs are in `gates/` (local paths replaced by `<repo>`).

## Build date and versionCodes

| build | build_date | armeabi-v7a | arm64-v8a | x86_64 | universal |
|---|---|---|---|---|---|
| 158.0-1 (Latest) | 20261013160000 | 2016190144 | 2016190146 | 2016190150 | 2016190151 |
| **158.0-2** | **20261014100000** | **2016190288** | **2016190290** | **2016190294** | **2016190295** |

The codes come from `scripts/android-aab.py versioncode`. versionName is
`158.0-2-default`.

## Build

On box B, from main:

    gh workflow run android-release.yaml -R CPlusPlus17/Redoubt --ref main \
      -f mode=full -f update_check=true -f bundle=false -f build_date=20261014100000

The run id and head sha are recorded with the acceptance evidence.
`site/update/` is not touched here: the update document is published only
after the owner signs and the GitHub release is public.
