# LW-M7-42: login fields inside open shadow roots reach Android Autofill

Branch `android/firefox-158` (local only), against Firefox 158.0b3. One agent
did this on the build host on 2026-10-05.

## The problem

reddit.com/login puts its username and password `<input>`s inside open shadow
roots (`faceplate-text-input`, `name=username autocomplete="username webauthn"`,
`name=password autocomplete=current-password`, no `<form>` owner). Android
password managers (Proton Pass, Bitwarden, KeePassDX, any `AutofillService`)
got nothing when one of them was focused. Stock Fenix 157 behaved the same.

The cause is in `mobile/shared/actors/GeckoViewAutoFillChild.sys.mjs`. It
registers fields with the app (the `Add` message that becomes the
`ViewStructure` an AutofillService sees) from three places:

- `DOMFormHasPassword` and `DOMInputPasswordAdded`. These events are not
  composed, so they never leave a shadow root.
- `scanDocument`. Its `querySelectorAll` stops at shadow roots.

`onFocus` only resolves fields that were registered there, plus upstream's
datalist fallback. A shadow-DOM login field was never registered, so no `Focus`
message went to Java and Android never sent a fill request.

## The change

`patches/android/autofill-shadow-dom.patch` touches one file, and the patch
header describes it in full. It adds one fallback to `onFocus`, next to the
datalist one. The fallback applies when the focused `<input>` is not
registered, sits in a shadow tree whose shadow roots are all open, and is a
login field. A login field means one of these:

- a password field;
- a username-type field that LoginHelper infers to be a username or email
  field;
- the field LoginManagerChild's `_getFormFields` picks as the username.

In that case the fallback builds a FormLike whose elements include every open
shadow root's fields under the field's root, and hands it to `addElement`.
`addElement` then runs LoginManagerChild's username heuristics over those
elements, because LoginManagerChild's own LoginForm only sees the light DOM.

These keep the upstream path:

- light-DOM fields (the fallback returns before doing anything);
- closed shadow roots and UA-widget roots (`Element.shadowRoot` is null for
  both);
- non-login inputs;
- null-principal documents.

The patch makes no network requests and adds no prefs.

`scanDocument` was left alone. Registering on focus is enough, because focus is
what triggers Android's fill request anyway.

## Gates (158.0b3, scratch copy with `version`/`version.android` = `158.0b3`)

| check | result |
|---|---|
| `check-patchfail.sh --targets=android` | exit 0; the new patch applies exactly; 8 hunks with fuzz overall, all in common entries, the same as PREBASE section 6 (`gates/`) |
| `check-patchfail.sh --targets=desktop` | exit 0; 30 hunks with fuzz, as before; the android list is not applied |
| `patch --dry-run --fuzz=0` on pristine 158.0b3 | clean. No other patch touches the file, so list order does not matter |
| `check-patch-order.py` | `patch order ok: 36/36 … 148 shared-file pair(s)` |
| `lint-patch-scope.py` | OK, 109 patch files |
| `board.py --check-scope` | `ok: 109 listed patch files — 22 common, 44 desktop, 43 android` |
| `board.py --check` | `ok: 125 tasks, 32 waves, 0 warning(s)` |

## Build (`build/`)

The build reused the PREBASE section 4/6 tree
`work/buildrepo/librewolf-158.0-1`, objdir `obj-x86_64`, image `fx158`
(`98e61be72eec`) and `MOZ_BUILD_DATE` 20261004120000. The patch was applied
there at `--fuzz=0`; the result is byte-identical to the patched file.
Script: `build/build-af.sh`.

- `android-fat-aar.sh --abis x86_64`. The per-ABI pass took 801 s (peak
  10.1 GB) and the merge pass 770 s. `obj-x86_64` was last configured by the
  merge pass, so `moz.configure` was touched first to make the per-ABI pass
  reconfigure with per-ABI substs. That reconfigure rebuilt part of the
  native code (801 s, against 2180 s for a clean pass). The run reports one
  `buildid.h` date, 20261004120000.
- The merged AAR's `omni.ja` and the APK's `assets/omni.ja` both carry
  `actors/GeckoViewAutoFillChild.sys.mjs`. In the APK it is sha256
  `71a3bb06…4bab`, the same bytes as the patched source file.
- `android-apk.sh --skip-gecko --update-check --variant release`:
  `BUILD SUCCESSFUL in 14m 1s`, and `:fenix:compileReleaseKotlin` ran with
  Kotlin `-Werror`. The patch changes no Kotlin, so the task was up to date.
  The script then exits 1 on the expected universal-APK ABI check for an
  x86_64-only build (PREBASE section 4). `libxul.so` is sha256-identical to
  the AAR input.
- The emulator APKs are signed with a throwaway key generated for this run
  (`CN=LW-M7-42 throwaway`, cert SHA-256 `9de4ab77…9113`) and are not
  distributable. Their hashes are in `build/SHA256SUMS.throwaway-signed`.
  For reference, the published Beta asset `fenix-x86_64-release.apk` passes
  `android-verify-signature.sh` against SIGNING.md's
  `64:14:EB:33:…:3B:D0`: v2 and v3 present, no v1.

The Fenix unit tests were not run: no Kotlin changed. No GeckoView test was
added either. `AutofillDelegateTest.kt` covers this actor, but it is a
`geckoview-junit` instrumented test, and nothing on this host runs that
harness. The pages in `www/` together with `emu-run.sh` are the test.

## Emulator (`emu/`)

The emulator was the API 34 `google_apis` x86_64 AVD from the investigation
(`pp-investigate/emu/avd/pp34`). The `AutofillService` was the investigation's
probe, `com.ppinv.af/.ProbeAutofill`. It logs every `onFillRequest` and dumps
the `AssistStructure` under tag `PPINV_AF`, offers one dataset, and fills
"ppinv" into every text node. Each build was installed fresh, so each run
started from a new profile.

The pages were served from `www/` by `python3 -m http.server 8642` and reached
through `adb reverse`. `emu-run.sh` drives one case: it loads the page, taps
the first field, then the second, then saves the probe log.

| case | 157.0-2 (unpatched) | 158.0b3 + patch |
|---|---|---|
| `plain.html`, light-DOM `<form>` (regression) | 1 fill request, 2 EditText (username/password hints) | **1 fill request, 2 EditText, same hints**: unchanged |
| `shadow-open.html`, reddit-like, open roots, no form | **0 fill requests** | **1 fill request**: `webDomain=localhost`; username `hints=[username] focused=true`, password `hints=[password]`, OTP `hints=[phone]` |
| same, password tapped first | not run | 1 fill request, same 3 nodes |
| same, tap the probe's suggestion | not run | all three shadow fields filled (`shadow-open-filled.jpg`) |
| `shadow-closed.html`, same markup, closed roots | not run | 0 fill requests; the field was focused (screenshot) |
| `shadow-nonlogin.html`, open-root search and one-time-code fields, no password | not run | 0 fill requests; both fields were focused (screenshots) |
| **https://www.reddit.com/login/** | not reachable cold (see below) | **1 fill request**: `webDomain=www.reddit.com webScheme=https`; `username` `hints=[username] focused=true`, `password` `hints=[password]`, `appOtp` `hints=[phone]`, and reddit's `g-recaptcha-response` textarea (`hints=null`) |

An empty `probe-*.txt` means the probe logged nothing in that window. That is
no fill request, and also no `onConnected`. Android only binds the service
when it has a request to make.

Android sends one fill request per autofill session, so tapping the second
field adds no second request, on either build.

### reddit.com/login on a cold profile

On a fresh profile, a direct load of `https://www.reddit.com/login/` stays
blank: reddit's JS interstitial never gets past its spinner page. This happens
on the unpatched 158 build (PREBASE run 4,
`emu/reddit-login-blank-cold-158-unpatched.jpg`) and on 157.0-2. Stock Fenix
157 on the same AVD renders it, so this patch does not cause it. After a visit
to `https://www.reddit.com/` the login page rendered, and that is the row
above. Not investigated further.

## Known limit

Suppose a page also has a formless light-DOM password field, and upstream's
events register it after the fallback did. Upstream then re-sends the
document root with its light-DOM element list, and the app's structure can
lose the shadow fields for that page. No tested page showed this.
