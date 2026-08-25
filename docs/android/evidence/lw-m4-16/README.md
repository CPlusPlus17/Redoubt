# LW-M4-16 — the two residual GMS strings

Third attempt, 2026-08-25. The two previous ones were rejected for proposing
remedies that would each have produced a **false green**; this directory is the
measurement behind the one that landed, including the artefacts that would
break it if it were wrong.

## The question

`./scripts/android-smoke.sh --check-no-gms` reported `2 distinct GMS strings`
on the APK this repo builds. Zero GMS is a hard F-Droid requirement
(`LW-M6-03`), so the choice was: remove them, or keep them under a contract
that says exactly why they are harmless and **fails when they stop being so**.

## What they are

Values of two static final fields on androidx.activity's
`ActivityResultContracts$PickVisualMedia`:

    GMS_ACTION_PICK_IMAGES     = "com.google.android.gms.provider.action.PICK_IMAGES"
    GMS_EXTRA_PICK_IMAGES_MAX  = "com.google.android.gms.provider.extra.PICK_IMAGES_MAX"

They arrive inside a **prebuilt Maven class file**. No manifest attribute, no
ProGuard rule, no resource, no source of ours. `patches/android/no-gms.patch`
therefore has nothing to delete: removing them at source means vendoring a fork
of an AndroidX core artifact.

## Why naming the two strings is not enough

This is what sank attempt #2. A verifier built an APK from **androidx.activity
1.8.2**, where `getGmsPicker` is live code that hands off to the Play Services
photo picker — and that live path references **no** `Lcom/google/android/gms/`
descriptor at all. The same two literals are its only trace.

String-identical, behaviour-opposite. An allowlist keyed on the strings passes
the version that actually calls Play Services.

## The floor is 1.10.0, and it was measured, not assumed

The task brief assumed the pinned 1.13.0 was the boundary. It is not. Every
stable release from 1.8.0 to 1.13.0, plus the whole 1.10.0 prerelease series,
was fetched from `dl.google.com` and its `PickVisualMedia` class parsed —
`androidx-activity-version-bisect.txt`, with per-`.aar` sha256.

| version | GMS-named members | verdict |
|---|---|---|
| 1.8.0 … 1.9.3 | the 2 fields **+ `getGmsPicker$activity_release`, `isGmsPickerAvailable$activity_release`** | LIVE |
| 1.10.0-alpha01 | same | LIVE |
| **1.10.0-alpha02** | the 2 fields only | **first INERT** |
| 1.10.0 … 1.13.0 | the 2 fields only | INERT |

Upstream replaced the path with `SystemFallbackPicker`. The `GMS_*` fields are
what it left behind. Assuming 1.13.0 would have been *safe but wrong* — it
would fail a legitimate 1.10–1.12 tree.

The floor is **1.10.0 stable**. A prerelease of the floor is rejected rather
than rounded up, because `1.10.0-alpha01` was still live.

## The contract that landed

`--check-no-gms` passes only if all of:

1. **zero** `Lcom/google/android/gms/` type descriptors in any dex — a class
   reference is what a real dependency looks like, and no exemption covers one;
2. **zero** `gms` APK entries;
3. every GMS string is one of the two, matched by **exact value**; and, if any
   is exempted, both of:
   - **the version condition** — `META-INF/androidx.activity_activity.version`
     is present and ≥ 1.10.0 stable. AGP stamps this as a *resource*, so unlike
     a class it survives R8;
   - **the class-shape condition** — where the declaring class is present, it
     declares the two GMS-named *fields* and **no** GMS-named *method*.

The threshold was not relaxed and nothing here decodes an instruction. The dex
`type_ids`/`method_ids`/`field_ids` tables are fixed-width index tables read at
offsets the header states; that is why they are allowed where attempt #1's
linear-sweep disassembler (whose opcode width table was wrong, and which a
verifier drove to a concrete false pass) was not.

## The adversarial test

`controls/` holds seven APKs. The 1.8.2 and 1.13.0 `classes.jar` were dexed
with the **pinned container's d8** (`localhost/librewolf-android-build:latest`,
`build-tools/37.0.0/lib/d8.jar`) — the same route the verifier used to break
the old allowlist. Full output in `logs/controls.log`.

| fixture | dex | version marker | expected | result |
|---|---|---|---|---|
| `nc1-live182-marker182` | 1.8.2 **live** | `1.8.2` | FAIL | FAIL — both conditions |
| `nc2-live182-marker1130` | 1.8.2 **live** | `1.13.0` **(forged)** | FAIL | FAIL — class shape |
| `nc3-inert1130-marker182` | 1.13.0 | `1.8.2` | FAIL | FAIL — version |
| `nc4-inert1130-alpha01` | 1.13.0 | `1.10.0-alpha01` | FAIL | FAIL — prerelease of floor |
| `nc5-inert1130-nomarker` | 1.13.0 | *(absent)* | FAIL | FAIL — cannot establish |
| `pc1-inert1130-marker1100` | 1.13.0 | `1.10.0` | PASS | PASS — at the floor |
| `pc2-inert1130-marker1130` | 1.13.0 | `1.13.0` | PASS | PASS |

**`nc2` is the one that matters.** It is the exact artefact that defeated the
previous allowlist, carrying a *forged* version marker claiming the safe
version — and it is still caught, on class shape alone. The two conditions
cover each other: neither is load-bearing by itself.

`pc1`/`nc4` pin the boundary from both sides, one patch version apart.

## The real artefacts

- `logs/real-debug-apk.log` — `~/lw-m4-16-debug-apk/apk/fenix-x86_64-debug.apk`
  (built 2026-08-25 20:14): **PASS**, exemption granted, 9 methods on the
  declaring class, none GMS-named, marker `1.13.0`.
- `logs/release-apk.log` — `~/lw-fresh-2026-08-22/apk/fenix-x86_64-release.apk`:
  **PASS**, but by the *unconditional-zero* path — R8 removed the class and both
  literals, so neither condition was exercised.

## What is NOT proven, and what would prove it

- **A minified build cannot be checked this way.** With the class and strings
  gone, the check never asks about the version, so a release APK built against
  a downgraded androidx.activity would pass. Read a release PASS as evidence
  about R8, not about the dependency; cite the debug artefact.
- **The build-time floor covers the minified case, and it is implemented.**
  `patches/android/no-gms.patch` now adds an assertion to the root
  `build.gradle`, after the `plugins {}` block, that reads the version through
  Gradle's own catalog accessor (`libs.versions.activity`) and throws a
  `GradleException` below the floor. It runs at configuration time, before R8,
  so it is the guard that still works when the strings and the class are gone.

  It is **tested, not assumed** — `gradle-floor-assertion.txt` runs it under the
  same Gradle the build uses (9.5.1, from the build tree's wrapper dist,
  offline) across ten versions, and `gradle-floor-harness.build.gradle` is the
  harness. Two drafts failed that test before this one passed: the first
  compared version triples with Groovy's `<=>` on `ArrayList`, which throws
  rather than comparing, so *every* version including 1.13.0 failed the build.
  Shipping it unverified would have broken the Android build outright.
- **Nothing was installed or launched.** No device, no emulator. Every result
  above is static analysis of an artefact.

## Reproducing

    ./scripts/android-smoke.sh --check-no-gms --apk <apk>          # needs --apk
    LW_SMOKE_PACKAGE=org.redoubtbrowser.fixture \
      ./scripts/android-smoke.sh --check-no-gms --apk controls/nc2-live182-marker1130.apk

`class-members.py` parses a `.class` file's field/method tables — the tool
behind the version table. It takes a path to an extracted class file.

The build-time floor, against the Gradle the build actually uses:

    GB=$(ls -d ~/*/gradle-home/wrapper/dists/gradle-*-bin/*/gradle-*/bin/gradle | head -1)
    printf '[versions]\nactivity = "1.8.2"\n' > <harness>/gradle/libs.versions.toml
    "$GB" -p <harness> --offline help      # must exit 1

## The 2026-08-19 files in this directory

They predate this attempt and are kept as the record of what was tried:
`case1-prepatch-full-gms.txt` (the 63,646-class dexdump behind the original
"4,474 → 2" count), the `result-*.json` pair, and the `reverify-*` set — which
includes the run that drove attempt #1's disassembler to a **false pass**
(`reverify-mut-control-PASS.txt`). Read them as history. Where they disagree
with this README, this README is the later measurement.
