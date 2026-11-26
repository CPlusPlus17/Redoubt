# 161.0-1 rebuilt on a second machine (2026-11-26)

**Result: every APK entry matches the release except one,
`assets/build-metadata.properties`.** That asset holds a hash of R8's mapping
file. R8 writes one section of the mapping in an order that varies between
runs. The dex code, resources, native libraries and `omni.ja` are all
byte-identical. `patches/android/no-build-metadata.patch` stops the asset being
written. A cross-machine pair of builds with that patch has not been run yet,
so the full claim is still unmeasured (see "Open").

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
`$$compose` mapping section changed. That order most likely depends on which
worker thread finishes first. This was not measured directly. It would explain
why two builds on runner 24 matched (rebuild 45780592911) while a different
CPU did not.

`image-compare.txt` shows the build image was not the cause:
- Of the 29,187 files in `/root/.mozbuild`, five differ: sdkmanager
  bookkeeping, cargo's cache index, rustup's component list, and the `nasm`
  binary, which the image compiles from source. The native libraries built
  with it are identical.
- Three jammy packages differ by a security update: libexpat, krb5 and libtiff.
- The HEAD of the image's unpinned `/source` clone differs. The build does not
  read that clone.

## The fix

`patches/android/no-build-metadata.patch` removes `configureBuildMetadata` from
the conventions plugin, so no build writes the asset.
- Nothing in Redoubt reads the asset. `no-crashreporter.patch` removed the
  Sentry and Socorro paths that used it.
- `BuildMetadata.fromAssets()` already returns empty metadata when the asset
  is missing, as it does for non-minified builds.
- Redoubt does not upload mappings.

The R8 mapping itself stays order-dependent. That does not matter for
F-Droid, which compares APKs, but it means two published mapping files can
differ even when the APKs are identical.

## Open

- A cross-machine pair of builds with the patch, compared the same way: one
  on runner 24 and one on the second machine. Until that is done, cross-machine
  byte identity is expected, not measured.
- That pair should also vary the in-container build path, which neither build
  here did.
- The image's `/source` clone (Dockerfile.android:572) is unpinned. It is not
  a build input, but it makes the image itself differ between builds.

## Files

| File | What |
|---|---|
| `SHA256SUMS.release-45650986628` | release APK hashes (copy of the same-host evidence) |
| `SHA256SUMS.second-vm-a` | second-machine APK hashes |
| `entry-compare.txt` | `cmp_apk.py` output, four APK pairs |
| `build-metadata.properties.txt` | the differing asset from both builds |
| `mapping-compare.txt` | mapping sizes, hashes, headers, sorted comparison, diff hunks |
| `r8-inputs-compare.txt` | build-tree and Gradle-cache manifest comparison |
| `image-compare.txt` | build-image toolchain, dpkg and version comparison |

The full exports (mapping directories and manifests, about 45 MB each) are not
committed.
