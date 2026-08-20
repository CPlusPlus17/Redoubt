# Is any Gecko content sandbox reachable on Android?

**Owner: LW-M5-07.** Time-boxed research spike. This document answers one
question and makes one recommendation. It is not an implementation plan, and it
deliberately does not become one.

**Recommendation: do not pursue `MOZ_SANDBOX` on Android. Ship Android's own
containment (LW-M5-02) and RLBox, and say precisely what that does and does not
buy.** The reasoning is below; the cost estimate is in
[§7](#7-what-it-would-cost-us).

Every factual claim carries an evidence grade:

| grade | meaning |
|---|---|
| **M** | measured — read out of a build artefact produced by our own M2 build |
| **S** | source — read out of the pristine tree at `firefox-153.0.4/` |
| **U** | upstream — a Mozilla bug, a Chromium doc, or Android platform source |
| **I** | inference — reasoned from M/S/U, stated as such, not measured |

Nothing below is graded from memory.

---

## 1. The premise, re-verified from the build (not from the source)

The brief said not to re-derive that `toolkit/toolkit.mozbuild:37` gates
`/security/sandbox` on `MOZ_SANDBOX`, and that `MOZ_SANDBOX` is off. It is
correct **(S)**. But a source reading is the weaker form of this claim, so here
is the artefact form — four independent proofs out of the M2 objdir
`/home/mgysin/lw-m2-01b/firefox-153.0.4/obj-aarch64-unknown-linux-android`
(`/home/mgysin/lw-m0-15/...` agrees on every point):

| # | proof | where | grade |
|---|---|---|---|
| 1 | `MOZ_SANDBOX` appears **nowhere** in `config.status`. The only `*SANDBOX*` keys are `MOZ_USING_WASM_SANDBOXING` and the six `MOZ_WASM_SANDBOXING_*` | `config.status:136-143` | **M** |
| 2 | there is **no `security/sandbox/` directory in the objdir at all**, and no `libmozsandbox.so` anywhere under `dist/` — `find dist -iname '*sandbox*'` returns only RLBox headers, `nsSandboxFlags.h`, pdf.js and IdP files | objdir `security/` listing | **M** |
| 3 | `security.sandbox.content.level` compiles to **0** | `modules/libpref/init/StaticPrefList_security.h:138-141` | **M** |
| 4 | `AppConstants.MOZ_SANDBOX: false` in the **shipped** JS module | `dist/bin/modules/AppConstants.sys.mjs:42` | **M** |

Proof 4 matters more than it looks. `toolkit/modules/Troubleshoot.sys.mjs:1141`
wraps the whole sandbox block in `if (AppConstants.MOZ_SANDBOX)`, so
`about:support` on Android does not report a sandbox level at all — it does not
report a *wrong* one. Good: no artefact of ours will claim a sandbox we do not
have.

### The "every `security.sandbox.*` pref is inert" claim, checked properly

A name grep is not evidence (landmine lesson 1). Every consumer of a
`security.sandbox.*` pref outside `security/sandbox/` was enumerated and each
one's guard was read **(S)**:

| consumer | guard | live on Android? |
|---|---|---|
| `dom/media/gmp/GMPProcessParent.cpp:54` | `#if defined(XP_MACOSX) && defined(MOZ_SANDBOX)` | no |
| `dom/ipc/ContentParent.cpp:2362,2376,2389,2397` | inside `CacheSandboxParams`, macOS-only | no |
| `dom/ipc/ContentChild.cpp:1700` | `XP_MACOSX` branch of `RecvSetProcessSandbox` | no |
| `toolkit/xre/nsAppRunner.cpp:655-864` | win32k experiment, Windows-only | no |
| `toolkit/modules/Troubleshoot.sys.mjs:1141` | `if (AppConstants.MOZ_SANDBOX)` → false **(M)** | no |
| `mobile/ios/app/mobile.js:14` | iOS product | no |
| `toolkit/components/nimbus/FeatureManifest.yaml:5248-5258` | **none** — `contentProcessSandbox.Level` writes `security.sandbox.content.level` on the **user** branch | **yes, and it is a write path** |
| `toolkit/components/nimbus/lib/TargetingContextRecorder.sys.mjs:239` | none | yes (telemetry; LibreWolf strips it) |

So the honest statement is: **every `security.sandbox.*` pref is inert on
Android in the sense that nothing reads it, but one of them is still remotely
*writable* by a Nimbus experiment.** Writing it changes nothing, because the
code that would act on it was never compiled. Two consequences:

- LW-M3-04 does **not** need `security.sandbox.content.level` on its lock list.
  Locking it would be security theatre — it would defend a value nobody reads.
- LW-M5-06 must not write "the pref does not exist". It exists, it is settable,
  and it does nothing.

---

## 2. Policy decision, or technical impossibility?

**Neither, exactly. It is a never-finished port that upstream is now closer to
deleting than to shipping.** The three sub-answers:

**(a) The build system does not exclude Android — the *default* does.** **(S)**
`toolkit/moz.configure:4018-4038`:

```python
@depends(target, tsan, asan)
def sandbox_default(target, tsan, asan):
    # Only enable the sandbox by default on Linux, OpenBSD, macOS, and Windows
    if target.kernel == "Linux" and target.os == "GNU":
        ...
    return target.kernel in ("WINNT", "Darwin", "OpenBSD")
```

Android canonicalises to `kernel="Linux", os="Android"` **(M**, `config.status`
`OS_ARCH: 'Linux'`, `OS_TARGET: 'Android'`, `TARGET_OS: OS('Android')`**)**, so
it falls through both branches and the default is `False`. But `--enable-sandbox`
is a *plain option with a computed default*, not a `when=`-gated one. Passing it
on an Android mozconfig is syntactically legal, and
`security/sandbox/moz.build:21` dispatches on `OS_ARCH == "Linux"` — which is
true on Android — so `security/sandbox/linux` **would** be traversed.

**(b) The Android support in the sandbox code is real, and old.** **(S)**
`security/sandbox/linux/moz.build` still carries two live Android branches
(`:9-13` links `mozglue` only on Android; `:131-135` skips `-lrt` only on
Android), and the C++ carries **14** `#if(n)def ANDROID` / `defined(ANDROID)`
sites across the directory — four of them in `SandboxFilter.cpp` itself
(`:138`, `:1223`, `:1446`, `:1975`). Counted with
`grep -rnE '^\s*#\s*if(n)?def\s+ANDROID|defined\(ANDROID\)' --include=*.cpp
--include=*.h security/sandbox/linux | wc -l`, not by eyeballing hits — a plain
`grep -irc android` over the same files totals 34 and most of those are
comments. Their provenance
is written in the file — `SandboxFilter.cpp:1403-1407`:

> The seccomp-bpf filter for content processes **is not a true sandbox on its
> own**; its purpose is attack surface reduction and syscall interception in
> support of a semantic sandboxing layer. **On B2G this is the Android process
> permission model**; on desktop, namespaces and `chroot()` will be used.

That is Firefox OS code, last exercised around 2015.

**(c) Upstream's own read, from two bugs.** **(U)**

- **[Bug 1660102 — "[meta] seccomp-bpf in GeckoView"](https://bugzilla.mozilla.org/show_bug.cgi?id=1660102)**
  — filed 2020-08-19, still `NEW`, unassigned, P2, whiteboard
  `[sandboxing] [geckoview:2022q4?]`, `depends_on: [1565196]`. Jed Davis
  (`jld`, the sandbox owner), comment 7, **2025-05-24**:

  > seccomp-bpf support in Gecko was first implemented for B2G, and there's
  > still a certain amount of `#ifdef ANDROID` code lying around, which is
  > **likely somewhat bit-rotted by now**, but it could be helpful if/when we
  > try to use seccomp on regular Android.

- **[Bug 2040639 — "Remove Android-specific dead code in `security/sandbox/linux/`"](https://bugzilla.mozilla.org/show_bug.cgi?id=2040639)**
  — filed **2026-05-19** by Yannis Juglaret, `NEW`. Reports that the Android
  code paths cause confusion about whether Android uses the sandbox module, that
  no supported Android configuration reaches them, and — the line that matters
  most for a cost estimate — that **enabling the sandbox on Android yields build
  errors**. The `needinfo` on `jld` is still unanswered as of this writing.

So: not a policy decision in the sense of "we decided Android does not need it",
and not a technical impossibility either. It is an unfinished port whose most
recent upstream activity is a proposal to delete the remaining scaffolding.
Anyone building on it is building on a directory that upstream may strip of
Android support in the next release or two. **(I)**

---

## 3. What Chrome on Android actually does

Chromium documents this precisely, and the doc is the best single reference on
the whole question:
[`docs/security/android-sandbox.md`](https://chromium.googlesource.com/chromium/src/+/refs/tags/128.0.6613.5/docs/security/android-sandbox.md).
**(U)**

Chrome runs a **bilayer** sandbox on Android, mirroring desktop Linux:

- **Layer one is `android:isolatedProcess`**, not anything Chrome implements.
  The OS puts the renderer in the **`isolated_app`** SELinux domain with an
  ephemeral UID. The doc: `isolated_app` "prevents the process from accessing
  virtually all system services, devices, the network, and most of the
  filesystem."
- **Layer two is seccomp-bpf**, applied by Chrome itself via
  `sandbox/linux/seccomp-bpf-helpers/seccomp_starter_android.{h,cc}`. So **yes,
  a browser can and does run a seccomp-bpf filter on Android.** That settles the
  possibility question empirically.

Three details from Chrome's implementation matter to us more than the headline:

1. **Chrome's Android filter cannot restrict the filesystem.** From
   `sandbox/linux/seccomp-bpf-helpers/baseline_policy_android.cc`, on the
   `__NR_openat` case: *"File system access cannot be restricted with
   seccomp-bpf on Android, since the JVM classloader and other Framework
   features require file access."* Chrome **allows `openat` outright**. It also
   has to allow `connect`/`getsockopt` so the renderer can reach `logd` and
   `debuggerd`, and a batch of ART/JIT syscalls (`membarrier`,
   `set_thread_area`, the `sched_*` family).
2. **The Android policy is deliberately looser than desktop.** The doc: "The
   policy applied to Android is based on the desktop Linux policy. But,
   additional system calls are permitted compared to desktop Linux."
3. **Chrome cannot make layer one stronger or weaker.** The doc, on SELinux
   being a mandatory access control system: "Chrome cannot modify the policy,
   nor create gradations of sandboxes as can be done on other operating
   systems. A process on Android runs at either the same security principal as
   the browser, or in the tightly sandboxed **isolated_app** domain."

Point 1 is the load-bearing one for us, and §6 explains why.

Chrome's process-creation model is also ours: "all process creation goes through
the Activity Manager and a zygote", a six-step Binder dance rather than
`fork()`+`execve()`. **(U)** Gecko does exactly the same thing —
`ipc/glue/GeckoChildProcessHost.cpp:1326-1339` (`AndroidProcessLauncher::DoLaunch`)
delegates to `:1804-1826` (`LaunchAndroidService`), which calls
`java::GeckoProcessManager::Start()` over JNI and gets a pid back. **(S)** The
parent never forks the child.

---

## 4. What seccomp-bpf permits under Android's own sandbox

Short answer: **stacking a second filter is allowed and is what Chrome does.**
The constraints, in order of how much they cost:

| constraint | detail | grade |
|---|---|---|
| a filter already exists | the Android zygote installs an app-wide seccomp filter on every app process (`bionic/libc/seccomp/seccomp_policy.cpp`, cited from the Chromium doc) | **U** |
| filters stack | Chromium doc: "seccomp-bpf policies stack and **can only be made more restrictive**" | **U** |
| the existing one is permissive | Android O's app filter blocked **17 of 271** syscalls on arm64 (Google's own [announcement](https://android-developers.googleblog.com/2017/07/seccomp-filter-in-android-o.html)); the current policy is generated from bionic's `SYSCALLS.TXT` + `SECCOMP_WHITELIST_APP.TXT` and is the same shape | **U** |
| installing needs `NO_NEW_PRIVS` or `CAP_SYS_ADMIN` | bionic's own comment; the zygote has already set `NO_NEW_PRIVS` for app processes, so the precondition is satisfied for free | **U** |
| SELinux does not gate it | seccomp filter installation has no SELinux hook; `isolated_app` neither grants nor denies it | **I** |
| TSYNC is available | Chrome's starter calls `SandboxBPF::SupportsSeccompSandbox(MULTI_THREADED)` and starts `MULTI_THREADED`, which requires `SECCOMP_FILTER_FLAG_TSYNC`; if it were unavailable Chrome would log `DETECTION_FAILED` on every Android device. Gecko's equivalent probe is `SandboxInfo::HasSeccompTSync()`, `SandboxInfo.cpp:71-83` | **I** from **U**+**S** |

**What is *not* available:** the namespace half of Gecko's Linux sandbox.
`SandboxInfo::CanCreateUserNamespace()` (`SandboxInfo.cpp:111`) proves the
capability by actually `clone(CLONE_NEWUSER)`-ing a child; on `untrusted_app`
and `isolated_app` that fails, and Android's app seccomp filter blocks the
`set*uid`/`set*gid` family outright, which is precisely what would make a new
user namespace useful. **(U/I)** So `chroot`, the pid namespace and the network
namespace — desktop Linux level 4's contribution — are unreachable, and
`SandboxLaunch.cpp:384,397` (the only two `CLONE_NEWUSER` sites) sit in the
parent-side launch path that Android never executes anyway **(S)**.

**What *is* structurally fine:** the seccomp filter itself. Gecko installs it in
the child, not the parent — `ContentParent.cpp:3103` sends
`SendSetProcessSandbox(brokerFd)`, and `ContentChild.cpp:1710-1731` calls
`SetContentProcessSandbox()` from inside the content process **(S)**. That is
self-sandboxing, so the fact that we cannot fork our own children on Android
does **not** block seccomp. It blocks only the namespace/chroot layer.

---

## 5. Has Mozilla an open bug, and what did they conclude?

Three bugs and one meta-tree. **(U)**

| bug | title | status | last touched | relevance |
|---|---|---|---|---|
| [1660102](https://bugzilla.mozilla.org/show_bug.cgi?id=1660102) | [meta] seccomp-bpf in GeckoView | **NEW**, unassigned, P2 | 2025-05-24 | the actual ask; open five years, zero patches |
| [2040639](https://bugzilla.mozilla.org/show_bug.cgi?id=2040639) | Remove Android-specific dead code in `security/sandbox/linux/` | **NEW** | 2026-05-19 | upstream proposes deleting the scaffolding; notes enabling it "yields build errors" |
| [1565196](https://bugzilla.mozilla.org/show_bug.cgi?id=1565196) | [meta] Enable `android:isolatedProcess` on GeckoView | **NEW** | 2026-08-14 | **65 dependencies**; whiteboard `[sandboxing] [geckoview:2022q3] [fxdroid]` |
| [790923](https://bugzilla.mozilla.org/show_bug.cgi?id=790923) | (b2g-seccomp) B2G content process sandboxing via seccomp filter | closed | — | where the `#ifdef ANDROID` code came from |
| [1498614](https://bugzilla.mozilla.org/show_bug.cgi?id=1498614) | Enable `android:isolatedProcess` on Fennec | **WONTFIX** | 2020-02-13 | the previous attempt, abandoned with Fennec |

Mozilla's conclusion, as far as one exists, is jld's comment 7 on 1660102: the
interesting idea is not "seccomp for its own sake" but "seccomp as the
*enabler* for `isolatedProcess`" — intercepting `open` and brokering it to the
parent so the content process can survive having no filesystem. He explicitly
flags that the answer to whether that helps "might be 'no'".

**It is "no", and Chrome already ran the experiment.** Chrome's
`baseline_policy_android.cc` comment (§3, point 1) is the result: the JVM
classloader and the Android framework need file access in the renderer, so
`openat` cannot be filtered at all. Gecko's content process on Android is an
Android `Service` with a full ART runtime and GeckoView Java code in it — it
needs *more* file access than a Chrome renderer, not less. The one idea that
would have made MOZ_SANDBOX strategically valuable on Android is the one idea
that has been tested and does not work.

**Do not read bug 1565196's 65 dependencies as encouragement for LW-M5-02
either.** Sampling the open ones **(U)**: 1806129 "Isolated process is not
compatible with Android >= 10" (NEW, touched 2026-07-28), 1810736 "Media
decoding is not compatible with isolated process" (**REOPENED**), 1989379
"Isolated Content Process breaks IME", 2009308 "cubeb still accesses android
services disallowed in isolated process mode", 2043165 "SecurityException:
Isolated process not allowed to call registerReceiver by Jetpack's Media3",
1969818 "Fenix content process always crash when GeckoView is isolated process
build". That is not a finished feature behind a flag. See §9.

---

## 6. The real question: what would `MOZ_SANDBOX` add *on top of* what we are already shipping?

This is the question that decides the answer, so it gets the most space.

LibreWolf for Android will ship containment stock Fenix does not: LW-M5-02
turns on `isolatedProcess` + the app zygote, LW-M5-01 raises
`fission.webContentIsolationStrategy`. Desktop LibreWolf's Linux content
sandbox is `security.sandbox.content.level = 6`
(`browser/app/profile/firefox.js:1643`), and that file documents exactly what
each level buys **(S)**. Taking level 6 apart layer by layer against what
`isolated_app` already provides:

| desktop Linux layer (`firefox.js:1626-1651`) | what `isolated_app` already does | marginal value of MOZ_SANDBOX |
|---|---|---|
| **2** seccomp-bpf + write file broker | filesystem is almost entirely inaccessible already, by MAC, from a distinct ephemeral UID | **negative.** Chrome proved `openat` cannot be filtered on Android (ART classloader). Gecko traps *every* `openat`/`faccessat`/`fstatat`/`readlink`/`unlink`/… to the broker at `SandboxFilter.cpp:927-996` **(S)**. Under ART that is a SIGSYS + unix-socket round-trip to the parent on every class load |
| **3** read/write file brokering | as above | **negative**, same reason |
| **4** network/socket restrictions + `chroot` | `isolated_app` has no network at all; ephemeral UID; no system services | **zero for network.** `chroot` is unreachable — no user namespaces (§4) |
| **5** blocks GL / DRI / display servers | `isolated_app` cannot open device nodes or reach SurfaceFlinger | **zero.** And it is already causing upstream pain: bugs 1806129 / 1810736 |
| **6** default-deny for `ioctl` | Android's app filter does **not** default-deny `ioctl`; `isolated_app` narrows *which fds exist*, not what you may do to them | **this is the one real gain.** See below |
| — | — | plus generic syscall-surface reduction beyond bionic's ~17-of-271 |

So the marginal contribution of a Gecko seccomp filter on Android, honestly
stated, is **kernel attack-surface reduction only**: `ioctl` argument filtering,
and denial of the couple hundred syscalls bionic's permissive app filter allows.
That is genuinely worth something — historically the strongest Android sandbox
escapes have been `ioctl` calls into GPU and vendor drivers — but note that
`isolated_app` has already removed the ability to *open* those device nodes, so
the reachable `ioctl` surface is limited to fds the process is handed. **(I)**

And it comes with a hard conflict: the isolated content process talks to the
parent over **Binder**, which is `ioctl(BINDER_WRITE_READ)`. A default-deny
`ioctl` policy on Android has to allow the single most security-sensitive
`ioctl` in the system, on the one device node it can still reach. **(I)** The
level-6 idea substantially does not port.

### The other half of the parity gap, which MOZ_SANDBOX would not fix anyway

Desktop Linux has **five** sandboxed process types — `SetContentProcessSandbox`,
`SetMediaPluginSandbox`, `SetRemoteDataDecoderSandbox`, `SetSocketProcessSandbox`,
`SetUtilitySandbox` (`security/sandbox/linux/Sandbox.h:75-86`) with matching
policy classes at `SandboxFilter.cpp:1408, 1798, 1968, 2188, 2353` **(S)**.

On Android, `mobile/android/geckoview/src/main/AndroidManifest_overlay.jinja`
declares `isolatedProcess="false"` for **every** non-content service — `media`
(:24), `gmplugin` (:31), `socket` (:38), `gpu` (:45), `rdd` (:52), `utility`
(:59), `crashhelper` (:16) — and generates isolated variants only for tab slots
(`:81`) plus one `useAppZygote` service (`:89`, `useAppZygote` at `:93`). **(S)**

Meaning: even with LW-M5-02 fully landed, the GPU, RDD, socket, utility, media
and GMP processes on Android run **as the same UID and in the same
`untrusted_app` SELinux domain as the browser** — no OS isolation and no Gecko
sandbox. On desktop each of them has its own seccomp policy. **That is the
sharpest, most defensible row in the parity matrix, and it is unfixable by us**:
`isolatedProcess` is not applicable to processes that must reach MediaCodec,
the GPU and the network, and MOZ_SANDBOX would need six new Android policies
before it touched them.

---

## 7. What it would cost us

Assume we chose to do it anyway. **(I)**, built up from the S/U facts above.

| # | work item | why it is not small |
|---|---|---|
| 1 | make `--enable-sandbox` configure and build for `aarch64-linux-android` | upstream states it "yields build errors" (bug 2040639). `broker/`, `launch/`, `glue/`, `interfaces/`, `reporter/` all get traversed and none has been compiled for Android in a decade |
| 2 | neutralise the launch path | `SandboxLaunch.cpp` (namespaces, `chroot` helper, `LinuxCapabilities`) is parent-side and structurally dead on Android — it must be compiled out, not merely skipped at runtime |
| 3 | disable the file broker for Android | forced by Chrome's finding. Removes desktop levels 2 and 3 from the design, i.e. most of what the level ladder means |
| 4 | write an Android content policy from scratch | bionic ≠ glibc; ART/JIT syscalls; JNI; GeckoView's Java layer; `logd`/`debuggerd` sockets; Binder `ioctl` must stay open. Chrome's `baseline_policy_android.cc` is the shape of the answer and it is not a small file |
| 5 | repeat for GPU/RDD/socket/utility/GMP, or accept that only content is covered | see §6 |
| 6 | field validation across the device fleet | vendor kernels and vendor GL/codec blobs get `dlopen`ed into our processes. Every one can call a syscall we denied. Chrome spent years here |
| 7 | carry it forever | against a directory upstream has an open bug to strip of Android support |

Rough shape: **4–8 engineer-weeks to a first booting build on one device,
6–12 engineer-months to something safe to ship to a fleet, then permanent
maintenance.** Compare the whole Android port to date, which is 78 board tasks.

### The LibreWolf-specific multiplier that settles it

A seccomp policy that is one syscall too tight does not degrade — it kills the
content process with `SIGSYS`. The only reason Chrome can ship one is that it
watches `SeccompSandboxStatus` and renderer-crash rates across hundreds of
millions of devices and fixes the misses within a release. **(U/I)**

**We have deliberately given up that instrument.** `assets/mozconfig.android`
sets `ac_add_options --disable-crashreporter` and `export
MOZ_TELEMETRY_REPORTING=`; LW-M4-01/02/05 remove the Glean/Adjust stack; the
patch set includes `disable-data-reporting-{common,android,desktop}.patch` and
`remove-pingsender-*.patch` **(S**, this repo**)**. Upstream is *already*
struggling here — bug 1969818: the Fenix content process "always crashes" in an
isolated-process build, and 1989887: an isolated process cannot even start the
crash handler before libxul is loaded. **(U)**

So we would be shipping the most fragile, most device-dependent security
mechanism in the browser, to a fleet of vendor-kernel Android devices, with **no
telemetry and no crash reports**, on a volunteer maintenance budget, on top of
code upstream wants to delete. The first user with an unusual SoC gets a browser
that closes tabs and cannot tell us why.

---

## 8. Recommendation

**Do not pursue `MOZ_SANDBOX` on Android.** Not now, not as a stretch goal, and
specifically not as "let's just try `--enable-sandbox` and see". Close the
question with this document.

Do these instead — all cheaper, all more effective per hour:

1. **Land LW-M5-02 (`isolatedProcess`) carefully.** This is where essentially
   all real containment comes from, and it is one Kotlin default. Read §9 first;
   it is not free.
2. **Protect RLBox — it is our one genuinely working sandbox on Android, and it
   is easy to lose.** **(M)** `config.status:136-143` and `mozilla-config.h:149-156`
   have `MOZ_USING_WASM_SANDBOXING` plus `MOZ_WASM_SANDBOXING_{EXPAT, GRAPHITE,
   HUNSPELL, OGG, SOUNDTOUCH, WOFF2}`; `security/rlbox/` built 52 `.wasm`
   modules and `security/rlbox/rlbox.wasm.o` carries **8937 `w2c_*` symbols**.
   Six memory-unsafe parsers that run in-process on desktop-without-RLBox are
   wasm-isolated here. Upstream turned this on for 64-bit Android in
   [bug 1726101](https://bugzilla.mozilla.org/show_bug.cgi?id=1726101)
   (FIXED) **(U)**. LW-M5-03 should add an explicit assertion on all six
   defines, so a future mozconfig edit cannot silently drop them.
3. **Land LW-M5-01 (fission isolation).** Site isolation is the containment
   layer that does not depend on the OS at all, and Fenix currently forces it to
   `ISOLATE_NOTHING` on release.
4. **Consider `MOZ_WIDGET_ANDROID`-safe hardening with no device risk** —
   allocator, CFI, RELRO/BIND_NOW, `-ftrivial-auto-var-init` (already on).
   LW-M5-03's territory.
5. **Say the truth loudly** (§10) rather than closing the gap badly.

### The one condition under which to reopen this

If upstream lands seccomp-bpf in GeckoView (bug 1660102 moving to `ASSIGNED`
with patches), adopt it immediately — the cost model inverts completely, because
then Mozilla carries items 1, 2, 4, 6 and 7 of §7 and pays for the field
validation with their telemetry. **Watch bug 1660102 and bug 2040639. Do not
lead.** Conversely, if 2040639 lands first, the Android scaffolding is gone and
this document's answer becomes permanent.

---

## 9. Cross-task findings (not mine to fix — reporting them)

Three things fell out of this spike that belong to other tasks. I own only this
file, so they are recorded here rather than acted on.

**(a) LW-M5-02: the app zygote is an ASLR regression, and it is measurable.**
**(S)** `mobile/android/geckoview/src/main/java/org/mozilla/gecko/process/ZygotePreload.java:23-25`:

```java
System.loadLibrary("mozglue");
System.loadLibrary("xul");
System.loadLibrary("nss3");
```

With `android:useAppZygote="true"` (`AndroidManifest_overlay.jinja:88-94`),
every content process is forked from **one** zygote that has already mapped
`libxul`, `libmozglue` and `libnss3`. All content processes therefore share
identical load addresses for those libraries, and identical pre-fork heap state
and allocator secrets. This is the long-documented [zygote ASLR
weakness](https://wenke.gtisc.gatech.edu/papers/morula.pdf) applied to the
browser's own binary. **(U/I)**

Without the app zygote, each isolated content process `dlopen`s `libxul`
itself and gets an independent base. So `isolatedProcessEnabled` and
`appZygoteProcessEnabled` are **not** two settings of the same knob:
`isolatedProcess` is a security win; the app zygote is a startup/memory
optimisation that costs cross-content-process ASLR — precisely the
randomisation a site-isolation bypass chain wants to defeat.

Note also `GeckoRuntimeSettings.java:710` — app zygote "will take precedence
over `isolatedProcessEnabled` if both are enabled" — and `:718-721`, which
silently forces it false below API 29. **Recommendation to LW-M5-02: enable
`isolatedProcessEnabled`, and default `appZygoteProcessEnabled` to false**
unless startup on a low-end device is measured to be unacceptable. If it is
enabled, the ASLR tradeoff must appear in PARITY.md. This is a judgement call
for LW-M5-02's owner, not mine.

**(b) LW-M5-02: upstream's own isolatedProcess blocker list.** The open bugs in
§5 (Android ≥ 10 incompatibility, media decoding, IME, cubeb, Media3
`registerReceiver`, crash reporter) are the acceptance risk for that task. The
board's `adb shell ps -A -Z | grep -c isolated` verify will pass while media,
IME or audio are broken, because it only counts processes. That is exactly the
verify-that-passes-but-proves-nothing shape from lesson 2. LW-M5-02 should
exercise video playback, audio and IME on device.

**(c) LW-M5-06 wording.** See §10.

---

## 10. Input to the public parity statement (LW-M5-06)

The agreed wording is *"…on a platform whose process containment is weaker — and
we publish exactly where."* **Keep it. Do not soften it.** But it is only
unambiguously true in the stock-Fenix configuration, and LW-M5-02 changes the
configuration. Publishing a claim that is defensible in one dimension and wrong
in another is how a parity statement loses credibility. Precise version, safe to
publish:

> LibreWolf for Android has **no Gecko process sandbox**. `MOZ_SANDBOX` is not
> compiled on Android (upstream default; `toolkit/moz.configure:4018-4029`), so
> the seccomp-bpf filter, syscall policy and file broker that protect LibreWolf
> desktop's content, media, GPU, network and utility processes on Linux do not
> exist in the Android build, and every `security.sandbox.*` preference there is
> inert.
>
> In their place LibreWolf for Android uses the containment the operating system
> provides, which stock Firefox for Android does not enable: content processes
> run as `android:isolatedProcess`, each with its own ephemeral UID in Android's
> `isolated_app` SELinux domain — no network, no device access, no system
> services and essentially no filesystem. In several respects that is a stronger
> boundary than the desktop sandbox. In one respect it is weaker, and it is the
> respect that matters most for kernel exploits: **the system-call surface
> reachable from a compromised content process is only what Android's own
> permissive app-wide filter denies, and LibreWolf adds nothing on top of it.**
>
> Two gaps have no mitigation on Android and are not expected to gain one:
> the GPU, media, network, utility and GMP processes are **not** isolated — they
> run at the same privilege as the browser — and there is no `ioctl` filtering
> anywhere.
>
> What does carry over intact: RLBox/wasm isolation of the Expat, Graphite,
> Hunspell, Ogg, SoundTouch and WOFF2 parsers is compiled and shipped in the
> Android build, and Fission site isolation is enabled rather than disabled as
> it is in stock Firefox for Android.

Every clause is backed by a row in §1, §5 or §6. Nothing there overclaims, and
nothing there is softer than the agreed sentence.

---

## 11. How to re-verify this on the next rebase

Cheap, and all of it is mechanical:

```bash
OBJ=<android objdir>          # e.g. .../obj-aarch64-unknown-linux-android
grep -c 'MOZ_SANDBOX' "$OBJ/config.status"                 # expect 0
grep -n 'MOZ_SANDBOX' "$OBJ/dist/bin/modules/AppConstants.sys.mjs"   # expect: false
ls "$OBJ/security/" | grep -x sandbox || echo "no sandbox objdir (expected)"
find "$OBJ/dist" -name 'libmozsandbox.so' | wc -l           # expect 0
grep -c 'MOZ_WASM_SANDBOXING'       "$OBJ/mozilla-config.h"  # expect 6 (the libs)
grep -c 'MOZ_USING_WASM_SANDBOXING' "$OBJ/mozilla-config.h"  # expect 1 (the master switch)
nm "$OBJ/security/rlbox/rlbox.wasm.o" | grep -c 'w2c_'      # expect thousands (8937 here)
```

Every line of that block was executed against
`/home/mgysin/lw-m2-01b/.../obj-aarch64-unknown-linux-android` while writing
this document and produced exactly the stated values — including the two
`grep -c` lines, which are separate on purpose: `MOZ_WASM_SANDBOXING` does not
substring-match `MOZ_USING_WASM_SANDBOXING`, so a single combined grep silently
returns 6 and looks like a missing define.

And re-read four upstream things:
[bug 1660102](https://bugzilla.mozilla.org/show_bug.cgi?id=1660102) (has anyone
started?), [bug 2040639](https://bugzilla.mozilla.org/show_bug.cgi?id=2040639)
(has the Android code been deleted?),
[bug 1565196](https://bugzilla.mozilla.org/show_bug.cgi?id=1565196) (is
isolatedProcess shipping upstream yet?), and
`toolkit/moz.configure`'s `sandbox_default` (did the Android branch change?).

---

## Sources

- [Bug 1660102 — [meta] seccomp-bpf in GeckoView](https://bugzilla.mozilla.org/show_bug.cgi?id=1660102)
- [Bug 2040639 — Remove Android-specific dead code in security/sandbox/linux/](https://bugzilla.mozilla.org/show_bug.cgi?id=2040639)
- [Bug 1565196 — [meta] Enable android:isolatedProcess on GeckoView](https://bugzilla.mozilla.org/show_bug.cgi?id=1565196)
- [Bug 1498614 — Enable android:isolatedProcess on Fennec (WONTFIX)](https://bugzilla.mozilla.org/show_bug.cgi?id=1498614)
- [Bug 790923 — (b2g-seccomp) B2G content process sandboxing via seccomp filter](https://bugzilla.mozilla.org/show_bug.cgi?id=790923)
- [Bug 1726101 — Enable wasm sandboxing on 64-bits Android (FIXED)](https://bugzilla.mozilla.org/show_bug.cgi?id=1726101)
- [Chromium — Chrome Android Sandbox Design](https://chromium.googlesource.com/chromium/src/+/refs/tags/128.0.6613.5/docs/security/android-sandbox.md)
- [Chromium — sandbox/linux/seccomp-bpf-helpers/baseline_policy_android.cc](https://source.chromium.org/chromium/chromium/src/+/main:sandbox/linux/seccomp-bpf-helpers/baseline_policy_android.cc)
- [Chromium — sandbox/linux/seccomp-bpf-helpers/seccomp_starter_android.h](https://source.chromium.org/chromium/chromium/src/+/main:sandbox/linux/seccomp-bpf-helpers/seccomp_starter_android.h)
- [Android Developers Blog — Seccomp filter in Android O](https://android-developers.googleblog.com/2017/07/seccomp-filter-in-android-o.html)
- [bionic — libc/seccomp/seccomp_policy.cpp](https://android.googlesource.com/platform/bionic/+/master/libc/seccomp/seccomp_policy.cpp)
- [Android — isolated_app SELinux policy](https://cs.android.com/android/platform/superproject/main/+/main:system/sepolicy/private/isolated_app.te)
- [Lee et al., "From Zygote to Morula: Fortifying Weakened ASLR on Android" (IEEE S&P 2014)](https://wenke.gtisc.gatech.edu/papers/morula.pdf)
