# Redoubt 158.0-3 (Firefox 158.0): release build configuration

Owner decision 2026-10-15: "merge" (LW-M7-39, done in `fe249a3d`) and ship it as
**"-3"**, that is Redoubt 158.0-3.

This commit sits on main directly after

1. the signed merge `fe249a3d` of `fix/drm-isolation` (LW-M7-39: Widevine works under
   isolated content on Android 12+, and the DRM permission defaults to Blocked; design in
   `docs/android/ISOLATION-MEDIA.md` section 9, device evidence in [`../../`](../../README.md)),
2. the signed merge `962581ef` of `port/sept24-gaps` (LW-M7-38: no "Report broken site"),
3. the docs merge `22f062df` (public DoH wording), and the launch and site commits since
   158.0-2.

## What this commit changes

| file | was | now | why |
|---|---|---|---|
| `release.android` | `2` | `3` | third build of Firefox 158.0 for Android |
| `version`, `version.android` | `158.0` | `158.0` | unchanged |
| `release-158.0/receipts/` | present | unchanged | the receipt tests look up `release-158.0`; they pass unchanged (`gates/scripts-tests.txt`) |

## What 158.0-3 is

158.0-2 plus:

- **LW-M7-39, DRM under isolation.** `isolation-eme.patch`: on Android 12+ the parent asks
  the NDK once whether Widevine is supported and publishes the answer as the locked pref
  `media.redoubt-eme.widevine-support`; isolated content reads it and no longer calls Java
  MediaDrm (which crashed the tab in a loop). It also carries the bug 2075686 backport and
  two fixes in upstream's RDD CDM path (key expiration 0 becomes "none"; Init waits for the
  MediaCrypto). Below API 31 only a Java try/catch is active.
- **The DRM switch works.** `drm-permission-default.patch` is listed: Settings > Site
  settings > DRM-controlled content defaults to **Blocked** (no prompt). Settings
  `bddc198f` drops `android.cfg`'s `media.eme.enabled=false`, which had made that setting
  useless. So DRM stays off by default, and a user can turn it on per site or for all.
- **LW-M7-38:** "Report broken site" is removed (`no-webcompat-reporter.patch`).

The packaged `librewolf.cfg` changes against 158.0-2 by the removed `media.eme.enabled` line
and its comment (settings `008b87f` -> `bddc198f`).

## Gates on this tree, against the 158.0 tarball

| check | result |
|---|---|
| tarball | the GPG-verified copy used for 158.0-1 and 158.0-2: 814889676 bytes, sha256 `fc77f780...a2bb`, GOODSIG/VALIDSIG with the pinned key, re-checked today (`gates/tarball-158.0.txt`) |
| `check-patchfail.sh --targets=android` | exit 0, 73 patches; 158.0-2's output plus the three added patches (`no-webcompat-reporter`, `isolation-eme`, `drm-permission-default`), which apply (`gates/patchfail-android.out.gz`) |
| `check-patchfail.sh --targets=desktop` | exit 0, 66 patches; identical to 158.0-2's apart from the scratch path (`gates/patchfail-desktop.out.gz`) |
| `check-patch-order.py` | ok: 40/40 constraints, 183 shared-file pairs |
| `lint-patch-scope.py` | OK, 118 patch files |
| `board.py --check`, `--check-scope`, `--check-cfg-split`, `--diff-mozconfig --strict` | ok (137 tasks; 22 common / 44 desktop / 51 android, 1 overlay patch; librewolf.cfg regenerates; 0 documented differences) |
| `site-check.py site` | PASS, 10 pages |
| `actionlint` on `.github/workflows/*.yaml` | exit 0, with the self-hosted label `redoubt-boxb` message ignored |
| `scripts/tests/test-*.py`, `*.sh` | all exit 0 except `test-android-signing.py`, `test-android-version-code.py` and `test-update-check-jvm.sh`, which need a built APK, Gradle classes or a tree, as for 158.0-2 (`gates/scripts-tests.txt`) |

All logs are in `gates/` (local paths replaced by `<repo>`).

## Build date and versionCodes

| build | build_date | armeabi-v7a | arm64-v8a | x86_64 | universal |
|---|---|---|---|---|---|
| 158.0-1 | 20261013160000 | 2016190144 | 2016190146 | 2016190150 | 2016190151 |
| 158.0-2 (Latest) | 20261014100000 | 2016190288 | 2016190290 | 2016190294 | 2016190295 |
| **158.0-3** | **20261015170000** | **2016190536** | **2016190538** | **2016190542** | **2016190543** |

The codes come from `scripts/android-aab.py versioncode`. versionName is `158.0-3-default`.

## Build

On box B, from main:

    gh workflow run android-release.yaml -R CPlusPlus17/Redoubt --ref main \
      -f mode=full -f update_check=true -f bundle=false -f build_date=20261015170000

`bundle=false` as for 158.0-2: Redoubt is not on Google Play (`DISTRIBUTION.md`). The run id
and head sha are recorded with the acceptance evidence. `site/update/` is not touched here:
the update document is published only after the owner signs and the GitHub release is public.

## Release notes (draft)

See [`RELEASE-NOTES-draft.md`](RELEASE-NOTES-draft.md). The final text goes with the signing
bundle after acceptance.
