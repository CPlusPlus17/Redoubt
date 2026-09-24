# Android APK build reproducibility (LW-M6-02)

This document records how the unsigned release APK is built reproducibly,
what was measured, what is known to be nondeterministic (and why), and what
could *not* be verified. It accompanies the check script
[`scripts/android-verify-repro.sh`](../../scripts/android-verify-repro.sh).

**Audit reopened 2026-09-08 (LW-M6-08).** The historical identical builds below
ran within one hour and did not establish deterministic version codes. The final
unsigned handoff differed from them in its manifest and generated Glean version
string. Fenix's config plugin used `Date()` instead of `MOZ_BUILD_DATE`; the normal
APK builder omitted `gleanBuildDate`; and the repro script computed that property
before parsing `--build-date`, so it retained its old default date.

All three inputs are now corrected. `deterministic-version-code.patch` uses strict
UTC parsing of `MOZ_BUILD_DATE`, preserves the ABI bit layout, and rejects missing
or impossible dates. Both build scripts pass the same Glean date derived after
argument parsing. The compiled Config regression probe rejects the old plugin
(22 failed assertions) and passes with the patched plugin.

The two fresh R8-on builds completed on 2026-09-08; the script exits 0. All four
APKs match each other **and the normal candidate build** by SHA-256 and `cmp`.
The one-byte negative control was detected. See the
[current reproduction evidence](evidence/lw-m6-08/repro/README.md) and
[unsigned candidate manifest](evidence/lw-m6-08/SHA256SUMS.candidate). The
historical hashes below are not the current candidate reference. This remains a
same-machine APK assembly result using shared prebuilt Gecko/AAR inputs.

---

## 1. What the test does

`scripts/android-verify-repro.sh` runs **two independent builds** of the
unsigned release APK and compares the results byte for byte:

- Two full `./mach gradle` passes over the same source tree
  (`fenix:generateSafeArgsRelease`, then `fenix:assembleRelease`), the same
  per-ABI Gecko AAR inputs, and the same pinned `MOZ_BUILD_DATE`.
- Each build runs in its **own fresh container** with its **own
  `GRADLE_USER_HOME`**, and the shared Gradle intermediate outputs
  (`obj-*/gradle/build`) are wiped between the two, so the second build is a
  real rebuild, not an up-to-date no-op.
- Gradle configuration-cache and build-cache are disabled in `gradle.properties`.
  Each Gradle home is seeded with the same downloaded dependency artifacts;
  dependency resolution still runs, and APK build outputs are rebuilt.
- The result is asserted to be **unsigned**: `apksigner verify` must *reject*
  every APK (return non-zero). This is checked rather than trusted, because
  the debug keystore is generated per container and would otherwise guarantee
  a difference between two builds.
- A **negative control** proves the comparator is not vacuous: one byte is
  flipped in a copy of an APK and the comparator must report a difference.

The script exits `0` only if **both** builds succeed, **every** APK is
byte-identical across the two runs, **every** APK is unsigned, and the
negative control detects its injected difference.

### Why unsigned, and why R8 was off (and no longer is)

- **Unsigned** (`-PdisableDebugSigning`): the debug keystore is auto-generated
  per container (the image ships no `/root/.android/debug.keystore`), so any
  debug-signed APK is guaranteed to differ between two builds even on the same
  machine. `-PdisableDebugSigning` (fenix/app/build.gradle) is the same
  mechanism upstream uses for official automation builds, where signing happens
  in a separate service.
- **R8** — the paragraph below describes the ORIGINAL run. Since 2026-09-06 the
  script takes `--r8` and the R8-on configuration has been verified reproducible;
  see residual item 2, which is now closed. The historical reasoning follows.
- **R8 off** (`-PdisableOptimization`): in this tree the R8-minified release
  build crashes on launch (LW-M4-09: JNA field-order reflection vs R8
  renaming; the fix is LW-M6-07, not applied here), and every release APK this
  project has actually built and booted used R8 off. Testing a known-broken
  configuration would measure the determinism of a build nobody ships. R8's
  determinism is therefore a **residual, unverified surface** (section 4).

### Scope

The test covers the **APK assembly pass** (`./mach gradle
fenix:assembleRelease`). The gecko pass and the per-ABI AARs are shared
prebuilt inputs here; their own reproducibility is a separate question and is
listed as unverified (section 4), together with everything else this test does
not cover.

### Cross-machine claim

**Cross-machine reproducibility is NOT claimed.** This is a same-machine test
(one machine exists in this environment). The residual cross-machine sources
that a second, independent machine could surface are enumerated in section 4.

---

## 2. Historical Glean timestamp investigation

### Symptom (run 1, Glean timestamp *not* pinned)

Two same-machine builds produced APKs that differed in **exactly two entries
in every artifact**, and only those two:

| APK artifact | identical entries | differing entries |
|---|---|---|
| fenix-arm64-v8a-release-unsigned.apk | 3418 | 2 |
| fenix-armeabi-v7a-release-unsigned.apk | 3418 | 2 |
| fenix-universal-release-unsigned.apk | 3448 | 2 |
| fenix-x86_64-release-unsigned.apk | 3418 | 2 |

The two differing entries, in every artifact, were:

- `assets/dexopt/baseline.prof` (14736 vs 14738 bytes)
- `classes6.dex` (10367544 vs 10367544 bytes, same size, different content)

Everything else — including all seven other dex files, `libxul.so`, every
resource, and every other entry — was byte-identical. Zip entry timestamps were
deterministic (only 2 of ~3400 entries differed).

### Root cause: a build wall-clock timestamp embedded in `classes6.dex`

`org.mozilla.fenix.GleanMetrics.GleanBuildInfo` (generated by the Glean Gradle
plugin into `classes6.dex`) embeds the build wall-clock time as a
`Calendar.set(year, month, day, hour, minute, second)` call. In run 1 the two
builds produced different `const/16` minute/second immediates
(measured: 15:36:30 vs 15:42:33), so `classes6.dex` — and only `classes6.dex`
— differed.

Mechanism (all confirmed from primary sources):

- The Glean Gradle plugin (glean-gradle-plugin 67.3.2) reads the project
  property **`gleanBuildDate`** and appends `build_date=<value>` to the
  `glean_parser translate` arguments.
- The vendored `glean_parser` (`third_party/python/glean_parser`,
  `util.py` `build_date()`): `"0"` → unix epoch; an ISO8601 string → that
  instant (tz ignored, UTC); **absent → `datetime.now(UTC)`** — the
  nondeterminism.
- `kotlin.py` generates `GleanBuildInfo.kt` (with six `Calendar` components)
  when `with_buildinfo` is set (default on), which lands in `classes6.dex`.

`MOZ_BUILD_DATE` was *not* sufficient on its own: it only drives
`BuildConfig.BUILD_DATE` (fenix/app/build.gradle), not the Glean value.

### The fix (applied)

Pin the same instant for Glean as for `MOZ_BUILD_DATE`, by passing the
project property to both `./mach gradle` invocations in the script:

```
GLEAN_BUILD_DATE = ISO8601 form of BUILD_DATE   # 20260816204534 -> 2026-08-16T20:45:34
./mach gradle ... -PgleanBuildDate=$GLEAN_BUILD_DATE
```

`mach gradle` passes `-P` properties through (the existing
`-PdisableDebugSigning` in the same tree proves this path).

### `baseline.prof` is a consequence, not an independent source

`assets/dexopt/baseline.prof` differed only in run 1, and **only** in the
region that encodes the per-dex record for `classes6.dex`. Layout of the
decompressed payload: for each dex file (sorted by name), a 16-byte record
*precedes* the name, with the record's first u16 equal to the name length
(0x0b=11 for `classes.dex`, 0x0c=12 for the rest — all matched). The exactly
4 differing bytes fell in the 2nd u32 of the record that precedes
`classes6.dex` — i.e. a per-dex, dex-content-derived field (hash/checksum),
and `classes6.dex` was the one dex whose content changed. All other per-dex
records and all method data were byte-identical.

So `baseline.prof` was nondeterministic **because** `classes6.dex` was
nondeterministic. There is a single root cause (the Glean timestamp); pinning
it removes both differences. Confirmed empirically by run 2 below.

---

## 3. Evidence

All artifacts are preserved (never deleted). Two runs:

### Run 1 — Glean timestamp not pinned (before the fix)

- Log / verdict: `DIFFERENT` for all four APKs; 2 differing entries per APK
  (`baseline.prof`, `classes6.dex`), as detailed in section 2.
- Run 1 sha256 (for the record):
  - fenix-arm64-v8a: `847c6f5e…36347cb1` (A) vs `8d9bce3b…f4d7ea1` (B)
  - fenix-armeabi-v7a: `474c8a02…637aea` vs `48a17d29…dcd637`
  - fenix-universal: `a7d2aff7…f7aeb` vs `c237d7c0…9ace841da62`
  - fenix-x86_64: `5ced5ed2…8eba` vs `339aa391…d7ed8`
- Negative control: one byte flipped at offset 70342428 of the arm64 APK →
  comparator correctly reported 1 differing entry. (Comparator is not vacuous.)
- Preserved at: `/home/mgysin/lw-m6-02/evidence-run1-diff-20260822/` and
  `/home/mgysin/lw-m6-02/{out1,out2}/apk-run1-diff-20260822/`.

### Run 2 — Glean timestamp pinned (after the fix)

- Both builds succeeded (`build 1 ok`, `build 2 ok`); all four APKs **byte-identical**;
  all four confirmed **unsigned** (`apksigner verify` rc=1); negative control OK.
- Run 2 sha256 (identical for build 1 and build 2):
  - fenix-arm64-v8a: `b6b6b91c7bc87c921c3a8861b88c5c66e7d25a07ba4d01dbc8226eae01be8703`
  - fenix-armeabi-v7a: `804a07f3a2f3aa24eec9e2f6974264a0847b754a21855c14f3a169946d317eff`
  - fenix-universal: `75e6f75549a3bca308299659e64b5699ce4948160872f7e5f85d5ed611ac8e38`
  - fenix-x86_64: `2003b53318e071e471bd617aa436ffe11aaf1ea4729c7b88493feea1c3c4acd4`
- Preserved at: `/home/mgysin/lw-m6-02/evidence/` (`summary.txt`,
  `compare.log`, `negative-control.log`, `zip-listing-*.txt`) and
  `/home/mgysin/lw-m6-02/{out1,out2}/apk/`.

---

## 4. Residual nondeterminism and unverified surfaces

The acceptance criterion "any residual nondeterminism is listed with the
reason" is satisfied by the following honest list. Within the scope actually
tested in the old runs, the Glean pin removed the observed differences within
one hour. The 2026-09-08 audit above supersedes the broader claim that this fixed
all nondeterminism. The items below describe additional limits of the test.

1. **Cross-machine reproducibility — UNVERIFIED.** Only one machine exists in
   this environment, so the "two builds on different machines" criterion cannot
   be executed here. Surfaces a second machine could surface include:
   - Different filesystem / inode / directory-enumeration ordering fed into any
     step that is order-sensitive (none observed in this pass, but not provable
     without a second host).
   - Different toolchain bit-exactness (JDK, Kotlin compiler, D8/R8, aapt2,
     zip/packaging) — these are pinned by the container image, but a genuinely
     different host with a different image build is out of scope.
   - Locale / timezone / host-identifiers leaking into any tool that is not
     already neutralized by the pinned `MOZ_BUILD_DATE` / `GLEAN_BUILD_DATE`.
   This is stated plainly: **we have not, and on this hardware cannot, verify
   cross-machine byte-identity.**
2. ~~**R8 / minified release build — untested.**~~ **Closed 2026-09-06.** The
   premise expired: `r8-keep-rules.patch` (LW-M6-07) is in
   `assets/patches/android.txt`, and R8-on release APKs built that day boot and
   browse. `scripts/android-verify-repro.sh --r8` was run against the three-ABI
   tree at `MOZ_BUILD_DATE=20260906190000`, and **two independent builds with R8
   ON produced byte-identical unsigned APKs for all four artifacts** —
   `armeabi-v7a`, `arm64-v8a`, `x86_64` and the universal — in 1,438 s. The
   negative control detected an injected 1-byte difference, so the comparator is
   not vacuous. Evidence: `docs/android/evidence/lw-m6-02/`.

       fenix-arm64-v8a-release-unsigned.apk    e458419dd9aadb49…
       fenix-armeabi-v7a-release-unsigned.apk  f2340a1e91850f04…
       fenix-universal-release-unsigned.apk    c698a7feda552cc1…
       fenix-x86_64-release-unsigned.apk       4a9a5d12dbbe91e1…

   R8's determinism is therefore measured, not assumed. What is still not claimed
   is cross-machine byte-identity (item 1) — this remains a same-machine result.
3. **Gecko pass and per-ABI AAR inputs — out of scope.** The AARs
   (`target.maven.zip`) and the gecko build that produced them are shared
   prebuilt inputs here (LW-M2-03). Their reproducibility is a separate
   question and is not asserted by this test.
4. **Four `PARITY.md` measured rows still PENDING** (no GPU/device available)
   and **LW-M4-08 / LW-M4-11** are explicitly out of scope for this task.
   These affect feature parity, not build byte-identity, and are listed for
   completeness of the "could not be verified" record.

---

## 5. Third-party verification of a published release

The build comparison produces **unsigned** APKs. Compare those only with the
unsigned candidate manifest, currently
[`SHA256SUMS.candidate`](evidence/lw-m6-08/SHA256SUMS.candidate). Release signing
changes the archive bytes, so a signed download has a separate
`SHA256SUMS.signed`. It cannot match the unsigned manifest.

Rebuild and compare the unsigned candidate:

```sh
# 1) Re-run the two independent builds and confirm they are byte-identical,
#    unsigned, and that the comparator is not vacuous. Exits 0 only on a
#    fully passing result.
scripts/android-verify-repro.sh \
  --srcdir <source tree with configured obj-x86_64> \
  --aar-dir <per-ABI target.maven.zip inputs> \
  --build-date 20260906190000 \
  --base <scratch dir for out1/ out2/ evidence/> --r8

# 2) Compare against the unsigned candidate manifest:
cd <scratch dir>/out1/apk
sha256sum -c <trusted-checkout>/docs/android/evidence/lw-m6-08/SHA256SUMS.candidate
```

The historical run-2 values in section 3 describe that earlier experiment. They
are not the current candidate reference.

For a returned or published **signed** APK, check its signed checksum manifest,
then verify the release fingerprint and required schemes. The optional intake
comparison binds all signed ZIP payloads to the rebuilt unsigned APKs:

```sh
APKSIGNER=/path/to/apksigner.jar scripts/android-verify-signature.sh \
  --unsigned-dir <scratch-dir>/out1/apk \
  /path/to/fenix-arm64-v8a-release.apk \
  /path/to/fenix-armeabi-v7a-release.apk \
  /path/to/fenix-universal-release.apk \
  /path/to/fenix-x86_64-release.apk
```

That verifier needs a trusted `SHA256SUMS` in the unsigned directory. Copy the
candidate manifest there after the rebuild hash comparison above succeeds.
Signature and payload checks do not establish offline key custody; see the
[holder handoff](evidence/lw-m6-01/RELEASE-HANDOFF.md).

---

## 6. Proposed acceptance-criterion correction (proposal only)

The task acceptance states: *"two builds on different machines produce
byte-identical unsigned APKs."* Only one machine is available in this
environment, so that wording cannot be satisfied as literally written. This is
a **proposed** correction to the `what` (not applied to tasks.yaml — see the
M6 report for the declared change log):

> **Proposed replacement:** "Two independent builds on the available machine,
> in fresh containers with independent `GRADLE_USER_HOME` and wiped shared
> intermediates, produce byte-identical unsigned APKs; the cross-machine
> property is documented as unverified with the specific residual surfaces
> listed."

This preserves the substantive guarantee (byte-identity of the unsigned APK
across independent builds) while stating honestly that the cross-machine leg
is a documented, unverified surface rather than an executed test.
