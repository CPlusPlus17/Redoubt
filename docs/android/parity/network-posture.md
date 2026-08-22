# LW-M5-05 — network posture of the reference Android build

Measured, not assumed. Companion to `scripts/android-network-check.sh`.

**Reference artifact:** `~/lw-fresh-2026-08-22/apk/fenix-x86_64-release.apk`
(`org.mozilla.firefox`, 126 593 061 bytes, HEAD 5d8af8f, R8 on).

The four behaviours the task names — HTTPS-only, DoH (provider + fallback),
revocation checking, and the TLS version floor — are all configured in
`settings/common.cfg` (pulled into `librewolf.cfg` with `android.cfg`). This file
records the measured **configured** posture, the **honoured** status on Android,
and the divergences.

## 1. Configured posture (measured from the cfg the build is composed from)

`scripts/android-network-check.sh` (configured layer) against
`settings/common.cfg` + `settings/android.cfg`:

| Behaviour | Measured value (common.cfg) | Posture |
|---|---|---|
| **HTTPS-only** | `dom.security.https_only_mode.upgrade_local=true` (:183); `…error_page_user_suggestions=true` (:346); main `dom.security.https_only_mode` **not force-set** | Local (http) navigations upgraded + suggestions shown; **top-level HTTP not hard-blocked** (Gecko default off) |
| **DoH** | `network.trr.mode=5` (:259, off-by-default-but-usable); `network.trr.uri=https://dns10.quad9.net/dns-query` (:260, Quad9); `network.trr.default_provider_uri=https://doh.dns4all.eu/dns-query` (:267, fallback); provider list :290-297 | DoH available with **Quad9 primary + dns4all fallback**, off by default |
| **Revocation** | `security.pki.crlite_mode=2` (:331, enforce); `security.OCSP.enabled=0` (:335); `security.OCSP.require=false` (:336) | **CRLite enforced; OCSP disabled** |
| **TLS floor** | `security.tls.version.min` **not set** (Gecko default = TLS 1.2+); `security.tls.enable_0rtt_data=false`; `security.tls.version.enable-deprecated=false`; `security.ssl.require_safe_negotiation=true` | Floor at **Gecko default (≥ TLS 1.2)**; 0-RTT off; legacy protocols disabled; safe negotiation required |

**Configured verdict: PASS** — all four behaviours are configured to the LibreWolf
posture. The gate's `--self-test` **negative control passes**: it rejects four
synthetic weakened configs (HTTPS-only off, DoH off, CRLite off, TLS 1.0 floor)
and accepts the real cfg, so the gate is capable of failing.

## 2. The divergence: what Android actually honours is narrower

`settings/common.cfg` marks each pref it ships. Of the four behaviours:

| Behaviour | Mechanism | Honoured on Android? |
|---|---|---|
| **DoH** | `[ANDROID: LOCK] GeckoRuntimeSettings.java` (common.cfg:259-260) | **Yes — code-locked**, independent of the cfg file |
| **HTTPS-only** | cfg-only (no `[ANDROID: LOCK]`) | **At risk** — depends on the cfg being applied |
| **CRLite/OCSP** | cfg-only (no `[ANDROID: LOCK]`) | **At risk** — depends on the cfg being applied |
| **TLS floor** | cfg-only (no `[ANDROID: LOCK]`) | **At risk** — depends on the cfg being applied |

`scripts/android-apk.sh:1202` records, as a measurement, that **on Android none of
`librewolf.cfg`, `local-settings.js`, or `policies.json` is packaged** — "the M3 gap
LW-M3-08 exists to close." So the three cfg-only behaviours (HTTPS-only,
CRLite/OCSP, TLS floor) are **not guaranteed to be honoured** in the reference
build; only DoH is, because it is additionally locked in `GeckoRuntimeSettings`.

**This is the honest divergence from desktop**: desktop LibreWolf ships the cfg
(via `settings/distribution/` + autoconfig), so all four are applied; Android
applies only the code-locked subset. The gap is LW-M3-08 (ship the cfg layer on
Android), not a per-pref disagreement.

## 3. Honoured layer — PENDING

The `--serial/--sdk/--apk` honoured layer dumps the running prefs and navigates
(the HTTPS-only block, a DoH resolution with Quad9-then-dns4all fallback, a
revoked-cert block, and a TLS-floor connection). **It could not be run: no device
is reachable** in this environment (the only available AVD is 3072 MB; the
reference build was validated on-device in M3, not re-run here). Recorded PENDING,
not faked — per the M5 ground rule that claims come from a running build.

## 4. Acceptance status (stated plainly)

The task's own `what` says each behaviour needs "a live test against a server that
exercises it, **not a pref read**", and its `risk` is that "a pref that is set but
not honoured reads as done in a pref dump and fails in the field." So the layers
must be read against that:

- **Built and proven here:** the one script (`scripts/android-network-check.sh`),
  the four checks, and the **negative control** (`--self-test` rejects four
  weakened configs — HTTPS-only off, DoH off, CRLite off, TLS 1.0 — and accepts
  the real cfg). The configured posture is measured (sec 1). These are real, but
  by the task's own wording a pref read is *not* the acceptance.
- **PENDING — this is the acceptance as written:** the four live tests against
  servers that exercise them (the HTTPS-only interstitial on a top-level HTTP
  navigation; a DoH resolution that shows Quad9 then falls back to dns4all; a
  revoked-cert block; a TLS 1.0-only server refused while TLS 1.2 connects) need a
  running device **and** test servers. Neither is available here (only a 3072 MB
  AVD; no test servers). Parked per rule G, recorded, not faked. Next try: with a
  device, run the honoured layer against those four servers.
- **DoH** is the one behaviour with a code path (`GeckoRuntimeSettings`) that does
  not depend on the cfg, so it is the strongest of the four on Android.

## 5. Naming note (item e — the task's framing vs LibreWolf's mechanism)

The task names the third behaviour "OCSP hard-fail". LibreWolf's actual
revocation mechanism is **CRLite mode 2** (enforce) with **OCSP disabled**
(`security.OCSP.enabled=0`, `security.OCSP.require=false`, common.cfg:331-336).
The substance the task is after — hard-fail on a revoked certificate — is what
LibreWolf implements; the mechanism is CRLite, not OCSP. The gate therefore checks
CRLite-enforce + OCSP-off, and this records the discrepancy rather than silently
testing a mechanism LibreWolf has disabled.

## 6. Negative control (the gate is real)

```
$ scripts/android-network-check.sh --self-test
  ok: gate correctly REJECTED bad-https
  ok: gate correctly REJECTED bad-doh
  ok: gate correctly REJECTED bad-revoc
  ok: gate correctly REJECTED bad-tls
  ok: gate correctly ACCEPTED the real common.cfg
SELF-TEST PASSED: the gate fails on every weakened config
```
