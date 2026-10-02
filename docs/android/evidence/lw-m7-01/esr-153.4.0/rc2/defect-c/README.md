# rc2 defect C: the quiet "Review" action in a private tab "opens nothing" (2026-10-02)

## Verdict

**This is a harness defect, not a product defect. LW-M7-14 / `canvas-webgl-permissions.patch` is unchanged.**

Fix commit: `f7f519f6` (`scripts/android-graphics-smoke.py` and its tests). The product is unchanged,
so there is no rc3 and the rc2 APK stays the candidate.

- In rc2, the harness tapped Review through a **soft keyboard that stayed on screen**. The keyboard covered
  the snackbar. The tap landed on a keyboard key, so Fenix never received it.
- Once the keyboard is out of the way, Review opens the permissions dialog in private tabs. That holds on
  rc2 and on Beta 2.
- With the committed harness, the full graphics acceptance now **passes 3 of 3** fresh-profile runs on the
  rc2 APK (161 checks each). No earlier build had completed it.

## What happens

1. The harness opens a private tab with the tab-counter menu's **New private tab**, types the URL, and
   presses Enter.
2. After that, the soft keyboard (LatinIME) stays in the input dispatcher as a visible, touchable window
   over `[0,1145][1080,1920]`, above the app window. `InputMethodManagerService` reports it hidden at the
   same time (`mInputShown=false`, `mWindowVisible=false`).
   - Evidence: `instrumented/private-snackbar-input-windows.txt`, `…-ime-state.txt`, `…-ime-window.txt`,
     and the uninstrumented `repro/rc2-imep-*.txt`.
3. On screen the keyboard is still there, sometimes half-faded. The quiet snackbar sits under it.
   - Evidence: `instrumented/new-tab-snackbar-under-keyboard.png`.
4. `uiautomator dump` reads only the app window. The harness therefore "saw" the snackbar at its normal
   place and tapped Review at 946,1805, which is the keyboard's bottom row.
5. At the tap, `VibratorService` logs a `Usage=TOUCH` vibration from uid 10106, which is
   `com.android.inputmethod.latin` and not Fenix (`instrumented/run2-defc-input-vibrator.log`).
6. In a scratch build with logging only (`scratch-build/`), the snackbar's action listener **never runs**
   for that tap. The same tap in a fresh normal tab runs the listener, `show()` and the dialog's `onStart`
   (`instrumented/run1-defc.log`).

The task brief listed three suspects. None of them is the cause:

- `show()`'s early return: it is never reached.
- `findTabOrCustomTab` returning null: it is never reached either.
- The snackbar's exit animation: the tap was 2.1 s after the request, the same as working normal-tab taps.

Further results:

- `dumpsys activity top` shows no stale `origin-bound-permissions` fragment and `mStateSaved=false`.
- The private site-information path opens the same dialog.

### The keyboard does not depend on private mode or on LW-M7-14

All of the following are on rc2 unless noted:

- **Normal tab, same path.** A *normal* tab opened from the same menu's **New tab** behaves the same:
  Review opens nothing (`repro/rc2-back.log`).
- **No permission request at all.** On a page with no canvas or WebGL request, the keyboard is still on
  screen and touchable 1, 3, 6, 12 and 25 s after the page loaded
  (`repro/rc2-plain-page-keyboard-1-3-6-12-25s.png`, `repro/rc2-timeline.log`).
- **Control.** Typing into the home screen's address bar instead releases the keyboard within 1 s
  (`repro/rc2-control*.{log,png}`).
- **Not a harness keystroke artefact.** Submitting with the keyboard's own Go key instead of
  `input keyevent 66` gives the same result.
- **Not the hardware keyboard.** An AVD copy with `hw.keyboard = no` gives the same result.
- **Not the re-tap.** Not re-tapping the already focused field gives the same result.
- **Back does not help.** Back does not hide the keyboard. It goes to the browser, which navigated away
  from the page.
- **Beta 2 does the same.**
  - With the keyboard stuck, Review opens nothing (`repro/b2-back.log`).
  - The keyboard stays after a plain page (`repro/b2-timeline.log`).
  - With the keyboard closed, Review opens the dialog in the private tab and in the normal tab after the
    mode switch (`repro/b2-back-kbd.log`).

### What the rc2 harness fix changes

- **`tap()`** reads `dumpsys input` and refuses to tap through any foreign window. A soft keyboard is
  closed first; anything else is a `Failure`.
- **`type_url()`** closes the keyboard after submitting. It allows 1.5 s for the normal hide. A keyboard
  still taking touches after that is ended with `am force-stop` of the default IME, never the app.
  The event is recorded as `soft-keyboard-closed`.
- **Expired notice.** The quiet notice is a `LENGTH_LONG` snackbar shown at the first blocked request.
  After a full 15-probe matrix it can expire between the dump that finds it and the tap:
  - rc2 had one such normal-tab miss.
  - Each run here has one, always at the same step: the first blocked probe is about 3.5 s before the tap.

  The harness treats a miss as an expired notice only when the notice is gone and no other permission UI
  opened. It then uses the site controls. Each attempt is recorded as a `quiet-review` event.
  `run()` **requires** Review to have opened the list in a normal tab and in a private tab, as check
  `quiet-review-opens-permissions-in-normal-and-private-tabs`. A broken Review action therefore still
  fails the run.
- **Second private page.** After "Close tab" closes the last private tab, Fenix shows the empty private
  home. Its tab-counter menu has no "New private tab". The second private page is typed into that home's
  address bar. The harness had never reached this step before.

## Runs with the committed harness (`smoke/`)

Conditions:

- emulator-5582: android-30 `default` x86_64, swangle, fresh AVD, `-dns-server 9.9.9.9 -tcpdump`.
  The harness booted it.
- AMO reachable. No priming, no iptables. One emulator.
- The harness wipes app data, so each run starts on a fresh profile.
- APK: the rc2 throwaway-signed `77348e7d…af83`.

Every row of `smoke/exit-status.jsonl` for `baseline-defc-r*` records:

- `repo_head` `f7f519f6`, with `uncommitted_script_changes` 0;
- `android-smoke.sh` sha256 `aabbb7a7…3ad5`;
- `android-graphics-smoke.py` sha256 `ce0072ea…4612`.

| Run | Exit | Graphics acceptance | Review: private / normal opened | Keyboard force-closed |
| --- | --- | --- | --- | --- |
| `baseline-defc-r1` | 0 | PASS, 161 checks | 2/2 / 9/10 (1 expired, fell back) | 1, after the private URL |
| `baseline-defc-r2` | 0 | PASS, 161 checks | 2/2 / 9/10 (1 expired, fell back) | 1, after the private URL |
| `baseline-defc-r3` | 0 | PASS, 161 checks | 2/2 / 9/10 (1 expired, fell back) | 1, after the private URL |

The baseline's other checks passed in all three runs: https-only, page-load, video, getusermedia,
extension and pref-dump.

`DIAG-uncommitted-baseline*` are three earlier runs of the **uncommitted** harness on the same emulator.
They are kept because they show how the fix was reached; they do not count as acceptance.

1. 54 checks, then the expired-notice miss, before the fallback existed.
2. 112 checks. Private Review opened 2/2, then the empty private home stopped the run.
3. PASS.

The older rows in `exit-status.jsonl` do not have the graphics-hash fields.

## Manual reproduction (`repro/`, scripts in `diag-scripts/`)

The scripts drive uiautomator against a local fixture served from `diag-scripts/fix/`:

- `index.html` makes its canvas/WebGL requests on load;
- `delayed.html` makes them 4 s after load, as the harness's probes run after navigation;
- `plain.html` makes none.

| Build | Scenario | Fresh normal (VIEW intent) | Private (menu, typed) | Normal after private (menu, typed) |
| --- | --- | --- | --- | --- |
| rc2 `77348e7d` | keyboard left as is (`rc2-back.log`) | opens | **nothing** | **nothing** |
| rc2 | keyboard closed as the harness does (`rc2-back-kbd-delayed-{1,3,4}.log`) | opens 3/3 | **opens 3/3** | opens 3/3 |
| Beta 2 `9b63f2ed` (versionCode 2016184438) | keyboard left as is (`b2-back.log`) | opens | **nothing** | **nothing** |
| Beta 2 | keyboard closed (`b2-back-kbd.log`) | opens | **opens** | opens |

Notes on the rc2 rows:

- `rc2-back-kbd-delayed-2.log` aborted before any typed-tab Review. An "Redoubt isn't responding" dialog
  covered the tab-counter long-press (`…-2-anr-dialog.xml`). The same transient ANR happened once more
  during this session's scratch runs. The ANR trace taken then showed the main thread idle again.
- `rc2-back-kbd-onload-fixture-expired.log` closed the keyboard *after* `index.html` had already raised
  its request. The tap came about 3.6 s after the request, so the notice had expired. The timing comes from
  that run's logcat as read in the session; the logcat was not kept.

Earlier scratch runs, 9+ of them with Review in a private tab or a menu-opened normal tab and the keyboard
not closed, gave the same result on rc2, on the instrumented build and on Beta 2. Their outputs were lost to
a shared scratch directory being cleaned, and they were rerun as listed above.

## Are testers affected?

**The Review action itself works in Beta 2 and in rc2.**

On this emulator, though, a URL typed after the tab-counter menu's New tab or New private tab leaves the
keyboard over the bottom 40 % of the screen, in both builds. The quiet snackbar is then hidden under it,
and Back navigates instead of closing it. Whether real devices or other keyboards do this was **not
tested**: no physical device, only LatinIME on API 30.

The keyboard behaviour does not involve any Redoubt patch. No Android patch touches toolbar focus or
keyboard handling. It needs separate triage, upstream Fenix 153 first.

## Not done

- No rc3: the product is unchanged.
- No physical device, no other API level, no other IME.
- No Fenix unit-test run: no Fenix code changed.
- The scratch tree `build/scratch-defc/` (26 GB, instrumented) is diagnostic only and was not committed.
