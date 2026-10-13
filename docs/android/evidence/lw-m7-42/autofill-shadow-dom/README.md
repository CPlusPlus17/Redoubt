# LW-M7-42: login fields inside open shadow roots reach Android Autofill

Branch `android/firefox-158` (local only), against Firefox 158.0b3. One agent
did this on the build host on 2026-10-05. A follow-up the same day, after an
independent review, narrowed which fields count as login fields (see
"Follow-up: narrowed to forms with a password field" below); everything below
describes the narrowed patch unless it says otherwise.

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

- a password field (`hasBeenTypePassword`);
- a username-type field whose shadow-inclusive FormLike (below) contains a
  password field, and which LoginHelper infers to be a username or email
  field, or which LoginManagerChild's `_getFormFields` picks as the username.

The fallback builds a FormLike rooted where FormLikeFactory would root it (the
closest `<form>` across shadow hosts, else the document element). Its elements
include every open shadow root's fields under that root. It gets the
factory's `toJSON` (`FormLikeFactory._addToJSONProperty`), so logging it does
not dump DOM objects. If the focused field is not a password field and the
element list holds no password field, the fallback returns there, before any
username heuristic runs. Otherwise the FormLike goes to `addElement`, and
`addElement` runs LoginManagerChild's username heuristics over those
elements, because LoginManagerChild's own LoginForm only sees the light DOM.

The password requirement matches upstream. Upstream registers a light-DOM
form only through `DOMFormHasPassword` / `DOMInputPasswordAdded`, that is,
only when it holds a password field. The FormLike's own element list is what
gets checked; for a field owned by a `<form>` inside a shadow root, that list
is `form.elements`.

These keep the upstream path:

- light-DOM fields (the fallback returns before doing anything);
- closed shadow roots and UA-widget roots (`Element.shadowRoot` is null for
  both);
- non-login inputs: search, one-time-code, and email or text fields whose
  FormLike holds no password field (newsletter, checkout);
- null-principal documents.

The patch makes no network requests and adds no prefs.

`scanDocument` was left alone. Registering on focus is enough, because focus is
what triggers Android's fill request anyway.

reddit.com/login still qualifies. Its username, password, `appOtp` and
`backupOtp` inputs each sit in their own open `faceplate-text-input` shadow
root with no `<form>` owner
(`pp-investigate/emu/reddit-dom-inputs.json`), so the FormLike is rooted at
the document element and its element list holds the password input.

## Follow-up: narrowed to forms with a password field

The first version (commit `c09247b8`) accepted any username-type field that
`LoginHelper.isInferredUsernameField` or `isInferredEmailField` matched, with
or without a password field near it. `isInferredEmailField` is true for every
`type=email` input and for any field with "email" in an attribute or label.
So a newsletter or checkout email field in an open shadow root, on a page with
no password field, produced a fill request. Upstream never registers such a
field in the light DOM. The follow-up adds the password check described
above, adds the `toJSON`, and adds `www/shadow-email-only.html` (below).

## Gates (158.0b3, scratch copy with `version`/`version.android` = `158.0b3`)

Re-run on the narrowed patch.

| check | result |
|---|---|
| `check-patchfail.sh --targets=android` | exit 0; the new patch applies exactly; 8 hunks with fuzz overall, all in common entries, the same as PREBASE section 6 (`gates/`) |
| `check-patchfail.sh --targets=desktop` | exit 0; 30 hunks with fuzz, as before; the android list is not applied |
| `patch --fuzz=0` on pristine 158.0b3 | clean. The result is byte-identical to the build tree's file (sha256 `8e799ac0…c03a`). No other patch touches the file, so list order does not matter |
| `check-patch-order.py` | `patch order ok: 36/36 … 148 shared-file pair(s)` |
| `lint-patch-scope.py` | OK, 109 patch files |
| `board.py --check-scope` | `ok: 109 listed patch files — 22 common, 44 desktop, 43 android` |
| `board.py --check` | `ok: 125 tasks, 32 waves, 0 warning(s)` |

## Build (`build/`)

The build reused the PREBASE section 4/6 tree
`work/buildrepo/librewolf-158.0-1`, objdir `obj-x86_64`, image `fx158`
(`98e61be72eec`) and `MOZ_BUILD_DATE` 20261004120000. Script:
`build/build-af.sh`, unchanged from the first build. The narrowed file was
written into that tree; it equals pristine 158.0b3 plus the patch at
`--fuzz=0`.

- `android-fat-aar.sh --abis x86_64`: per-ABI pass 856 s (peak 9.4 GB),
  merge pass 1158 s (`build/fat-aar-build-times.txt`). The logs carry one
  build date, 20261004120000.
- The merged AAR's `omni.ja` and the APK's `assets/omni.ja` both carry
  `actors/GeckoViewAutoFillChild.sys.mjs` with sha256 `8e799ac0…c03a`, the
  same bytes as the patched source file.
- `android-apk.sh --skip-gecko --update-check --variant release`:
  `BUILD SUCCESSFUL in 1m 26s`; `:fenix:compileReleaseKotlin` was up to date
  (no Kotlin changed; `build/apk-gradle.txt`). The script then exits 1 on the
  expected universal-APK ABI check for an x86_64-only build (PREBASE section
  4). `libxul.so` is sha256-identical to the AAR input. Unsigned hashes:
  `build/SHA256SUMS.apk`.
- The emulator APKs are signed with the throwaway key
  `keep/throwaway-keys/throwaway.p12` (`CN=Redoubt throwaway test key
  2026-10-02, O=NOT A RELEASE KEY`, cert SHA-256 `31e9a40f…b760`, apksigner
  36.0.0) and are not distributable. Their hashes are in
  `build/SHA256SUMS.throwaway-signed`, and each run directory under `emu/`
  has an `installed-apk.txt` with the host hash and the hash of the
  `base.apk` read back from the device after install.
- The first build's hashes (a run-local throwaway key,
  `CN=LW-M7-42 throwaway`) are kept in `build/*.c09247b8`.

The Fenix unit tests were not run: no Kotlin changed. No GeckoView test was
added either. `AutofillDelegateTest.kt` covers this actor, but it is a
`geckoview-junit` instrumented test, and nothing on this host runs that
harness. The pages in `www/` together with `emu-run.sh` are the test.

## Emulator (`emu/`)

The emulator was the API 34 `google_apis` x86_64 AVD from the investigation
(`pp-investigate/emu/avd/pp34`), headless. The `AutofillService` was the
investigation's probe, `com.ppinv.af/.ProbeAutofill`. It logs every
`onFillRequest` and dumps the `AssistStructure` under tag `PPINV_AF`, offers
one dataset, and fills "ppinv" into every text node.

`emu-install.sh <apk> <outdir>` uninstalls `org.redoubtbrowser`, installs the
APK (so each build starts from a new profile), writes `installed-apk.txt`,
sets up `adb reverse tcp:8642`, and dismisses the first-run uBlock Origin
sheet. The pages were served from `www/` by `python3 -m http.server 8642`.
`emu-run.sh` drives one case: it loads the page, taps the first field, then
the second, then saves the probe log.

Android keeps one autofill session per activity and reuses its response, so a
page opened in the same activity after a fill request can show the probe's
suggestion without a new `onFillRequest`. The narrowed runs therefore ran
`am force-stop org.redoubtbrowser` before each case (fresh activity, fresh
session), with the negative cases first and the positive ones after them, so
a 0 cannot come from a reused session:

```
for c in shadow-email-only shadow-nonlogin shadow-closed shadow-open plain shadow-email-only; do
  adb shell am force-stop org.redoubtbrowser; sleep 2
  LOAD_WAIT=15 ./emu-run.sh <label> http://localhost:8642/$c.html <outdir>
done
```

reddit.com/login was run the same way by hand: force-stop, load
`https://www.reddit.com/`, wait 35 s, load `https://www.reddit.com/login/`,
wait 25 s, tap "Email or username" (540,1426).

### Narrowed patch, `emu/after-narrowed/` (APK `4d4c123a…1d07`)

| case | fill requests | notes |
|---|---|---|
| `plain.html`, light-DOM `<form>` (regression) | **1** | 2 EditText, `hints=[username]` / `[password]`: unchanged |
| `shadow-open.html`, reddit-like, open roots, no form | **1** | `webDomain=localhost`; username `hints=[username] focused=true`, password `hints=[password]`, OTP `hints=[phone]` |
| `shadow-closed.html`, same markup, closed roots | **0** | field focused |
| `shadow-nonlogin.html`, open-root search and one-time-code, no password | **0** | both fields focused |
| `shadow-email-only.html`, newsletter (formless) and checkout (`<form>` inside the shadow root) `type=email autocomplete=email`, open roots, no password | **0**, twice (first and last case) | both fields focused (`shadow-email-only-*-focus.jpg`), no suggestion shown |
| **https://www.reddit.com/login/** (after `reddit.com/`) | **1** | `webDomain=www.reddit.com webScheme=https`; username `hints=[username] focused=true`, password `hints=[password]`, `appOtp` `hints=[phone]`, `g-recaptcha-response` textarea `hints=null` |

`emu/after-narrowed/first-pass-no-restart/` is the same install run through
the local pages in one activity without force-stop: plain 1, shadow-open 1,
closed 0, non-login 0, email-only 0. A shadow-open re-run at the end logged no
new `onFillRequest` but showed the probe's suggestion
(`shadow-open-recheck-cached-suggestion.jpg`): the field was registered, and
Android served it from the session's earlier response. That is why the main
table uses force-stop.

### Unpatched 158.0b3, `emu/unpatched-158.0b3/` (APK `a8419fce…b576`)

The PREBASE run 4 APK (`work/build/apk4`, unsigned `8e3840f9…d249`), re-signed
with the same throwaway key. Its `omni.ja` actor is byte-identical to pristine
158.0b3 (`9197a7b4…8156`). Same AVD, same probe, fresh install.

| case | fill requests |
|---|---|
| `plain.html` (probe positive control) | 1 |
| `shadow-open.html` | **0**; the username field was focused (`shadow-open-username-focus.jpg`) |
| `shadow-email-only.html` | 0 |

This closes the gap in the first run, whose "before" column was 157.0-2
only: unpatched 158.0b3 also produces no fill request for the open-shadow
login.

### First build (c09247b8), `emu/after-c09247b8/` and `emu/before-157.0-2/`

| case | 157.0-2 (unpatched) | 158.0b3 + first patch |
|---|---|---|
| `plain.html` | 1 fill request, 2 EditText | 1 fill request, same hints |
| `shadow-open.html` | **0** | **1**; also 1 with the password tapped first, and tapping the suggestion filled all three shadow fields (`shadow-open-filled.jpg`) |
| `shadow-closed.html` | not run | 0 |
| `shadow-nonlogin.html` | not run | 0 |
| reddit.com/login | not reachable cold (see below) | 1 |

`shadow-email-only.html` did not exist then. By the code, the first patch
registered both of its fields, which is the defect the follow-up fixes.

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
to `https://www.reddit.com/` the login page renders. Not investigated further.

## Known limit

Suppose a page also has a formless light-DOM password field, and upstream's
events register it after the fallback did. Upstream then re-sends the
document root with its light-DOM element list, and the app's structure can
lose the shadow fields for that page. No tested page showed this.

The password check uses `hasBeenTypePassword`, as LoginManagerChild does, so a
password field that a "show password" toggle has switched to `type=text`
still counts.
