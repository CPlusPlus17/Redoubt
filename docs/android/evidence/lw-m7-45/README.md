# LW-M7-45: delete browsing data on quit after swipe-away, kill or crash

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

**Caveat (c8):** a cold start through a link is not behind the restore gate.
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
