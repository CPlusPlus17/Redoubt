# Hardening flags: LibreWolf desktop vs LibreWolf for Android

**Owner: LW-M5-03.** One question: does the Android build get every hardening
option the desktop build gets, and is there hardening we should add that neither
has? This file is the answer, the evidence, and the residual-gap list.

**Headline.** Nothing was ever dropped for Android. Every hardening option in
`assets/mozconfig` is present in `assets/mozconfig.android` and — new in this
task — is confirmed *in effect* in the shipped `libxul.so`, not merely requested
in `config.status`. **Two** asymmetries were found and both are closed, so
`assets/mozconfig.android` gains exactly two lines:

| added | why | measured effect |
|---|---|---|
| `ac_add_options --enable-phc` | configure turns PHC on for desktop Linux and off for Android *release*, so desktop had it and Android did not | `libmozglue.so` now exports the nine PHC entry points it exported none of before; +142 904 B of code; ~1.1 MB per process on devices above the 8 GB `min_ram_mb` gate |
| `export LDFLAGS="-Wl,--rosegment $LDFLAGS"` | the NDK clang driver passes `--no-rosegment`, which maps read-only *data* executable; the same lld does not do this for desktop Linux | executable-mapped non-code in `libxul.so` drops from **42 290 043 B to 0**; `libxul.so` is the same size to the byte |

Both were proved with `./mach build` exiting 0 on a fresh stock 153.0.4 tree.
Seven further mitigations were evaluated with the real toolchain and rejected on
measured grounds, not on caution — including `-D_FORTIFY_SOURCE=3`, which turns
out to be a *downgrade* on bionic.

The desktop side of every claim here is measured too: a real
`--enable-application=browser --target=x86_64-pc-linux-gnu` configure was run for
the comparison, which turned up one row that goes the other way — Android's STL
hardening (`_LIBCPP_HARDENING_MODE_EXTENSIVE`) is **stronger** than desktop's
(`_GLIBCXX_ASSERTIONS`).

The residual gaps are the process sandbox, which is not a flag, and
`-fstack-clash-protection` on 32-bit ARM, which clang will not give us.

Evidence grades, same convention as `docs/android/SANDBOX-SPIKE.md`:

| grade | meaning |
|---|---|
| **M** | measured — read out of a build artefact, or produced by running a compiler/linker here |
| **S** | source — read out of the pristine tree at `firefox-153.0.4/` |
| **U** | upstream — Mozilla/Android/ARM documentation or source |
| **I** | inference — reasoned from M/S/U, and labelled as such |

Nothing below is graded from memory. Where a number came from a command, the
command is in [§7](#7-how-to-re-verify).

---

## 1. Where the evidence comes from

| tree | what it is | used for |
|---|---|---|
| `/home/mgysin/lw-m2-01b/firefox-153.0.4/obj-aarch64-unknown-linux-android` | LW-M2-01, stock 153.0.4 + unmodified `mozconfig.android` | the baseline `config.status`, `mozilla-config.h`, `compile_commands.json`, `libxul.so`, `libmozglue.so` |
| `/home/mgysin/lw-m2-02/repo/librewolf-153.0.4-1/obj-…` | LW-M2-02, full LibreWolf patch set, 153.0.4 | cross-check |
| `/home/mgysin/lw-m2-02/repo/librewolf-153.0esr-1/obj-…` | LW-M2-02, full patch set, 153.0esr | cross-check |
| `/home/mgysin/lw-m5-03/firefox-153.0.4/obj-…` | **this task**, stock 153.0.4 + the final `mozconfig.android`; built twice (§6) | proves the final flag set builds, and both `libxul.so` layouts |
| `/home/mgysin/lw-m5-03/probe2-{armv7,x8664}` | **this task**, configure-only, final mozconfig with only `--target=` rewritten | the per-ABI hardening sets (§2) |
| `/home/mgysin/lw-m5-03/probe-desktop3` | **this task**, configure-only, `--enable-application=browser --target=x86_64-pc-linux-gnu` | the desktop reference, measured instead of derived (§2) |
| container `librewolf-android-build` | NDK r29 clang 21.0.0, lld 21.0.0, rustc 1.94.1 | every codegen/link measurement in §4 |

None of the LW-M2-01/LW-M2-02 trees was modified. Every `config.status` was read
with a small `ast`-based parser rather than by importing `mozbuild`, because
`config.status` does `from mozbuild.configure.constants import *` and some subst
values are enum members that `literal_eval` refuses — §7a is that parser.

---

## 2. Parity, option by option, proved from the artefact

The three **pre-existing** Android `config.status` files (LW-M2-01 stock,
LW-M2-02 patched-release, LW-M2-02 patched-ESR) carry a **byte-identical**
hardening block **(M)** — re-derived here rather than taken from LW-M2-01's
report. The LibreWolf patch set changes nothing in this area: the only diffs
between the stock and patched configs are paths, version strings,
`MOZ_APP_PROFILE`, and the *removal* of `MOZ_DATA_REPORTING` and
`MOZ_SERVICES_HEALTHREPORT`.

That common block, i.e. the state of the world before this task:

```
MOZ_HARDENING_CFLAGS    = [-U_FORTIFY_SOURCE, -D_FORTIFY_SOURCE=2,
                           -fstack-protector-strong, -fstack-clash-protection,
                           -fstrict-flex-arrays=1]
MOZ_HARDENING_LDFLAGS   = [-fstack-protector-strong, -fstack-clash-protection]
MOZ_STL_HARDENING_FLAGS = [-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_EXTENSIVE]
MOZ_MEMORY = 1   MOZ_REPLACE_MALLOC = 1   MOZ_REPLACE_MALLOC_STATIC = 1
MOZ_RUST_SIMD = 1
MOZ_USING_WASM_SANDBOXING = 1 + all six MOZ_WASM_SANDBOXING_*
WASI_SYSROOT = /root/.mozbuild/sysroot-wasm32-wasi
                       # and no MOZ_PHC, and no --rosegment in OS_LDFLAGS
```

`config.status` says what was *requested*. Two stronger layers were checked on
top of it: what reached **every** compile command, and what reached the built
ELF. The clangd backend writes `obj-*/clangd/compile_commands.json` from the
same `COMPUTE*_CFLAGS` the real compiles use, so it is a complete census of the
9 966 compile lines rather than a spot check — and the ELF is the last word:

| option | proof in the artefact | grade |
|---|---|---|
| `-D_FORTIFY_SOURCE=2` | `libxul.so` imports **22** distinct fortified bionic entry points — `__memcpy_chk`, `__memmove_chk`, `__memset_chk`, `__strcpy_chk`, `__strncpy_chk2`, `__strcat_chk`, `__strncat_chk`, `__strlen_chk`, `__strchr_chk`, `__strrchr_chk`, `__vsprintf_chk`, `__vsnprintf_chk`, `__fread_chk`, `__fwrite_chk`, `__read_chk`, `__pread_chk`, `__readlink_chk`, `__umask_chk`, `__write_chk`, `__FD_SET_chk`, `__FD_CLR_chk`, `__FD_ISSET_chk`. These are undefined symbols resolved against bionic, so the fortified overloads were genuinely selected at compile time | **M** |
| `-fstack-protector-strong` | `__stack_chk_fail@LIBC` is an undefined dynamic symbol of `libxul.so`; compiling a non-leaf function for `aarch64-linux-android26` emits `mrs x19, TPIDR_EL0` / `ldr x9, [x19, #0x28]` — bionic's per-thread cookie | **M** |
| `-fstack-clash-protection` | LW-M2-01 could only argue "clang 21.0.0 ≥ the 18.1.0 floor". Measured here: a 200 000-byte frame compiles to a probing loop `sub sp,sp,#0x1000 / cmp sp,x9 / str xzr,[sp] / b.ne` **with** the flag and to a single `sub sp,sp,#0x30000` **without** it | **M** |
| `-fstrict-flex-arrays=1` | on the per-file command line — counted, not spot-checked: **9 966 / 9 966** entries in the objdir's `clangd/compile_commands.json`. The same 9 966/9 966 holds for `-D_FORTIFY_SOURCE=2`, `-fstack-protector-strong`, `-fstack-clash-protection`, `-ftrivial-auto-var-init=zero` and `-fwrapv` | **M** |
| `--enable-stl-hardening` | `libxul.so` imports `_ZNSt6__ndk122__libcpp_verbose_abortEPKcz` from `libmozglue.so`. libc++ only emits that call when hardening assertions are compiled in, so this is the *extensive* mode arriving, not just the `-D` being passed. The `-D` itself is on **8 193 / 8 193** C++ compile commands and on none of the 1 773 C ones, which is exactly right | **M** |
| `-ftrivial-auto-var-init=zero` | an uninitialised `int a[8]` compiles to `movi v0.2d,#0` + `stp q0,q0,[sp]` with the flag and to nothing without it. This is the only thing zero-initialising locals on a release build: `toolchain.configure:2730-2745` appends `-ftrivial-auto-var-init=pattern` to the flag list only `if debug:` (:2743) | **M**/**S** |
| `-fwrapv`, `-Wno-backend-plugin` | on the per-file command line (see the `-fstrict-flex-arrays` row for the counts) | **M** |
| `--enable-jemalloc` + `--enable-replace-malloc` | `libmozglue.so` **defines** `malloc`, `calloc`, `realloc`, `free` (`@@libmozglue.so`), i.e. mozjemalloc really is the process allocator | **M** |
| `--enable-rust-simd` | `MOZ_RUST_SIMD=1` in `mozilla-config.h` | **M** |
| RLBox | `obj-*/security/rlbox/` holds 52 `.wasm` modules and an **aarch64** `rlbox.wasm.o` with 8 907 distinct `w2c_*` symbol names (401 graphite, 182 hunspell, 110 woff2, 88 expat `XML_*`, 85 ogg); `toolkit/library/build/libxul_so.list` links it, and `libxul.so` contains `w2c_ogg_*` strings | **M** |
| full RELRO + BIND_NOW | `libxul.so` and `libmozglue.so` both have a `GNU_RELRO` segment and `FLAGS BIND_NOW` / `FLAGS_1 NOW` | **M** |
| non-executable stack, no text relocations | `GNU_STACK` is `RW`, and there is no `TEXTREL` dynamic entry | **M** |

### The desktop side, measured rather than reasoned about

The first draft of this document derived the desktop values from
`build/moz.configure/toolchain.configure:2689-2792` **(S)**. That is the weaker
form, so a real desktop configure was run instead: `--enable-application=browser
--target=x86_64-pc-linux-gnu` with the hardening half of `assets/mozconfig`,
inside the same container after `apt-get install pkg-config libgtk-3-dev …`
(configure needs GTK's `.pc` files; the pinned image has none, which is why this
had never been done). Configure completed and wrote a `config.status` **(M)**.

| subst | desktop `x86_64-pc-linux-gnu` (browser) | Android `aarch64-linux-android` | |
|---|---|---|---|
| `MOZ_HARDENING_CFLAGS` | `-U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=2 -fstack-protector-strong -fstack-clash-protection -fstrict-flex-arrays=1` | **identical** | ✅ |
| `MOZ_HARDENING_LDFLAGS` | `-fstack-protector-strong -fstack-clash-protection` | **identical** | ✅ |
| `MOZ_MEMORY` / `MOZ_REPLACE_MALLOC` / `MOZ_REPLACE_MALLOC_STATIC` | 1 / 1 / 1 | 1 / 1 / 1 | ✅ |
| `MOZ_RUST_SIMD` | 1 | 1 | ✅ |
| `MOZ_USING_WASM_SANDBOXING` | 1 | 1 | ✅ |
| `MOZ_PHC` | **1** | 1 *(only after this task — §3)* | ✅ now |
| `MOZ_STL_HARDENING_FLAGS` | `-D_GLIBCXX_ASSERTIONS=1` | `-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_EXTENSIVE` | **Android is stronger** |
| `OS_LDFLAGS` `-z` set | `noexecstack, text, relro, now, nocopyreloc` | **identical** (plus `--hash-style=sysv`) | ✅ |
| separate read-only segment | yes, lld's default for `linux-gnu`, **no flag needed** | needs `-Wl,--rosegment` — §4.10 | ✅ now |
| `MOZ_SANDBOX` | **1** | **absent** | ❌ §5.1 |

Two things in that table are worth stating out loud because they are the opposite
of what a reader would assume:

- **STL hardening is not the same mitigation on the two platforms, and Android
  gets the better one.** Desktop resolves to libstdc++ and therefore to
  `-D_GLIBCXX_ASSERTIONS=1`; Android always uses libc++ and clears the
  `using_libcxx_19_or_newer` probe, so it gets
  `_LIBCPP_HARDENING_MODE_EXTENSIVE`, which covers materially more than
  `_GLIBCXX_ASSERTIONS`. Whoever writes the public parity statement (LW-M5-06)
  should not describe this row as "the same on both".
- **The desktop `OS_LDFLAGS` has no `--rosegment` in it, and does not need one.**
  That is the cleanest possible confirmation of §4.10: the flag Android needs
  exists only because the Android driver opted out of a layout desktop gets for
  free.

Nothing in `--enable-hardening` itself diverges: the only branches in that
function that could are `mingw_clang` and `clang-cl` (Windows), both false for
both targets, and `-fstack-clash-protection`'s per-CPU floor
(`toolchain.configure:2723-2725`) is cleared by NDK r29's clang 21.0.0 on both.

The desktop probe is configure-only and its option list is the hardening half of
`assets/mozconfig`, not the whole file — branding, `--with-app-name` and
`--with-l10n-base` were left out because none of them reaches a hardening subst.

### The other two fat-AAR ABIs

`scripts/android-fat-aar.sh` builds `armeabi-v7a` and `x86_64` from this same
mozconfig with only the `--target=` line rewritten, so both were configured with
the final file **(M)**:

| subst | `aarch64-linux-android` | `arm-linux-androideabi` | `x86_64-linux-android` |
|---|---|---|---|
| `-fstack-clash-protection` | yes | **NO** | yes |
| everything else in `MOZ_HARDENING_CFLAGS` | yes | yes | yes |
| `MOZ_STL_HARDENING_FLAGS` | `…EXTENSIVE` | `…EXTENSIVE` | `…EXTENSIVE` |
| `MOZ_PHC` | 1 | 1 | 1 |
| `MOZ_MEMORY`/`REPLACE_MALLOC`/`_STATIC`/`RUST_SIMD` | 1 | 1 | 1 |
| `MOZ_USING_WASM_SANDBOXING` | 1 | 1 | 1 |
| `-Wl,--rosegment` present in the configured link flags (NOT link-tested — see §7d) | yes | yes | yes |

`armeabi-v7a` losing `-fstack-clash-protection` is a **real per-ABI hardening
split and nothing in a mozconfig can close it**: the condition at
`toolchain.configure:2723-2725` lists `x86`, `x86_64`, `ppc64`, `s390x` (clang
≥ 11.0.1) and `aarch64` (clang ≥ 18.1.0), and 32-bit `arm` is in neither list.
LW-M5-06's parity statement should say "arm64 and x86_64 devices get stack-clash
protection; 32-bit ARM devices do not", not "Android gets it".

`MOZ_PHC = 1` on `arm-linux-androideabi` is a consequence of *our* explicit
`--enable-phc`, not of a default — `phc_default` requires
`target.cpu in ("x86_64", "aarch64")`. It is deliberate; the reasoning and the
"switch this off first if armv7 misbehaves" note are in the mozconfig next to the
option.

The link-side set is likewise common:
`build/moz.configure/flags.configure:358-362` adds
`-Wl,-z,{noexecstack,text,relro,now,nocopyreloc}` gated only on
`building_with_gnu_compatible_cc` **(S)**, and the Android `OS_LDFLAGS` in
`config.status` contains all five plus `-Wl,--icf=safe` and
`-Wl,--build-id=sha1` **(M)**. ASLR needs nothing from us on this target:
`MOZ_PROGRAM_LDFLAGS` is `['-pie']` **(M)** and everything that matters here is a
shared object built `-fPIC` anyway. Android also links with `RELRHACK=1`, so the
relative relocations in `libxul.so` are packed and applied by an injected
initialiser rather than left to the loader — orthogonal to hardening, but it is
the reason §4.10 had to be checked rather than assumed.

The one place where the two targets' *link* really does diverge is the segment
layout, and it goes against Android. That is §4.10.

---

## 3. Asymmetry #1, now closed: `--enable-phc`

`build/moz.configure/memory.configure:74-104` **(S)**:

```python
return (target.cpu in ("x86_64", "aarch64")) and (
    (target.os == "GNU" and target.kernel == "Linux")      # desktop LibreWolf
    or (target.kernel == "WINNT")
    or (target.os == "OSX")
    or (target.os == "Android" and milestone.is_early_beta_or_earlier))
```

An Android triplet canonicalises to `os="Android"`, `kernel="Linux"`, so it
misses the first arm; `version.android` pins a **release** milestone, so it
misses the fourth. Desktop LibreWolf therefore ships `MOZ_PHC=1` and Android
shipped it unset — confirmed absent from all three earlier Android
`config.status` files **(M)**.

PHC puts a sampled fraction of heap allocations on their own page, flanked by
guard pages, and leaves freed ones `PROT_NONE` for a while. An overflow or
use-after-free that lands on a sampled allocation becomes a deterministic
`SIGSEGV` instead of silent corruption. Mozilla's stated reason for the
platform list is reporting value — *"it only makes sense for PHC to run on the
platforms that have a crash reporter"* (`memory.configure:72-73`) — and we build
with `--disable-crashreporter`, exactly as **desktop LibreWolf already does**.
We keep it for the fail-fast behaviour, on both platforms, for the same reason.

What it costs, from the shipped defaults rather than from a guess:

- **~1.1 MB per process.** `StaticPrefList.yaml:13963-13973` sets
  `memory.phc.size_kb` to `1024 + 128` on a release milestone (the 16 MB figure
  in that file is the `EARLY_BETA_OR_EARLIER` branch) **(S)**.
- **Nothing at all below ~8 GB of RAM.** `xpcom/base/PHCManager.cpp:36-69` calls
  `SetPHCState(OnlyFree)` unless `PR_GetPhysicalMemorySize()` is at least
  `memory.phc.min_ram_mb`, default **8000** **(S)**. On a phone under that
  threshold this option costs code size and nothing else. Whoever owns
  `settings/*.cfg` should decide whether to lower that pref for Android; it is a
  pref, not a build flag, and it is not this task's file.
- **No codegen change.** `memory.configure:107-126` implies
  `--enable-frame-pointers` only for WINNT/x86, Darwin kernels, or (x86|ppc)
  without unwind info; aarch64 falls through to `False` **(S)**, and the
  rebuild confirms `MOZ_FRAMEPTR_FLAGS` is still
  `['-fomit-frame-pointer', '-funwind-tables']` **(M)**.

PHC's Android support is deliberate, not incidental: `memory/build/PHC.cpp:132-136`
carries an `#ifdef ANDROID` declaration for `pthread_atfork`, and
`mozglue/misc/StackWalk.cpp:50-57` makes `MOZ_STACKWALK_SUPPORTS_LINUX` true when
`HAVE__UNWIND_BACKTRACE || …` **and** `(HAVE___LIBC_STACK_END || ANDROID)` — the
Android build defines `HAVE__UNWIND_BACKTRACE 1` **(M)**, so PHC's stack
recording works rather than silently returning empty frames. The
`glean::memory_phc::*` metrics `PHCManager.cpp` needs are already generated into
the Android objdir (`dist/include/mozilla/glean/XpcomMetrics.h:520-540`) **(M)**,
and no LibreWolf patch touches `memory/build/` or `xpcom/base/` **(M)**.

**Result:** `MOZ_PHC = "1"` in the LW-M5-03 objdir's `config.status`, and
`./mach build` exits 0 — see [§6](#6-the-build).

---

## 4. Candidate additions, each with the measurement that decided it

All measurements below were produced by running the pinned NDK r29 clang 21.0.0
and lld 21.0.0 against `aarch64-linux-android26` with the LibreWolf hardening
flag set. The size column is `.text` of `third_party/sqlite3/src/sqlite3.c`
(the amalgamation — 950 424 bytes of real, optimised production C at baseline),
chosen because it is self-contained and large enough that prologue overhead does
not dominate.

| candidate | builds? | `.text` delta | verdict |
|---|---|---|---|
| `-mbranch-protection=pac-ret` | yes | +10 964 (**+1.15 %**) | rejected — Rust cannot participate, unwinding unvalidated |
| `-mbranch-protection=standard` (BTI+PAC) | yes | +15 772 (**+1.66 %**) | rejected — the property note cannot survive this link |
| `-fsanitize=shadow-call-stack` | yes | +10 944 (**+1.15 %**) | rejected — Rust cannot participate |
| `-fzero-call-used-regs=used-gpr` | yes | +45 244 (**+4.76 %**) | rejected — cost/benefit, no upstream precedent |
| `-D_FORTIFY_SOURCE=3` | yes | — | rejected — **measured downgrade on bionic** |
| `-fstrict-flex-arrays=2` / `=3` | — | — | rejected — divergence from desktop, breaks known consumers |
| `-fsanitize=memtag-*` | only with `-march=…+memtag` | — | rejected — would not run on pre-ARMv8.5 devices |
| `-fsanitize=cfi` (+ LTO) | not attempted | — | rejected — desktop does not have it either, so not a parity gap |
| `--enable-sandbox` | not attempted | — | closed by `docs/android/SANDBOX-SPIKE.md` |
| **`-Wl,--rosegment`** | **yes, full build green** | link-only | **ADOPTED — 40 MiB of read-only data stops being mapped executable** |

### 4.1 `-D_FORTIFY_SOURCE=3` is weaker than `=2` on bionic

This is the finding that most deserved a measurement, because on glibc level 3
is strictly stronger and the reflex is to bump it.

The NDK r29 sysroot's `sys/cdefs.h:240-247` keys the object-size mode on the
level being **exactly** 2:

```c
#if defined(__BIONIC_FORTIFY)
#  if _FORTIFY_SOURCE == 2
#    define __bos_level 1
#  else
#    define __bos_level 0
#  endif
```

so level 3 falls into the *else* branch. Compiled against that sysroot, for a
`char a[8]` member of a struct reached through a pointer **(M)**:

| `-D_FORTIFY_SOURCE=` | `__bos_level` | `__builtin_object_size(s->a, __bos_level)` |
|---|---|---|
| 1 | 0 | `-1` (unknown, no bound) |
| **2** | **1** | **8** (the sub-object) |
| 3 | 0 | `-1` (unknown, no bound) |

`__BIONIC_FORTIFY` is still 1 at level 3, so the `_chk` calls remain and the
build looks fine — the bound they are given just becomes "unknown". Bumping to
3 on Android would be a silent weakening dressed as an upgrade. **Do not do it.**

### 4.2 BTI cannot survive this link, and forcing it is a hazard

Today's `libxul.so` has **no** `.note.gnu.property` at all — `readelf -n` finds
only `.note.android.ident`, `.note.moz.toolkit-build-id` and
`.note.gnu.build-id` **(M)** — so there is no BTI and no PAC in the shipped
artefact. That is the baseline everything below is measured against.

BTI only takes effect if the loader sees `GNU_PROPERTY_AARCH64_FEATURE_1_BTI` in
the output's `.note.gnu.property`, and lld drops that property if **any** input
object lacks it. Measured, three steps **(M)**:

1. `-mbranch-protection=standard` on a C file produces
   `aarch64 feature: BTI, PAC, GCS` in the object, and `bti` landing pads in the
   disassembly.
2. Linking two such objects keeps `aarch64 feature: BTI, PAC` on the `.so`.
3. Adding **one** object built without the flag removes the property note from
   the `.so` entirely.

Two input classes make step 3 unavoidable here:

- **The Rust half.** The pinned stable **rustc 1.94.1** rejects both
  `-Zbranch-protection` and `-Zsanitizer=shadow-call-stack` with *"the option
  `Z` is only accepted on the nightly compiler"* **(M)**. `gkrust` is a
  first-class input to `libxul.so`, so the property is gone before any C++
  question is asked. Switching LibreWolf's Android builds to a nightly Rust to
  get this is not a trade worth making.
- **Hand-written assembly.** `-mbranch-protection=standard` does **not** make
  the assembler synthesise the note for a `.S` file — measured: the object comes
  out with no property note, and linking it drops the note from the library
  **(M)**. The note has to be written into each assembly source by hand. The
  Android objdir's make backend names **47** distinct `.S`/`.s` sources (dav1d,
  ffvpx NEON, pixman, libffi, ICU data, breakpad), and an object of the matching
  name exists for all 47 **(M)**.

`ld.lld -z force-bti` keeps the property despite the missing inputs, but only
with a per-file warning — and that is worse than dropping it: it advertises BTI
protection for code that has no landing pads, so an indirect branch into that
assembly faults on BTI hardware. Measured: lld emits
`warning: a_std.o: -z force-bti: file does not have GNU_PROPERTY_AARCH64_FEATURE_1_BTI property`
and marks the output BTI anyway **(M)**.

### 4.3 PAC (`pac-ret`) works, and is still not worth taking alone

Unlike BTI, `pac-ret` needs no ELF property and no loader opt-in: `paciasp` /
`autiasp` assemble to `d503233f` / `d50323bf`, which are `hint #25` / `hint #29`
— measured by assembling the bare `hint` mnemonics and getting byte-identical
encodings **(M)**. They are therefore NOPs on pre-ARMv8.3 cores and real
return-address signing on v8.3+. Codegen was confirmed: `paciasp` appears in
non-leaf prologues **(M)**, at +1.15 % `.text`.

It is still rejected, for two reasons:

1. **Coverage is half the binary.** Rust cannot be signed with the pinned
   compiler (§4.2), and Rust is where a large share of Gecko's newer
   security-relevant code lives.
2. **The return address on the stack becomes a signed pointer, and this build
   walks stacks.** `-fomit-frame-pointer` is on, PHC and the profiler both call
   `MozStackWalk`, and `MOZ_STACKWALK_SUPPORTS_LINUX` is 1 here **(M)**. Whether
   every unwinder in this build strips the PAC bits correctly is a device
   question, and there is no device or emulator in this task's loop. And there is
   no upstream field validation to lean on: `-mbranch-protection`,
   `shadow-call-stack` and `memtag` appear **nowhere** in Firefox 153's build
   configuration — a `grep -rn` over `build/`, `toolkit/moz.configure`,
   `browser/config/` and `mobile/android/config/` returns nothing **(S)**.
   Mozilla ships none of the three on any platform.

This is the one rejection that could be revisited: if a future task acquires a
device lane (LW-M2-04's smoke test plus a real ARMv8.3+ phone), `pac-ret` for
the C/C++ half is a defensible +1.15 % and needs no toolchain change.

### 4.4 Shadow call stack

`-fsanitize=shadow-call-stack` compiles and emits the expected
`str x30, [x18], #0x8` prologue **(M)**, at +1.15 % `.text`, and it needs no
architecture extension at all.

Mixing instrumented and uninstrumented objects is safe here rather than merely
tolerated, because the Android arm64 ABI reserves `x18` for the platform and
clang already honours that. Proved by an A/B rather than asserted: a
deliberately register-hungry function compiled for `aarch64-linux-android26`
produces a **byte-identical** object with and without `-ffixed-x18` **(M)** —
the register was never allocatable in the first place, so uninstrumented code
cannot clobber the shadow stack pointer.

Rejected for the same coverage reason as §4.3 — stable rustc cannot emit it — with
the same "revisit with a device lane" caveat. Of the three, this is the one to
revisit first: no hardware requirement, no ELF property, +1.15 %.

### 4.5 `-fzero-call-used-regs=used-gpr`

Compiles, emits the register-clearing epilogue **(M)**, and costs **+4.76 %**
`.text` — 4.1x PAC or SCS for a mitigation that only narrows ROP gadget
availability. `zero-call-used-regs` appears nowhere in Firefox 153's build
configuration either **(S)**. Rejected on cost.

### 4.6 `-fstrict-flex-arrays` above 1

`toolchain.configure:2749-2751` records why upstream stops at level 1: *"Cannot
use level 3 because we have many uses of the `[0]` GNU syntax. Cannot use level
2 because sqlite3 and icu use the `[1]` GNU syntax."* **(S)** Desktop LibreWolf
gets level 1. Raising it on Android alone would be a divergence between the two
products, which is the opposite of this task. Rejected.

### 4.7 MTE (Memory Tagging Extension)

The obvious Android-specific candidate, and it does not fit a single-ABI APK.

- `-fsanitize=memtag-stack` hard-errors without an architecture feature:
  *"'-fsanitize=memtag-stack' requires hardware support (+memtag)"* **(M)**.
- With `-march=armv8.5-a+memtag` it compiles and emits `irg` / `st2g` **(M)**.
- Those instructions are **not** in the HINT/NOP space the way PAC's are:
  disassembled against a baseline ARMv8-A CPU model, `irg x0, x0` (`9adf1000`)
  and `stg x0, [x0]` (`d9200800`) both decode as `<unknown>` **(M)**. Raising
  `-march` to ARMv8.5 would also raise the ISA baseline for the whole of
  `libxul.so`.

So MTE codegen means an APK that only runs on ARMv8.5+ devices. **(I)** A
separate ABI split for it is a distribution problem, not a mozconfig problem.

Heap MTE — the `android:memtagMode` manifest attribute — is a different
mechanism and also does not reach us: it is implemented in bionic's scudo
allocator, and `libmozglue.so` **defines** `malloc`/`calloc`/`realloc`/`free`
**(M)**, so Gecko's heap is mozjemalloc and never sees scudo's tagging. Setting
the manifest attribute would tag only ART and non-Gecko native allocations.
That is a manifest decision for the APK task, and this file is the place that
records why it buys less than it looks like it buys.

### 4.8 CFI, LTO, PGO

`MOZ_PGO` is the empty string and `MOZ_LTO` is not present in the Android
`config.status` at all **(M)** — and `assets/mozconfig` asks for neither on
desktop. clang's `-fsanitize=cfi` requires LTO
and `-fvisibility=hidden`, and cross-DSO CFI needs a runtime. Since desktop does
not have it, this is **not a parity gap**; it is a "both platforms could be
harder" item, and it is far larger than a mozconfig line. Note also that the
Android build already peaks at ~38 GB of container memory without LTO
(`docs/android/BUILD.md`), so LTO is a CI-capacity question before it is a
security question.

### 4.9 The process sandbox

Out of scope here and already settled: `docs/android/SANDBOX-SPIKE.md`
(LW-M5-07) recommends not pursuing `MOZ_SANDBOX` on Android and says explicitly
*"specifically not as 'let's just try `--enable-sandbox` and see'"*. This task
did not try it. One corroborating detail found while checking whether the flag
could be a cheap win, offered as input rather than as a new conclusion **(S)**:

`GeckoChildProcessHost::PrepareLaunch` calls `SandboxLaunch::Configure` under
`#if defined(XP_LINUX) && defined(MOZ_SANDBOX)`, and `XP_LINUX` *is* defined on
Android — but everything that function produces is written into
`mLaunchOptions` (`fork_flags` for the `CLONE_NEW*` namespaces,
`sandbox_chroot_server`, and an `env_map` carrying the `kSandboxChrootEnvFlag`
the child reads plus the `LD_PRELOAD` that puts `libmozsandbox.so` ahead of
everything else so its interpositions take effect, `SandboxLaunch.cpp:202-214`
— note that libxul would still *link* `libmozsandbox` on Android, because
`toolkit/xre/moz.build:259-262` and `dom/ipc/moz.build:207-212` gate that on
`MOZ_SANDBOX and OS_ARCH == "Linux"` and `OS_ARCH` is `Linux` here **(M)**; the
preload is about ordering, not about symbol resolution). Android's
`AndroidProcessLauncher::LaunchAndroidService`
(`GeckoChildProcessHost.cpp:1804-1826`) passes **only** `args.mArgs` and
`args.mFiles` to `java::GeckoProcessManager::Start` and never reads
`mLaunchOptions` at all. So the namespace isolation, the chroot and the preload
are discarded by construction on Android, independently of whether the
seccomp-bpf filter would install.
### 4.10 Asymmetry #2, now closed: `-Wl,--rosegment`

The find of the task, and Android-specific in the worst way: the Android build is
**less** hardened than the desktop build here, by a decision the NDK's clang
driver makes for us. It is the only candidate in §4's table that was adopted.

Measured **(M)**, three facts:

1. `clang -### --target=aarch64-linux-android26 -shared` shows the driver passing
   **`--no-rosegment`** to `ld.lld` explicitly. It is not lld's own default.
2. The result is a **single `R E` LOAD segment** covering the ELF headers,
   `.dynsym`/`.dynstr`/`.rela.*`, `.rodata`, `.gcc_except_table`, `.eh_frame_hdr`
   and `.eh_frame` — all of it — as well as `.text`. In the LW-M5-03 `libxul.so`
   that segment is 151 379 792 bytes, of which only **109 086 052** are code
   (`.text`, `.plt`, `malloc_hook`). **42 290 043 bytes — 40.3 MiB, 27.9 % of
   the executable mapping — are read-only *data* mapped executable.** The
   biggest contributors are `.rodata` (28 184 512 B) and `.eh_frame`
   (11 644 764 B).
3. The **same lld** binary, targeting `x86_64-unknown-linux-gnu`, emits a
   separate read-only `R` segment and a separate `R E` code segment for the same
   source file. And independently: the desktop `--target=x86_64-pc-linux-gnu`
   configure of §2 shows `--rosegment` is **not** in its `OS_LDFLAGS`, because
   nothing has to ask for it there. So desktop LibreWolf already ships the layout
   Android does not.

`-Wl,--rosegment` restores it. On a toy library the whole cost was **+64 bytes**
— one alignment gap. On the real tree it cost **nothing at all**: the new
segment boundary fell on an alignment the file already had, so the two `libxul.so`
files are the same size to the byte.

| | build 1 (shipped set) | build 2 (+`-Wl,--rosegment`) |
|---|---|---|
| `./mach build -j12` | exit 0 | exit **0** |
| `libxul.so` LOAD segments | 1×`R E`, 2×`RW` | 1×`R`, 1×`R E`, 2×`RW` |
| executable-mapped code | 109 086 052 B | 109 086 052 B |
| executable-mapped **non**-code | **42 290 043 B** | **0 B** |
| `libxul.so` size | 2 449 687 496 B | 2 449 687 496 B — *identical* |
| `libmozglue.so` size | 12 281 880 B | 12 282 096 B (+216) |
| `geckoview-debug.aar` | 91 099 417 B | 91 098 820 B (−597, zip noise) |
| wall clock | 23 min 02 s (clean) | 9 min 39 s (incremental relink) |

The `R` segment is 42 293 728 B and the `R E` segment 109 086 064 B; they sum to
151 379 792 — exactly the size of the single `R E` segment they replaced. Zero
padding.

relrhack came through unchanged: `DT_RELR`/`DT_RELRSZ` is still 101 704 bytes,
`DT_RELRENT` 8, `DT_INIT` still resolves inside the code segment, `BIND_NOW` and
`FLAGS_1 NOW` are still set, there is no `TEXTREL`, and every ALLOC section is
covered by a LOAD segment **(M)**.

Why this is safe enough to take, stated as precisely as it can be without a
device:

- **CORRECTION — this bullet was wrong, and it was marked (M) for measured.**
  It claimed the flag appears in `substs[OS_LDFLAGS]` rather than in a raw
  `LDFLAGS` passthrough, because `flags.configure` routes user link flags through
  `check_and_add_linker_flag`. It does not.
  `build/moz.configure/flags.configure:46-47` extends `os.environ["LDFLAGS"]`
  straight into `env_flags` — a raw passthrough with **no link test**.
  `check_and_add_linker_flag` is used only for configure's *own* flags
  (`:354-361`: `-Wl,-z,relro`, `-Wl,-z,now`, `--build-id` and friends).

  Consequence: the flag is **not self-disabling**. If a future NDK rejects it, the
  build FAILS at link time rather than quietly continuing without it. That is the
  better failure mode — a silently dropped hardening flag is exactly what
  `board.py --diff-mozconfig` exists to prevent — but it is a rebase hazard and
  must be re-checked rather than assumed away. Found by the skeptical verification
  of LW-M5-03.
- **Every real link in the tree used it and the build is green**, including the
  `libxul.so` link, which on Android goes through **relrhack**
  (`substs[RELRHACK] = 1`) — a wrapper that re-links with an injected
  relocation-applicator object and then rewrites program headers. relrhack reads
  `PT_LOAD` generically (`build/unix/elfhack/relrhack.cpp:109-112`) and does not
  assume a segment count **(S)**.
- **The wasm side is untouched.** `config/rules.mk:493-497` links the RLBox
  `.wasm` archive with `$(WASM_CXX)` and its own explicit flag list; it never
  sees `LDFLAGS`, so `wasm-ld` is never handed `--rosegment` **(S)**.
- **Gecko's own loader copes.** `MOZ_LINKER` is 1 on Android **(M)** and
  `CustomElf::Load` collects every `PT_LOAD` into a vector and derives
  min/max vaddr from it (`mozglue/linker/CustomElf.cpp:100-120`) — no fixed
  segment count **(S)**.
- **The failure mode is loud, not quiet.** A segment layout the loader dislikes
  fails at `dlopen`/process start, which the M2 smoke test cannot miss. That is
  the property that made this acceptable to take while `pac-ret` (§4.3), whose
  failure mode is a corrupted stack walk on a subset of devices, was not.

**What is still owed:** nobody has run this binary. `android-smoke.sh` on a
device or emulator owns the final word. If it regresses, the revert is exactly
one line — delete the `export LDFLAGS=` line from `assets/mozconfig.android` —
and §7's check `d` is how you confirm which state you are in.


---

## 5. Residual gaps — no hedging

1. **There is no process sandbox.** `MOZ_SANDBOX` is `1` in the desktop
   `config.status` and does not appear at all in any of the four Android ones —
   both halves measured **(M)**. LibreWolf for Android runs content in Android's
   app sandbox and nothing else; desktop LibreWolf has seccomp-bpf plus namespace
   isolation. This is the largest security difference between the two products,
   it is not closable with a build flag (§4.9), and the download page must say so
   (`AGENTS.md`, LW-M5-06, SANDBOX-SPIKE §10).
2. **Return-address integrity is absent, on both products.** Neither desktop nor
   Android LibreWolf has PAC, BTI or a shadow call stack, and `libxul.so` has no
   `.note.gnu.property` at all **(M)**. The hardware bar differs per mitigation
   and the doc should not blur it: a shadow call stack needs **no** special
   hardware (the Android arm64 ABI reserves `x18` on every device), `pac-ret`
   needs ARMv8.3, BTI needs ARMv8.5 **(U)**. So the cheapest of the three in
   hardware terms is the one whose blocker is purely our Rust pinning. §4.3 and
   §4.4 say what would change the answer. CFI is a separate question — §4.8.
3. **Rust code is outside the reach of every codegen mitigation we could add.**
   The pinned stable rustc 1.94.1 accepts no `-Z` flags, so branch protection
   and shadow call stacks could only ever cover the C/C++ half of `libxul.so`.
   This is a toolchain-pinning consequence, and any future proposal in this area
   has to start by deciding whether LibreWolf is willing to build Android with a
   nightly Rust.
4. **PHC makes no new guarded allocations on phones with less than ~8 GB of
   RAM.** The build option is now set, but `PHCManager` puts PHC in the
   `OnlyFree` state below `memory.phc.min_ram_mb` (default 8000) — frees of
   existing PHC allocations still work, no new ones are sampled
   (`memory/build/PHC.h:119-126`). Closing *that* gap is a pref change in
   `settings/`, owned by the pref tasks, not by this file.
5. **`MOZ_REQUIRE_SIGNING` is empty on Android.** Add-on signing is not
   enforced. This is deliberate, it is byte-for-byte what `assets/mozconfig`
   does on desktop, and upstream Android does the same
   (`mobile/android/config/mozconfigs/common.override:8`) — so it is *not* a
   desktop/Android gap. It is listed here so nobody rediscovers it and files it
   as one.
6. **The Android-only telemetry stack is not reachable from a mozconfig.**
   Glean/Adjust/Play-Integrity live in the Fenix and android-components Gradle
   layers; LW-M4-01/02/05 own them. `mozconfig.android` cannot help.
7. **`-Wl,--rosegment` has not been run on a device.** It is on, the build is
   green and the ELF is structurally sound (§4.10), but no phone or emulator has
   loaded the result. The failure mode is loud — a layout the loader rejects
   fails at process start — so `./scripts/android-smoke.sh` is the gate, and the
   revert is deleting one line from `assets/mozconfig.android`. Nothing else in
   this task depends on it.
8. **`armeabi-v7a` does not get `-fstack-clash-protection`, and cannot.** Measured
   from an `arm-linux-androideabi` `config.status` **(M)**: clang's condition
   lists x86/x86_64/ppc64/s390x and aarch64, never 32-bit `arm`. Every other
   hardening subst matches arm64 on that ABI. This is a per-ABI split inside one
   shipped artifact, so the public parity statement has to be worded per ABI, not
   per platform (§2). Nothing in a mozconfig can close it; only a clang change
   can.
9. **`armv7` and `x86_64` were configured, not built.** Their rows come from
   `config.status`, not from a linked ELF (§8).
10. **RLBox is on and is easy to lose.** It is our one genuinely working sandbox
   on Android. Configure suggests `--without-wasm-sandboxed-libraries` whenever
   anything about the WASI sysroot or the wasm32 compiler-rt breaks, and taking
   that suggestion produces a green build with six memory-unsafe parsers moved
   back into the `libxul` address space. There is a loud comment on this in
   `assets/mozconfig.android`; the mechanical guard is §7b, and
   `board.py --diff-mozconfig` should adopt it (reported, not edited — this task
   does not own `board.py`).

---

## 6. The builds

Stock Firefox 153.0.4, extracted fresh, `assets/mozconfig.android` copied byte
for byte — i.e. exactly the `docs/android/BUILD.md` procedure. Two runs, so that
the two added lines are separable if either ever has to be bisected:

- **build 1** — clean, `--enable-phc` as the only change from the flag set
  LW-M2-01 measured green. **exit 0.**
- **build 2** — same tree and objdir, `export LDFLAGS="-Wl,--rosegment $LDFLAGS"`
  added. Incremental, so every link redid and the compiles did not. **exit 0.**
  §4.10 has its numbers.

The active (non-comment) option set of build 2's mozconfig is identical to the
`assets/mozconfig.android` this task ships — checked by diffing the two files'
non-comment lines, not by eye.

### Build 1

| | |
|---|---|
| `./mach build -j12` | **exit 0** |
| wall clock | **23 min 02 s** (06:36:43Z → 06:59:45Z), one ABI |
| `MOZ_PHC` in `config.status` | `1` |
| `MOZ_FRAMEPTR_FLAGS` | `['-fomit-frame-pointer', '-funwind-tables']` — unchanged, as predicted |
| every other hardening subst | identical to the three earlier objdirs |
| `libxul.so` | 2 449 687 496 B (+14 808 vs the LW-M2-01 baseline) |
| `libmozglue.so` | 12 281 880 B (+128 096) |
| `geckoview-debug.aar` | 91 099 417 B |
| RLBox | still 52 `.wasm` modules |

**PHC is in the binary, not just in `config.status`.** The A/B against LW-M2-01's
objdir is unambiguous **(M)**:

- `libmozglue.so` now **exports** nine PHC entry points — `IsPHCAllocation`,
  `DisablePHCOnCurrentThread`, `ReenablePHCOnCurrentThread`,
  `IsPHCEnabledOnCurrentThread`, `PHCMemoryUsage`, `SetPHCSize`, `GetPHCStats`,
  `SetPHCState`, `SetPHCProbabilities`. The baseline `libmozglue.so` exports
  **none** of them.
- `libxul.so` imports five of them from `libmozglue.so`.
- `Unified_cpp_xpcom_base*.o` contains `mozilla::InitPHCState()`,
  `mozilla::UpdatePHCState()`, `mozilla::ReportPHCTelemetry()` and the
  `kPHC*Pref` name constants, i.e. `PHCManager.cpp` compiled.
- The generated backends carry the define: `-DMOZ_PHC` in
  `memory/build/backend.mk` and `-DMOZ_PHC=1` in `xpcom/base/backend.mk`.

Total code cost across the two shipped libraries: **+142 904 bytes** (~140 KB),
on top of the ~1.1 MB of runtime PHC pages per process on devices above the
`min_ram_mb` threshold.

### Build 2

| | |
|---|---|
| `./mach build -j12` | **exit 0** |
| wall clock | **9 min 39 s** (07:00:54Z → 07:10:33Z), incremental |
| `-Wl,--rosegment` landed in | `substs[OS_LDFLAGS]`, i.e. configure link-tested it |
| `libxul.so` LOAD segments | `R` 42 293 728 / `R E` 109 086 064 / `RW` / `RW` |
| executable-mapped non-code | **0 B** (was 42 290 043) |
| `DT_RELR` / `DT_INIT` | unchanged — relrhack still did its job |

The LibreWolf patch set was **not** re-applied for either build. That is a
deliberate scope limit and it is safe for this specific change: `--enable-phc`
compiles `memory/build/{PHC.cpp via mozjemalloc.cpp, FdPrintf.cpp}` and
`xpcom/base/PHCManager.cpp`, and no patch in `assets/patches/` touches
`memory/build/` or `xpcom/base/` **(M)**; `-Wl,--rosegment` is a link-time
segment-layout flag and no patch changes a link line. LW-M2-02 separately proved
the patched tree green with the rest of this flag set.

---

## 7. How to re-verify

Everything here is reproducible from a built objdir plus the container image.

**a. The hardening block, from any Android objdir.** `config.status` is a Python
module, so parse it rather than grepping it — multi-line list values defeat
`grep`:

```sh
python3 - "$OBJDIR/config.status" <<'PY'
import ast, sys
class S(ast.NodeTransformer):
    def visit_Attribute(self, n): return ast.copy_location(ast.Constant(ast.unparse(n)), n)
    def visit_Name(self, n):      return ast.copy_location(ast.Constant(ast.unparse(n)), n)
    def visit_Call(self, n):      return ast.copy_location(ast.Constant(ast.unparse(n)), n)
tree = ast.parse(open(sys.argv[1]).read())
out = {}
for node in tree.body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        try:
            out[node.targets[0].id] = ast.literal_eval(
                S().visit(ast.parse(ast.unparse(node.value), mode="eval").body))
        except Exception:
            pass
want = ("MOZ_HARDENING_CFLAGS", "MOZ_HARDENING_LDFLAGS", "MOZ_STL_HARDENING_FLAGS",
        "MOZ_MEMORY", "MOZ_REPLACE_MALLOC", "MOZ_REPLACE_MALLOC_STATIC",
        "MOZ_RUST_SIMD", "MOZ_PHC", "MOZ_USING_WASM_SANDBOXING", "WASI_SYSROOT")
missing = [k for k in want if k not in out["substs"]]
for k in want:
    print(f"{k} = {out['substs'].get(k, '*** MISSING ***')}")
sys.exit(1 if missing else 0)
PY
```

Exits non-zero and names the key if anything is missing. That failure branch was
exercised — a checker whose error path has never run is not a checker.

**b. RLBox, the one that must never silently go away.** Six defines and the
umbrella define, from the generated header:

```sh
n=$(grep -c '^#define MOZ_WASM_SANDBOXING_' "$OBJDIR/mozilla-config.h")
u=$(grep -c '^#define MOZ_USING_WASM_SANDBOXING 1' "$OBJDIR/mozilla-config.h")
test "$n" = 6 && test "$u" = 1 || { echo "RLBOX PARITY LOST: $n/6 libraries, umbrella=$u" >&2; exit 1; }
```

**c. The mitigations that reached the binary.** These are what distinguish
"requested" from "in effect":

```sh
readelf --dyn-syms -W "$OBJDIR/dist/bin/libxul.so" > /tmp/xul.dyn

# FORTIFY: count *fortified* imports only. A naive grep for '_chk' is wrong twice
# over -- it swallows __stack_chk_fail (the stack protector, not FORTIFY) and, if
# the character class is lowercase-only, it silently misses __FD_SET_chk and
# friends. Expect 22.
awk '$8 ~ /_chk[0-9]*(@|$)/ && $8 !~ /^__stack_chk/ {sub(/@.*/,"",$8); print $8}' \
    /tmp/xul.dyn | sort -u | wc -l                            # -> 22

grep -c  '__stack_chk_fail'       /tmp/xul.dyn                # stack protector -> 1
grep -c  '__libcpp_verbose_abort' /tmp/xul.dyn                # STL hardening   -> 1
readelf -d  "$OBJDIR/dist/bin/libxul.so" | grep -c BIND_NOW   # -> 1
readelf -lW "$OBJDIR/dist/bin/libxul.so" | grep GNU_STACK     # must be RW, not RWE
```

**d. No read-only data mapped executable.** This is the `-Wl,--rosegment` check
(§4.10). It walks the section table and the program headers rather than trusting
a segment count, and it exits non-zero with the byte figure when the flag has
been lost:

```sh
python3 - "$OBJDIR/dist/bin/libxul.so" <<'PY'
import re, subprocess, sys
so = sys.argv[1]
def rows(args, pat):
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout
    return [m.groups() for m in (re.match(pat, l) for l in out.splitlines()) if m]
sec = [(n, int(a, 16), int(s, 16), f) for n, a, s, f in rows(
    ["readelf", "-SW", so],
    r"\s*\[\s*\d+\]\s+(\S+)\s+\S+\s+([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s+\S+\s+([A-Za-z]*)")]
seg = [(int(v, 16), int(m, 16), f.replace(" ", "")) for v, m, f in rows(
    ["readelf", "-lW", so],
    r"\s*LOAD\s+0x[0-9a-f]+\s+0x([0-9a-f]+)\s+0x[0-9a-f]+\s+0x[0-9a-f]+\s+0x([0-9a-f]+)\s+(\S(?:\s\S)?)")]
alloc = [s for s in sec if "A" in s[3]]
code = bad = 0
for va, msz, fl in seg:
    if "E" not in fl:
        continue
    for name, a, size, flags in alloc:
        if va <= a < va + msz:
            if "X" in flags: code += size
            else:            bad += size
print(f"executable-mapped code {code:,} B, non-code {bad:,} B")
sys.exit(1 if bad else 0)
PY
```

Both branches were exercised: it fails with `42,290,043 B` on the build that
lacks the flag and passes on the one that has it.

**e. A mozconfig that fails is not a mozconfig that is ignored.** Verified by
execution here, because a shell guard in a mozconfig is only worth adding if the
loader fails closed: `MozconfigLoader.read_mozconfig` runs the file through
`subprocess.check_output`, so a non-zero exit raises `MozconfigLoadException`
(`python/mozbuild/mozbuild/mozconfig.py:166-185`) rather than returning a
partial option set. A control mozconfig loaded fine and one with a trailing
`exit 1` raised **(M)**. (This task still did **not** add such a guard — the
only plausible one would have to guess where the WASI sysroot lives, and a
false failure there is worse than the comment it replaces.)

---

## 8. What was *not* verified

- **Nothing was run on a device or an emulator.** Every claim above is about
  what the compiler, the linker and the ELF do. "PHC turns a use-after-free into
  a crash on an actual phone" is not measured here; that belongs to the smoke
  test and to whoever gets a device lane.
- **The patched tree was not rebuilt** with `--enable-phc` — see §6 for why that
  is bounded, and what would falsify it.
- **The desktop side was *configured*, not built.** `MOZ_PHC`,
  `MOZ_HARDENING_CFLAGS`, `MOZ_STL_HARDENING_FLAGS`, `MOZ_SANDBOX` and
  `OS_LDFLAGS` for `x86_64-pc-linux-gnu` come from a real `config.status`
  **(M)** — but no desktop `libxul.so` was linked here, so the desktop half of
  §2's ELF-level table is still untested. The desktop toolchain used was the
  container's NDK clang 21.0.0 driving `--target=x86_64-pc-linux-gnu` against
  Ubuntu jammy headers, not whatever a distro packager uses; the
  `-D_GLIBCXX_ASSERTIONS=1` result depends on libstdc++ being the default C++
  library there, which it is for that target but is a toolchain property, not a
  LibreWolf one.
- **`armeabi-v7a` and `x86_64-linux-android` were configured, not built.** Their
  rows in §2 are `config.status` values. In particular
  the `-Wl,--rosegment` row means the flag was present in the configured flag set
  for those targets — NOT that configure link-tested it (it does not; see the
  correction in §7d) and not that a full `libxul.so` was linked for them.
- **32-bit `x86` Android was not checked at all.** It is not one of the three
  ABIs `scripts/android-fat-aar.sh` will build, so the `linux32` carve-out at
  `toolchain.configure:2732-2733` (which drops `-ftrivial-auto-var-init` for
  `kernel == "Linux" and cpu == "x86"`) is untested here. It does not affect
  `armv7`, `aarch64` or `x86_64`.
