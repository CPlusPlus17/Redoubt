# 158.0-2 dev APK for the owner's phone

| | |
|---|---|
| APK | `~/redoubt-artifacts/iso-158-2/apk/redoubt-dev-158.0-2r2-arm64-v8a.apk` (review fix build, `956b05ea`; supersedes the `b78d361d` one, `58edf016…bf85`, now in `apk/superseded-b78d361d/`) |
| sha256 | `b00b29c8125f687fe1e798c634726f59acee3ce92d98f4a7eefc413b120a3685` |
| package | `org.redoubtbrowser.dev` ("Redoubt Dev"), versionName 158.0-2-default, versionCode 2016189778 |
| signer | dev key, certificate sha256 `1dfc331a114e241a994ea9a0eba56e5b13a24553a277bf009bf38224483655a5` (not the release key) |
| built from | `release/158.0-2-isolation` at `956b05ea`, `OVERLAYS=dev-app`, arm64-v8a, C/C++ `-Werror` |
| contains | `media.redoubt-isolation-media.enabled` and the RDD/Utility refusal string in `lib/arm64-v8a/libxul.so` (grep of the APK) |

**Not installed (2026-10-11 ~13:45 UTC).** The owner's Pixel 10 Pro was paired
at `10.0.0.168` earlier the same day (port 40303), but during this session it
dropped off: `adb mdns services` listed no `_adb-tls-connect` service at
10.0.0.168, `adb devices` did not list it, `ping 10.0.0.168` got no answer and
`adb connect 10.0.0.168:40303` said "No route to host". No other adb device was
touched.

**Still not installed after the review fix build (2026-10-11, later the same
day):** `ping 10.0.0.168` no answer, `adb mdns services` empty.

To install when the phone is back (wireless debugging on):

```
adb mdns services                          # _adb-tls-connect at 10.0.0.168:<port>
adb connect 10.0.0.168:<port>
adb -s 10.0.0.168:<port> install -r redoubt-dev-158.0-2r2-arm64-v8a.apk   # over org.redoubtbrowser.dev only
adb -s 10.0.0.168:<port> shell ps -A -o LABEL,USER,NAME | grep org.redoubtbrowser.dev
```

On the Pixel 10 Pro (Android 17, API 37 > 31) the gate is ON: once a page is
open, the tab processes must show `u:r:isolated_app` with `u0_i…` users and an
`org.redoubtbrowser.dev:rdd…` process as `untrusted_app`. The same signer as
the installed 2fa22e51 dev build, so `install -r` updates in place.
