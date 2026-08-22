# LW-M5-04 — RFP and fingerprinting protection on Android

Companion to `scripts/android-rfp-check.sh`.

**Reference artifact:** `~/lw-fresh-2026-08-22/apk/fenix-x86_64-release.apk`
(`org.mozilla.firefox`, 126 593 061 bytes, HEAD 5d8af8f, R8 on).

The task's risk is the frame: *"copying desktop RFP values unexamined can make
Android users MORE identifiable, not less."* So this document separates what is
measured from what needs a device, and does not let a green configured layer stand
in for a measured fingerprint.

## 1. What RFP actually controls, and where it differs on Android

RFP (`privacy.resistFingerprinting`) is one master switch; the properties it
normalizes are platform-specific. The differences that matter for a coherent
fingerprint:

| Signal | Desktop LibreWolf | Our Android build | Why it differs |
|---|---|---|---|
| **RFP master switch** | on (`common.cfg:300`) | on (`common.cfg:300`, shared) | Same cfg; parity at the switch |
| **Window size** | capped to 1600×900 (`desktop.cfg:144-145`, `maxInnerWidth/Height`) | **n/a** — Fenix has no desktop window; the viewport is the screen | `desktop.cfg` is not in the Android composition |
| **Letterboxing** | **false** (`desktop.cfg:146`); `RFPHelper.sys.mjs` drives it via chrome DOM + `letterboxing.css`, which GeckoView does not have | **not enabled** (correctly; `android.cfg:117-119`) | Letterboxing is desktop-only machinery; **not a parity gap** — desktop ships it off |
| **UA string** | RFP spoofs to a common desktop value | mobile UA (Fenix/GeckoView), RFP's desktop UA spoof does not apply cleanly | app/platform-controlled on Android |
| **screen dims / DPR** | RFP spoofs to common values | real device screen/DPR; RFP's desktop normalization may not apply | device-determined on Android |
| **`block_mozAddonManager`** | on (`common.cfg:302`) | on (`common.cfg:302`, shared) | prevents RFP breaking the AMO UI |
| **GPC** | on (`common.cfg:304-306`) | on (`common.cfg:304-306`, shared) | a fingerprinting signal LibreWolf ships on |

## 2. Comparison to the two reference browsers

- **Desktop LibreWolf** — RFP on, window capped at 1600×900, letterboxing off.
  Produces a coherent *desktop* fingerprint. Its two sub-features (window-size,
  letterboxing) are desktop-only machinery and are correctly **not** part of the
  Android composition.
- **Tor Browser for Android** — explicitly presents *one of a small set of common
  Android fingerprints*: a fixed mobile UA and a normalized screen-size/DPR pair,
  chosen so the result matches a plausible real device. That is the bar for
  "coherent on Android."
- **Our build** — RFP master on, but the desktop sub-features absent and the
  mobile UA/screen/DPR platform-determined. Whether RFP's on-switch normalizes
  those to a coherent Android value, or leaves a plain mobile-Firefox fingerprint,
  or (worst case) an incoherent hybrid of desktop-spoof + mobile-real values, is
  **not resolvable from the cfg** — it is the live-probe question below.

## 3. The android.cfg decision (acceptance item 2)

**No Android-specific RFP pref adjustment is landed, and that is the documented
decision, not an omission.** From the configured layer:

- The RFP master switch is already on via `common.cfg` — nothing to add.
- The desktop-only sub-features (window-size, letterboxing) are correctly *not*
  in the Android composition; pulling them in would be a regression (letterboxing
  does not work on GeckoView; `desktop.cfg:139`). The gate asserts this.
- There is no cfg-level lever that fixes the coherence question — that lives in
  the engine's mobile RFP behaviour, which is measured, not configured.

So the "adjustment with a reason" is: *none warranted from the configured layer;
the coherence question is deferred to the live probes rather than answered by a
pref that has no mobile effect.*

## 4. What is and is not verified

- **Verified (configured gate, `--self-test` passes):** RFP master on,
  `block_mozAddonManager` on, GPC on, and the desktop-only sub-features (window
  size, letterboxing) not pulled into the Android composition. The gate rejects
  RFP-off and letterboxing-enabled configs, so it can fail.
- **PENDING (the acceptance's substance, needs a device):** the standard
  fingerprint probes — UA, `screen.width/height`, `devicePixelRatio`, canvas, the
  RFP coherence check — run against the reference build and compared to desktop
  LibreWolf and Tor Browser for Android. The task's risk (a MORE identifiable
  incoherent fingerprint) can only be confirmed or ruled out with those probes on
  a real device. Parked per rule G; not faked. Next try: on a device, run the
  honoured layer and the probe suite, and compare the three fingerprints side by
  side.

## 5. Negative control (the gate is real)

```
$ scripts/android-rfp-check.sh --self-test
  ok: gate correctly REJECTED bad-rfpoff
  ok: gate correctly REJECTED bad-letterbox
  ok: gate correctly ACCEPTED the real cfg
SELF-TEST PASSED: the gate fails on every incoherent config
```
