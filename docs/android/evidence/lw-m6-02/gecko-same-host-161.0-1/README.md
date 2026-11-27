# 161.0-1 full rebuild on the same builder (2026-11-26)

**Result: all four unsigned APKs are byte-identical to the release.** This covers
the whole chain: the Gecko pass (`libxul.so`, `omni.ja` and the Rust code), the
per-ABI and fat AARs, and the Fenix APK pass. It is the first measurement of the
Gecko stage. The earlier LW-M6-02 runs rebuilt only the APK stage from shared
prebuilt AARs.

## What was built

| | Release | Rebuild |
|---|---|---|
| Actions run | [45650986628](https://github.com/CPlusPlus17/Redoubt/actions/runs/45650986628) | [45780592911](https://github.com/CPlusPlus17/Redoubt/actions/runs/45780592911) |
| Commit | `683c8915` | `683c8915` |
| Inputs | mode=full, update_check=true, bundle=false | mode=full, update_check=true, bundle=false, build_date=20261125160740 |
| `MOZ_BUILD_DATE` | 20261125160740 (the AAR pass's own "now") | 20261125160740, passed to both passes |
| Runner | `redoubt-ci-boxb` (id 24) | the same runner |
| Job | 2026-11-25 16:05–17:48 UTC | 2026-11-26 08:08–09:49 UTC (Gecko/AAR 75 min, Fenix 22 min) |

The two builds shared the following:
- The same builder VM and physical host.
- The same workspace path (`/home/runner/actions-runner/_work/Redoubt/Redoubt`).
- The same podman image `librewolf-android-build`. The image was not rebuilt
  because its `org.redoubt.dockerfile-sha256` label still matched
  `assets/Dockerfile.android` (`c7afbc26…10728a8`).

So the toolchain was bit-for-bit the same in both builds.

Before the rebuild, nothing was carried over from the release build:
- The checkout's `git clean -ffdx` removed `librewolf-161.0-1/`,
  `librewolf-android-aar-161.0-1/`, `librewolf-android-apk-161.0-1/`, `dist/`
  and the source tarball.
- The tarball was downloaded again and its GPG signature checked again.
- `GRADLE_USER_HOME` is under the cleaned output directory, and the build
  uses no ccache or sccache.
- Each pass ran in a fresh container.

## Result

`SHA256SUMS.release-45650986628` and `SHA256SUMS.rebuild-45780592911` are the
same file:

    fc8bb9707ec6e97412e395d6a468bd00fe1dfef46336e979bcd5b30775319a48  fenix-arm64-v8a-release-unsigned.apk
    16163979415601c83fbab8334627addc661019e3997cc3ce3c0f109113ed3109  fenix-armeabi-v7a-release-unsigned.apk
    8bbe784434348def58455b1d6c44826a5cccdcf249ffd78bc1cca546ef292a6f  fenix-universal-release-unsigned.apk
    3bd277e132da4d73e9414bf4eee705e6d4648f6721c55e59015e18e9db0d8f60  fenix-x86_64-release-unsigned.apk

These hashes were not just read from the published sums. After downloading, the
APKs were checked three ways:
- `cmp` against the release artifacts.
- `sha256sum`, computed locally.
- `cmp_apk.py`, which compares content, CRC, size, timestamp and compression
  for each zip entry, plus the entry order. Its output is in
  `entry-compare.txt`: 3832/3832 entries identical for each per-ABI APK and
  3866/3866 for the universal APK, with the same entry order. Every entry has
  the fixed timestamp 1981-01-01 01:01.

The only difference between the two artifact downloads is the order of the
elements in `output-metadata.json`. That file is a Gradle side file and is not
part of any APK.

## What this does and does not show

It shows that, inside one build environment, the full build is deterministic.
That holds even with parallel compilation (`-j8`), Rust, the link step, the
`omni.ja` packaging and R8. No timestamps, random seeds or ordering effects
appeared.

It does not show:
- **Cross-machine reproducibility.** The host, VM, path, user and hostname were
  all the same.
- **That a fresh image gives the same bytes.** The image was reused. A
  rebuilt image could pull different package or toolchain versions.
- **Anything about the F-Droid-shaped variant (`update_check=false`).** It has
  not been built for comparison.

The next step is a rebuild on a new VM, with an image built from the Dockerfile.
The plan for that is tracked separately.
