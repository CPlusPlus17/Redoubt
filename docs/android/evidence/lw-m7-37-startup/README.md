# LW-M7-37: interrupted-session cleanup at startup

`patches/android/interrupted-session-cleanup.patch` closes the largest LibreWolf
behaviour gap in Beta 2: LibreWolf deletes cookies, site data and cache whenever
the browser closes; Redoubt deleted them only from the explicit Quit menu item.
A swiped-away or killed session kept everything.

## What it does

On every cold start in the main process, if "Delete browsing data on quit" is on,
`LibreWolfStartupCleanup` deletes the selected categories before any engine
session exists:

- Cookies/site data, cache and site permissions go through Gecko's `clearData`,
  **awaited on its callbacks**. Fenix's Quit path launches the same calls without
  waiting, so its completion runs before Gecko is done.
- Tabs are removed only after `BrowserState.restoreComplete`, so restore cannot
  bring them back.
- History and downloads use the same stores Fenix's controller uses.

Engine sessions are held by a second `LibreWolfUboPreinstallMiddleware` instance
(the uBO startup hold, `ubo-preinstall.patch`), so no restored tab, incoming link
or custom tab loads before deletion finishes. A failed category or the 30 s bound
is logged and browsing continues; the next cold start tries again. Quit behaves
as before; a start after Quit re-deletes what is already gone.

With Redoubt's defaults (LW-M7-09: cookies/site data and cache selected) this is
LibreWolf desktop's `sanitizeOnShutdown` behaviour, applied at the first moment an
Android session's end can be observed.

## Verified here

- `run-jvm-tests.sh`: `LibreWolfStartupCleanup.kt` and its test compile with
  `-Werror` (Kotlin 2.3.20) against [`stubs/`](stubs/), whose signatures are copied
  from the `FIREFOX_153_3_0esr_RELEASE` sources, and all 7 tests pass
  ([`jvm-tests.txt`](jvm-tests.txt)). A mutant that releases sessions before
  deleting fails 3 of them.
- The patch applies with `--fuzz=0` after the full 66-patch series on 153.3.0esr
  (`evidence/esr-153.3/replay-series.py`: 67 patches, 0 failed).
- Ordering against its eight shared-file partners was measured by swapping
  ([`ordering-swap.txt`](ordering-swap.txt)): six must precede it (they precede
  `ubo-preinstall`, whose lines are its context), two are order-free with
  byte-identical results. `check-patch-order.py` records all eight.

## Not verified

The Android glue (`AndroidDependencies`, `Components`, `Core`, `FenixApplication`)
has not been compiled against real Fenix, and nothing ran on a device. Stubs prove
the logic and its types as read, not the real classes. Required before a candidate:
`:fenix:compileReleaseKotlin`, `board.py --check-fenix-tests`, and a device run that
seeds a cookie, force-stops the app, relaunches and checks the cookie is gone before
the first page loads.

Not implemented: desktop's per-site cookie retention (`allow_cookies_for_site`);
LW-M7-37's durable journal. A kill during the startup deletion itself is retried on
the next start because the selection, not a journal, drives it.
