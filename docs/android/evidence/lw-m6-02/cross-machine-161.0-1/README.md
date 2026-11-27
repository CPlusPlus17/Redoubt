# 161.0-1 rebuilt on a second machine (2026-11-26/27)

**Result: with `no-build-metadata.patch`, two builds on different machines give
byte-identical unsigned APKs.** All four APKs from CI run 45953992693 (runner
24) and from build C on a second machine have the same SHA-256, and every zip
entry matches (see "The patched pair").

Without the patch (release 45650986628 vs build A), every entry matched except
`assets/build-metadata.properties`. That asset holds a hash of R8's mapping
file. One section of the mapping comes out in a different order on the two
machines, though two builds on the same machine give the same order. The dex
code, resources, native libraries and `omni.ja` were all byte-identical. The
patch stops the asset being written.

## What was built

| | Release | Second machine, build A |
|---|---|---|
| Build | Actions run [45650986628](https://github.com/CPlusPlus17/Redoubt/actions/runs/45650986628) | `make android-package`, same flags as the release job |
| Commit | `683c8915` | `683c8915`, settings submodule `3982f7e6` |
| Inputs | mode=full, update_check=true | update_check=true, `--build-date=20261125160740` for both passes, `-j8` |
| Machine | runner `redoubt-ci-boxb` (id 24): KVM guest, AMD Ryzen 9 7950X3D host, 16 vCPU, 19 GB | KVM guest on a different physical host, Intel Core Ultra 9 285K, 16 vCPU, 24 GiB |
| Guest OS | Fedora 44, kernel 6.19.10, podman 5.8.1 | Fedora 44 Cloud, kernel 6.19.10 |
| Build filesystem | btrfs, `compress=zstd:1` | xfs |
| Build image | `ac5bb9c0b7b5…`, built 2026-11-25 by run 45647640735 | built fresh from the same `assets/Dockerfile.android` (`c7afbc26…10728a8`), with a newly pulled `ubuntu:jammy` |

Inside the container, both builds used the same paths (`/work/src`,
`/work/out`) and user (root), so this run does not vary the build path. The
host, CPU vendor, filesystem, image build and network path all differed.

## Result

`SHA256SUMS.release-45650986628` and `SHA256SUMS.second-vm-a` differ for all
four APKs. `entry-compare.txt` is the output of
`../gecko-same-host-161.0-1/cmp_apk.py` for each pair:

| APK | Entries | Identical | Differing |
|---|---|---|---|
| arm64-v8a, armeabi-v7a, x86_64 | 3832 | 3831 | `assets/build-metadata.properties` |
| universal | 3866 | 3865 | `assets/build-metadata.properties` |

The entry order is the same in every pair. `build-metadata.properties.txt` has
the asset from both builds, which is the same in all four APKs of a build:

| | `r8.pg_map_hash` | `proguard.uuid` |
|---|---|---|
| Release | `1566d07b…cacf3d` | `3f73c4ad-…-0d9e91a0bdc7` |
| Second machine | `98b55b31…46f336` | `bb359efa-…-318e285d418f` |

## Why the asset differs

Mozilla's Gradle conventions plugin (`WriteBuildMetadata.kt`, registered in
`ProjectPlugin.kt configureBuildMetadata`) copies the `# pg_map_hash` line
from R8's `mapping.txt` header into this asset. To find out why the hash
differed, the R8 mapping directory and hash lists of every R8 input were
exported from both machines:
- runner 24: workflow `repro-export-runner.yaml` on branch
  `inspect/runner24-mapping`, run 45859821016. It read the tree that rebuild
  run 45780592911 left in the workspace; that rebuild's APKs are
  byte-identical to the release.
- second machine: the same commands.

`mapping-compare.txt`:
- Both `mapping.txt` files are 216,733,283 bytes, with the same
  `pg_map_id` and R8 9.4.24.
- **Sorted line by line, they are identical**, apart from the hash line.
- Every difference in order falls inside the last section,
  `ComposeStackTrace -> $$compose:` (from line 1,496,207 of 1,505,581). That
  section maps Jetpack Compose code back to source lines. Whole per-file blocks
  appear at different positions, for example the bookmarks
  `AddFolderScreen`/`EditFolderScreen`/`SelectFolderScreen` blocks.
- `seeds.txt` also differs only in order. `resources.txt` differs in 50 lines,
  where it names a different "reachable from" reason for the same resources.
  `configuration.txt` and `usage.txt` are identical. None of these files is
  packaged.

`r8-inputs-compare.txt`:
- The 49,938 class, jar, dex, Kotlin and Java files under the Gradle build
  trees have the same paths on both machines, and every `.class` and `.dex`
  file has the same hash.
- The only files that differ are 48 AIDL-generated `.java` sources (their
  compiled classes are identical) and `build-metadata.properties.jar`, the
  compressed copy of the asset itself.
- Both Gradle dependency caches (APK pass and AAR pass) are identical.

So R8 got identical inputs and wrote identical code, and only the order of its
`$$compose` mapping section changed. The order is stable on each machine:
- runner 24: release 45650986628 and rebuild 45780592911 have the same
  `pg_map_hash`;
- second machine: build A and build C have byte-identical `mapping.txt`
  files (`mapping-compare.txt`, last section).

So it is not a per-run race. Something about the machine decides it, and which
property was not determined. Candidates are the filesystem (btrfs vs xfs),
which some input listing would pass on, or CPU-dependent scheduling.

`image-compare.txt` shows the build image was not the cause:
- Of the 29,187 files in `/root/.mozbuild`, five differ: sdkmanager
  bookkeeping, cargo's cache index, rustup's component list, and the `nasm`
  binary, which the image compiles from source. The native libraries built
  with it are identical.
- Three jammy packages differ by a security update: libexpat, krb5 and libtiff.
- The HEAD of the image's unpinned `/source` clone differs. The build does not
  read that clone.

## The patched pair

Commit `ba2a9c3b` (branch `fix/repro-no-build-metadata`) is `683c8915` plus
`no-build-metadata.patch` and documentation. It was built twice:

| | CI | Second machine, build C |
|---|---|---|
| Build | Actions run [45953992693](https://github.com/CPlusPlus17/Redoubt/actions/runs/45953992693), mode=full, update_check=true, build_date=20261125160740 | `run-c.sh`: `make android-package`, same flags, 2026-11-27 07:05-08:41 UTC |
| Machine | runner 24, as above | the second machine, as above |
| Image | `ac5bb9c0b7b5…` (CI's) | `73901ba826f0…`, build A's fresh image |

`SHA256SUMS.ci-45953992693` and `SHA256SUMS.second-vm-c` are the same file:

    6ec0bc82c7c25c6b2f40edb2ff657665a55ad74981f376916cd750ebb7634104  fenix-arm64-v8a-release-unsigned.apk
    e65e0270d4f03e1ab1e2822549838ad5cd4b7ac823e10327bace3942838f9b6c  fenix-armeabi-v7a-release-unsigned.apk
    43756334b08fb935fc6cf952983981afe56b9eee03efc18cf2c9ad3c2eadfd19  fenix-universal-release-unsigned.apk
    32759ff69c13078d1368bf8610d81992e3900f68c0d3b08322d53bf30f6dedaf  fenix-x86_64-release-unsigned.apk

How this was checked:
- the CI artifact was downloaded, and the hashes were recomputed on the
  workstation for both sets;
- `cmp` of each pair;
- `entry-compare-patched.txt`: 3831/3831 entries identical per ABI and
  3865/3865 universal, same order;
- `patched-vs-release.txt`: against the published release, the only change is
  the missing asset; every other entry is identical.

Both builds passed the release job's checks: unsigned, update-check key
present. Both used the same settings submodule `3982f7e6` and no overlay. The
CI build is also the compile check for the patch.

The two builds still differed in host, CPU vendor, filesystem, image build and
network path. They shared the in-container paths, user and build date.

## The fix

`patches/android/no-build-metadata.patch` removes `configureBuildMetadata` from
the conventions plugin, so no build writes the asset.
- Nothing in Redoubt reads the asset. `no-crashreporter.patch` removed the
  Sentry and Socorro paths that used it.
- `BuildMetadata.fromAssets()` already returns empty metadata when the asset
  is missing, as it does for non-minified builds.
- Redoubt does not upload mappings.

The R8 mapping itself still differs between machines (the patched pair's
mappings were not compared; build C's equals build A's). That does not matter
for F-Droid, which compares APKs, but it means two mapping files can differ
even when the APKs are identical.

## Open

- The in-container build path (`/work/src`), user and build date were the
  same in every build here. An F-Droid-style build without a container, at
  its own path, is not covered.
- The `update_check=false` (F-Droid-shaped) variant has not been built as a
  pair.
- Which machine property decides R8's `$$compose` order is unknown. It no
  longer reaches the APK.
- The image's `/source` clone (Dockerfile.android:572) is unpinned. It is not
  a build input, but it makes the image itself differ between builds.

## Files

| File | What |
|---|---|
| `SHA256SUMS.release-45650986628` | release APK hashes (copy of the same-host evidence) |
| `SHA256SUMS.second-vm-a` | second-machine build A APK hashes (unpatched) |
| `entry-compare.txt` | `cmp_apk.py` output, release vs build A |
| `SHA256SUMS.ci-45953992693` | patched CI build APK hashes |
| `SHA256SUMS.second-vm-c` | patched second-machine build C APK hashes |
| `entry-compare-patched.txt` | `cmp_apk.py` output, CI 45953992693 vs build C |
| `patched-vs-release.txt` | `cmp_apk.py` output, release vs CI 45953992693 |
| `build-metadata.properties.txt` | the differing asset from both builds |
| `mapping-compare.txt` | mapping sizes, hashes, headers, sorted comparison, diff hunks; build C vs build A |
| `r8-inputs-compare.txt` | build-tree and Gradle-cache manifest comparison |
| `image-compare.txt` | build-image toolchain, dpkg and version comparison |

The full exports (mapping directories and manifests, about 45 MB each) are not
committed.
