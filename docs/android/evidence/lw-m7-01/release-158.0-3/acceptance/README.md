# 158.0-3 (Firefox 158.0, DRM under isolation): acceptance of CI run 38775774781, 2026-10-15: **PASS, with one open owner decision**

**Result.** Every 158.0-2 row passes again, and the new DRM rows pass on Android 11, 14, 15 and 17.
**One new defect was found: on Android 12 (API 31) Widevine playback stops after about 8 seconds.**
The cause is an Android 12-13 platform bug (below); it is not a crash and not a security problem,
DRM is off by default, and 158.0-2 had no working DRM on any version. The owner decides whether to
sign this build with the limitation in the release notes, or to fix it first (new build, new
acceptance). Owner decision 2026-10-15: "merge" (LW-M7-39) and ship as "-3"; the release-day gates
are in [`../../../lw-m7-39/release-158.0-3/release-day/`](../../../lw-m7-39/release-158.0-3/release-day/README.md).

158.0-3 is 158.0-2 plus LW-M7-39 (`isolation-eme.patch`; `drm-permission-default.patch`; settings
`bddc198f` drops `media.eme.enabled=false`) and LW-M7-38 (no "Report broken site").

## What was tested

| | |
| --- | --- |
| CI run | <https://github.com/CPlusPlus17/Redoubt/actions/runs/38775774781>, `android-release.yaml`, `workflow_dispatch` on `main`, job `build-unsigned` on box B (`redoubt-ci-boxb`), 17:16:36-18:58:00 UTC, `success` (`ci/run.json`, `ci/run.log.gz`). Inputs: `mode=full`, `update_check=true`, `bundle=false`, `build_date=20261015170000`. The log shows `build overlays: none`, the tarball signature checked against the pinned key, and the cache step (1 tree removed, 202 GB free) |
| headSha | `f2c690f5e270299634fdfb140bb2870941fe254c` = the merge of `release/158.0-3` on main, where this branch starts. Settings gitlink `bddc198fbb608de0e460879416a2eb88e5a46f3d` |
| Artifact | `redoubt-android-unsigned`, 624,028,265 bytes, digest `sha256:a0814a01e55115a53898576e43d13df06f7a99522fdad1fa91d01e60149d09cc`. `sha256sum -c SHA256SUMS`: 4 OK (`ci/SHA256SUMS.check.txt`) |
| Unsigned APKs | arm64-v8a `755e10c01175c0e7ca23267b2c518f17850c66ae5f0167004bbb0522a541ed3c`<br>armeabi-v7a `fc0a3844726b651c102e335f14e18c6639594b3aefbd127d2ead5aed7c6f15ad`<br>universal `c80ed76379574d72a6939116c2e03bdf26a9e253d7843df2af0663aadfac45d8`<br>x86_64 `ce2aea5df099718c36c3ef0ffce6841342210481be80ce2b420494f0ad76d04a` |
| Installed | x86_64 `a20c30751eb92676ad57b48762405e5934af2a8543a34a02cf4b198b7f8d3ce9` (emulators) and arm64-v8a `b34772a43fc9438a59d8cad7419c632f21e90fffa18387359f0fe370a163f101` (phones), both re-signed with the **throwaway** key (`CN=Redoubt throwaway test key 2026-10-02, O=NOT A RELEASE KEY`, cert `31e9a40f…b760`), v2+v3. All 3,278 non-signature entries equal the unsigned APK's (`static/apk-identity.txt`). Every harness run recorded the installed hash, HEAD `f2c690f5` and 0 uncommitted script changes (`*/smoke/exit-status.jsonl`) |
| Upgrade source | 158.0-2 x86_64, throwaway-signed `0080b12f…b3b9` (the file of 158.0-2's own acceptance) |
| Scripts | `scripts/`: the 158.0-2 acceptance scripts with paths changed; `batch2.sh` adds `--check-eme` x2, `drive-api31.sh` adds `--check-eme` x2 and the DRM flows, `drive-api30.sh` adds `--check-eme` and the DRM flows, `static-checks.sh` compares with 158.0-2 and adds S16. `scripts/drm/`: LW-M7-39's `drm-flow.py`, `play.html` (Shaka 5.2.12, the public "Angel One" Widevine stream), `eme-server.py`, `ui.py` (now also on one named phone), plus `batch.sh`, `phone.sh`, `phone-menu.sh`, `phone-harness.sh`, `menu-check.py` (from LW-M7-51) |

**Devices.** One emulator at a time, booted by the harness: API 34 `google_apis` x86_64
(emulator-5584, Wi-Fi off from batch 2, as before), API 31 `google_apis` x86_64 (emulator-5582,
`google/sdk_gphone64_x86_64/…:12/SE1A.220826.008`), API 30 `default` x86_64 (emulator-5582,
`generic_x86_64:11/RSR1.210722.013.A2`). Two of the owner's phones over wireless adb, in parallel with
the API 34 emulator (they share only the page server): **Pixel 9a**, Android 17
(`google/tegu/tegu:17/CP3A.260905.009`, user build) and **Xiaomi MI 8**, LineageOS on Android 15
(API 35, userdebug). Redoubt was not installed on either; the scripts installed the arm64 APK,
restored the stay-awake settings they changed, and uninstalled it (`phones/*/device.txt`). The third
phone (USB serial `2C091JEHN03336`) shows "no permissions" over USB (host udev rule) and has no
wireless adb, so it was not used.

## Static (`static/`)

| # | Check | Result |
| --- | --- | --- |
| S1 | versionName / codes | **PASS.** `158.0-3-default`; v7a **2016190536**, arm64 **2016190538**, x86_64 **2016190542**, universal **2016190543**, all above 158.0-2 (…288-295) and 158.0-1 (…144-151). Package `org.redoubtbrowser`, label `Redoubt`, targetSdk 37 |
| S2 | ELF per ABI | **PASS** |
| S3 | Unsigned | **PASS.** 0 signature entries, `apksigner verify` exit 1 for all four |
| S4 | Branding | **PASS**, byte-equal to 158.0-2 |
| S5 | uBO | **PASS.** 1.75.0, sha256 `5b744158…5287` = the pin, in all four |
| S6 | Packaged `librewolf.cfg` | **PASS.** sha256 `374b65780ceee00622755652fbdc84bca7a4b3903cd88b071326037d6cce9ca7` in all four, byte-equal to `common.cfg + android.cfg` at `bddc198f`. Against 158.0-2 the only change is the removed `defaultPref("media.eme.enabled", false)` and its comment (`librewolf-cfg-vs-158.0-2.txt`) |
| S7 | Update-check key and endpoint | **PASS.** key `8e714075…7de8`, endpoint, `Redoubt-UpdateCheck/1` once each in `classes2.dex` |
| S10 | Build ID and diff | `MOZ_APP_VERSION 158.0-3`, `MOZ_BUILDID 20261015170000`. Against 158.0-2 x86_64: 14 of 3,278 APK entries differ (the same rebuild set as last time), 2 of 2,310 in omni.ja (`librewolf.cfg`, `AppConstants.sys.mjs`) |
| S11 | Isolation gate | **PASS.** `isolation-gate-dex.py` exit 0 for all four (`SDK_INT >= 31`); manifest unchanged (41 isolatedProcess, 1 useAppZygote) |
| S12, S14, S15 | store installers, LW-M7-46 pref, no dev-app overlay | **PASS** |
| **S16** | **LW-M7-39 compiled in** | **PASS.** `media.redoubt-eme.widevine-support` (x3) and `Redoubt isolation-eme` (x1) in each ABI's `libxul.so`; 0 in 158.0-2 |

## Device

PASS = passed. HL = harness limit, no product finding. E12 = red as expected under E12. NEG = a
negative control that must fail, and did.

### DRM (LW-M7-39), new for 158.0-3

The play rows use Shaka with the public Widevine "Angel One" stream: `play-low` pins the lowest H.264
variant for 60 s, `play` lets ABR choose for 40 s, `play-switch` switches to the highest variant after
10 s and plays 50 s. "First play" = a fresh profile (`pm clear`), DRM set to Allowed, then `play`.
`play.html`'s own `ok` flag only needs 5 s of playback, so the rows below are graded on the reached
time and the key status, not on that flag.

| # | Device | Check | Exit | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| D1 | API 34 | `--check-eme` x2 | 0, 0 | **PASS, 4/4 each.** `widevine-support=2` locked; fresh profile rejects without a prompt; Gecko alone resolves Widevine in isolated content, H.264+AAC, MediaKeys created (CDM in RDD), VP9/WebM refused; no MediaDrm exception, no tab death | `device-api34/smoke/check-eme-{1,2}/` |
| D2 | API 34 | DRM flow + 3 first plays | 0 | **PASS.** Default: Widevine rejected, no prompt. Allowed: resolves. play-low 60.0 s (1,799 frames), play 39.9 s (320x240), play-switch 48.1 s at 768x576, all keys `usable`. Ask: the prompt "Allow http://127.0.0.1:18766 to play DRM-controlled content?" appears. Blocked: rejected. First plays 3/3 at 40 s. 0 MediaDrm exceptions, 0 tab deaths, 0 fatal lines; the parent's Widevine line in every run | `device-api34/drm/`, `device-api34/logs/drm-batch.log` |
| D3 | **API 31** | `--check-eme` x2 (never measured before) | 0, 0 | **PASS, 4/4 each**, the same rows as API 34 | `device-api31/smoke/check-eme-{1,2}/` |
| **D4** | **API 31** | DRM flow + 3 first plays | 0 | **FAIL, playback.** Settings, default, Allowed, Ask and Blocked behave as on API 34, and nothing crashes. **Every play stops at 8.2-8.3 s** (`waitingforkey` at 7.93 s, no key ever loaded, `keyStatuses` empty), 5 of 5. See "Defect: DRM on Android 12-13" | `device-api31/drm/`, `device-api31/drm-diagnosis/` |
| D5 | API 30 | `--check-eme` | 0 | **PASS, 4/4.** Isolation off: pref unused (0), the 158.0 Java path resolves Widevine | `device-api30/smoke/check-eme-1/` |
| D6 | API 30 | DRM flow + 1 first play | 0 | **PASS.** play-low 59.8 s, play 39.8 s, play-switch 49.7 s (VP9+AAC: the Java path offers VP9), first play 39.7 s; prompt and Blocked as above | `device-api30/drm/` |
| **D7** | **Pixel 9a, Android 17** | DRM flow + 3 first plays | 0 | **PASS, on hardware.** play-low 59.8 s (1,793 frames), play 39.8 s, play-switch 47.5 s at 768x576, first plays 3/3 at 39.7-39.8 s, keys `usable`; Ask prompt, Blocked rejects. 4 isolated processes, 0 MediaDrm exceptions, 0 tab deaths | `phones/pixel9a/` |
| **D8** | **MI 8, Android 15** | DRM flow + 3 first plays | 0 | **PASS, on hardware**, the same results (play-low 59.8 s, play-switch 47.5 s at 768x576, first plays 3/3) | `phones/mi8/` |
| D9 | MI 8 | `--check-eme` x2, `--check-isolation` | 1, 2, 2 | **HL.** `eme-prefs` (isolation ON, `widevine-support=2`, locked), `eme-no-crash`, `isolation-mode` and `isolation-prefs` pass; every row that loads a page times out, because the harness serves its pages at `10.0.2.2`, the emulator's host address, which a phone cannot reach | `phones/mi8/harness/` |
| M | MI 8 | LW-M7-38 menu | 0 | **PASS.** Main menu and "More" opened on a page: no "Report broken site" (0 mentions in the UI dump) | `phones/mi8/menu/` |

### Defect: DRM on Android 12-13

- **What happens.** On API 31 the license exchange starts with a Widevine service-certificate
  request (`DispatchKeyMessage() type=license-request message='0804'`). The page answers it, the
  RDD process passes the answer to `AMediaDrm_provideKeyResponse`, and then the CDM signals
  `EVENT_KEY_REQUIRED` so that the real license request can be made. That event never reaches
  `MediaDrmRemoteCDMParent::HandleEventCb`. Logcat instead shows
  `E NdkMediaDrm: invalid event data size=0`, twice per session (`drm-diagnosis/eme-log-excerpt.txt`,
  MOZ_LOG `EME:5` through the GeckoView debug config). No license is requested, so the stream plays
  its clear lead (about 8 s for this stream) and then waits for a key forever.
- **Cause.** Android's NDK drops events that carry no data on Android 12 and 13:
  `NdkMediaDrm.cpp` `DrmListener::sendEvent` has `if (dataSize > 0)` in `android12-release` and
  `android13-release`, and `if (dataSize >= 0)` from `android14-release` on
  (`drm-diagnosis/aosp-ndk-sendevent.txt`). The 0-byte drop count is 2-4 in every API 31 DRM run and
  0 in every API 34 run (`drm-diagnosis/dropped-event-counts.txt`).
- **Who is affected.** Android 12, 12L and 13 (API 31-33) with DRM turned on, on sites whose
  license server uses the service-certificate round trip (Widevine privacy mode), which is common.
  API 31 was measured; 32 and 33 are read from the AOSP source, not measured. Android 14+ and
  Android 8-11 (Java path) are not affected. Upstream Firefox's RDD CDM path is the same code, so
  Firefox 159 is expected to have the same gap (not checked; not reported, owner rule).
- **Not affected:** no crash, no tab death, no MediaDrm exception, no leak. DRM stays off by default.
- **Fix, if the owner wants it before release** (not done here): in
  `MediaDrmRemoteCDMParent::RecvUpdateSession`, below API 34, when the session's last message was the
  service-certificate request, call `AMediaDrm_getKeyRequest` again after `provideKeyResponse` and send
  the result as a `license-request` message, which is what the dropped event would have triggered.
  That needs the init data and the "certificate pending" state kept per session, about 30 lines in
  `isolation-eme.patch`, then a new build and a new acceptance.

### Isolation (LW-M7-50), as in 158.0-2

| # | Check | API | Exit | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| I1 | `--check-isolation` x3 | 34 | 0, 0, 0 | **PASS, 12/12 each, ON.** H.264 `ffvpx video decoder (RDD remote)`, AAC `(Utility Generic remote)`, VP8/VP9/AV1+Opus in content; 3 content processes `isolated_app`, isolated uids; 20 baseline denials; `:rdd` refused VP9 and `:utility` Opus | `device-api34/smoke/check-isolation-{1,2,3}/` |
| I2 | `--check-video` x3 | 34 | 0, 0, 0 | **PASS, 3/3 each** | `device-api34/smoke/check-video{,-2,-3}/` |
| I3 | `--check-isolation` x2 | 31 | 0, 0 | **PASS, 12/12 each, ON** | `device-api31/smoke/` |
| I4 | `--check-video` x2 | 31 | 0, 0 | **PASS, 3/3 each** | `device-api31/smoke/` |
| I5 | `--check-isolation` | 30 | 0 | **PASS, 12/12, OFF**, 158.0-1's media path | `device-api30/smoke/check-isolation-1/` |
| I6 | `--check-video` | 30 | 0 | **PASS, 3/3** | `device-api30/smoke/check-video/` |
| P | process labels | 34 / 31 / 30 | 0 | **PASS, as gated.** API 34 and 31: four content processes in `isolated_app` (uids 90000-90003) forked by the app zygote, `:rdd` `untrusted_app`. API 30: four `:tab_disable_art_image_N` as `untrusted_app` under the app uid | `device-api{34,31,30}/process-labels/` |

### Rows carried over from 158.0-2

| # | Check | API | Exit | Result |
| --- | --- | --- | --- | --- |
| 1 | `--check-launcher-start` | 34 | 0 | **PASS** |
| 2 / 2a | `--check-aboutconfig` / CSP probe | 34 | 0 / 0 | **PASS** |
| 3, 4, 4a, 5 | uBO preinstall (2/2), lifecycle (10/10), user-disable (3/3), `--check-ubo` | 34 | 0 | **PASS** |
| 6 | `--check-search` | 34 | 0 | **PASS** |
| 7 | `--check-no-suggest` | 30 | 0 | **PASS** |
| 7′ | `--check-no-suggest` | 34 | 1 | **HL**, as before: the OS's own `www.google.com` flow in the typing window |
| 7a | negative control | 34 | 1 | **NEG**, caught `ac.duckduckgo.com` on 5 connections |
| 8 | baseline with full graphics acceptance | 30 | 0 | **PASS, 10/10**, graphics `acceptanceComplete: true`, PASS |
| 8′ | baseline | 34 | 1 | **HL.** 9/10, only `webgl` (API 34 window-list parser), as before |
| 9 | `--check-update-privacy` | 34 | 1 | **HL.** The one flagged flow is an IPv6 SYN with 0 bytes to `2606:50c0:8003::153`, a GitHub Pages address that DNS gave for `redoubtbrowser.org` (the update host), `ublockorigin.github.io` (seen with the check off) and `curbengh.github.io`. The update fetch itself went over IPv4 with SNI `redoubtbrowser.org`. The harness grades a shared address by every name it had, so a Happy Eyeballs attempt to the update host's own AAAA reads as "new name". 158.0-1 had the same limit (its row 9′); 158.0-2 passed this run by timing |
| 9″ | `--check-update-privacy` | 30 | 1 | **HL**, the same kind: an IPv6 SYN with 0 bytes to Fastly `2a04:4e42:400::347`, an address shared by the Remote Settings hosts (seen with the check off) and `accounts.firefox.com`; not the update host |
| 9a | update check, live endpoint | 34 | 0 | **PASS.** ON: `GET latest.json` 200 and `latest.json.sig` 200 from GitHub; the live document is the owner-signed **158.0-2** one (`version_code` 2016190288), older than this build: **nothing offered**, only `last_run_ms` written, app alive. No `Accept-Language`. Second resume 0 requests; OFF 0 requests; control 6 records |
| 9b | **update check against a local document** | 34 | 0 | **PASS.** The local TLS endpoint served `doc-wrongkey-158` (`158.0-99`, code 2016199999, above this build), signed with a key that is not the committed one. Both files fetched (`server-requests.jsonl`), **nothing offered**, app alive. Test CA valid until 2026-10-27 |
| ST | store installer hides the check | 34 | 0 | **PASS** (F-Droid as installer: row absent, 0 requests; after `install -r`: row back, both GETs, no `Accept-Language`) |
| DQ | `--check-delete-on-quit` | 34 | 0 | **PASS** |
| 10 | `--check-https-only` | 34 | 0 | **PASS, 5/5** |
| TLS, RV, RFP | `--check-tls-floor`, `--check-revocation` (3/3), `--check-rfp-coherence` | 34 | 0 | **PASS** |
| AF | shadow-DOM autofill | 34 | 0 | **PASS**, the same counts as 158.0-2 (`shadow-open` 1 request / 3 fields, `plain` 1 / 2, the others 0) |
| RD | reddit.com/login, fresh profile | 34 | 0 | **Known limit, unchanged**: blank at 30 and 60 s; the home page renders |
| 11 | `--check-no-gms --check-no-adjust` + graphics | 30 | 0 | **PASS, 12/12**, a second full graphics acceptance |
| 11′ | the same | 34 | 1 | **HL**, only `webgl` |
| W | manual WebGL page | 30 | 0 | **PASS** (`WEBGL-MANUAL PASS`) |
| 12 | `--check-strings` | 34 | 0 | **PASS.** 244,495 rows, 0 unexplained, 34 screen stops |
| 13 | `--self-test` | 34 | 0 | **PASS** (`SELF-TEST OK`) |
| 14 | `--first-run-capture` | 30 | 1 | **E12.** 116 events (158.0-2: 120). **Named hosts: none added, none gone.** Three more unnamed addresses, all in the GitHub Pages and Fastly ranges seen before (`device-api30/first-run-host-comparison.json`). No `redoubtbrowser.org` |
| 14′ | `--first-run-capture` | 34 | 1 | **E12**, 118 events (Wi-Fi off; not compared) |
| 15 | `--check-no-remote-settings` | 34 | 1 | **E12**, the same 3 Remote Settings hosts |
| 16 | pref audit | 34 | 0, 0 | **PASS.** Generator diff against the committed `expected-prefs.txt` is empty; audit exit 0 |
| 17 | **upgrade 158.0-2 → 158.0-3** (`adb install -r`) | 34 | 0 | **PASS.** Code 2016190294 → 2016190542, same signer, same `firstInstallTime`; suggestions ON, DoH Max Protection (quad9), the bookmark, uBO 1.75.0 with `dpollock-0`, and the update-check switch ON all kept; `appinfo` 158.0-3 / 20261015170000. `state-A-final` and `state-C-after-upgrade` differ only in `appinfo` and the TRR build fields |
| 18 | the same upgrade | 30 | 0 | **PASS**, the same result |

**No crash:** no `FATAL EXCEPTION`, `Fatal signal` or `ANR in org.redoubtbrowser` in any of the 60
emulator logcat streams, nor in the phone runs (`fatal=0` in `phones/*/drm-batch.log`).

## Update document (host side; nothing signed with the owner's key)

- `scripts/update-manifest.py generate --tag android-158.0-3` on this run's `output-metadata.json`:
  `version_code` **2016190536** (the lowest of the four), the `android-158.0-3` release URLs,
  published `2026-10-15T19:18:10Z`; sha256 **`8ce232a2bf13d67c237a9dcce81e296cacf489e20f12600aa44080506f951a68`**
  (`update-check/latest.json`, the same bytes as the signing bundle's).
- Signed here with the 157.0-2 acceptance's **throwaway** P-256 key (`update-check/host-verifier.txt`):
  with the committed key `update-manifest.py verify` says **REJECTED** (exit 1); with the throwaway key
  the signature verifies and the `--metadata` cross-check passes; "update offered" for all four
  158.0-2 codes, 158.0-1 arm64 and 157.0.1-1 x86_64; "up to date" for all four 158.0-3 codes.
  `sign-update-manifest.sh` refused the throwaway key (exit 2) and wrote no `.sig`.
- `site/update/` is untouched.

## Signing bundle

`~/redoubt-artifacts/release-158.0-3/signing-bundle/` (not in the repository), laid out like 158.0-2's:
- the four unsigned APKs and the CI `SHA256SUMS` (`sha256sum -c`: 4 OK);
- `sign.sh` (`0af4851e…1252`), `android-verify-signature.sh` (`8a251c45…a483`), `SIGNING.md`
  (`7c8e3645…f3f2`), all byte-equal to main at `f2c690f5`, and `apksigner.jar` (`3716d931…3dec`,
  158.0-2's), listed in `SHA256SUMS.tools`. `sign.sh` and `SIGNING.md` are newer than 158.0-2's
  bundle copies: main's 0f878558 added the YubiKey (PKCS#11) option; the keystore form is unchanged;
- `update/`: `latest.json` (`8ce232a2…1a68`), `sign-update-manifest.sh` (`9c1ad1ef…9f06`, main's,
  also with the token option), `update-check.android.pubkey` (`8e714075…7de8`) and
  `SHA256SUMS.update`.

## Run notes

- The first start of the API 34 driver stopped at once: the harness needs `output-metadata.json` next
  to the APK to learn the package name. It was copied there and the driver restarted (19:11 UTC);
  nothing ran on the device before.
- `phones/*`: `phone.sh` first started logcat through a shell function, so its `kill` stopped the
  function and not `adb`; the eight leftover `adb logcat` processes were stopped by PID after the
  runs. The flows had finished, so the saved logs are complete. The script now starts `adb` directly.
- The API 31 diagnosis booted the same image once more (`drm-diagnosis/boot-exit-status.jsonl`),
  set `MOZ_LOG` through `/data/local/tmp/org.redoubtbrowser-geckoview-config.yaml` and
  `am set-debug-app`, ran one Allowed+Play flow, then removed both before the emulator was shut down.

## Not covered

- **Android 12L and 13 (API 32, 33)** were not run; see the defect section.
- **The third phone** (USB, no permissions on this host).
- **The harness on phones**: only the rows that need no page load (D9).
- **Real streaming services**: DRM was tested with the public Shaka test stream only.
- **Owner-key signatures**: nothing was signed with a release key.
