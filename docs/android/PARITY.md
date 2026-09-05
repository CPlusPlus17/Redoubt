# Security & privacy parity — LibreWolf desktop vs. Redoubt (Android)

**Status: M5 deliverable (LW-M5-06), the close-out of milestone M5.**
Every status below is **backed by measurement, not intent** — a binary scan of
`libxul.so`, a running-build capture, a config parse, or an upstream bug number.
Where a status depends on a measurement we could not run this session (no
device, no test server), the row is marked **PENDING** and is *not* counted as
verified (see §4).

## 1. The bottom line — read this first

**Redoubt has no Gecko content sandbox.** `MOZ_SANDBOX` is off on Android,
`toolkit.mozbuild:37` never traverses `security/sandbox`, and every
`security.sandbox.*` pref is inert. Upstream never finished the port (bug
1660102, still NEW and touched 2025-05; bug 2040639, "enabling it yields build
errors"). This is a platform fact, not a configuration choice, and it is the
single largest containment gap versus desktop.

What recovers **most, not all**, of it:

- **Per-site process isolation** — `fission.webContentIsolationStrategy` locked
  to `ISOLATE_HIGH_VALUE` (LW-M5-01). Stock Fenix ships `0` (ISOLATE_NOTHING);
  this is a genuine win over the browser we build from.
- **Process separation** — `isolatedProcess` plus the app zygote (LW-M5-02) give
  the content process a distinct uid.
- **JS/WASM sandboxing** — 52 RLBox modules are built (measured in `libxul.so`).

The two **irreducible** gaps, stated plainly, are the **Gecko content-process
sandbox** (above, §3.1) and the **loss of the desktop build's signing-key
identity** (§3.2).

## 2. The parity matrix

Legend: **Equivalent** = the same effective security/privacy property as desktop;
**Partial** = present or configured but not fully honoured, with the shortfall
stated in the mechanism; **Absent** = not present, no Android equivalent.
"Measured by" names the evidence type so a reader can tell measurement from
assertion.

| # | Property | Desktop | Android | Mechanism / evidence |
|---|---|---|---|---|
| 1 | Gecko content-process sandbox (`MOZ_SANDBOX`) | ON | **Absent** | Not compiled; `toolkit.mozbuild:37` skips `security/sandbox`; `security.sandbox.*` inert. Upstream port unfinished (bugs 1660102, 2040639). Mitigated by rows 2–4. Measured by: build config + upstream bugs. [ROADMAP, SANDBOX-SPIKE] |
| 2 | Per-site process isolation (Fission) | `ISOLATE_HIGH_VALUE` | **Equivalent (stronger than stock)** | Locked to `ISOLATE_HIGH_VALUE` (LW-M5-01); stock Fenix ships `0`. Measured by: running-build pref read. [no-nimbus.patch, LW-M5-01] |
| 3 | JS/WASM sandboxing (RLBox) | ON | **Equivalent** | 52 RLBox modules present. Measured by: binary scan of `libxul.so`. [SANDBOX-SPIKE] |
| 4 | Compiler memory hardening (CFI, PHC, rosegment, …) | ON | **Equivalent (some stronger)** | All desktop flags present + PHC + rosegment; Android STL hardening (libc++ EXTENSIVE) is stronger than desktop `_GLIBCXX_ASSERTIONS`. Residual: 32-bit ARM lacks `-fstack-clash-protection`. Measured by: binary scan of `libxul.so`. [hardening-flags.md] |
| 5 | HTTPS-only mode | ON | **Partial** | `upgrade_insecure_requests` + `upgrade_local` + error-page-suggestions configured; the main switch is not force-set (a desktop design choice, not an Android regression); on Android the cfg layer is not packaged (LW-M3-08), so the configured value is at-risk of not being honoured — only `[ANDROID: LOCK]` prefs are. Measured by: config parse (network-check.sh). [network-posture §1–2] |
| 6 | DNS-over-HTTPS | ON (mode 5, Quad9, dns4all fallback) | **Absent — Fenix overrides it (DoH off)** | `common.cfg:259-260` set `network.trr.mode=5` and the Quad9 URI, but `Core.kt:190-191` → `GeckoEngine.kt:2032-2033` overwrite both on every cold start with Fenix's own defaults (mode 0, empty URI); the equality guard cannot save them because `PrefWithoutDefault` starts at null. Locking is not the remedy: Settings > Privacy > DNS over HTTPS owns both prefs, so a lock would leave the provider list interactive while discarding every choice (`must-not-lock.txt`, `network.trr.*`). The user can turn DoH on in that screen; our configured provider does not reach Gecko. Fix is Fenix-side and owned by no task yet. Measured by: code trace, commit 7c92b22. [must-not-lock.txt] |
| 7 | Certificate revocation (CRLite + OCSP off) | ON (CRLite mode 2, OCSP disabled) | **Partial** | Cfg-only, at-risk (LW-M3-08). Naming note: LibreWolf ships **CRLite mode 2 with OCSP disabled**, not "OCSP hard-fail" (report item e). Measured by: config parse. [network-posture §5] |
| 8 | Modern TLS floor (min ≥ 3, no 0-RTT, no deprecated ciphers) | ON | **Partial** | Cfg-only, at-risk (LW-M3-08). Measured by: config parse (network-check.sh). [network-posture] |
| 9 | Resist Fingerprinting | ON (incl. window-size normalization) | **Partial** | RFP master ON (shared `common.cfg`) + `block_mozAddonManager` + GPC; window-size/letterboxing are desktop-only prefs (letterboxing is off on desktop too, so not a loss); **live coherence PENDING** — no device. Measured by: config parse (rfp-check.sh) + cross-platform comparison. [RFP-ANDROID] |
| 10 | Global Privacy Control | ON | **Equivalent** | Not locked, and must not be: a visible Fenix switch owns `privacy.globalprivacycontrol.enabled` (`tracking_protection_preferences.xml:127-130`), but the only value it can push through `GeckoView:SetDefaultPrefs` is `true`, which is ours; `functionality.enabled` / `pbmode.enabled` are reached by nothing at stage 5b. Measured by: code trace (`must-not-lock.txt`, commit 7c92b22). [RFP-ANDROID] |
| 11 | Enhanced Tracking Protection (strict) | ON | **Equivalent** | `lockPref` in `settings/android.cfg:341` (`must-lock.txt`); the Fenix Tracking Protection selector still moves but no longer changes behaviour — the same UI/pref split desktop ships (`bare-prefs.md`). Measured by: source + running-build pref read (LW-M3-09). [RFP-ANDROID, POLICIES] |
| 12 | Cookie partitioning / SameSite | ON | **Equivalent** | `network.cookie.cookieBehavior` and its `.pbmode` / `.optInPartitioning` variants are `lockPref` (`must-lock.txt`), so stage 5b cannot move them. Measured by: source (`must-lock.txt`, generated by `gen-android-locks.py`). [network-posture] |
| 13 | Shared LibreWolf security/privacy patch set | common ∪ desktop (60) | common ∪ android (42) | **Equivalent for the shared (common) set.** 24 common patches apply to both targets; 36 desktop-only do not reach Android; 18 are Android-specific (isolation, telemetry removal). Measured by: `board.py --check-scope`. [PATCH-SCOPE] |
| 14 | Telemetry / experiments / sponsored content | patched off | **Equivalent (broader removal)** | `no-adjust`, `no-glean`, `no-nimbus`, `no-nimbus-toolkit`, `no-gms`, `no-onboarding` (all `android.txt`); 2,623 GMS dex classes → 0. Measured by: dex class count on a running build. [PATCH-SCOPE, POLICIES] |
| 15 | Enterprise policy keys (22) | via `policies.json` | **Partial** | `policies.json` engine absent on Android (`Services.policies` undefined); all 22 keys mapped to other mechanisms; gaps **P1–P8** (Nimbus P2, Glean P3, default-browser prompt P4, extension-type restriction P5, sponsored/contile P6, HttpsOnlyMode P7). Measured by: policy-key mapping + running build. [POLICIES] |
| 16 | Signing-key / codebase identity | LibreWolf/Mozilla code-signing trust root | **Absent (irreducible)** | Fork (Redoubt), not the LibreWolf project. Android identity is a distinct trust root — the `org.redoubtbrowser` applicationId plus the signing key (LW-M6-01) — and the current build still ships as `org.mozilla` + `.fenix.debug`. It cannot carry the desktop build's code-signing identity. [IDENTITY, ROADMAP] |

**Auxiliary-process containment (GPU / RDD / socket / utility / media):** not
counted as an independent row. On desktop several of these run under per-process
seccomp sandboxing; on Android that per-process sandboxing has no equivalent — they
run under the shared `isolated_app` uid without the content sandbox that would
complement them. This is a **consequence of row 1**, not a separate mechanism.
[SANDBOX-SPIKE]

## 3. The irreducible gaps

### 3.1 The Gecko content-process sandbox

Stated in §1. It is neither a policy decision nor a small port: upstream (bug
1660102, NEW; bug 2040639, NEW, "enabling it yields build errors") has not
finished it, and the cost of finishing it is 4–8 engineering-weeks to a first
build and 6–12 engineering-months to ship-safe, with permanent maintenance
(SANDBOX-SPIKE §7). The recorded recommendation is **not to pursue `MOZ_SANDBOX`**:
the marginal gain over `isolated_app` + RLBox is kernel-attack-surface only, and
it is undercut by the no-telemetry SIGSYS risk on a vendor-kernel fleet
(SANDBOX-SPIKE §8).

### 3.2 The signing-key / codebase identity

This is a fork, not the LibreWolf project. The MPL-2.0 licence grants the code,
not the name or the trust identity (§3.4 grants no rights in any contributor's
trademarks). The Android build's identity is a separate trust root — the
`org.redoubtbrowser` applicationId plus the signing key generated in LW-M6-01 — and it
cannot be the desktop build's code-signing identity. Both the applicationId and
the key are **one-way** decisions (a change strands every install), which is why
neither may be decided carelessly (IDENTITY.md, ROADMAP).

## 4. What is NOT verified (PENDING)

The rows above rest on the **configured / static** layer. The **live / honoured**
layer could not be measured this session: there is no device and no test server.
Per rule G (two failures → stop and park), these are **parked, not faked**:

- **Honoured-on-a-live-page** for HTTPS-only (row 5), revocation (row 7), TLS
  floor (row 8): `scripts/android-network-check.sh` returns exit 3 (PENDING)
  without a `--serial`; its configured layer passes and its `--self-test`
  negative control **passed** (it rejects 4 synthetic bad cfgs and accepts the
  real `common.cfg`).
- **Live fingerprint coherence** for RFP (row 9):
  `scripts/android-rfp-check.sh`'s configured layer passes and its `--self-test`
  negative control **passed** (rejects `bad-rfpoff` and `bad-letterbox`); the
  "more identifiable than desktop" risk still needs a device.
- **Honoured** behaviour for policy gaps P1–P8 (row 15): needs a device to
  confirm each Kotlin-side behaviour.

Both check scripts are **gates with a passing negative control**, so a
regression in the *configured* layer is caught automatically. What they cannot
prove is the *honoured* layer — which is exactly what the task's "not a pref
read" acceptance requires. That is the remaining work, and it is a
device-equipped session, not a documentation session.

## 5. The agreed public wording

> Redoubt ships the same privacy configuration and the same
> Gecko-level security patches as LibreWolf desktop, on a platform whose process
> containment is weaker — and we publish exactly where.

Quoted **verbatim** from ROADMAP.md and the LW-M5-06 task, which states: *"Do not
soften it."*

**Status of this wording: NEEDS OWNER SIGN-OFF. Do not publish it as-is.** The
owner must approve the final wording and the `redoubtbrowser.org` that will host it
before any external use (IDENTITY.md still carries `redoubtbrowser.org` as an open
placeholder). This section records the agreed text; it is not a publication.

## 6. Sources

- `docs/android/parity/hardening-flags.md` (LW-M5-03) — row 4
- `docs/android/parity/network-posture.md` (LW-M5-05) — rows 5–8, 12
- `docs/android/parity/RFP-ANDROID.md` (LW-M5-04) — rows 9–11
- `docs/android/POLICIES.md` (LW-M3-06) — rows 11, 14, 15
- `docs/android/PATCH-SCOPE.md` (LW-M1-01/12) — rows 13, 14
- `docs/android/SANDBOX-SPIKE.md` (LW-M5-07) — rows 1, 3, the auxiliary note, §3.1
- `docs/android/IDENTITY.md`, `docs/android/ROADMAP.md` — row 16, §3.2, §5
- Gates: `scripts/android-network-check.sh` (LW-M5-05),
  `scripts/android-rfp-check.sh` (LW-M5-04) — both with passing `--self-test`
