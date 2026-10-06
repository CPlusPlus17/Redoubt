# The Android smoke-test harness

**Owner: LW-M2-07.** The script is `scripts/android-smoke.sh`.

`docs/android/AGENTS.md` says a task is not done, from M2 onward, until
`./scripts/android-smoke.sh` is green. This file says what "green" actually
means: what each check proves, what it deliberately does **not** prove, and how
to add one without turning a gate into decoration.

The premise, from the same file: *"It builds" is not done. "It launched" is not
done — see landmine L1.* A build with `librewolf.webgl.prompt` compiled as
`true` installs, browses, plays video and passes every naive gate, while every
WebGL context in the browser is dead, silently, with no crash and no console
error. The whole harness exists so that build fails.

---

## Quick start

```sh
./scripts/android-smoke.sh --emulator          # the M2 gate. exit 0 = green.
```

That boots a headless x86_64 emulator with packet capture, installs the APK,
wipes the app's data, runs the ten baseline checks and kills the emulator
again. Runtime depends on the host, nested virtualization and candidate startup.

Against an emulator or device you already have running:

```sh
./scripts/android-smoke.sh --serial emulator-5554
```

### Requirements

| | |
|---|---|
| host | `python3` >= 3.8, `openssl`, an Android SDK with `platform-tools` (and `emulator` + an x86_64 system image for `--emulator`) |
| APK | a debug or release-configured build; the harness temporarily names a release package as the debug app to enable Gecko's test connection, then clears that setting |
| device | an emulator, for anything involving the network capture |

The SDK is found from `--sdk`, then `$ANDROID_SDK_ROOT`, `$ANDROID_HOME`, then
`~/Android/Sdk`. The APK from `--apk`, `$LW_SMOKE_APK`, `$LW_SMOKE_APK_DIR`, then
the directory `make android-package` writes — `librewolf-android-apk-<version.android>-<release.android>/apk`,
in the repository and beside it — and `$REPO/out/apk`, preferring `--abi`
(default `x86_64`). Neither list names anyone's scratch directory any more; both
did, and both pointed at paths that had been deleted. The applicationId is read from the `output-metadata.json`
Gradle writes next to the APK — never guessed — and the harness verifies the
package is really present after `adb install` before it continues.

Work directory: `$LW_SMOKE_WORK`, default `~/.cache/librewolf-android-smoke`.
It holds the AVD, the emulator log, `capture.pcap`, `prefs.txt`,
`prefs-all.json` and `result.json`. Nothing is written inside the repo. The AVD
is created on first use and reused afterwards, which is what keeps a cold
`--emulator` run down to half a minute; delete
`$LW_SMOKE_WORK/avd` to start from a factory image again. App state is wiped
(`pm clear`) at the start of every run regardless, unless `--keep-state`.

The local origin binds to `127.0.0.1` only — the emulator's user-mode network
maps `10.0.2.2` to the host's loopback, so nothing is published to the LAN.

---

## The exit-code contract

| code | meaning |
|---|---|
| 0 | every requested check passed |
| 1 | a check **failed** — a real defect in the build under test |
| 2 | the harness could not run: missing tool, no device, no APK, no capture |
| 3 | the flag is recognised but **not implemented** — never a pass |

Codes 2 and 3 exist so that "the check did not happen" can never be mistaken
for "the check passed". A missing `adb`, an emulator that was started without
`-tcpdump`, or a `--check-*` nobody has written yet all stop the run loudly.

**Watch out for pipelines.** Several `verify:` lines in `tasks.yaml` are of the
form

```sh
./scripts/android-smoke.sh --network-capture | grep -c telemetry.mozilla.org
```

In a pipeline `$?` is *grep's* status, so the harness's exit code is discarded.
The harness compensates as far as it can — when it cannot capture it writes
**nothing** to stdout, so the grep has nothing to match on — but if you are
wiring this into CI, use `set -o pipefail`, or run the harness and the grep as
two steps.

Everything human-readable goes to **stderr**. stdout carries only the payload:
the pref dump, or the capture table. That is what makes
`--pref-dump | diff - docs/android/expected-prefs.txt` (LW-M3-05) work.

---

## How it works

Four independent channels, chosen so that no check has to trust the thing it
is testing.

### First-navigation uBlock Origin checks

`--check-ubo-preinstall` now opens a real fixture as the first incoming URL of
an empty app profile. Its HTML immediately loads two scripts: one matches an
exact rule verified in the APK's bundled EasyList, and one is an allowed control.
The gate requires the completed page, execution of the allowed script, and the
origin server's request log. A late registry entry cannot erase an earlier leaked
request. The installed add-on must also be the pinned ordinary AMO-signed uBO.

`--check-ubo-lifecycle` adds a negative control by disabling uBO through the real
AddonManager API and requiring both scripts to execute and reach the server.
It then checks disabled-state retention across a restart, removal across another
restart, and removal across reinstallation of the same APK. These operations
exercise Gecko's add-on state; they do not prove Fenix's extension controls,
private-mode controls, or an upgrade to a different APK version. Those require
separate runs and evidence. Both flags refuse `--keep-state` because their first
phase requires an empty app profile.

`--check-ubo-user-disable` (LW-M7-44) runs two phases. Each phase provisions an
empty profile with a first navigation, then cold-starts on a held fixture URL. As
soon as Marionette attaches, it changes uBO through the real AddonManager API while
the preinstaller is still waiting for filter readiness. A fresh profile is needed
each time because only uBO's first restart is slow enough. On API 34 a later
restart was ready after 1.8 s, before Marionette attached. The first start is a control: `addon.reload()`, which is what a
private-browsing permission change does, must still show the setup-failure dialog,
and the held page must never reach the origin. The second start calls
`addon.disable()`, which is what Settings > Add-ons does. It must log the
user-disabled readiness line and show no dialog, and the held page must load
unfiltered. If the preinstaller was already ready before the change, the phase
fails as a missed window, never as a pass. The check refuses `--keep-state`.

The fixture uses `adb reverse` and Android loopback (`127.0.0.1`). Gecko exempts
loopback from HTTPS-only in `nsHTTPSOnlyUtils::LoopbackOrLocalException`, so the
first page needs neither a seeded certificate store nor changed browser prefs.
The reverse mapping is removed when the probe finishes. This measures filtering
of a same-origin script, not an external tracker or every resource type.

Results include the exact APK digest and size, the harness digest when its source
is available, the packaged XPI pin and hash, the filter file hash and matching
rule, the installed add-on's signature state, the DOM observations, and origin
requests. The gate never adds test filters or installs a test uBO extension.
Runtime evidence is still required before claiming that a candidate passes.

### Launcher cold start: `--check-launcher-start`

Every other device check starts the app with a URL (`App.start_url`), because
Marionette's NewSession needs a Gecko window and the Fenix home screen is not
one. That made one startup path invisible: a VIEW intent goes through
`IntentReceiverActivity`, which opens a speculative GeckoSession, and that
window's `extensions-late-startup` notification is what releases Gecko's delayed
background-page startup. A launcher start opens no window — the uBO session
middleware holds every tab until uBO is ready — so on Beta 2 and the first
153.4 candidate uBO's background page never started and every launcher cold
start after the first showed "uBlock Origin setup failed" exactly 30 s in, while
every harness run (URL-started) was green.

`--check-launcher-start` wipes the profile, then twice (fresh profile, then a
restart) force-stops the app, clears logcat, starts the package manager's
resolved launcher activity (`am start -a MAIN -c LAUNCHER -f 0x10200000 -n
<pkg>/.App`, as a home-screen tap does), waits 45 s (past the preinstaller's 30 s
timeout), and requires: no failure dialog in a `uiautomator` dump, no
`uBlock Origin startup failed` log line, a positive `uBlock Origin startup ready:
Ready(installed=true, enabled=true)` line, and a live process. Silence is not a
pass. It uses no Marionette and no debug config. With AMO reachable the first
phase also exercises an add-on update racing first-run readiness whenever AMO
serves a newer uBO than the pin. The UI dump and logcat of each phase are kept
in the work directory as `launcher-start-<phase>-*`.

### Delete on quit after a swipe: `--check-delete-on-quit` (LW-M7-45)

"Delete browsing data on quit" used to run only from the menu's Quit item; a
recents swipe left the data and the next start restored it. The check needs a
rootable image (`adb root`): it writes the app's `fenix_preferences.xml` and
reads its session file. Two phases on one install: with the setting on (all six
categories) and then off, it opens two tabs, waits until the session file holds
both, swipes the task away with the real recents gesture, cold starts from the
launcher and waits 20 s. On: PASS needs a completed deletion -- the guard's
start-up one (`cold start after unclean exit` ... `deletion complete`, before any
`RestoreAction`), or `onTaskRemoved`'s (`task-removed: deletion confirmed`) when
the swipe left the process alive -- and no saved tab afterwards. Off: no start-up
deletion, the guard's `setting off` line, and both tabs restored. Whether
`onTaskRemoved` fired and finished is recorded per phase, not graded. On
2026-10-06 it PASSED on the LW-M7-45 build and FAILED on Beta 5 (2 tabs restored
after the swipe), on the API 34 x86_64 emulator
(`evidence/lw-m7-45/harness/`). Logcat of each phase is kept in the work
directory as `delete-on-quit-<phase>-*`.

`--check-https-only` exercises the new default and is also part of the baseline
page-load suite. HTTP to the local non-loopback fixture must show the browser's
HTTPS-only interstitial. The test uses its actual Continue button, then requires
the HTTP page to load; valid HTTPS must also load with a real trusted throwaway
chain. A generic network error, a pref value alone, a hidden button, or a page
loaded before the exception cannot pass. Normal smoke sessions bootstrap over
ADB loopback before trusting the fixture CA, without changing HTTPS-only prefs.

`--keep-state` now refuses to uninstall an incompatible existing app when APK
installation fails. This preserves the state whose retention the caller intends
to test instead of silently turning the run into a fresh installation.

### 1. Marionette, over GeckoView's debug config

`GeckoRuntime.java:499-526` reads a YAML file at
`/data/local/tmp/<applicationId>-geckoview-config.yaml` whenever the app is
debuggable, and `DebugConfig.java` turns its three keys into Gecko's command
line, its environment and its startup prefs. The harness writes:

```yaml
args:  ["-remote-allow-system-access"]
env:   {MOZ_MARIONETTE: "1"}
prefs: {remote.prefs.recommended: false, marionette.port: 2828}
```

`MOZ_MARIONETTE` starts the Marionette server (`Marionette.sys.mjs:29`), which
is present in our APK's `omni.ja` — `ENABLE_WEBDRIVER` is on for this build, so
`chrome://remote/content/marionette/*` ships. `adb forward` reaches port 2828
and the harness speaks the protocol directly; there is no geckodriver, no
Selenium and no Python dependency.

Two details that are not optional:

- **`-remote-allow-system-access`.** Without it `Marionette:SetContext chrome`
  is refused (`Assert.sys.mjs:130`) and none of the pref, add-on or certificate
  work is possible.
- **`remote.prefs.recommended: false`.** Marionette otherwise applies
  `RecommendedPreferences.COMMON_PREFERENCES` at startup
  (`Marionette.sys.mjs:142`), which rewrites a pile of network and safebrowsing
  prefs. That would poison the pref dump and the network capture — the harness
  would be measuring itself. `RecommendedPreferences.sys.mjs:443-448` returns
  early when the pref is false.

The only prefs the harness sets are those two. `HARNESS_SET_PREFS` in the
script names them, and `--pref-dump` refuses to run if either ever appears in
the dump list — so the dump cannot silently start reporting the harness's own
configuration.

**Debuggable, or named as the debug app.** `GeckoRuntime.java:509` reads that
file when the app is `FLAG_DEBUGGABLE` **or** when it is the package named in
`Settings.Global.DEBUG_APP` (`isApplicationCurrentDebugApp`, `:603-609`). This
paragraph used to say a release-configured APK "cannot be driven this way";
that is measured to be **wrong**, and it is what left `--check-aboutconfig`
with no runnable path for a milestone. `push_debug_config()` now runs
`am set-debug-app --persistent <pkg>` whenever the installed package is not
debuggable, and `remove_debug_config()` clears it again from `main()`'s
`finally`.

That door does **not** soften the build under test: `dumpsys package` still
reports `flags=[ HAS_CODE ALLOW_CLEAR_USER_DATA ]` with no `DEBUGGABLE`,
`run-as` still refuses, `Config.channel` and the build type are untouched, and
the applicationId is still the release one. It only makes Gecko read the YAML.
The M2 baseline gate is still normally run against the debug APK; what changed
is that a release-configured APK is now drivable when a check needs one, which
`--check-aboutconfig` does by definition.

### 2. A local origin, over http and https

The harness serves one probe page from the host on two throwaway ports; the
emulator reaches it at `10.0.2.2`. Every request is logged, so "the page
loaded" is corroborated from both ends: the browser reports
`document.readyState` and the marker element, and the server reports that it
actually served the bytes.

For https it mints a throwaway CA and a leaf for `IP:10.0.2.2` with `openssl`,
and adds the CA to the profile's certificate database from chrome context
(`nsIX509CertDB.addCertFromBase64`). The chain is then **genuinely validated** —
`acceptInsecureCerts` stays `false` and the page reports
`window.isSecureContext === true`. This is deliberately not the
`acceptInsecureCerts` shortcut, which would prove only that the certificate
error page can be skipped. The CA is deleted from the profile at the end of the
run, and the profile is wiped at the start of the next one.

### 3. The emulator's own packet capture

`emulator -tcpdump` writes a pcap at the virtual NIC. That is *below* the
guest: an app cannot evade it, proxy around it or opt out of it. The harness
parses the pcap itself (DNS question names, TLS ClientHello SNI, plaintext HTTP
`Host:`), records the file offset at the start of a window and reads only what
was appended.

The capture contains **both directions**, so events are filtered to those whose
source is one of the device's own IPv4 addresses, read from `ip -o -4 addr` on
the device at capture time. Skipping that step counts every DNS *reply* as an
outbound request — it inflated an early first-run measurement from 53 events to
92.

Alongside it the harness reads the kernel's per-uid byte counters
(`dumpsys netstats detail --uid`) before and after the window. The pcap says
*which hosts*; the uid counters say *whether it was our app*. The two have to
agree, and in the recorded first-run measurement they did: 53 non-OS events and
`rx+4,850,317 tx+137,766` bytes on the app's uid.

### 4. The APK itself

`--check-no-gms` and `--check-no-adjust` read the **DEX `string_ids` table** of
every `classes*.dex` in the APK, not `grep` over the file and certainly not over
the sources. A hit is a real string constant in the compiled app.

---

## The checks

`./scripts/android-smoke.sh` with no `--check-*` flag runs the baseline suite.
These are the checks that must stay green from M2 onward.

### `page-load-http` / `page-load-https`

**Proves:** a real top-level navigation completes, JS runs in the page, the
document reaches `readyState === "complete"`, the expected element is in the
DOM, the origin server logged the request, and for https that the TLS handshake
and **certificate chain validation** succeeded and the page is a secure
context.

**Does not prove:** anything about the public internet, DNS, HSTS, HTTP/2 or
HTTP/3. The origin is on the host, and its CA was trusted for the profile.
Point `--https-url`-style testing at a public site by hand if you need that.

### `webgl` — the L1 canary

**Proves:** `librewolf.webgl.prompt` exists and is `false` (read from chrome
context in the running app), *and* that a WebGL context can be created, a
vertex and fragment shader compiled and linked, a triangle drawn and the
resulting pixel read back with `readPixels`. The expected value is
`[51, 102, 153, 255]` — `vec4(0.2, 0.4, 0.6, 1.0)` rounded — so the whole
pipeline from shader compilation to framebuffer readback has to have run.

**Does not prove:** that the pixel reached the screen, or anything about GPU
process sandboxing or hardware acceleration. The emulator renders with
SwiftShader; the check is about whether Gecko lets WebGL work at all, which is
what L1 is about.

**Diagnosis.** If the pref is `true` the failure message says so and names L1
explicitly. If the pref is `false` and the pixel is still wrong, the message
says the cause is the GL stack under the emulator, not L1. The
`webglcontextcreationerror` `statusMessage` is captured and reported either way.

**This check has been proven to fire.** See "proving a check can fail" below.

### `video`, `video-h264`, `video-mse`

Also runnable alone: `--check-video` (the same three rows, nothing else).

**Proves:** the media stack demuxes and decodes, through both decoder paths
Gecko has on Android.

- `video`: a 64x64 VP8 + Opus WebM. ffvpx decodes it **inside the content
  process**.
- `video-h264`: a 64x64 H.264 Constrained Baseline + AAC-LC progressive MP4
  played from `<video src>`. H.264 and AAC need **Android MediaCodec**.
- `video-mse`: `MediaSource.isTypeSupported('video/mp4;
  codecs="avc1.42E01E,mp4a.40.2"')` must be `true`, `addSourceBuffer()` with
  that type must succeed, and a fragmented MP4 of the same H.264 + AAC content,
  fetched and appended in one `appendBuffer()`, must play. This is the path
  hls.js, dash.js and most site players use.

The two `<video src>` rows must each reach `readyState >= 3`, advance
`currentTime` by more than 0.25 s and report at least 4 frames through
`getVideoPlaybackQuality().totalVideoFrames`, with `video.error === null`. The
MSE row requires `readyState >= 2`, the same clock advance and 4 frames. A media
error ends a probe at once instead of after the 30 s timeout. The origin must
have served every fixture.

The fixtures are embedded in the script as base64, like the WebM. The H.264
ones are deterministic: the ffmpeg recipe is in the comment above them, and the
driver checks their sha256 before it serves them.

**Why three rows (LW-M7-43).** Redoubt 157.0-2 shipped with this check green
and no H.264 or AAC playback at all. Isolated content processes were on, and
Gecko refuses the MediaCodec module in an isolated process (upstream bug
1810736). VP8/Opus kept working because ffvpx needs no MediaCodec, so a
VP8-only fixture could not see the defect. On the 157.0-2 build the
progressive MP4 fails with `MEDIA_ERR_SRC_NOT_SUPPORTED`. MSE fails before any
element error: `isTypeSupported` returns `false` and `addSourceBuffer()` throws
`NotSupportedError`. The fail-on-157.0-2 / pass-on-the-fix runs are in
`docs/android/evidence/video-playback/harness/`.

**Does not prove — measured, not assumed:** that any decoded pixel is correct.
On Android, decoded video frames are **not readable from content**:
`drawImage(video, …)` into a 2-D canvas leaves the canvas untouched (a canvas
pre-filled with `rgb(1,2,3)` still read back `[1,2,3,255]` after the draw, while
`getVideoPlaybackQuality()` reported 26 decoded frames), and `texImage2D` from
the video into a WebGL texture returns a constant `[51,0,51,255]` **regardless
of the video's content** — verified with a video split into a red half and a
blue half, which read identically. Both paths were tried and both were
discarded. Frame-count and clock evidence is what is available; do not
"strengthen" this check with a pixel assertion without re-measuring.

Also note: the harness performs a real click on the page before playing.
Without a user gesture the probe was racy — three otherwise identical runs gave
two passes and one `play() → NotAllowedError` with zero decoded frames, on a
build whose `media.autoplay.default` was 1 and `blocking_policy` 0, so the
prefs did not explain the block. With the click, three consecutive runs passed.

### `getusermedia`

The brief is to distinguish permission-denied (fine) from a crash or a silent
hang (not fine). All three are reachable, so the check answers the prompt and
then insists the promise settles:

1. `getUserMedia({audio: true, video: true})` starts, with a bounded script
   timeout.
2. A background thread polls `uiautomator dump` and taps the deny button of
   whichever dialog is up. On a wiped profile there are **two** kinds:
   Android's own runtime-permission grant dialog
   (`com.android.permissioncontroller:id/permission_deny_button`) and Fenix's
   site-permission doorhanger (`:id/deny_button`). Both ids are handled — the
   first version of this check only knew about the second, and reported a false
   HANG.
3. **Pass** if a prompt was shown and the promise then rejects (observed:
   `NotAllowedError` in ~4.8 s) or resolves with live tracks.
   **Fail — HANG** if it never settles while the app is alive and no prompt was
   found. **Fail — CRASH** if the process is gone or the crash log names it.

**Proves** additionally that the browser *asks*: a rejection with no prompt ever
shown is reported as a failure, because a privacy browser must not answer a
camera request on the user's behalf.

**Does not prove:** that capture works. The grant path is not exercised — it
would need the Android runtime permission granted and a working emulated
camera, and it would leave a persistent site permission behind. If you add it,
add it as a separate probe.

### `extension`

**Proves:** an unsigned WebExtension installs (`Addon:Install`, which takes the
XPI as base64 — nothing has to be pushed to the device) **and runs**: its
content script must leave a marker attribute on a real https page, read back
afterwards. An add-on that installs and does not run is not a working add-on.
The probe extension is uninstalled again at the end.

**Does not prove:** that a *signed* XPI installs, or that permanent (non-
temporary) installation works. `xpinstall.signatures.required` is `true` in
this build; the check uses a temporary install, which bypasses that. The uBO
preinstall path is exercised by `--check-ubo-preinstall` and
`--check-ubo-lifecycle`, including genuine signature and first-page blocking
assertions. The older `--check-ubo` flag checks the registry only.

### `pref-dump`

Writes `prefs.txt` — a fixed, curated, sorted list of security-relevant prefs
with their type, value, `locked` state and whether a user value is set — and
`prefs-all.json`, every pref in the running profile (about 4,090 of them) for
when you need to look something up.

The curated list is **fixed on purpose**: LW-M3-05 diffs this file against a
checked-in baseline, so a list that grew with the build would make every rebase
a spurious diff. It contains only prefs whose value is a decision, never one
with a client id, timestamp or random token in it. A pref that does not exist
in the build is printed as `missing`, which is information, not an error — but
`librewolf.webgl.prompt` going missing fails the run.

Measured: byte-identical across consecutive runs on the same build.

---

## Task gates

These are opt-in. They are **not** part of the baseline suite, because most of
them describe work that has not landed, and a gate that fails for the whole
milestone would train everyone to ignore the harness. Each one is written
against its task's acceptance, so it will go green when — and only when — that
task is genuinely done.

| flag | task | status | today, on `fenix-x86_64-debug.apk` |
|---|---|---|---|
| `--check-no-gms` | LW-M4-05 | implemented | **FAIL** — 4,478 distinct `com.google.android.gms` strings in the dex string table |
| `--check-no-adjust` | LW-M4-02 | implemented | **FAIL** — 324 `com.adjust.sdk` / `INSTALL_REFERRER` strings |
| `--check-search` | LW-M4-06 | implemented | reads the engine list and the default off the running app's Settings > Search (deep link `settings_search_engine`), compares them with `assets/search-config-v2.json`, then runs a real typed query and inspects the landing URL for partner codes. On the stock build: **FAIL** (Google, `client=firefox-b-m`, no Mojeek) |
| `--check-ubo` | LW-M4-04 | implemented | **FAIL** — no uBlock Origin among the 6 installed add-ons; `librewolf.uBO.assetsBootstrapLocation` unset |
| `--first-run-capture` | LW-M4-10 | implemented | **FAIL** — 53–58 outbound events before any navigation |
| `--network-capture` | LW-M4-01/03/08 | implemented | reports; the caller greps |
| `--check-aboutconfig` | LW-M4-09 | implemented | exit 3 on a **debuggable** build (a pass there proves nothing); **PASS** on the release-configured APK — see below |
| `--check-no-suggest` | LW-M4-11 | implemented | after uBO's post-launch list update has gone quiet, types a query into the toolbar and idles with Enter NOT pressed: no connection may open, no DNS query may leave and no connection open before typing may carry more than an HTTP/2 keep-alive record (see below), then Enter must produce traffic (the positive control that proves the capture was alive), no sponsored-tile host (`ads.mozilla.org`) anywhere since launch, and the "Show search suggestions" switch must exist in Settings > Search and read OFF |
| `--check-strings` | LW-M4-12 | implemented | two halves: the resource table (`aapt2` over the APK's `resources.arsc`, every locale) and a running-app traversal of the deep-linked settings screens (`--strings-locale`, `--strings-depth`, `--strings-max-taps`); a brand word in any string value that is not on the enumerated exception list fails it |
| `--check-update-privacy` | LW-M6-06 | implemented | OFF window: launch, idle, open Settings — no event to an update host, and a dead capture (zero events) fails rather than passes. If the "Check for updates" row exists it must read OFF; the harness flips it, relaunches, and requires the update host to be contacted and nothing else new. A build without a row (compiled out, as a store build should be) passes the OFF half only |
| `--check-launcher-start` | LW-M3-07 | implemented | launcher (not URL) cold starts on a fresh profile and a restart; fails on the uBO setup-failure dialog, a logged failure, or a missing readiness line. Beta 2 and the first 153.4 candidate: **FAIL** (dialog 30 s into the restart) |
| `--check-delete-on-quit` | LW-M7-45 | implemented | needs `adb root`; recents swipe then launcher cold start, setting on (selected data deleted before restore, by the start-up guard or by a completed `onTaskRemoved`) and off (tabs restored). LW-M7-45 build: **PASS**; Beta 5: **FAIL** (2 tabs restored) |

### `--check-search` deserves a note

`Services.search` **does not exist in GeckoView** — the chrome script raises
`TypeError: Services.search is undefined`. The engine list is not readable from
Gecko at all on Android; Fenix owns it, and ships it as
`assets/search/list.json` plus 147 `assets/searchplugins/*.xml` in the APK.

So the check does what LW-M4-06's acceptance actually asks and runs a **real
query**: it finds the address bar in the UI tree (Compose test tag
`ADDRESSBAR_URL_BOX`, with the older view ids as fallbacks), taps it, types a
unique token, presses Enter, and reads the resulting URL back through
Marionette. That URL is then scanned for partner/attribution parameters. If the
address bar cannot be found the harness raises a harness error rather than
guessing — a static scan of the shipped engine list would not satisfy "verified
from a real query", because a code appended at runtime would not appear in it.

### `--check-no-suggest`: how the typing window is judged

The check restarts the app, types a token into the toolbar in three
`input text` chunks, idles `--capture-seconds` (60 s) with Enter **not**
pressed, then presses Enter. The steps that make the typing window mean
something:

1. **The uBO installed notice.** On a fresh profile the "uBlock Origin was
   added" sheet covers the toolbar. `toolbar_ready()` recognises that exact
   native notice with the graphics harness's own `ubo_added_notice()` (loaded
   from `scripts/android-graphics-smoke.py`, not copied), taps its OK once, and
   accepts the address bar only after two dumps 2 s apart show it at the same
   place with no sheet. A generic OK or a permission dialog is never tapped; a
   notice that does not close is a harness error. `--check-search` uses the
   same wait. The evidence records `ubo_notice_acknowledged`.
2. **The pre-typing quiet wait.** uBO's asset updater runs
   `autoUpdateDelayAfterLaunch` seconds after every launch and then fetches one
   stale list every `autoUpdateAssetFetchPeriod` seconds. Both values are read
   from the APK's bundled `ublock_origin.xpi` (`js/background.js`), never
   assumed (1.75.0: 37 s and 5 s). Typing starts only when the launch timer must
   have fired (delay + 30 s startup allowance) **and** the capture has carried
   no non-background outbound payload for `max(20 s, 3 × fetch period)`. Nothing
   is exempted: traffic seen during the wait is recorded per host
   (`pre_typing_settle.hosts_bytes`). A capture that never goes quiet within
   300 s is named in the failure detail.
3. **Attribution by connection** (`attribute_typing_flows`). The quiet wait
   cannot outlast HTTP/2 keep-alives: connections opened during startup (AMO,
   uBO's list hosts) ping about every 59 s, so a ping or an idle-timeout close
   lands in any 60 s window. rc2's final acceptance failed on exactly that: 13
   non-background packets, all 39/46 B pings and 24/31 B TLS alerts on
   connections opened before typing. The capture is therefore read from its
   header to the end of the window in both directions, and every flow with an
   outbound SYN, datagram or payload in the window gets a verdict. It is
   **typing traffic** (the check fails) when any of these holds:

   | reason | meaning |
   | --- | --- |
   | `dns-query` | a query to port 53 or 853, unless every name in it is an exempt background host (as before) |
   | `new-connection` | an outbound TCP SYN inside the window |
   | `not-open-before-typing` | a flow first seen inside the window without a SYN |
   | `udp-datagram` | any other non-background UDP, QUIC included. No evidence justifies a UDP keep-alive exemption |
   | `resolved-during-typing` | the flow's address came from a DNS answer inside the window |
   | `search-or-suggest-host` | the flow's SNI is a search or suggestion host of any engine in `assets/search-config-v2.json`, whatever the size |
   | `payload-exceeds-keepalive` | an outbound segment that is not **one** complete TLS application-data or alert record of at most 46 B |

   A flow passes only as `background` (an SNI or DNS name on the existing
   security-settings / OS-noise lists, the same exemption `pcap_payloads`
   applies) or as `keepalive` (open before typing, nothing out but
   keep-alive-sized records). As a cross-check, every non-background payload
   `pcap_payloads` sees in the window must sit on a flow that passed.

   **Why 46 B.** An HTTP/2 PING or GOAWAY is a 9-byte frame header plus an
   8-byte payload: 17 B. TLS 1.3 wraps it in 5 B of record header, 1 B of inner
   content type and a 16 B AEAD tag (39 B on the wire). TLS 1.2 AES-GCM uses a
   5 B header, an 8 B explicit nonce and a 16 B tag (46 B). A 2-byte alert in the
   same envelopes is 24 B or 31 B. Those four sizes are exactly what rc2 sent. A
   46 B record leaves at most 24 B of HTTP/2 (15 B of HPACK after the frame
   header) under TLS 1.3, too little for a request whose `:path` carries the
   suggestion endpoint and the typed text. Plaintext, a handshake record, two
   records coalesced into one segment, or a 47 B record all count as payload.

   Every flow is listed in the check JSON under `typing_flow_attribution.flows`
   (addresses, ports, SNI, when it was opened, the size of each outbound and
   inbound segment in the window, the reasons and the verdict). The failing
   ones are repeated in `typing_flows_failed`.
4. **The search control.** Enter alone must then put the query on the wire to
   the default engine's host, and Marionette must read the token from both the
   current URL and the loaded document. A dead capture cannot pass.
5. **Settings.** No sponsored-tile host since launch, and "Show search
   suggestions" must exist in Settings > Search, read OFF, and survive an
   ON/OFF round trip through the UI.

**Negative control.** `--check-no-suggest --no-suggest-negative-control` turns
"Show search suggestions" ON through Settings before the quiet wait, then runs
the same window. It must FAIL, and its detail begins `NEGATIVE CONTROL` and
names the suggestion host it caught (`ac.duckduckgo.com` for the shipped
default). The switch is put back OFF afterwards; failing to restore it is
reported too. The result row is called `check-no-suggest-negative-control`, so
it cannot be mistaken for the gate.

### Graphics acceptance: the soft keyboard and the quiet Review

`scripts/android-graphics-smoke.py` (run as part of the baseline) taps controls
it found in a uiautomator dump. A dump contains only the app window, so it
cannot see a window above the app. On the rc2 emulator, a URL submitted from
the tab-counter menu's New (private) tab leaves the soft keyboard on screen and
taking touches over the bottom of the screen, even though
`InputMethodManagerService` reports it hidden. A tap on the quiet "Review"
snackbar then landed on a key (rc2 defect C, commit `f7f519f6`).

- **Every tap is checked against the input dispatcher.** Before tapping, the
  harness reads `dumpsys input` and refuses to tap through any foreign window.
  If only a soft keyboard covers the point, it is closed first; anything else
  is a failure.
- **Keyboard force-close.** After submitting a URL the harness gives the
  normal hide 1.5 s. A keyboard still taking touches after that is ended with
  `am force-stop` of the **default IME package**, never the app under test.
  Before doing so the harness checks that the covering window belongs to that
  IME's uid, and afterwards it waits up to 5 s for the window to go. The event
  is recorded as `soft-keyboard-closed`.
- **Review-expiry fallback, and its requirement.** The quiet notice is a
  LENGTH_LONG snackbar and can expire between the dump and the tap (rc2 had one
  such miss in a normal tab). A missed Review counts as expired only if the
  notice is gone **and** no other permission UI opened; the harness then opens
  the permissions through the site controls instead. A Review that is still
  shown after the tap, or that opened something other than the permissions
  list, is a failure. To stop the fallback from hiding a broken Review action,
  the run must still have had Review open the permissions list **at least once
  in a normal tab and at least once in a private tab**. That is the check
  `quiet-review-opens-permissions-in-normal-and-private-tabs`, and its evidence
  lists every attempt.
- After "Close tab" closes the last private tab, Fenix shows the empty private
  home, whose tab-counter menu has no "New private tab". The next private page
  is typed into that home's address bar.

### `--check-aboutconfig`, and the selector bug that made it a lie

It still **refuses on a debuggable build**, and that part was always right:
LW-M4-09's acceptance is *"about:config reachable on a **release-configured**
build"*, `GeckoProvider.kt` gates `aboutConfigEnabled` on
`Config.channel.isBeta || Config.channel.isNightlyOrDebug`, so on the debug APK
about:config is already on for a reason that has nothing to do with that task.
A pass there would mean nothing. Exit 3, and re-run against a release APK.

**So this flag needs a release APK.** The default search finds whatever
`make android-package` last wrote, which is a *debug*-variant APK unless the
build was run with `--variant=release` — and against a debuggable build this
check exits **3**, not 0. The command that passes is

```sh
./mach gradle fenix:assembleRelease -PdisableOptimization    # inside the build container
./scripts/android-smoke.sh --check-aboutconfig --serial <dev> \
    --apk .../outputs/apk/release/fenix-x86_64-release.apk
```

(`-PdisableOptimization` because a fully minified release build compiles and
then dies at startup in `FenixApplication.onCreate` — R8 strips the
`@Structure.FieldOrder` annotation uniffi's JNA bindings need, because
`third_party/application-services/.../proguard-rules-consumer-jna.pro` is
absent from the tarball. That is upstream's vendoring gap, unrelated to
about:config, and it needs its own task.)

**What was wrong** was the check itself, and it was wrong in the worst
direction: it could not go green on a correct build. It asked for

```js
document.querySelector("#about-config-search, #warningTitle, .toggleButton")
```

which is **desktop's** about:config. On Android
`docshell/base/nsAboutRedirector.cpp:106-113` maps `about:config` to
`chrome://geckoview/content/config.xhtml`, and
`toolkit/components/moz.build:103-113` builds toolkit's `aboutconfig/`
directory only when `MOZ_BUILD_APP != "mobile/android"` — so desktop's page,
its `#about-config-search` box and its "Proceed with Caution" interstitial are
not in the APK's `omni.ja` at all. All three selectors return null on a build
where about:config demonstrably works; the harness reported
`check-aboutconfig FAIL url=about:config recognised-ui=False` against a
running release APK showing 30 pref rows.

The replacement asserts seven things, and each one names a build it would
reject:

| assertion | rejects |
|---|---|
| the installed package is not debuggable | a green that would have come free on the debug APK |
| the navigation lands on `about:config` | the unpatched release build, whose `general.aboutConfig.enable=false` makes `nsAboutRedirector.cpp:285-288` return `NS_ERROR_NOT_AVAILABLE` and the navigation never land |
| `#filter-input`, `#prefs-container`, `#new-pref-item` all present | an error document that merely carries that URL |
| ≥ 20 rows in `#prefs-container` | a page that renders its chrome and then dies (`PREFS_BUFFER_MAX` is 30, so a healthy page shows 30) |
| `general.aboutConfig.enable` true **on the default branch, with no user value** | a green produced by a stale profile, a `user_pref`, or the harness itself. GeckoView commits this pref from `RuntimeSettings.Pref.addToBundle` (`mIsSet ? mValue : defaultValue`, and `GeckoRuntimeSettings.java:768` declares the default `false`) on every startup, so the only writer of that branch is the `GeckoProvider.kt` call site |
| an edit made by clicking the row's own `.pref-button.toggle` reaches the pref service | a page whose JS is broken |
| that edit survives `am force-stop` + a cold relaunch | acceptance line 3, and landmine L2b — the pref name is generated per run, so `GeckoView:ResetUserPrefs` cannot be declaring it |

The interstitial is **reported, never required**: Android has never had one
(it lives in toolkit's page, which is not built here), and if a future build
grows one the check clicks through it rather than failing.

**It has been observed failing, on a build, not on a forced expectation.** Two
APKs were built from the same tree, the same objdir, the same GeckoView and
`omni.ja`, the same `MOZ_BUILD_DATE` and the same signing key, differing only
in the one Kotlin argument:

```
patched    .aboutConfigEnabled(true)                                       -> exit 0
  check-aboutconfig PASS  about:config reachable on a release-configured
  build: 30 pref rows, general.aboutConfig.enable=true on the default branch
  (no user value), an edit through the page's own toggle survived a restart.
  67 prefs locked; interstitial present=False (Android ships none).

unpatched  .aboutConfigEnabled(Config.channel.isBeta || isNightlyOrDebug)  -> exit 1
  check-aboutconfig FAIL  navigation to about:config did not complete
  (WebDriver:Navigate -> timeout: Navigation timed out after 45000 ms);
  general.aboutConfig.enable reads value=False default-branch=False
```

The two APKs were checked to differ in one thing, from the archives rather than
by assertion: comparing the CRC-32 of every entry, exactly **2 of 3350** differ
— `classes6.dex` and the `assets/dexopt/baseline.prof` derived from it.
`assets/omni.ja`, every `.so` and every resource are CRC-identical.

That is a build-level ablation, not a forced expectation: `--self-test` proves
a probe *can* report failure, and this proves the whole check reports it on a
real defective APK. The short 45 s page-load timeout on that one navigation is
deliberate — when the pref is false the navigation never lands, and the failure
has to come back as a check failure (exit 1) inside the Marionette socket's own
120 s timeout rather than as a socket read error escaping as a traceback.

### How the last three checks were implemented

Each of them has a version that would be easy to write and would go green while
the defect it exists to catch is still present. That is the one outcome this
harness must not produce, so each stayed at exit 3 until it could be written the
hard way:

- **`--check-no-suggest`** — implemented 2026-09-02, the way this note asked for:
  `input text` into the Compose toolbar, a capture window with Enter not
  pressed, and a positive control (Enter must put the search on the wire) so a
  dead capture cannot pass. It also refuses a build whose Settings > Search has
  no "Show search suggestions" row, because LW-M4-11's third acceptance line is
  that the setting stays user-toggleable.
- **`--check-strings`** needed a traversal of the whole Fenix UI, because a
  `uiautomator dump` of the home screen and the settings root would pass on a
  build whose deeper screens still say Firefox. It now has two halves: the
  resource table of the APK itself (every string value in every locale, read
  with `aapt2`), and a deep-linked traversal of the settings screens on the
  running app, repeatable per system locale. (For the record, one such string
  was visible from the `getusermedia` check before LW-M4-12: Android's own
  permission dialog read *"Allow **Firefox Fenix** to take pictures and record
  video?"*, which comes from the app label.)
- **`--check-update-privacy`** — implemented 2026-09-02 against LW-M6-06's
  code. It measures the OFF state first and refuses to pass on a dead capture,
  then, only when the row exists, turns the check on through the UI like a
  user would and requires the update host to be the one new thing on the wire.
  Since 2026-10-05 "new" is judged per connection by name, not by bare
  destination address (`grade_update_privacy_flows`, reusing the
  `--check-no-suggest` flow attribution): an ON-window connection must carry
  the update host's name, a name seen with the check off, or a background-list
  name, by its TLS SNI or DNS query. A connection with no name of its own needs
  a plaintext DNS answer for its address whose every name passes, or must carry
  no payload to an address the OFF window also contacted. CDN address rotation
  and the update host's shared GitHub Pages address no longer fail it; a new
  host on an old address does.

---

## Proving a check can fail

A smoke test that has never been observed failing is a hypothesis. Two
mechanisms exist to turn it into a measurement.

### `--self-test`

Runs the whole baseline suite with every probe's expected value deliberately
wrong, and **fails the run if any probe still reports PASS**. It is the harness
checking that its own assertions are load-bearing rather than ornamental.

```
$ ./scripts/android-smoke.sh --emulator --self-test
[smoke] page-load-http   FAIL …
[smoke] webgl            FAIL …
[smoke] video            FAIL …
[smoke] video-h264       FAIL …
[smoke] video-mse        FAIL …
[smoke] getusermedia     FAIL …
[smoke] extension        FAIL …
[smoke] SELF-TEST OK: every probe reported failure when fed a wrong expectation
```

### `LW_SMOKE_EXTRA_PREFS` — the L1 negative control

Injects prefs into the app at startup through the same GeckoView debug config,
so you can reproduce a defect and watch the harness catch it. The run is marked
`"tainted": true` in `result.json`, and **a tainted run can never exit 0** — if
every check passes it exits 2 with "a run that changes the configuration under
test is a diagnostic, not a gate". It cannot be used to make something green.

This is how the L1 canary was verified against a running build:

```sh
LW_SMOKE_EXTRA_PREFS='{"librewolf.webgl.prompt": true}' \
  ./scripts/android-smoke.sh --emulator
```

Result — the entire point of this harness in six lines:

```
page-load-http   PASS
page-load-https  PASS
webgl            FAIL  librewolf.webgl.prompt is TRUE on Android -- this is
                       landmine L1 and every WebGL context in the build is dead.
video            PASS
getusermedia     PASS
extension        PASS
```

with the probe's own evidence recorded as:

```json
{"stage": "getContext", "reason": "getContext returned null",
 "creationErrors": ["WebGL is currently disabled.", …]}
```

Every other check passed. The build installed and browsed. That is the failure
mode landmine L1 describes, reproduced on purpose, and the harness caught it.

---

## Adding a check

1. **Decide what would make it fail.** Write that down first. If you cannot
   describe a build the check would reject, it is not a check.
2. **Pick the channel.** Content-side behaviour → a JS probe run through
   Marionette in content context. Browser configuration → a chrome-context
   script. Network behaviour → a capture window. Something about the shipped
   artefact → the APK reader. UI behaviour → `uiautomator dump` plus
   `input tap` / `input text`, as in `check_search`.
3. **Write the probe so it reports evidence, not a verdict.** Every check in
   here returns a dict that goes into `result.json` verbatim. The pass/fail
   decision lives in Python, next to the message that explains it. That is what
   makes `--self-test` possible: the harness can be fed a wrong expectation and
   the probe is unchanged.
4. **Add it to `Results` with a message a stranger can act on.** Name the owning
   task id in the failure text. Every existing failure message does.
5. **Make it fail on purpose, once, and record how you did it.** Either through
   `--self-test`'s `forcefail` argument or with `LW_SMOKE_EXTRA_PREFS`. Put the
   result in this file.
6. **Write down what it does not prove**, in the section above. Every check here
   has such a paragraph, and two of them (video pixels, https trust) exist
   because a stronger-looking version was tried and measured to be wrong.

If a check needs work that does not exist yet, add it to `NOT_IMPLEMENTED` with
a specific reason — not a TODO. The reason is what stops someone from writing
the vacuous version later.

---

## Options and environment

```
--emulator             boot a headless x86_64 emulator with capture and use it
--serial ID            use an already-running device
--sdk DIR / --apk PATH / --abi ABI / --work DIR
--keep-emulator        leave the emulator running afterwards
--keep-state           do not wipe app data first (default is a fresh profile)
--json FILE            where to write the full result (default $WORK/result.json)
--capture-seconds N    window length for the two capture modes (default 60)
--pref-dump --network-capture --first-run-capture --self-test
--check-{ubo,search,no-gms,no-adjust,aboutconfig,no-suggest,strings,update-privacy,video}
--no-suggest-negative-control  with --check-no-suggest: suggestions ON before typing; must FAIL
```

| variable | effect |
|---|---|
| `LW_SMOKE_WORK` | work directory |
| `LW_SMOKE_APK` | APK path |
| `LW_SMOKE_PACKAGE` | applicationId, if there is no `output-metadata.json` |
| `LW_SMOKE_PCAP` | pcap of an emulator you started yourself with `-tcpdump` |
| `LW_SMOKE_EXTRA_PREFS` | JSON object of prefs to inject; taints the run |
| `LW_SMOKE_BIND` | address the local origin binds to (default `127.0.0.1`) |
| `ANDROID_SERIAL` | default device |

---

## Limitations, and the ways this gate could be weakened

Read this before deciding the harness says more than it does.

- **The app must be debuggable, *or* named as the debug app.** The whole
  Marionette channel depends on GeckoView reading
  `/data/local/tmp/<pkg>-geckoview-config.yaml`. That happens for a debuggable
  app and also for the package in `Settings.Global.DEBUG_APP`, which the
  harness now sets itself when the installed package is not debuggable — so a
  release-configured APK **is** drivable. What remains true is that the
  baseline suite is normally run against the debug APK, and that a check whose
  answer depends on the build type must say so: `--check-aboutconfig` is the
  one that does, and it refuses on a debuggable build rather than lie.
- **The emulator is not a phone.** No real GPU, no real camera, no real
  cellular network, and the process sandbox is not what a device gives you. The
  WebGL check passing under SwiftShader does not promise a working driver on
  hardware.
- **The OS-noise allowlist is a hand-maintained list** of six hostnames and a
  few transports (mDNS, DHCP, NTP, the emulator's own DNS). If Fenix ever
  contacted one of them the first-run check would not notice. Every entry is
  something Android does with no browser installed; keep it that way, and keep
  it short.
- **The capture is per-VM, not per-app.** The pcap cannot attribute a packet to
  a uid. The per-uid byte counters are the corroborating signal, and the two
  should be read together — a first-run failure with hostnames but zero app
  bytes would mean the OS, not us.
- **`--pref-dump` reflects a profile that has been driven by Marionette.** The
  two prefs the harness sets are excluded by construction and asserted not to
  overlap the dump list, and `remote.prefs.recommended` is off so Marionette
  applies nothing else — but it is still not a pristine first-run profile.
- **Timing.** `--first-run-capture` idles for `--capture-seconds` (default 60).
  A beacon on a longer period than that would be missed. Raise it when a task's
  acceptance says "10-minute capture".
- **Nothing here checks the arm64 build.** `--abi x86_64` is the default
  because the emulator is x86_64. The APKs are built per-ABI from the same
  Gecko tree, but "smoke passed" means "passed on x86_64".

The fastest way to make this gate worthless would be to add a check that cannot
fail, or to soften an existing one so a red run goes green. Both look like
progress in a diff. `--self-test` is the defence: it will not tell you a check
is *correct*, but it will tell you it is *load-bearing*.

---

## What was measured, and when

Everything above marked "measured" was run on 2026-08-18 against
`~/lw-m2-04/out-make/apk/fenix-x86_64-debug.apk` (`versionName 1.0.2634`,
Gecko `153.0esr-1`, `buildID 20260816204534`) on the reference host: Fedora,
kernel 7.1.x, x86_64, SELinux enforcing, KVM available, emulator 37.1.11,
Android 11 (API 30) `default` x86_64 system image — the tag with **no** Google
Play services.

Not verified: any physical device, any ABI other than x86_64, any
release-configured APK, and the harness on a host without KVM.
