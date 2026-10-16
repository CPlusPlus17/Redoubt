# LW-M7-39: DRM on Android 12 and 13 (2026-10-16)

Owner decision 2026-10-16: "go" (fix first, rebuild and re-accept, then the owner signs 158.0-3).
The 158.0-3 acceptance (`evidence/lw-m7-01/release-158.0-3/acceptance/device-api31/drm-diagnosis/`)
found that on API 31 every Widevine play stopped at about 8 s. This directory has the cause,
the fix (`isolation-eme.patch` item 7) and the measurements. Each hash below comes from `sha256sum`.

## Cause

- Widevine runs in privacy mode. A session's first message to the page is the service
  certificate request (`0804`). After the page provides the certificate (`update()` with a
  SignedMessage of type 5), the CDM signals `EVENT_KEY_REQUIRED` with **empty** data. The RDD CDM
  (`MediaDrmRemoteCDMParent::HandleEvent`, Firefox 158.0) answers that event with
  `AMediaDrm_getKeyRequest` and sends the real license request to the page.
- The NDK listener of Android 12 and of the first Android 13 release drops every event with
  empty data (`aosp-ndk-sendevent.txt`): `DrmListener::sendEvent` has `if (dataSize > 0)` on
  `android12-release`, `android12L-release`, `android13-release` and `android13-s1-release`,
  and `>= 0` on `android13-qpr1/2/3-release` and `android14-release`. Logcat shows
  `E NdkMediaDrm: invalid event data size=0`.
- So no license was requested. Playback ran through the clear lead of the stream and stopped
  with `waitingforkey` at about 8 s. Java's `MediaDrm` listener has no such check, so the
  non-isolated path (Android 8-11, `GeckoMediaDrmBridge.onEvent`, same `getKeyRequest` with the
  event's data) never had this problem.
- The other events with empty data are not affected in practice: `HandleEvent()` ignores
  `KEY_EXPIRED`, `VENDOR_DEFINED` and `SESSION_RECLAIMED` on every Android version, and the
  dropped `PROVISION_REQUIRED` (one per flow on API 31/32, for the crypto session) is already
  handled through `AMEDIA_DRM_NOT_PROVISIONED` from `openSession`. A license **renewal** is also
  signalled by an empty `KEY_REQUIRED` and stays lost on these versions (see "Not fixed").

## Fix (`patches/android/isolation-eme.patch`, item 7)

- `MediaDrmRemoteCDMParent::RecvUpdateSession`: after a successful `provideKeyResponse` whose
  response is a Widevine service certificate (first bytes `08 05`), and only for Widevine on
  SDK 31-33 (runtime check: `__builtin_available(android 34)` false, `android 31` true), it
  calls `HandleEvent(EVENT_KEY_REQUIRED, empty data)` itself. That is exactly what the event
  does on Android 14. It logs `Redoubt isolation-eme: service certificate provided; requesting
  the license (...)`.
- Idempotent: the session is marked. If the event does arrive (Android 13 builds with the AOSP
  fix), `HandleEventCb()` skips it once (`... arrived after all; the license was already
  requested, skipped`). The mark is cleared by the next `update()`.
- Errors take the existing paths: `NOT_PROVISIONED` provisions and retries inside
  `HandleEvent()`, any other `getKeyRequest` failure is a warning, as for the event.
- Android 14+ and the Java path below Android 12 run no new code.

## Builds

From this branch's state before the commit (`build/commands-*.log` records HEAD `d884a14d`,
settings `bddc198f`, the uncommitted diff hash and `isolation-eme.patch`
`6cf8a6314ce2aca1…`), the GPG-verified 158.0 tarball (`fc77f780…a2bb`), image `98e61be72eec`,
C/C++ `-Werror` (Rust lints capped), build date `20261016100000`. `build/chain.sh`.

| APK | sha256 |
|---|---|
| x86_64 release, unsigned | `a7153b506ad051eda36cbd762bec7b271c43cd9cbce8cdc3301b42f280d3d5e5` |
| x86_64 release, throwaway key (`31e9a40f…b760`), versionCode 2016190679 | `48aa7e6b521bd5b227a3d9280443ec939d9c2ba2afbea80b26c3f5e04a95adee` |
| arm64-v8a Redoubt Dev (`OVERLAYS=dev-app`), unsigned | `ff5e15351738b748a02dec631f4b928a7d95937e681f787330c2d70f57d580ab` |
| arm64-v8a Redoubt Dev, dev key (`1dfc331a…55a5`), versionCode 2016190674 | `e119d774277e9683f06f64a45f95f634272f188361bebe324036ea11feb16792` |

The three log strings are in the x86_64 `libxul.so`.

## Device runs

Emulators (`build/emu.sh`, x86_64, wiped at boot, `scripts/batch.sh`): `--check-eme`,
`--check-isolation`, `--check-video`, then the DRM flow (fresh profile probe, Allowed,
Widevine Shaka "Angel One" pinned low 60 s / ABR 40 s / switch to 576p at 10 s, Ask to allow,
Blocked) and five first plays on fresh profiles (`pm clear`, Allowed, ABR, report at 70 s; the
stream is 60 s long). MOZ_LOG `EME:5` through the GeckoView debug config for every flow.
`scripts/count.py` counts, per EME session, the license requests the CDM sent to the page;
`play.html` counts the requests Shaka sent to the license server. Both agree in every run.

| device | checks | flow | first plays (s) | sessions | license requests per session | `invalid event data size=0` | fix lines (request / skipped) | tab, RDD deaths, fatal |
|---|---|---|---|---|---|---|---|---|
| API 31 `SE1A.220826.008` | all PASS | pass: 59.9 / 39.9 / 48.1 s at 576p, prompt, rejected | 60, 60, 60, 60, 60 | 8 | 1 in all 8 | 14 (one per session, one provisioning per flow) | 8 / 0 | 0, 0, 0 |
| API 32 (12L) `SE1B.240122.005` | all PASS | pass: 60.0 / 39.9 / 48.2 s at 576p | 60 x5 | 8 | 1 in all 8 | 14 | 8 / 0 | 0, 0, 0 |
| API 33 `TE1A.240213.009` | all PASS | pass: 59.9 / 39.9 / 47.8 s at 576p | 60 x5 | 8 | 1 in all 8 | 0 (image has the AOSP fix) | 8 / 8 | 0, 0, 0 |
| API 34 `UE1A.230829.050` | all PASS | pass: 60.0 / 39.9 / 48.0 s at 576p | 60 x5 | 8 | 1 in all 8 | 0 | 0 / 0 | 0, 0, 0 |
| API 30 (not isolated, Java path) | all PASS | pass (VP9+AAC): 59.7 / 39.8 / 49.7 s | 60 x5 | 8 | 1 in all 8 | 0 | 0 / 0 | 0, 0, 0 |

"all PASS" = every row of `--check-eme` (4), `--check-isolation` (12; API 30: isolation off as
designed) and `--check-video` (3). Every flow: Widevine rejected on a fresh profile, resolved
after Allowed, DRM prompt after Ask to allow, rejected after Blocked. Every session first sent
one service certificate request, then exactly one license request. The parent's Widevine line
is in every isolated flow and absent on API 30.

Controls with the unfixed 158.0-3 x86_64 APK (`a20c3075…3ce9`, from CI run 38775774781):

| device | result |
|---|---|
| API 32 | every play stops at 8.2-8.3 s (`waitingforkey`, keyStatuses empty); 4 sessions, 0 license requests; 6 `invalid event data size=0` |
| API 33 (`TE1A.240213.009`) | plays to the end; 1 license request per session; 0 dropped events: this image already has the AOSP fix |

API 31 with 158.0-3: `evidence/lw-m7-01/release-158.0-3/acceptance/device-api31/drm-diagnosis/`.

Phones (arm64 Redoubt Dev, `scripts/phone.sh`; owner 2026-10-15: "you hae 3 phones conencted, you
can use all of them"). Only `org.redoubtbrowser.dev` was installed and removed; it was not
installed before. `--check-eme` ran through the phone harness copy
(`scripts/harness-loopback-origin.diff` on this branch's unchanged `scripts/android-smoke.sh`,
sha256 `2561998e…`). Settings were recorded first and restored (`device.txt`).

| phone | `--check-eme` | plays (fresh profile, Allowed, ABR, 70 s) | license requests per session | deaths, fatal |
|---|---|---|---|---|
| Pixel 9a, Android 17 (API 37), user build | 4/4 PASS | 60, 60, 60 s | 1, 1, 1 | 0, 0 |
| Mi 8 LineageOS, Android 15 (API 35) | 4/4 PASS | 60, 60, 60 s | 1, 1, 1 | 0, 0 |

Pixel 10 Pro: not in `adb devices` (it advertised `_adb-tls-connect` at 10.0.0.161 over mDNS,
but was not connected), so it was not used.

## Not fixed / not measured

- License renewals on Android 12 and 13: Widevine asks for a renewal with an empty
  `KEY_REQUIRED` too, and the NDK still drops it there. A license with a renewal policy would
  expire instead of renewing. Nothing in the NDK tells the CDM when to renew, so there is no
  safe trigger; the test stream has no renewals. Android 14+ is not affected.
- An Android 13 image without the AOSP fix was not available (the SDK offers only the 2024
  image), so on API 33 only the "event arrives, skip it" path was run; the "event dropped" path
  is the same code and ran on API 31 and 32.
- If the dropped event ever arrived after the license response (not seen; it comes within
  milliseconds of `provideKeyResponse`), it would make a second license request, as Android 14
  would.

## Files

`device-api3x/`, `phones/`, `controls/`: `batch.log` / `drm-batch.log`, `exit-status.jsonl`, per
harness run the `.json`/`.out`/`.err` and a trimmed logcat, per flow `flow.out`, `counts.json`,
the page and step JSON, a few screenshots and `logcat.txt-trimmed.gz` (`scripts/trim-logcat.py`:
EME, MediaDrm, Widevine, Redoubt, death and crash lines; `count.py` gives the same numbers on the
trimmed and the full files, 42 of 42; on the phones, other apps' process lines were then removed).
Full captures: `~/redoubt-artifacts/drm-a12/runs*/`.
`aosp-ndk-sendevent.txt`: the AOSP lines per branch. `gates/`: the gate runs.
