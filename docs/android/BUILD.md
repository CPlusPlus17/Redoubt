# Building GeckoView for arm64 — the unpatched baseline

**Owner: LW-M2-01.** This file documents one thing: how to take a **stock,
unpatched Firefox 153.0.4 source tree** and `assets/mozconfig.android` and get
`./mach build` to exit 0 for `aarch64-linux-android` inside the pinned
`librewolf-android-build` container image.

No LibreWolf patch is applied anywhere in this document. That is the entire
point — every later Android build failure is bisected against this result, so
the baseline has to be free of our own changes. LW-M2-02 adds the common patch
set on top of exactly this sequence.

What this build produces is the **GeckoView AAR**, not an APK.
`assets/mozconfig.android` deliberately does not set
`--enable-android-subproject=fenix`; the APK is LW-M2-04.

- Firefox version: 153.0.4 (`firefox-153.0.4.source.tar.xz`, GPG-verified)
- mozconfig: `assets/mozconfig.android` — **used unmodified, no edit was needed**
- Image: `librewolf-android-build` (from `assets/Dockerfile.android`, LW-M0-06)
- Target: `aarch64-linux-android` only

---

## Result

`./mach build` exits **0** on a stock 153.0.4 tree with `assets/mozconfig.android`
unmodified. Measured twice: once while working the deviations out, then once
more end-to-end from a fresh container and a freshly extracted tree, driving
only the commands in this file. The numbers below are from that second run.

| | |
|---|---|
| `./mach build -j16` wall-clock | **21 min 56 s** (1316 s) |
| §4 toolchain prep (node + cbindgen + 2 artifact fetches) | 55 s |
| §1 tarball extraction (not in the numbers above) | ~1–6 min, depending on page cache |
| **Peak container memory, incl. page cache** (`memory.peak`) | **37.97 GB** (35.4 GiB) |
| **Peak anonymous memory** (`memory.stat` `anon`) | **30.88 GB** (28.8 GiB) |
| Peak container swap | 0.84 GB |
| Disk read / write during the build | 25.6 GB / 53.0 GB |
| CPU efficiency reported by mach | 42 % |
| Object directory when finished | 21 GB |
| `dist/bin/libxul.so` | 2.4 GB, unstripped, `ARM aarch64 … for Android 26, built by NDK r29` |
| `geckoview-debug.aar` | 91 MB |

Measured on a 32-core / 62 GB machine that was **not idle** — five other agents
were working on it — with `-j16`. Treat the wall-clock as an upper bound for a
dedicated machine and the memory as representative.

**For LW-M2-08 (CI budget) and LW-M2-03 (three-ABI fat AAR):**

- The 22 minutes is *one* ABI. Nothing here is shared between ABIs except the
  Gradle/Java half and the host tools, so three ABIs is closer to 3× than to
  1×; budget ~60 min of build plus the fat-AAR merge, not 25.
- Memory is the binding constraint, not CPU. 30.9 GB of anonymous memory at
  `-j16` is a little under 2 GB per job, and it *swapped* on a 62 GB host
  (mach's own counter: 5.5 GB paged out). A CI runner with less than 32 GB
  should drop to `-j8`. Do not raise `-j` past 16 without re-measuring.
- Three JVM daemons (one Gradle at `-Xmx7g`, two Kotlin compile daemons at
  `-Xmx7g` each) stay resident for most of the build and are a large fixed
  chunk of that total. They are not sized by `-j`.
- ~55 s of the run is network fetches that a prepared image would make zero,
  and the Gradle/Maven downloads inside `mach build` are on top of that.

---

## 0. Prerequisites on the host

- `podman` (rootless, 5.8.4 on the reference machine). Docker is not installed
  there, so nothing below has been tried under Docker; the `:z` mount suffix in
  particular is podman/SELinux-specific.
- The image built and tagged:
  `podman build -f assets/Dockerfile.android -t librewolf-android-build .`
- ~40 GB free disk for the source tree plus object directory.
- **Network access inside the container.** This build is not hermetic. See
  §5 for exactly what it fetches and why.

### SELinux

The reference host runs SELinux in `Enforcing` mode. A podman bind mount
without a label suffix is **read-only from inside the container**, and the
failure surfaces as permission-denied errors deep in the build on paths that
look perfectly writable from outside. Every `-v` below therefore carries `:z`
(shared label — safe when more than one container touches the path).

Do not use `:Z` on a tree anything else reads: it relabels exclusively and
will break other readers.

## 1. Get your own source tree

The tree is mutated by the build (object directory, `lw/l10n`, gradle caches).
Extract your own; never build in a tree someone else is reading.

```sh
mkdir -p ~/lw-build
tar -xf firefox-153.0.4.source.tar.xz -C ~/lw-build      # ~5 min, 4.7 GB
cp assets/mozconfig.android ~/lw-build/mozconfig.android
```

`assets/mozconfig.android` is copied **byte for byte**. Nothing in it had to
change to make this build work.

## 2. Create the l10n base directory

```sh
mkdir -p ~/lw-build/firefox-153.0.4/lw/l10n
```

`assets/mozconfig.android` passes
`--with-l10n-base="$topsrcdir/lw/l10n"`, and `toolkit/moz.configure:500-504`
**dies** — `Invalid value --with-l10n-base, ... doesn't exist` — if the path is
not a directory. On a patched LibreWolf tree that directory is created by
`scripts/librewolf-patches.py` when it unpacks the l10n archive; on a stock tree
it does not exist.

An empty directory is enough for a GeckoView build: `L10NBASEDIR` is only read
by l10n repacks, and on Android it would only ever cover
`mobile/android/locales/en-US` (two `.ftl` files) anyway — the Fenix UI strings
come from a different mechanism entirely. Creating it keeps the mozconfig
unmodified, which is why this is preferred over dropping the option.

## 3. Start the container

```sh
podman run -d --name lw-build \
  -v ~/lw-build:/work:z \
  -w /work/firefox-153.0.4 \
  -e MOZCONFIG=/work/mozconfig.android \
  librewolf-android-build sleep infinity
```

Everything the image already provides — JDK 17.0.18+8, NDK r29, SDK
build-tools 37.0.0 / platform android-37.0 / platform-tools / emulator,
bundletool 1.18.3, Rust 1.94.1 with the Android targets — is found by configure
with **no extra environment variables**. `MOZBUILD_STATE_PATH`,
`ANDROID_SDK_ROOT`, `ANDROID_NDK_ROOT`, `JAVA_HOME` and
`ANDROID_BUNDLETOOL_PATH` are already exported by the image, and
`assets/mozconfig.android` turns them into `--with-android-sdk`,
`--with-android-ndk` and `--with-java-bin-path`.

## 4. Add the four toolchain pieces the image is missing

This is the whole deviation list. Each one is a real configure hard-stop on the
image as built by LW-M0-06 — none is optional, and none required a mozconfig
change, because in every case configure finds the tool by looking in
`$MOZBUILD_STATE_PATH` (which is what `mach bootstrap` would have populated).

The mechanism that makes this work without editing anything:
`bootstrap_path()` in `build/moz.configure/bootstrap.configure:301-306` returns
a path under `$MOZBUILD_STATE_PATH` **whenever that path exists**, even with
`--enable-bootstrap` left at its default. So dropping a toolchain into the state
directory is equivalent to having bootstrapped it.

> **These four belong in `assets/Dockerfile.android`.** Doing them at runtime is
> a workaround for this task; see the "Hand-off to LW-M0-06" section.

### 4.1 A clang for the target and host compilers

```sh
podman exec lw-build ln -sfn \
  /root/.mozbuild/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64 \
  /root/.mozbuild/clang
```

Without this, configure never looks inside the NDK for a compiler — the NDK's
`bin/` is not on `PATH` and `--with-android-ndk` only supplies `--sysroot` and
`-gcc-toolchain` flags (`build/moz.configure/android-ndk.configure:264-296`),
not the compiler binary. Configure falls through to `/usr/bin/gcc` and stops
with:

```
checking for the target C compiler... /usr/bin/gcc
ERROR: Target C compiler target CPU (x86_64) does not match --target CPU (aarch64)
```

`build/moz.configure/toolchain.configure:760` is
`clang_search_path = bootstrap_search_path("clang/bin")`, so a `clang` directory
in the state dir is exactly where configure expects to find one. The symlink
makes the NDK's own clang 21.0.0 serve as target C/C++, host C/C++, assembler
and the wasm compiler.

Note this deviates from upstream, which builds Android with Mozilla's own clang
(`mobile/android/config/mozconfigs/common:18`), not the NDK's. The NDK clang is
what the pinned image contains, it satisfies the `clang >= 19.0` floor at
`build/moz.configure/toolchain.configure:1494-1498`, and it produced a clean
build — but if a future compiler-shaped failure appears, this is the first
thing to question.

### 4.2 Node.js 22.16.0

```sh
podman exec lw-build bash -c '
  wget -q -O /tmp/node.tar.xz https://nodejs.org/dist/v22.16.0/node-v22.16.0-linux-x64.tar.xz &&
  mkdir -p /root/.mozbuild/node &&
  tar -xJf /tmp/node.tar.xz -C /root/.mozbuild/node --strip-components=1 &&
  rm -f /tmp/node.tar.xz && /root/.mozbuild/node/bin/node --version'
```

`build/moz.configure/node.configure:5` defaults `--enable-nodejs` on, so a
missing node is a `FatalCheckError`, not a warning.

**Do not use the distro package.** `NODE_MIN_VERSION` is `12.22.12`
(`python/mozbuild/mozbuild/nodeutil.py:15`) and Ubuntu jammy ships 12.22.9 —
three patch releases short. 22.16.0 is what upstream builds Android with
(`taskcluster/kinds/toolchain/node.yml:23-38` → `nodejs-22-source`,
`taskcluster/kinds/fetch/toolchains.yml:645-649`).

`$MOZBUILD_STATE_PATH/node/bin` is the first entry in
`find_node_paths()` (`python/mozbuild/mozbuild/nodeutil.py:48-59`), so no
`NODEJS` environment variable is needed once it is installed there.

### 4.3 cbindgen 0.29.4

```sh
podman exec lw-build bash -c '
  cargo install cbindgen --version 0.29.4 --locked --root /root/.mozbuild/cbindgen &&
  ln -sf /root/.mozbuild/cbindgen/bin/cbindgen /root/.mozbuild/cbindgen/cbindgen'
```

`build/moz.configure/bindgen.configure:13` requires `>= 0.29.4`; upstream pins
exactly 0.29.4 (`taskcluster/kinds/fetch/toolchains.yml:245-251`). Without it:

```
checking for cbindgen... no
ERROR: Cannot find cbindgen. Please run `mach bootstrap`, ...
```

The extra symlink matters: `bootstrap_search_path("cbindgen")` puts
`$MOZBUILD_STATE_PATH/cbindgen` itself (not its `bin/`) on the search path, so
the executable has to sit directly in that directory — which is the layout
`mach bootstrap` produces when it unpacks the `cbindgen.tar.zst` artifact.

`cargo install` takes about a minute. This is the only step that compiles Rust
from crates.io.

### 4.4 The WASI sysroot and the wasm32 compiler-rt

```sh
podman exec lw-build bash -c '
  cd /root/.mozbuild &&
  /work/firefox-153.0.4/mach --log-no-times artifact toolchain \
      --from-build sysroot-wasm32-wasi'

podman exec lw-build bash -c '
  mkdir -p /root/crt && cd /root/crt &&
  /work/firefox-153.0.4/mach --log-no-times artifact toolchain \
      --from-build wasm32-wasi-compiler-rt-21 &&
  mkdir -p /root/.mozbuild/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64/lib/clang/21/lib/wasm32-unknown-wasi &&
  cp /root/crt/compiler-rt-wasm32-wasi/lib/wasi/libclang_rt.builtins-wasm32.a \
     /root/.mozbuild/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64/lib/clang/21/lib/wasm32-unknown-wasi/libclang_rt.builtins.a'
```

**Why this is required, and why it must not be "fixed" by turning it off.**
RLBox wasm sandboxing is on by default for every little-endian target —
`toolkit/moz.configure:2829-2833` returns the full library list
(graphite, ogg, hunspell, expat, woff2, soundtouch) whenever
`target.endianness == "little"`, and aarch64-linux-android qualifies. It is a
security mitigation we ship on desktop, so the correct action is to supply the
sysroot, **not** to pass `--without-wasm-sandboxed-libraries` — which is what
configure helpfully suggests, and which would be a silent parity loss.

Two separate failures, in order:

```
checking the wasm C compiler can find wasi headers...
ERROR: Cannot find wasi headers or problem with the wasm compiler.
```
→ fixed by the sysroot. `toolkit/moz.configure:2869` is
`bootstrap_path("sysroot-wasm32-wasi", ...)`, so unpacking the artifact into
`$MOZBUILD_STATE_PATH/sysroot-wasm32-wasi` is picked up with no `WASI_SYSROOT`
variable and no configure flag.

```
checking the wasm C linker can find wasi libraries...
wasm-ld: error: cannot open .../lib/clang/21/lib/wasm32-unknown-wasi/libclang_rt.builtins.a:
         No such file or directory
```
→ fixed by the compiler-rt copy. The NDK ships compiler-rt for Android targets
only (`lib/clang/21/lib/linux/`). clang resolves its resource directory from the
**real** path of the binary, so the `/root/.mozbuild/clang` symlink does not
help: the file has to land inside the NDK. The rename is real — the artifact
uses the old flat name `lib/wasi/libclang_rt.builtins-wasm32.a`, clang 21 wants
the per-target directory name `libclang_rt.builtins.a`.

This mirrors upstream, which repacks the same compiler-rt into its clang before
building the sysroot (`taskcluster/scripts/misc/build-sysroot-wasi.sh:8`).

Both artifacts come from Mozilla's public taskcluster index via
`mach artifact toolchain`, which works from a release tarball with no VCS
checkout. They are the exact artifacts a 153 build is tested against, which is
why they are preferred here over a wasi-sdk release tarball.

## 5. Build

```sh
podman exec lw-build bash -c 'cd /work/firefox-153.0.4 && ./mach build -j16'
```

`./mach build` runs configure itself; there is no separate `./mach configure`
step and no `mach bootstrap` at any point.

Pick `-jN` to leave headroom — see the measured numbers above. Peak memory
scales with `N`.

### What the build reaches out to the network for

Not hermetic, and the Gradle half is the larger part:

- **Gradle 9.5.1 distribution.** `assets/mozconfig.android` only passes
  `--with-gradle` when `GRADLE_BIN` is set, and the image does not set it, so
  `mobile/android/gradle.configure:29-42` falls back to the in-tree `./gradlew`
  wrapper, which downloads Gradle at build time (sha256-pinned in
  `gradle/wrapper/gradle-wrapper.properties`).
- **The Gradle/Maven dependency graph** (AGP 8.13.2, Kotlin 2.3.21 and their
  transitive deps) from google/mavenCentral/plugins.gradle.org.
- The two `mach artifact toolchain` fetches in §4.4, and node/cbindgen in
  §4.2/§4.3.

Upstream avoids all of this with a prepopulated `android-gradle-dependencies`
fetch and `GRADLE_MAVEN_REPOSITORIES` pointing at `file://` mirrors
(`mobile/android/config/mozconfigs/common:10-11`). Doing the same is the right
answer for CI — flagged for LW-M2-08.

### Why `mach build` runs Gradle at all

`config/baseconfig.mk:46` lists `android-stage-package` and
`android-archive-geckoview` in `ALL_TIERS`, and `:57-59` only filters them out
when `MOZ_BUILD_APP != mobile/android`. So for our build they are in the default
`TIERS`, and `Makefile.in:83-84` implements the second one as
`mach android archive-geckoview`. The GeckoView AAR is part of `mach build`,
not a follow-up step.

## 6. Verify

```sh
podman exec lw-build bash -c \
  'grep -E "MOZ_HARDENING_CFLAGS|MOZ_STL_HARDENING_FLAGS|MOZ_REPLACE_MALLOC|MOZ_RUST_SIMD" \
   /work/firefox-153.0.4/obj-*/config.status'
```

On a good build this prints, verbatim:

```
'MOZ_HARDENING_CFLAGS': [   '-U_FORTIFY_SOURCE',
                            '-D_FORTIFY_SOURCE=2',
                            '-fstack-protector-strong',
                            '-fstack-clash-protection',
                            '-fstrict-flex-arrays=1'],
'MOZ_HARDENING_LDFLAGS': [   '-fstack-protector-strong',
                             '-fstack-clash-protection'],
'MOZ_MEMORY': '1',
'MOZ_REPLACE_MALLOC': '1',
'MOZ_REPLACE_MALLOC_STATIC': '1',
'MOZ_RUST_SIMD': '1',
'MOZ_STL_HARDENING_FLAGS': [   '-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_EXTENSIVE'],
```

Check the artifacts too:

```sh
file  ~/lw-build/firefox-153.0.4/obj-aarch64-unknown-linux-android/dist/bin/libxul.so
# ... ELF 64-bit LSB shared object, ARM aarch64, ... for Android 26, built by NDK r29 ...
ls -l ~/lw-build/firefox-153.0.4/obj-aarch64-unknown-linux-android/gradle/build/mobile/android/geckoview/outputs/aar/geckoview-debug.aar
```

`libxul.so` reporting `ARM aarch64` and `NDK r29` is the check that matters:
it proves the cross build really used the pinned NDK and did not quietly fall
back to a host compiler.

---

## How this document was verified, and what was not verified

The board's `verify` for LW-M2-01 is `manual: follow docs/android/BUILD.md on a
clean machine`. What was actually done, so the next person knows what is still
untested:

**Executed end-to-end, in one run, from a fresh container and a freshly
extracted tarball:** §1 through §6. The container was created from the
`librewolf-android-build` image with nothing added to it, and the only commands
run inside it were the ones in §4 and §5, collected into a single script. It
finished with `MACH_EXIT=0`.

**Not verified:**

- The image itself was **not rebuilt** from `assets/Dockerfile.android` for
  this. It was the already-built `librewolf-android-build` image (LW-M0-06).
  "Clean image" here means "fresh container from that image", not "fresh
  `podman build`".
- Only this one host was used: Fedora, kernel 7.1.x, x86_64, SELinux
  Enforcing, podman 5.8.4 rootless. Nothing here has been tried on another
  machine, another distro, or under Docker.
- The build was never run **without** network access, so the fetch list in §5
  is what was observed, not a proven-complete list.
- `-j16` is the only parallelism level measured. The `-j8` advice for smaller
  runners above is an inference from the memory figures, not a measurement.
- Nothing was run on a device or emulator. This task ends at "`mach build`
  exits 0 and produces an aarch64 `libxul.so` and a GeckoView AAR". Whether
  that AAR *works* is LW-M2-04 and the smoke test.

## Things that look like they should be deviations and are not

Recorded so nobody spends an afternoon on them again.

- **`python3 -m venv` is broken in the image** (`ensurepip` missing; Ubuntu
  splits it into `python3.10-venv`) and this does **not** matter. mach builds
  its virtualenvs from the vendored `third_party/python/virtualenv`, not from
  `venv`. Installing `python3.10-venv` is not required.
- **`JAVA_HOME` is ignored by configure** (`build/moz.configure/java.configure:29-34`)
  but the image already places the JDK at
  `$MOZBUILD_STATE_PATH/jdk/jdk-17.0.18+8`, which is where configure actually
  looks. Nothing to do.
- **The `emulator` SDK package** is installed by the image and is genuinely
  required (`build/moz.configure/android-sdk.configure:376` checks for it
  unconditionally). Nothing to do — but do not "trim" it from the image.
- **`nasm` is not needed *for this document's `aarch64` baseline*, and IS needed
  for the `x86_64` ABI of the fat AAR.** This bullet used to read "No
  `nasm`/`yasm` is needed: they are x86-only" with no qualifier, which was true
  of the arm64-only build described here and false of `make android-aar`
  (LW-M2-03), whose third ABI is `x86_64` — one of the only three
  `mobile/android/moz.configure:161-166` permits. `toolkit/moz.configure:2631-2643`
  collects four nasm requirements, every one of them gated on `target.cpu` being
  `x86` or `x86_64`: AV1/dav1d (`:864-867`, version floor **2.14**, the binding
  one), VPX (`:2317-2323`), JPEG (`:2468-2471`) and FFVPX (`:2608-2611`). If any
  fire, `:2646-2651` runs `check_prog("NASM", ["nasm"], bootstrap="nasm")` and
  `:2655-2658` dies with *"Nasm is required to build with AV1, FFVPX, JPEG and
  VPX, but it was not found."* For `aarch64` and `armv7` none of the four fire,
  so `check_prog` is skipped entirely — which is why an arm-only build never
  notices. `assets/Dockerfile.android` has shipped **nasm 3.01** since LW-M0-16
  (built from the tarball the tree itself pins, `taskcluster/kinds/fetch/toolchains.yml:171-177`,
  the same source upstream's `linux64-nasm` uses, `taskcluster/kinds/toolchain/nasm.yml:59-70`).
  Do **not** trim it back out on the grounds that an arm build does not use it —
  `scripts/android-fat-aar.sh`'s preflight refuses to start an `x86_64` pass
  without it. `yasm` really is unneeded: no configure check in this tree looks
  for it (it survives only in `build/gyp_includes/common.gypi:683-684` and a
  macOS bootstrap package list, `python/mozboot/mozboot/osx.py:240`).
- **Host `gcc` 11.4** is present and is above the `10.1.0` floor
  (`build/moz.configure/toolchain.configure:1232-1233`), but it is not used —
  §4.1 makes clang the host compiler too.

## Hand-off to LW-M0-06 (`assets/Dockerfile.android`)

The four steps in §4 are runtime workarounds. They belong in the image, and
until they are there, "clean image" means "clean image plus §4". Suggested
layers, in the image's existing style:

1. `ln -sfn ${ANDROID_NDK_ROOT}/toolchains/llvm/prebuilt/linux-x86_64 ${MOZBUILD_STATE_PATH}/clang`
   — with an assertion that `${MOZBUILD_STATE_PATH}/clang/bin/clang` is executable.
2. Node.js pinned to 22.16.0, unpacked into `${MOZBUILD_STATE_PATH}/node`, with
   a `node --version` assertion. Pin cited from
   `taskcluster/kinds/fetch/toolchains.yml:645-649`.
3. cbindgen pinned to 0.29.4 (`taskcluster/kinds/fetch/toolchains.yml:245-251`),
   installed so the binary is at `${MOZBUILD_STATE_PATH}/cbindgen/cbindgen`.
4. The WASI sysroot and wasm32 compiler-rt. These need the source tree present
   to run `mach artifact toolchain`, so either run them against the `/source`
   clone the image already makes, or fetch the two artifact URLs directly.

**All four landed in `assets/Dockerfile.android` in LW-M0-15**, and a fifth one
that this document originally said was unnecessary landed in LW-M0-16:

5. `nasm`, pinned to 3.01 — **only** the `x86_64` ABI needs it, so an
   `aarch64`-only build like this one never hits it, but `make android-aar`
   (three ABIs, LW-M2-03) does. See the corrected bullet in the previous
   section for the `toolkit/moz.configure` lines that make it a hard configure
   stop. The image builds it from the tarball the tree pins by sha256
   (`taskcluster/kinds/fetch/toolchains.yml:171-177`) and installs it at
   `${MOZBUILD_STATE_PATH}/nasm/nasm` — the `bootstrap="nasm"` search path
   `check_prog` falls back to — as well as putting that directory on `PATH`.
   Verify with `podman run --rm librewolf-android-build bash -lc 'nasm -v'`.

A pre-populated Gradle/Maven cache is the other big win, but that is CI budget
work and belongs to LW-M2-08 rather than the toolchain image.

## Hand-off to LW-M5-03 (parity matrix)

Two things `assets/mozconfig.android` flagged as **UNVERIFIED** are now
verified against a real toolchain, and both came out in our favour:

- `-fstack-clash-protection` **is** applied on aarch64. It needs clang >= 18.1.0;
  the NDK r29 clang is 21.0.0.
- STL hardening resolves to the **stronger** of the two branches:
  `-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_EXTENSIVE`, not the
  `_LIBCPP_ENABLE_ASSERTIONS=1` fallback.

Also confirmed live rather than statically: `MOZ_REPLACE_MALLOC`,
`MOZ_REPLACE_MALLOC_STATIC`, `MOZ_MEMORY` and `MOZ_RUST_SIMD` are all set on
this target, i.e. `--enable-replace-malloc` and `--enable-rust-simd` are doing
real work on Android and are not silently ignored.

No hardening option had to be dropped, softened or worked around to make the
Android build succeed.

---

## Running the Fenix unit test suite (LW-M2-09)

`AGENTS.md` requires `./mach gradle fenix:testDebugUnitTest` to pass for any
Kotlin-layer change. This section explains how to run it, what a clean result
looks like, and why ~92 tests fail for environmental reasons that have nothing
to do with the code under test.

### How to run

```sh
# Prerequisites: a patched tree with a completed objdir (at least the Gradle
# half must have run, so the geckoview AAR and megazord dylib are present).
# The tree must be the one the build used — the Gradle project paths are
# relative to the tree root.

# From the tree root:
./mach gradle fenix:testDebugUnitTest 2>&1 | tee /tmp/test-run.log
```

The `mach gradle` command runs the Gradle task in the container's JDK (Temurin
17, from the image). No additional toolchain is needed — the unit tests run on
the host JVM, not on an Android device.

### What a clean result looks like

A **clean** run has **zero failures beyond the documented environmental set**.

The environmental set is **87 tests in 3 classes**, all failing because
`libmegazord.so` (the appservices UniFFI native library) cannot be loaded on
the host JVM. It is built as an **Android** native library (cross-compiled ELF
for ARM/x86 Android) and bundled in the APK under `lib/<abi>/libmegazord.so`,
but `testDebugUnitTest` runs on the **host** JVM (Linux x86_64), where an
Android `.so` is not loadable.

#### Environmental failures (EXPECTED — subtract from results)

| Test class | Tests | Root cause |
|---|---|---|
| `org.mozilla.fenix.search.awesomebar.SearchSuggestionsProvidersBuilderTest` | 70 | `UnsatisfiedLinkError: Unable to load library 'megazord'` — every test constructs a suggestion provider that calls into appservices via UniFFI |
| `org.mozilla.fenix.reviewprompt.ReviewPromptMiddlewareTriggerCriteriaTest` | 16 | every test calls `NimbusApi` methods that route through `UniffiLib`, whose static initializer loads `libmegazord.so`. Surfaces as `UnsatisfiedLinkError` **or** `NoClassDefFoundError: Could not initialize class ...UniffiLib` — see the note on `forkEvery` below |
| `org.mozilla.fenix.experiments.RecordedNimbusContextTest` | 1 | `UnsatisfiedLinkError: Unable to load library 'megazord'` — directly invokes a recorded `NimbusApi` event query |

**Total: 87 tests.** Full evidence: `docs/android/evidence/lw-m2-09/expected-failures.md`.

Note: the LW-M4-14 baseline (2026-08-22) also had
`AutofillSettingsMiddlewareTest` (5 tests) in this set. As of 2026-08-25 it
passes; if it regresses, add it back with the same reason (UniFFI binding
cannot initialize on host JVM).

#### Non-environmental failures (NOT expected — real signal)

Failures in **any other class** are real regressions and must be investigated.
Three known non-environmental failures (as of 2026-08-25) are:

| Test class | Tests | Error |
|---|---|---|
| `org.mozilla.fenix.components.lens.LensCameraFragmentTest` | 1 | `MockKException: no answer found for Context.getPackageManager()` — mockk stubbing gap |
| `org.mozilla.fenix.settings.HomeSettingsFragmentTest` | 1 | `AssertionError` — assertion failure |
| `org.mozilla.fenix.distributions.DefaultDistributionProviderCheckerTest` | 1 | `AssertionError: expected:<myProvider> but was:<null>` — new since LW-M4-14 |

These are tracked separately and are **not** part of the environmental allowlist.

### Verifying a clean result

Do not eyeball it. The allowlist above is checked in machine-readable form as
`docs/android/fenix-test-allowlist.yaml`, and the board tool subtracts it:

```sh
python3 docs/android/board.py --check-fenix-tests
# ...or against a specific results directory:
python3 docs/android/board.py --check-fenix-tests --results <objdir>/gradle/build/mobile/android/fenix/app/test-results/testDebugUnitTest
```

It reads the JUnit XML Gradle writes, **not** the console log — a log is only as
good as whoever remembered to `tee` it, and a `grep` over a log that was never
captured prints nothing, which is indistinguishable from a clean run. Exit 0
means no failure beyond the documented set. It errors on:

* a failing class that is in neither list — the signal the gate exists to surface;
* **more** failures in a listed class than declared — a real regression hiding
  behind an expected name;
* any listed class that **did not run at all** — a partial run, an aborted task,
  or the wrong Gradle module. This is the false green that matters: such a run
  has nothing beyond the allowlist in it precisely *because it barely ran*.

It warns (exit 0) when a listed class ran and passed, or failed fewer times than
declared — the entry is going stale and should be trimmed. That is how
`AutofillSettingsMiddlewareTest` left the list.

Quote the header lines in any task report: they name the results directory and
the timestamp of the newest result, so a green taken from a stale objdir is
visible to the reader rather than hidden.

#### Fallback: reading the console log

If you have a log but no objdir, the Mozilla conventions Gradle plugin
(`mobile/android/gradle/plugins/conventions/.../ProjectPlugin.kt`) prints
`  TEST-UNEXPECTED-FAIL | <class>.<test> | <exception>` per failure:

```sh
grep "TEST-UNEXPECTED-FAIL" /tmp/test-run.log \
  | sed 's/.*TEST-UNEXPECTED-FAIL | //' \
  | awk -F'|' '{print $1}' \
  | sed 's/ \+.*//' \
  | sed 's/\.[^.]*$//' \
  | sort | uniq -c | sort -rn
```

A **clean** result shows **only** the 3 environmental classes (87 tests), plus
possibly the 3 known non-environmental failures. Any **new** class, or a **count
increase** in an existing environmental class, is a real regression. Note this
form cannot detect a partial run — prefer `--check-fenix-tests`.

#### Why the allowlist is keyed on class name, not error type

`mobile/android/fenix/app/build.gradle` sets `forkEvery = 80`: the test JVM is
recycled every 80 tests. A megazord-backed test reports `UnsatisfiedLinkError`
on the first touch in a fresh JVM, and `NoClassDefFoundError: Could not
initialize class ...UniffiLib` on a later touch in a JVM whose static
initializer already failed. Which one you get depends on where the fork boundary
falls, and that moves whenever the patch set changes the test count — it has
already moved once, between the LW-M4-14 baseline and the 2026-08-25 run. The
error type is not a stable key; the class name is.

### Why not ship `libmegazord.so` in the image?

`libmegazord.so` is a cross-compiled **Android** ELF binary. The host JVM
(Linux x86_64) cannot load it — the ELF platform, ABI, and dynamic linker
paths are all wrong. Building a host-native version would require a separate
appservices build target (Rust → `libmegazord.so` for Linux x86_64), which the
current tree does not configure. Until a host build target exists, the
allowlist above is the correct gate.
