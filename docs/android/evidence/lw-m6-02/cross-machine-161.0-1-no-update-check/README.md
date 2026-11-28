# 161.0-1 with update_check=false on two machines (2026-11-27)

**Result: with `update_check=false`, two builds on different machines give
byte-identical unsigned APKs.** All four APKs from CI run 46003883919 (runner
24) and from build D on the second machine have the same SHA-256, and every
zip entry matches. No update-check key is in any of them.

`update_check=false` is the build flag F-Droid and Accrescent would use
(DISTRIBUTION.md): no `--update-check`, no key in the dex. Both builds here
used Redoubt's container at `/work/src`. This pair does **not** show:
- that F-Droid's environment gives the same bytes (F-Droid builds without the
  container, at its own path, with its own toolchain);
- anything about a signed update_check=false release, which does not exist
  yet. GitHub ships update_check=true.

The APKs carry 161.0-1's versionName and versionCodes. They are test
artifacts and were not signed or published.

## What was built

| | CI | Second machine, build D |
|---|---|---|
| Build | Actions run [46003883919](https://github.com/CPlusPlus17/Redoubt/actions/runs/46003883919), mode=full, update_check=false, bundle=false, build_date=20261125160740 | `run-d.sh`: `make android-package`, same flags without `--update-check`, 2026-11-27 12:59-14:29 UTC |
| Commit | `main` `7ee28fff`, settings submodule `3982f7e6` | the same |
| Machine | runner `redoubt-ci-boxb` (id 24) | the second machine from [cross-machine-161.0-1](../cross-machine-161.0-1/README.md) |
| Image | `ac5bb9c0b7b5…` (CI's; the image step ran no build steps) | `73901ba826f0…`, build A's fresh image, reused |

Both are the same machines and images as the update_check=true patched pair.
Build D ran with `LW_UPDATE_CHECK_PUBKEY` and `LW_UPDATE_CHECK_ENDPOINT`
unset, which was checked in its environment dump. Both builds used the same
in-container paths, user and build date (`MOZ_BUILD_DATE=20261125160740` in
both passes).

`7ee28fff` differs from the update_check=true pair's commit `ba2a9c3b` only
in `#` comment lines outside `docs/`, which do not reach the tree.

## The pair

`SHA256SUMS.ci-46003883919` and `SHA256SUMS.second-vm-d`:

    c26de12db0cf7db12c6b6e8771f58426a800efaada3a516b7a298f19a2cf9759  fenix-arm64-v8a-release-unsigned.apk
    0e0396898cee96662fdd25451b48631467eca03188f9cda6ac43a18785b5afbf  fenix-armeabi-v7a-release-unsigned.apk
    ac8517bc4397a9279d58cc36d2149a2a4d4a3cdecda89ee96124c6fbb0c23aa6  fenix-universal-release-unsigned.apk
    904332294b77a00cd4573cab3ff2e7ca0a8334764e95981847f3fc0e1671fd32  fenix-x86_64-release-unsigned.apk

How this was checked:
- the CI artifact was downloaded, and the hashes were recomputed on the
  workstation for both sets; they also match the SHA256SUMS CI uploaded;
- `cmp` of each pair;
- `entry-compare.txt` (`../gecko-same-host-161.0-1/cmp_apk.py`): 3831/3831
  entries identical per ABI and 3865/3865 universal, same order.

Both builds passed their gates. CI's release job: unsigned,
`OK: MOZ_BUILD_DATE 20261125160740`, "update check compiled out" for each
APK, which looks for the committed key. `run-d.sh`: the same, plus the search
below.

## No update-check key

`key-and-string-checks.txt` searches every `classes*.dex` for two strings:
- the committed key (`assets/update-check.android.pubkey`);
- `MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE`, the base64 of the fixed 27-byte
  header every P-256 public key starts with. It finds any compiled-in key,
  including one injected through `LW_UPDATE_CHECK_PUBKEY`, which the CI gate
  would miss.

| | committed key | P-256 header |
|---|---|---|
| update_check=true, CI 45953992693, each APK | 1 | 1 |
| update_check=false, CI and build D, all eight APKs | 0 | 0 |

## What the flag changes

`true-vs-false.txt` compares CI 45953992693 (update_check=true) with CI
46003883919 (update_check=false), same commit content, machine, image and
build date. In every APK, 6 entries differ, in the same order:

| Entry | true | false |
|---|---|---|
| `classes.dex` | 11,236,348 | 11,176,992 |
| `classes2.dex` | 10,757,692 | 10,814,372 |
| `classes3.dex` | 770,184 | 755,864 |
| `assets/dexopt/baseline.prof` | 10,339 | 10,316 |
| `assets/dexopt/baseline.profm` | 1,121 | 1,130 |
| `resources.arsc` | 16,602,212 | 16,601,852 |

Everything else is identical: the manifest, `META-INF`, every native library,
`assets/omni.ja` and all `res/` files. This is what the flag should reach: it
only goes to the Fenix Gradle pass, where it sets
`BuildConfig.LW_UPDATE_CHECK_PUBKEY`. The baseline profile indexes dex
methods, so it follows the dex.

`true-vs-false-resources.txt` (`aapt2 dump resources`): the false variant has
four strings fewer, all of the "update available" notification:
`lw_update_check_available_message`, `_title`, `_later`, `_open_download`.
With the check constant false, R8 removed the notification code, and resource
shrinking then dropped its strings.

The check is removed, not only unreachable (`key-and-string-checks.txt`, arm64
APK):
- the endpoint `https://redoubtbrowser.org/update/android/latest.json` and the
  `Redoubt-UpdateCheck/1` user agent are in the true dex once and absent from
  the false dex;
- the Settings row's "Check for updates" string stays in both, as the patch
  keeps the row and hides it at runtime;
- `org.fdroid.fdroid` is in both dex files.

`output-metadata.json` of both variants: versionName `161.0-1-default`,
versionCodes 2016198400/402/406/407. The build-date pin held.

## Open

- The in-container build path (`/work/src`), user and build date were the
  same in every build. An F-Droid-style build without a container, at its own
  path, is not covered.
- No signed update_check=false release exists.

## Files

| File | What |
|---|---|
| `SHA256SUMS.ci-46003883919` | CI APK hashes, recomputed on the workstation |
| `SHA256SUMS.second-vm-d` | build D APK hashes |
| `entry-compare.txt` | `cmp_apk.py` output, CI vs build D |
| `true-vs-false.txt` | `cmp_apk.py` output, CI 45953992693 (true) vs CI 46003883919 (false) |
| `true-vs-false-resources.txt` | diff of `aapt2 dump resources`, true vs false, arm64 |
| `key-and-string-checks.txt` | key search on all twelve APKs, string hit counts, versionCodes |
