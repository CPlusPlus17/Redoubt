# LW-M7-45: delete browsing data on quit after swipe-away, kill or crash

> **Follow-up 2026-10-06 (second commit):** owner decisions on the review of
> 8d2a68d7, the hard gate on link/custom-tab/PWA/widget cold starts, the
> history purge, and the bounded guarantee. See
> [Follow-up: hard gate, history purge, bound](#follow-up-hard-gate-history-purge-bound)
> at the end; everything above it describes the first commit.
>
> **Follow-up 2026-10-06 (third commit): several tasks.** A review found that
> `onTaskRemoved` fires for any task of the app (a PWA, a custom tab, or the
> main task while one of those stays open) and deleted a live session. See
> [Follow-up: several tasks](#follow-up-several-tasks) at the very end.

Owner report 2026-10-06: "when swiping away the app, the delete all on close does
not trigger. closing it with the close button, works". Owner decision 2026-10-06,
verbatim: **"lets build both as fallback"**.

The patch is `patches/android/delete-on-quit-swipe.patch`. Its header explains the
design: (b) a session-end marker plus a start-up deletion before the session
restore, and (a) a best-effort `onTaskRemoved` hook.

## Result

All device cases pass on the API 34 x86_64 emulator (google_apis image, rooted
over adb only for setup and inspection). The negative controls (setting off)
delete nothing. The new harness check passes on the patched build and fails on
Beta 5.

| case | exit | setting | marker before cold start | after cold start | verdict |
|---|---|---|---|---|---|
| c1b | real recents swipe (`exit-info`: REMOVE TASK) | on, all 6 | running | 0 cookies, 0 history, no localStorage origin, no session file; server got an empty `Cookie` header; page shows `cookie=[] ls=[]` | PASS |
| c2 | `am force-stop` (FORCE STOP) | on | running | same as c1b | PASS |
| c3 | `kill -9` of the main process (SIGNALED 9) | on | running | same as c1b | PASS |
| c4b | menu "Quit Redoubt" | on | **clean** (process survives Quit, as upstream) | data gone (upstream Quit), restart is warm, marker back to running | PASS |
| c4c | Quit, then `kill -9` of the surviving process | on | clean | `cold start: no deletion (last session ended with Quit)` | PASS |
| c5 | recents swipe | **off** | running | 4 cookies, 2 history, localStorage and 2 tabs all still there; server got all 4 cookies | PASS (negative control) |
| c6 | `kill -9` | **off** | running | same as c5 | PASS (negative control) |
| c7 | HOME, wait, return (twice) | on | running | no deletion line, all data intact | PASS |
| c8 | swipe, then cold start via a VIEW intent to a page | on | running | page request carried no cookie; page shows `cookie=[] ls=[]` | PASS (see the caveat below) |
| c9 | marker forced to cleaning/2, then cleaning/3 | on | cleaning | attempt 3/3 runs; at 3 the start logs "3 deletion attempts did not finish; continuing WITHOUT deleting" and the marker becomes running | PASS |
| c10 | 2 **private** tabs, swipe | on | the process survived (private-browsing FGS) | (a) completed: `task-removed: deletion confirmed; marked clean`; private and normal report pages got no cookie | PASS |

Each case first fills the browser through the test server (`tools/doq_server.py`,
`http://10.0.2.2:8765`). `a.html` and `b.html` set a header cookie and a JS cookie,
write localStorage, and load a cacheable `cached.js`. The case then waits 35 s, so
the session file holds both tabs and the cookie DB is flushed. A snapshot of the
stores is taken before the exit (`device/snapshots/<case>-before/summary.json`)
and after the cold start (`-after`). It reads `cookies.sqlite` and `places.sqlite`
(with their WAL), the session file, `storage/default` and the marker.

### Order: deletion before restore and before content

c1b cold start (`device/c1b-swipe-3-coldstart-logcat.filtered.txt`):

```
18:57:23.548 Start proc org.redoubtbrowser
18:57:23.976 cold start after unclean exit (marker running/0): deleting TABS,HISTORY,COOKIES,CACHE,PERMISSIONS,DOWNLOADS ... attempt 1/3
18:57:24.005 cold start: app-side deletion done (ok=true); waiting for the engine
18:57:24.231 engine: cookies cleared  ... 18:57:24.245 site permissions storage cleared
18:57:24.245 cold start: deletion complete; session restore may proceed
18:57:24.277 Start proc org.redoubtbrowser:tab...   (first content process)
```

The deletion takes about 270 ms. No `RestoreAction` is logged: the session file
was deleted, so there is nothing to restore.

**Caveat (c8), superseded by the follow-up below:** in this first version, a cold start through a link was not behind the restore gate.
Fenix dispatches that tab's `LoadUrlAction` at 19:09:55.894, and Gecko confirms
the cookie clear at 19:09:55.925. The page is still clean because the `clearData`
calls are dispatched to Gecko first, from `Application.onCreate`, and Gecko
handles them in order. The page's request reached the server at 19:09:57 with no
cookie, and the page read `cookie=[] ls=[]`. This rests on that ordering, not on
a gate. Holding link loads until the deletion completes would need a change to
Fenix's intent path; it is not done here.

### (a) best effort, measured

- **Swipe on a normal session (c1b):** `onTaskRemoved` fired at 18:57:15.874, and
  Android killed all app processes 3–6 ms later ("Killing ... remove task"). (a)
  started but could not finish, so (b) did the work at the next start.
- **Swipe with private tabs open (c10), and the harness "on" phase:** the process
  survived, and (a) completed and wrote "clean". The next start then had nothing
  to delete.

So (a) cannot be relied on, and the design does not rely on it.

### Found and fixed on the device (run 1)

The first build (APK sha256 `dbb8066f…`, `build/SHA256SUMS`) deadlocked at cold
start with all six categories selected (`device/run1-hang/`):

- The main thread was parked in `runBlocking` (`main-thread-trace.txt`). The
  marker stayed `cleaning/1`, and no page loaded.
- Bisecting one category at a time pinned it to **PERMISSIONS**. Fenix's
  `PermissionStorage` is backed by Gecko's site-permission storage and needs the
  main thread.

The fix has two parts:

1. The permissions DB step moved to the asynchronous, gated half.
2. The synchronous phase now runs the local deletion on IO, and only the bounded
   *wait* is on the main thread. A future step that needs the main thread
   therefore times out instead of deadlocking start-up.

A unit test pins this (`a local step that never returns does not hold the main
thread`). All results above come from the fixed build:
`redoubt-doq2-x86_64-throwaway.apk`, sha256 `ba374cc4…`.

## Harness

`scripts/android-smoke.sh --check-delete-on-quit` (needs `adb root`) is
documented in `docs/android/SMOKE.md`.

- LW-M7-45 build: **PASS** (`harness/smoke-check-delete-on-quit.json`). In the
  "on" phase the process survived the swipe and (a) completed; the "off" phase
  restored 2 tabs.
- Beta 5 (`keep/beta5-unsigned`, throwaway-signed): **FAIL**. With the setting
  on, 2 tabs were restored after the swipe (`harness/*beta5*`). This is the
  owner's bug, reproduced.

## Build and unit tests

| | |
|---|---|
| tree | `make android-dir` of origin/main 75852a26 (157.0-3), the patch applied in list order. The commit was then rebased onto local main 84a2015b (LW-M7-44); the gates were re-run there, and the patch file is byte-identical |
| Gecko | x86_64 fat AAR from that tree, `MOZ_BUILD_DATE` 20261006150000, image `localhost/librewolf-android-build:fx157` (`build/aar.sh`) |
| APK | `android-apk.sh --variant release` (Kotlin `-Werror`), the second build with `--skip-gecko` (`build/apk.sh`, `build/apk2.sh`, `build/commands.log`) |
| unit tests | `DeleteOnQuitGuardTest`: 18 tests, 0 failures (`build/TEST-…xml`) |
| signing | throwaway key only |

The first `aar failed; apk not started` line in `commands.log` is a chain-script
bug: it read the stale `aar.rc` left by a network-reset first attempt. It is
noted in the log and was re-armed.

## Gates

| gate | result |
|---|---|
| `check-patchfail.sh --targets=android`, Firefox 157.0 | exit 0; the patch applies with no fuzz and no offset (`gates/patchfail-android-157.0.out`) |
| `check-patchfail.sh --targets=android`, Firefox **158.0b3**, `android/firefox-158` at cfe13236 | exit 0; offsets only, no fuzz (`gates/patchfail-android-158.0b3.out`) |
| same, Firefox **158.0b4**, `android/firefox-158` at 96fc1a8e (its current base) | exit 0; offsets only, no fuzz (`gates/patchfail-android-158.0b4-at-96fc1a8e.out`) |
| same, 158.0b3 at 96fc1a8e | exit 1, only in `disable-157-cloud-features.patch` (SecretSettingsFragment.kt, which that branch rebased for b4); this patch applied (`gates/patchfail-android-158.0b3-at-96fc1a8e.out`) |
| `check-patch-order.py` | ok. 7 new shared-file pairs are recorded order-free: byte-identical in both orders (`gates/pairswap-157.0.out`, `tools/pairswap.sh`) |
| `lint-patch-scope.py`, `board.py --check`, `--check-scope` | ok |

The 158.0b3 check ran in a scratch detached worktree of the local
`android/firefox-158` branch at cfe13236. It had the patch appended to
`android.txt`, and `version`/`version.android` were set to 158.0b3, as in
`PREBASE.md`. The patch compiles against 158 only by inspection: every API it
calls is present, unchanged, in 158.0b3, and the 158
`DeleteBrowsingDataController.kt` is identical to 157's. No 158 build was made.

## Raw evidence

Full logcats, database copies and every screenshot are archived outside the repo
as `~/redoubt-artifacts/delete-on-quit/raw-evidence-lw-m7-45.tar.xz` (sha256
`0f7e8bf3d395eb9c71045d0ad8fb6c761b4242719e721976a364f94dc2ef5dc6`).

The test harness turns off Fenix's HTTPS-only switch, because the test server is
plain HTTP. The first c1 and c4 attempts are kept as harness failures:

- **c1:** HTTPS-only upgraded the test pages, so nothing loaded.
- **c4:** the Quit item is labelled "Quit Redoubt", and the first tap missed it.

## Follow-up: hard gate, history purge, bound

Owner decisions 2026-10-06 on the review of 8d2a68d7, verbatim:

- trigger rule **"Every non-Quit exit"**. Keep: any exit that is not Quit,
  including an OOM kill, a crash or a reboot, triggers the deletion at the
  next start;
- link starts **"Yes, hard gate"**. Cold starts through a VIEW intent (link),
  a custom tab, a PWA or a widget/search shortcut must not dispatch any page
  load until the deletion is confirmed, the same gate as the restore;
- keep the best-effort `onTaskRemoved` service.

### What changed in the patch

| review finding | change |
|---|---|
| HISTORY without TABS kept the restored tabs' back/forward history | `DeleteOnQuitStartGateMiddleware` strips `engineSessionState` from the tabs of the session restore that follows a cold-start HISTORY deletion (until `RestoreCompleteAction`), as upstream's `EngineAction.PurgeHistoryAction` does on Quit |
| link, custom tab, PWA, widget cold starts not gated | the same middleware, first in the BrowserStore list (`Core.kt`), holds every `EngineAction.CreateEngineSessionAction` while the cold-start gate is closed and replays them in order when it opens. Every page load needs an engine session (a `LoadUrlAction` on a tab without one dispatches a held creation), so nothing loads. Holding is a list and the replay a coroutine: no main-thread wait, no ANR. Same shape as `LibreWolfUboPreinstallMiddleware` |
| marker set back to "running" only on the process's first `ON_START` | `Application.ActivityLifecycleCallbacks.onActivityStarted`: every activity start (another task, split screen) |
| rename not durable | `fsync` of the marker's directory after the rename (`Os.open(dir, O_RDONLY)` + `Os.fsync`), best effort |
| stale wording | the permissions DB is deleted asynchronously with the engine deletions; the local stores are deleted on IO while the main thread waits at most 5 s |
| unbounded wording | one 20 s bound, counted from the start of the deletion (it was 20 s after a 5 s wait, and the local stores had their own 20 s) |

**The guarantee is bounded.** The gate opens when Gecko and every local store
confirmed, or 20 s after the deletion started, whichever is first. If Gecko
has not confirmed by then, or a local step failed, restore and page loads
proceed (fail open, logged `deletion incomplete ... continuing (fail open)`),
and the deletion is retried after the next exit that is not Quit. Not behind
the gate: a custom-tabs client's `mayLaunchUrl` speculative connect (TCP/TLS
only, no request, no cookie) and extension background pages (uBO's
filter-list updates).

**Release-notes line:** "Delete browsing data on quit" now also runs after
the app is swiped away, killed or crashes: the next start deletes the selected
data before any tab, link or custom tab loads (bounded: after 20 s without the
engine's confirmation the start continues, and the deletion is retried after
the next exit).

### Device results (API 34 x86_64 emulator, `followup/device/`)

APK `redoubt-doq3-x86_64-throwaway.apk`, sha256
`7b1b60cdb4955a2e5cc24cdd1db2eb8976e7a589345a29896ba2e8581ec5cc52`
(unsigned `c1b1005a10eff39684e6cad2c56622d0282dc73fb5b155281618ee2d6867f471`,
`followup/build/SHA256SUMS`). Patch sha256 `18793b83193fb22f…`. Driver
`followup/tools/` (`doq.sh` from the first round plus `doq2.sh`); every case
logs to `device/driver.log`, and the server log is `device/server.jsonl`
(times in ms, the cookie header of every request).

| case | setting | exit | cold start | result | verdict |
|---|---|---|---|---|---|
| c1b | on, all 6 | recents swipe (REMOVE TASK) | launcher | 0 cookies, 0 history, no localStorage, no session file; report request with an empty `Cookie` | PASS |
| c2 | on | `am force-stop` | launcher | same as c1b | PASS |
| c3 | on | `kill -9` main process | launcher | same as c1b | PASS |
| c4b | on | menu "Quit Redoubt" (process survives) | launcher (warm) | `quit: deletion confirmed; marked clean`; data gone; marker back to running | PASS |
| c5 | **off** | recents swipe | launcher | `cold start: no deletion (setting off)`; 4 cookies, history, 3 tabs restored; report request carried all 4 cookies | PASS (negative control) |
| c7 | on | HOME, 20 s, return (twice) | — | no deletion line; all data intact | PASS |
| **c11** | on | recents swipe | **VIEW intent link** | engine session held, released after the deletion; link request with an empty `Cookie` | PASS |
| **c12** | on | recents swipe | **custom tab** (VIEW + `android.support.customtabs.extra.SESSION`) | same as c11, through `ExternalAppBrowserActivity` | PASS |
| **c13, c22** | on, HISTORY + COOKIES (TABS off) | swipe (c13), `kill -9` (c22) | launcher | `restore: dropping the back/forward history of 1 restored tab(s)`; the restored tab loads fresh (`nav=navigate`); saved history after load `[h2]` | PASS |
| c21 | on, COOKIES only (control) | `kill -9` | launcher | the restored tab loads from session history (`nav=back_forward`); saved history `[h1, h2]` | control: the check sees history |
| harness | | | | `android-smoke.sh --check-delete-on-quit`: **PASS** (`followup/harness/`) | PASS |

**c11, link cold start** (`device/c11-swipe-link-3-coldstart-logcat.filtered.txt`):

```
20:45:42.596 Start proc org.redoubtbrowser for IntentReceiverActivity (VIEW report.html?tag=c11-swipe-link-first)
20:45:43.003 cold start after unclean exit (marker running/0): deleting TABS,HISTORY,COOKIES,CACHE,PERMISSIONS,DOWNLOADS ... attempt 1/3
20:45:43.053 cold start: app-side deletion done (ok=true); waiting for the engine
20:45:43.076 TabListAction$AddTabAction, EngineAction$LoadUrlAction      (the link's tab; no engine session yet)
20:45:43.105 holding engine session for tab ab21145b... until the on-quit deletion is confirmed
20:45:43.109 engine: cookies cleared
20:45:43.462 holding engine session for tab ab21145b... (second request, same tab)
20:45:43.532 cold start: deletion complete; session restore and page loads may proceed
20:45:43.534 gate open: releasing 2 held engine session(s)
20:45:44.072 EngineAction$CreateEngineSessionAction (x2), 44.075 EngineAction$LinkEngineSessionAction
server: 20:45:44.738 /report.html?tag=c11-swipe-link-first  cookie_header ""
```

The link's session creation was requested 4 ms **before** Gecko confirmed the
cookie deletion. The first version did not hold it (c8 above). Now it is held
until the gate opens. The first engine session exists 0.5 s after the deletion
is confirmed. The extra 0.5 s is uBO's own start-up gate, which is the next
middleware. The page request carries no cookie. c12 (custom tab) shows the
same order. The creation is held at 47:08.557, cookies are cleared at
08.671, the deletion completes at 08.887, and the session is created at
09.520. The request at 47:10.148 carries an empty `Cookie`.

**History (c21 control vs c22):** both profiles start empty (`pm clear`). Each
has one tab that went h1 → h2 (`no-store` pages), saved as `[h1, h2]`, and is
killed with `kill -9`. After the cold start, the tab is opened from the tabs
tray. With HISTORY kept (c21), Gecko restores the tab from session history:
the page reports `nav=back_forward`, and the saved history stays `[h1, h2]`.
With HISTORY deleted (c22), the tab is restored without engine state: the page
loads fresh (`nav=navigate`), and the saved history becomes `[h2]`. The h2
request carries no cookie in both cases (COOKIES is on in both).

Two signals were tried and are not used. The menu's Back arrow is greyed in
both c21 and c22 right after restore (upstream's restored-tab state;
screenshots `c21-…-4-menu.png`, `c22-…-4-menu.png`). The hardware Back key
returns to the tabs tray or the home screen.

c14 is not a valid control. The swipe left the process alive, so the
best-effort (a) completed (`task-removed: deletion confirmed; marked clean`)
and the start was warm. It is kept in `driver.log` as another measurement of
(a). c15–c20 are the iterations of the history check that led to the method
above (home screen after `pm clear`, the Back key, the menu arrow, and a
`/log` fetch blocked by the filter lists). Their lines are in `driver.log`.

**Not device-tested:** the split-screen / second-task case of the activity
callbacks (finding 3) and the directory fsync (finding 4). Both are covered by
unit tests only. A 20 s fail-open on a device was not forced; the unit tests
`the gate bound counts from the start of the deletion and fails open` and
`held loads are released when the deletion fails open after its bound` pin it.

### Build, unit tests, gates

| | |
|---|---|
| tree | `make android-dir` of 8d2a68d7 (157.0-3), then the Fenix sources edited in that tree; the patch is regenerated from it (`tools/mkpatch2.sh`) |
| Gecko | x86_64 fat AAR, `MOZ_BUILD_DATE` 20261006150000, image `fx157` (`build/dir-aar.sh`) |
| APK | `android-apk.sh --variant release` (Kotlin `-Werror`): `:fenix:compileReleaseKotlin` ok; the throwaway password is read from a file outside the repository (`build/apk.sh`) |
| unit tests | `DeleteOnQuitGuardTest` 24 tests, `DeleteOnQuitStartGateMiddlewareTest` 7 tests, 0 failures (`build/TEST-*.xml`) |
| `check-patchfail.sh --targets=android`, 157.0 | exit 0, this patch with no offset and no fuzz (`gates/patchfail-android-157.0.out`) |
| same, 158.0b4 at `android/firefox-158` 96fc1a8e, patch in list order | exit 0, this patch with offsets only (`gates/patchfail-android-158.0b4-at-96fc1a8e.out`) |
| `check-patch-order.py` | ok. Core.kt is a new shared file. `ubo-preinstall` → this patch and `fission-isolation` → this patch are now constraints (moving this patch earlier rejects its Core.kt hunk). `doh-mullvad-migration` is order-free (`tools/pairswap.sh`) |
| `lint-patch-scope.py`, `board.py --check`, `--check-scope` | ok |

Raw evidence (full logcats, UI dumps, screenshots, DB copies):
`~/redoubt-artifacts/delete-on-quit/raw-evidence-lw-m7-45-followup.tar.xz`,
sha256 `08a5864e66a7438548db0f8e11d9638a9a24e3893192da102e5cfafc8aaf82d1`.

## Follow-up: several tasks

**Finding (review, medium, by code reading).** `DeleteOnQuitTaskService.onTaskRemoved`
fires for ANY task of the app. The app can have several at once: the main
browser; each PWA in its own document task (`FennecWebAppIntentProcessor` /
`WebAppIntentProcessor` set `FLAG_ACTIVITY_NEW_DOCUMENT`); a custom tab in its
own task (`ExternalAppBrowserActivity` has `taskAffinity=""`) or inside the
calling app's task. Swiping one of them while another stayed visible kept the
process alive, yet the live deletion ran (`removeAllTabs`, cookies of a session
the user had not left) and wrote "clean". Browsing then continued under
"clean", and a later kill skipped the cold-start deletion.

**Fix** (`patches/android/delete-on-quit-swipe.patch`, sha256 `a165ab70…a678`):

- `LiveTasks`: `DeleteOnQuitActivityCallbacks` record every live activity
  (created, not yet destroyed) and its task id. A task counts as the app's own
  once it was seen in `ActivityManager.appTasks`.
- `onTaskRemoved` computes the tasks that still hold a live activity:
  - an own task still in `appTasks` counts. The removed task has already left
    `appTasks` when `onTaskRemoved` runs, because AOSP removes it from recents
    before it posts `cleanUpServices`. The device runs confirm this.
  - a task never listed there (a custom tab inside another app's task) counts.
  - a recents entry with no live activity does not count.
- `DeleteOnQuitGuard.onTaskRemoved(remaining)`: only when that set is empty
  does it run the live deletion and mark "clean" (as before: once the deletion
  is confirmed and no activity started meanwhile). Otherwise it deletes nothing
  and writes nothing, and the marker stays "running", so the cold-start
  guarantee still covers a later kill. The same applies when the task list
  cannot be read. While another task remains, the service also keeps running,
  so the next removal reaches it.
- Log: `onTaskRemoved: task swiped away (<root activity>); other live tasks: [ids]`
  and `task-removed: N other task(s) of the app still open; session continues,
  nothing deleted, marker stays unclean`.

The same commit also does the following:

- Gate exclusions: favicon downloads (`HttpIconLoader`, through the engine's
  fetch client, `CookiePolicy.INCLUDE` for normal tabs) are now listed beside
  `mayLaunchUrl` and extension background pages. A favicon fetch that runs
  before Gecko has processed the cookie deletion can carry a cookie from the
  old session to the icon's host.
- The `tasks.yaml` "what" no longer has the stale wording. It now says: the
  directory is fsynced; the permissions DB is deleted asynchronously; the
  local stores are deleted on IO with a 5 s wait.
- The throwaway keystore password is no longer passed inline. Three committed
  scripts now read it from a file outside the repository:
  `build/apk.sh`, `build/apk2.sh` and
  `../lw-m7-44/build/device-build-714e51cc/chain.sh`. History was not
  rewritten; the password belongs to a throwaway test key only.

**Unit tests** (`multitask/build/TEST-*.xml`): `DeleteOnQuitGuardTest`, 29
tests (5 new), and `DeleteOnQuitStartGateMiddlewareTest`, 7 tests. There were
0 failures. The new tests cover:

- swiping one of two tasks deletes nothing and leaves "running"; swiping the
  last task deletes and marks "clean";
- a custom tab in another app's task keeps the session;
- a stale recents entry does not keep the session;
- an unreadable task list never deletes;
- the callbacks feed the tracker.

**Build.** `make android-dir` of 726ded4c with the edited Fenix sources, an
x86_64 fat AAR (`MOZ_BUILD_DATE` 20261006150000, image `fx157`), then
`android-apk.sh --variant release`. `:fenix:compileReleaseKotlin` passed under
Kotlin `-Werror` (`multitask/build/`). Two earlier attempts are recorded in
`build/commands.log`:

- doq4 attempt 1 failed to compile: `taskInfo` is nullable.
- the doq4 unit tests did not compile: the old test's trailing lambda bound to
  a new constructor parameter, so `onActivityStart` is now last.

The device cases were run on doq4 first (`multitask/device-doq4/`). They were
then all re-run on the final doq5 (`multitask/device/`):

| item | value |
|---|---|
| APK | `redoubt-doq5-x86_64-throwaway.apk` |
| sha256 | `64f8bcfd76d1885ea5745eb7ab68b194c51a52eb81e3870254d509ba42851895` |
| unsigned sha256 | `b3b4df1c8c56e6ed84064276890f91cb44fbf5d7dc691721149ac7c647a30b08` |
| signing cert | `31e9a40f…b760` (throwaway) |

**Device** (API 34 `google_apis` x86_64 emulator, all six categories on).
Driver: `multitask/tools/` (`mt.sh`, `run-mt.sh`, `run-c-mt.sh` on top of
`followup/tools/`). Server log: `multitask/device/server.jsonl`, which holds
both runs.

Each case starts with the main task holding two tabs that set cookies and
localStorage, and waits 35 s for the autosave.

| case | tasks | action | result | verdict |
|---|---|---|---|---|
| **A** PWA | main task #28 plus a PWA document task #32 (`ExternalAppBrowserActivity`, opened through the Fennec web-app intent `org.mozilla.gecko.WEBAPP` with a manifest) | swipe ONLY the PWA task | `other live tasks: [28]` … `nothing deleted`; marker `running`; 4 cookies, 2 tabs and localStorage still there. A page opened in the main task afterwards sent all 4 cookies (`doq_hdr_a=1; doq_js_a=1; doq_hdr_b=1; doq_js_b=1`) | PASS |
| A, continued | main task only | swipe the main task | `other live tasks: []`, `task-removed: deleting …`, `deletion confirmed; marked clean`. Then the launcher start: 0 cookies, 0 history, no session file, and the report request had an empty `Cookie` | PASS |
| **B1** custom tab, own task | main #36 plus custom tab #39 (`am start`, so `NEW_TASK` and `taskAffinity=""`) | swipe the main task | `other live tasks: [39]`, nothing deleted, marker `running`, all data intact. Swiping the custom-tab task afterwards: `other live tasks: []`, deletion, `clean`; the next start has no data | PASS |
| **B2** custom tab, foreign task | main #41 plus a custom tab inside test client `org.redoubt.ctclient`'s task #44 (no `NEW_TASK`; client source in `tools/ctclient/`) | swipe the main task | `other live tasks: [44]` (a task never in `appTasks`), nothing deleted, marker `running`, all data intact. Then `kill -9`: the next cold start runs the start-up deletion (`marker running/0`) and the data is gone | PASS |
| **C1** single task | main only | swipe | process killed (REMOVE TASK); the cold start deletes; the report request had an empty `Cookie` | PASS |
| **C2** Quit | main only | menu Quit | `quit: deletion confirmed; marked clean`. The Quit's own `finishAndRemoveTask` also reaches `onTaskRemoved` with `other live tasks: []` (an idempotent second deletion). The next start shows no data | PASS |
| harness | | `android-smoke.sh --check-delete-on-quit` | **PASS** (`multitask/harness/`) | PASS |

Notes:

- **Tracker re-run in a fresh process.** In A (main swipe) and B1 (custom-tab
  swipe), Android killed the process with the last task (REMOVE TASK). It then
  started a fresh process to deliver the pending `onTaskRemoved` to the
  `stopWithTask="false"` service. That process ran the cold-start deletion
  (marker `running`) and then the live one, because it has no live activity,
  so `other live tasks: []`. This is why the following launcher start was warm
  with the data already gone.
- **B2 reload not seen.** B2's second client intent (to reload the custom tab
  after the swipe) did not reach the server: the client activity was already
  on top of its task. The cookie store snapshot (`snapshots/B2-*`) shows the
  data intact instead.

**Gates** (`multitask/gates/`, run on the final patch text). Every gate exited
0:

- `check-patch-order.py`
- `lint-patch-scope.py`
- `board.py --check` and `--check-scope`
- `check-patchfail.sh --targets=android` against 157.0
- at `android/firefox-158` e55a8329, with this patch text and the version
  files set to 158.0b4 in a scratch worktree: `check-patchfail.sh` for android
  (this patch applies with offsets only) and for desktop, and
  `check-patch-order.py`

**Not covered here:**

- A PWA installed through the menu's "Add to Home screen". Gecko needs a secure
  context to install a manifest, and the local server is plain HTTP on
  10.0.2.2. Both PWA paths open `ExternalAppBrowserActivity` with
  `FLAG_ACTIVITY_NEW_DOCUMENT`; the legacy Fennec web-app intent used here is
  one of them.
- Split screen.

