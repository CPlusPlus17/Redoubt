# LW-M7-46: no notice for WebGL and canvas blocked by default

Branch `fix/webgl-quiet-notice`, based on the local `android/firefox-158`
(`586b310e`). It targets **158.0-2**, not 158.0-1. Nothing was pushed.

**Update 2026-10-09 (owner decision, verbatim: "Beta 2 from the RC now"):**
merged into the local `android/firefox-158` as `cebb03c6`; it ships in the
158.0-1 Beta 2 prerelease built from the 158.0 RC and in the final 158.0-1,
not in 158.0-2. See `../lw-m7-01/release-158.0/PREBASE.md` section 11. The
device notes below (`158.0-2-default`) describe the test build only.

## Request

Owner, 2026-10-09, verbatim: "the disabled webgl popovers all the time, we
disabled it be choice, so do not show this warning".

Before this change, a WebGL or canvas attempt that is blocked by default
(a *quiet* request, `librewolf.webgl.prompt.hide=true`) made Fenix show
the snackbar "Canvas or WebGL was protected. Review in site permissions." on
every page that tried. The screenshot from a 158.0b4 build without this change
is `device/negative-158b4-lw-m7-45/old-notice.png`.

## Change (in `patches/android/canvas-webgl-permissions.patch`)

- `OriginBoundPermissionsFeature` has a new parameter,
  `quietNoticeEnabled: suspend () -> Boolean`, which defaults to `{ false }`.
  For a quiet request, the feature calls `onQuietRequest` (the snackbar) only
  when that returns true **and** the request is still pending. Non-quiet
  requests still call `onPromptRequest` directly, as before.
- `readQuietNoticePref(engine)` reads the Gecko pref
  `librewolf.webgl.prompt.notice` through `Engine.getBrowserPref` for each
  request. Only a boolean `true` turns the notice on. A missing pref, any
  other type, or an error counts as false.
- `StaticPrefList.yaml`: `librewolf.webgl.prompt.notice`, `bool`, default
  `false`, `mirror: never`. Setting it to `true` in about:config brings the
  notice back.
- `BaseBrowserFragment.kt` passes the pref reader. Its hunk keeps the same
  line count (the `shouldHide` lambda is now one line), so `sync-opt-in.patch`
  still applies at the same offsets.
- Nothing else in a quiet request changed. It is denied, and it stays pending
  and listed in the site controls (trust panel, "Canvas and WebGL
  permissions", "WebGL blocked ... Review request") until the page goes away.
  Then it is consumed and rejected, as before.

`settings/` is unchanged. The pref default lives in Gecko, so `android.cfg`
does not need it.

## Unit tests (`OriginBoundPermissionsFeatureTest`, 12 tests, 0 failures)

Results are in `build/TEST-org.mozilla.fenix.browser.permissions.*.xml`.
`OriginBoundPermissionsDialogFragmentTest` also passes, 9 of 9. The tests
that are new or changed:

- `quiet request shows no notice by default and stays pending until its page goes away`:
  this is the default (pref false). There is no notice and no modal, and the
  request stays in the tab's list with no decision and no rejection. When it
  is invalidated (`applied=false`), it is consumed and rejected exactly once,
  so the pending request does not leak.
- `quiet notice pref true offers the old notice ...`: this is the old
  behaviour. There is one notice and no modal, and stopping the feature keeps
  the request actionable.
- `stopping before the pref answers shows no notice ...` and
  `a quiet request consumed before the pref answers gets no notice`.
- `the notice pref is on only for a boolean true`: covers true, false, the
  string "true", a missing pref (INVALID/null), an error callback, and an
  engine without pref support.
- `nonquiet request opens one prompt ...` is unchanged and passes.

## Build

The build used 158.0b4 bytes (tarball sha256 `6e8c1788...`) in the
release-day layout (`version` 158.0, `release.android` 2, scratch copy only).
It was an x86_64 fat AAR plus a release APK in image `98e61be72eec`, with
`-Werror`. `:fenix:compileReleaseKotlin` and the build passed. The single-ABI
universal APK check exits 1, as expected. The APK was signed with the
throwaway key. The commands, and the sha256 of the unsigned and signed APKs,
are in `build/`. The built patch sha256 is `27243749bfcc844a...`, the same
file as the one committed.

## Gates (`gates/`)

| Gate | Result |
| --- | --- |
| `check-patchfail.sh --targets=android` on 158.0b4 | success, exit 0 |
| `check-patchfail.sh --targets=android` on 158.0 build2 (`rel158/build2`, GPG-verified tarball) | success, exit 0 |
| `check-patch-order.py` | ok, 38/38 |
| `lint-patch-scope.py` | OK, 110 patch files |
| `board.py --check` / `--check-scope` / `--check-cfg-split` | ok / ok (android 44, total 110) / ok |
| `scripts/tests/test-android-graphics-smoke.py` | 32 tests OK |
| `scripts/tests/test-android-smoke.py` | 96 tests OK |
| `evidence/lw-m7-18/test-android-graphics-smoke.py` | 38 tests OK |

`--fuzz=0` replays fail on both tarballs, but not because of this change.
The common `webgl-permission-common.patch` already fails `StaticPrefList.yaml`
at fuzz 0, and the Android WebGL hunks after it fail in turn. In the real
in-order apply (`make android-dir`), this patch applies to every file with no
fuzz and no offset in `StaticPrefList.yaml`.

`docs/android/evidence/lw-m7-28/test-addon-state-smoke.py` has one error
(`test_stop_is_first_command_after_completion_xml_before_artifacts`,
StopIteration in `input_windows`). That error is on `586b310e` too, without
this change. The notice check is opt-in (`UI.forbid_quiet_notice`, which only
the graphics Runner sets), so the add-on harness behaves as before.

## Harness

- `scripts/android-graphics-smoke.py`:
  - `facts()` requires `librewolf.webgl.prompt.notice` to be `false`.
  - Every uiautomator dump fails if the snackbar text or its `Review` action
    (`snackbar_action`) is on screen.
  - The quiet-Review tap path (`quiet_review`) is gone. The permissions are
    always opened through the site controls, which is also how users reach
    them.
  - New checks: `quiet-no-notice` and
    `no-quiet-notice-in-normal-and-private-tabs`. The second counts the dumps
    per tab kind, and both counts must be non-zero. They replace
    `quiet-review-opens-permissions-in-normal-and-private-tabs`.
- `scripts/android-smoke.sh` `PREF_LIST` and `docs/android/expected-prefs.txt`
  gain `librewolf.webgl.prompt.notice bool false`.

## Device

**API 34** (`device/api34/`): emulator `sdk_gphone64_x86_64`, Android 14,
google_apis, swangle. The installed app reports `versionName=158.0-2-default`.

| Step | Result | File |
| --- | --- | --- |
| `http://127.0.0.1:8466/webgl.html`, dumps at 1 to 6 s | `webgl=NULL webgl2=NULL`, no snackbar in any dump | `02-webgl-2.png/.xml` |
| trust panel, then "Canvas and WebGL permissions" | lists "WebGL blocked — http://127.0.0.1:8466 / Review request" | `04-permissions-list.*` |
| Allow (session) | the page reloads; the list shows "WebGL — Allowed · This browser session" | `05-decision.*`, `06-after-allow.*` |
| after the allow | `webgl=CONTEXT webgl2=CONTEXT`; the `readPixels` value is randomized (`120,23,179,24` for a cleared green), because canvas readback is still not allowed; no snackbar | `08-webgl-allowed-page.*` |
| `http://localhost:8466/canvas.html`, dumps at 1 to 6 s | `readback=PROTECTED`, no snackbar | `09-canvas-2.*` |

The graphics acceptance harness cannot run on API 34.
`dumpsys input` there uses a different window format, and the tap guard
reports "No org.redoubtbrowser window is in the input dispatcher's window
list" (`harness-on-api34-not-supported.txt`). This was already the case
before LW-M7-46: the harness was written for, and release acceptance runs on,
the android-30 `default` image.

**API 30** (`device/api30-smoke/`), android-30 `default` x86_64, swangle:
`android-smoke.sh --serial` baseline, **10 of 10 PASS, exit 0**. The graphics
acceptance passed with `acceptanceComplete: true` and **162 checks**,
including `quiet-no-notice` and
`no-quiet-notice-in-normal-and-private-tabs`. That last check ran 190
normal-tab dumps and 28 private-tab dumps with no notice in any of them. The
consent, revoke, lifetime (process restart), private and frame stages all
pass through the site controls. The pref dump (`prefs.txt`, 59 prefs) matches
`expected-prefs.txt` exactly.

**Negative control** (`device/negative-158b4-lw-m7-45/`): the APK is the
158.0b4 LW-M7-45 build without this change (sha256 `860056ba...`, from
`delete-on-quit/build158b`), on the same API 30 emulator. Opening the WebGL
page shows the snackbar, and the harness's `quiet_notice_present()` returns
True for that dump and False for the new build's dump (`02-webgl-2.xml`).

## Not tested on a device

Setting `librewolf.webgl.prompt.notice=true` in about:config. The pref-true
path is covered only by the unit test.
