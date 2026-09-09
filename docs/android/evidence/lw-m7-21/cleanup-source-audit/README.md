# F04 cleanup: retained source findings

Root captured 14 actual native4 source files read-only while compilation ran.
Six also match the build's 164-file manifest; every selected file was checked
again before capture completed. The archive retains the parent manifest and
per-file hashes. Three separate desktop/configuration inputs are archived from
the local frozen tree and settings submodule. No browser cleanup test or source
change was performed. These are implementation findings, not measured data loss.

1. Fenix `DeleteBrowsingDataController.kt:161–180` calls the callback-based
   `engine.clearData` without providing either completion callback. Its
   `withContext` waits for dispatch only. `DataCleanable.kt:20–25` supplies empty
   default callbacks; `GeckoEngine.kt:990–1012` forwards completion asynchronously
   from the GeckoResult. Thus the suspend declaration does not await deletion.
   Cache deletion has the same issue and ignores translation-model deletion
   completion. This does not by itself establish that every Quit loses data;
   it establishes that the controller does not enforce its completion boundary.
2. `clearBrowsingDataOnQuit:216–240` invokes `onDeletionComplete` in `finally`,
   including failure. `MenuDialogFragment.kt:335–341` uses that callback to call
   `finishAndRemoveTask`. A corrected failure path needs an explicit visible
   result/retry and must not label a failed operation as completed cleanup.
3. Actual native4 `GeckoViewStorageController.sys.mjs:381–406` discards the
   clear-data callback's failed-category mask and sends success regardless.
   `nsIClearDataService.idl:447–450` defines nonzero `aFailedFlags` as failure;
   `ClearDataService.sys.mjs:2778–2793` accumulates those failures. The adjacent
   host and base-domain handlers also ignore the result. Correct target tests
   need actual callback/error paths, not only Fenix mocks that instantly succeed.
4. The Android global clear path invokes each cleaner's `deleteAll`; it does
   not apply cookie retention permissions. Desktop `Sanitizer.sys.mjs:510–560`
   selects principal-based cookie/storage cleanup on shutdown, honoring
   `cookie` permissions through `maybeSanitizeSessionPrincipals:1173–1265`.
   Its startup path also recovers pending sanitizations left by an interrupted
   session. Android settings flags alone provide neither of these behaviors.

Future implementation must preserve unselected history, bookmarks, permissions,
download records and account data; retain desktop cookie-permission semantics
and origin attributes; distinguish explicit manual clearing from session cleanup;
and wait for real deletion outcomes before reporting success. An interrupted
cleanup needs persisted pending state and recovery before the next browsing
session. Android cannot run cleanup code while force-stopped, so startup recovery
must not be described as immediate deletion at process death. Desktop's own
pending-cleanup mechanism is the relevant comparison.

Required runtime evidence remains: cookie/localStorage/IndexedDB/cache seeds,
retained and removed site controls, preserved unrelated data, actual Quit,
failed clear/retry, interruption and next-start recovery before first navigation.
This audit creates no new task acceptance or runtime pass.
