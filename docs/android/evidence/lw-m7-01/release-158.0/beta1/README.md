# Redoubt 158.0-1 Beta 1 (from Firefox 158.0b4): build configuration

Owner request, 2026-10-07: "can we do a prerelease of it?" The answer is a
GitHub **prerelease** built from Firefox **158.0b4**, the newest 158 source
on archive.mozilla.org on that day. 157.0-3 stays Latest. The in-app update
check does **not** announce this build: `site/update/` is untouched, so
157.0-x installs keep being told they are up to date.

## Branch

`android/158-beta1` is a copy of the local-only `android/firefox-158` at
586b310e plus this one commit. It exists so that CI on box B can build it.
`android/firefox-158` itself stays unpushed and keeps `157.0` in its version
files until release day (PREBASE.md section 5). This branch is never merged.

## What this commit changes

| file | was | now | why |
|---|---|---|---|
| `version.android` | `157.0` | `158.0b4` | the Android tree, the tarball and the version string |
| `version` | `157.0` | `158.0b4` | desktop gates run against the same b4 tarball; desktop is not built or released from this branch |
| `release.android` | `3` | `1` | first build of 158, as release day will do (PREBASE.md section 5, step 2) |

No Makefile, workflow or patch change is needed.

- **Source.** With `version.android` set to `158.0b4`, the Makefile's
  default channel (`FF_CHANNEL=releases`) fetches
  `releases/158.0b4/source/firefox-158.0b4.source.tar.xz`. That is where
  Mozilla publishes the betas. `make fetch` verifies the `.asc` against the
  pinned `assets/mozilla-release-key.asc` and demands primary key
  `14F26682D0916CDD81E37B6D61B7B526D98F0353`. `FF_BETA_SUFFIX` and
  `FF_CHANNEL=beta` are not used. With `version.android` `158.0` they would
  fetch the same bytes from `candidates/`, but the build would then report
  `158.0-1`, the same as the final release.
- **Version shown.** `scripts/librewolf-patches.py` writes
  `<version>-<release>` into `browser/config/version.txt`, and Fenix's
  versionName is `MOZ_APP_VERSION-MOZ_UPDATE_CHANNEL`. This build therefore
  reports **`158.0b4-1-default`**, and 158.0-1 will report `158.0-1-default`.
  `build-fixes.patch` strips `-1` and then `b4` before `computeVersionCode()`
  parses the number. The milestone (`config/milestone.txt`, `158.0`) is
  untouched, so the build is still a release milestone (`is_release_or_beta`,
  PHC and the other release-milestone defaults as in sections 8 to 10).
- **versionCode.** This is Fenix's build-hour code, so it comes from
  `build_date`. It must be later than 157.0-3's `20261006090000` (codes
  2016188744-51), which lets it install over 157.0-3. It is earlier than
  158.0-1's release-day date, which lets 158.0-1 install over it.

## Gates on this commit, against 158.0b4

The tarball is 812620004 bytes, sha256
`6e8c17884180287eb31269bd7ada0b6c92440434caa285986101835373e2111a`. Its
signature was checked against the pinned key: `GOODSIG`, `VALIDSIG
827E658608679618CD349F93678E455D76767AA3 … 14F26682D0916CDD81E37B6D61B7B526D98F0353`.

| check | result |
|---|---|
| `check-patchfail.sh --targets=android` | exit 0, 66 patches, 8 hunks with fuzz (as in sections 8 to 10 of PREBASE.md) |
| `check-patchfail.sh --targets=desktop` | exit 0, 66 patches, 30 hunks with fuzz (as in sections 8 to 10) |
| `check-patch-order.py` | ok: 38/38 constraints, 157 shared-file pairs |
| `lint-patch-scope.py` | OK, 110 patch files |
| `board.py --check`, `--check-scope`, `--check-cfg-split`, `--diff-mozconfig --strict` | ok (129 tasks; 22/44/44; 0 documented differences) |
| `site-check.py` | PASS, 8 pages |

## Build

The build runs in CI on box B, from this branch:

    gh workflow run android-release.yaml -R CPlusPlus17/Redoubt --ref android/158-beta1 \
      -f mode=full -f update_check=true -f build_date=<YYYYMMDDHH0000 UTC>

`android-release.yaml` has no main-only guard on `workflow_dispatch`. Only
its `push` trigger is limited to main. Pushing this branch also starts
`android-test.yaml`'s `test-android` patch-set job, because it matches
`android/**`. `build-android` runs only on main.
