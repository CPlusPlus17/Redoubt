# LW-M7-49: the honoured layer of PARITY rows 5, 7, 8 and 9

Measured 2026-10-09/10 (CEST) on the build host. Owner decision 2026-10-09,
verbatim: "lets do 1,2,7". This is item 7.

## What was tested

- **APK:** the published `android-157.0-3` asset `fenix-x86_64-release.apk`
  (sha256 `4d3f7e7741134c3490582fc0a5c2d6766cce0ef6846d19658c2f49886eb97cf6`,
  equal to GitHub's asset digest), re-signed with the throwaway key so it can
  be installed beside nothing else; the re-signed file is
  `464d1213aeecdf7dc24608591bda81bf3c66cdfcbb0c8e0a369187b8b34792d8`, with
  every non-`META-INF` entry identical (`apk-identity.txt`). Gecko reports
  `Redoubt 157.0-3 buildID=20261006090000`.
- **Device:** Android 14 (API 34) `google_apis` x86_64 emulator,
  1080x1920 at 420 dpi, 4 cores (`emulator-identity.txt`). Emulator DNS was
  9.9.9.9, so Remote Settings was reachable and the host's telemetry sinkhole
  did not apply.
- **Harness:** `scripts/android-smoke.sh` sha256
  `580ef1e66bc941c5071a6e49fdc1171a9acabe8e5aaae8e1e42dbe12fe1cf8a1` (recorded
  in both final JSON files). Every probed server ran on the host loopback,
  reached from the emulator as `10.0.2.2`. The only third-party hosts contacted
  were in the separate CRLite run below.

## Results

`harness/final-positive.json` (exit 0) and `harness/final-negative.json`
(tainted, exit 1):

| row | check | 157.0-3 | negative control (`LW_SMOKE_EXTRA_PREFS`) |
|---|---|---|---|
| 5 | `https-only-interstitial`, `page-load-http/https` | PASS | not repeated here (LW-M7-11 owns it) |
| 5 | `https-only-upgrade`: `http://10.0.2.2:<tls port>/` | PASS, ends on `https://`, secure context | n/a |
| 5 | `https-only-exception-scope` | PASS: the exception holds for its origin, another port still gets the interstitial; permission `https-only-load-insecure`, `expireType=1` (session) | n/a |
| 8 | `tls-floor` | PASS: 1.0 and 1.1 refused (`SSL_ERROR_PROTOCOL_VERSION_ALERT`, no server handshake), 1.2 and 1.3 connect; `security.tls.version.min=3`, `enable-deprecated=false` | `min=1` + `enable-deprecated=true`: **FAIL**, all four connect |
| 7 | `revocation-ocsp-off` | PASS: `OCSP.enabled=0`, `crlite_mode=2`; good, revoked and closed-responder leaves load; **0** OCSP requests | `OCSP.enabled=1`: **FAIL**, revoked leaf blocked, 6 OCSP requests |
| 7 | `revocation-stapled` | PASS: stapled "revoked" refused with `SEC_ERROR_REVOKED_CERTIFICATE` | PASS (stapling does not depend on fetching) |
| 7 | `revocation-observed` (not graded) | must-staple without staple refused (`MOZILLA_PKIX_ERROR_REQUIRED_TLS_FEATURE_MISSING`); 76 CRLite filters loaded (1 full + 75 deltas), `cert-revocations` last modified 2026-10-09 14:57:05 UTC | filters not yet synced in that run |
| 9 | `rfp-coherence` | PASS 17/17 | `privacy.resistFingerprinting=false`: **FAIL** 12/17 (UA, appVersion, screen, time zone, timer) |

Values the RFP probe recorded but does not grade (final-positive run):
inner window and `screen` 414x647, `devicePixelRatio` 2, CSS `device-width`
414; `device-height` matched `innerHeight` in this run but not in an earlier
one on the same build (dynamic toolbar; see SMOKE.md); time zone
`Atlantic/Reykjavik` with the device on `Europe/Zurich` (nsRFPService
`GetSpoofedJSTimeZone`, not "UTC"); canvas readback randomized (a solid fill
read back as 8 distinct colours, and two `toDataURL()` calls on the same canvas
differed); `getContext("webgl")` returned null on the probe page while
`webgl.disabled` was false (cause not investigated here); fonts detected by
width: Roboto, Noto Serif, Droid Sans Mono, Cutive Mono, Dancing Script, Coming
Soon, Carrois Gothic SC, Source Sans Pro; `Accept-Language: en-US`;
`Sec-GPC: 1`; no `Sec-CH-*` header; `navigator.webdriver` true (Marionette).

## The cfg layer is applied (rows 5, 7, 8)

PARITY rows 7 and 8 called the posture "cfg-only, at risk", because the cfg
layer was not packaged on Android when they were written. It is now. On the
running build `security.OCSP.enabled`, `security.pki.crlite_mode` and
`security.tls.version.enable-deprecated` hold the `common.cfg` values, and
`harness/startup-injection-overridden.json` shows more: prefs injected as
startup defaults through GeckoView's debug config (`OCSP.enabled=1`,
`resistFingerprinting=false`, `enable-deprecated=true`) were replaced by the
cfg's values before any page loaded. That run used the harness before it
learned to re-apply injected prefs at runtime, so its harness hash differs; the
APK is the same.

## CRLite against the real network (`crlite-live/`)

Fresh profile, emulator on 9.9.9.9 (`crlite_live.py`, `crlite-live.json`):

- no filter at 0 s and 15 s; the `cert-revocations` collection synced by 30 s;
  29 filters loaded at 45 s; 76 in a later session.
- `https://revoked.badssl.com/` (a revoked Let's Encrypt certificate, issued
  2026-09-15): refused with `SEC_ERROR_REVOKED_CERTIFICATE`. With
  `security.pki.crlite_mode` set to 0 at runtime the same URL loaded (HTTP
  200), and it was refused again after the pref was cleared
  (`crlite-attribution.json`). CRLite is the mechanism.
- `https://revoked-isrgrootx1.letsencrypt.org/` and `-isrgrootx2`: **loaded**,
  with 76 filters. The isrgrootx1 certificate (issued 2026-10-07 17:38 UTC) is
  in its CRL `http://yr1.c.lencr.org/44.crl`, revoked 2026-10-07 18:37 UTC.
  The filters in use did not yet cover a revocation about two days old. This is
  CRLite's publication lag, the same Gecko code and data as desktop; it is not
  an Android difference. Do not use these two sites as a pass/fail test.
- Valid control `https://valid-isrgrootx1.letsencrypt.org/` loaded.

Consequence for the posture, stated plainly: with OCSP off and CRLite enforce,
a WebPKI certificate gets **no** revocation check until the first filter is
loaded (about 30-45 s after a first start with network, longer offline), and
none for revocations newer than the filters. A stapled response is honoured at
all times. Desktop LibreWolf ships the same posture.

## Not shown by the emulator (device-pending)

A phone's real screen size, DPR, fonts, GPU/WebGL and locale under RFP; the
filter sync on a phone network; TLS and HTTPS-only against public servers.
`docs/android/DEVICE-CHECKS.md` covers them in about ten minutes.

## Reproduce

```sh
LW_SMOKE_PACKAGE=org.redoubtbrowser ./scripts/android-smoke.sh --emulator \
  --sdk <SDK with only android-34> --apk <157.0-3 x86_64, re-signed> --dns-server 9.9.9.9 \
  --check-https-only --check-tls-floor --check-revocation --check-rfp-coherence
LW_SMOKE_EXTRA_PREFS='{"security.tls.version.min": 1, "security.tls.version.enable-deprecated": true, "security.OCSP.enabled": 1, "privacy.resistFingerprinting": false}' \
  ... --check-tls-floor --check-revocation --check-rfp-coherence      # must exit 1
```

`crlite-live/*.py` are the session scripts used for the CRLite run; they load
the harness from `scripts/android-smoke.sh` and drive an already running
emulator (`emulator-5584`).
