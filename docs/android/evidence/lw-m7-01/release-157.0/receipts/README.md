# 157.0 source receipts for six hash-pinned Android patches (2026-10-02)

Six `scripts/tests` files replay a patch onto pinned "before" source and
check pinned "after" hashes:

- `test-extension-update-controls.py` (LW-M7-35)
- `test-global-privacy-controls.py` (LW-M7-36)
- `test-session-cleanup.py` (LW-M7-37)
- `test-translation-assets.py` (LW-M7-16)
- `test-addon-state-durability.py` (LW-M7-19)
- `test-extension-permission-durability.py` (LW-M7-31)

On the 157 branch the first four failed. `version.android` reads `157.0`, so the
lookup found no `esr-<version>` receipts, fell back to the 153.0esr chain and
stopped at its first patch digest. This directory is the 157.0 counterpart of
`../../esr-153.4.0/receipts`, produced the same way.

The lookup in the four tests now reads `esr-<version without esr>` for an ESR
`version.android` and `release-<version>` otherwise. Without a matching
directory it still falls back to the original 153.0esr chain, which is left
untouched as history. `test-translation-assets.py` and the two durability
tests had no per-version lookup before; they now have the same one.

The two durability tests still passed on 157 at first, because their patches
still carried 153.0esr hunk headers that applied cleanly to the 153.0esr
baselines. They had to move to 157 receipts once the xpcshell run (below)
changed those patches.

## How the receipts were produced

```sh
python3 docs/android/evidence/lw-m7-01/release-157.0/receipts/recapture.py \
  --out docs/android/evidence/lw-m7-01/release-157.0/receipts \
  --objdir <release tree>/librewolf-157.0-1 \
  --input translation-assets:toolkit/components/translations/bergamot-translator/bergamot-translator.js \
  --input translation-assets:toolkit/components/translations/bergamot-translator/moz.yaml \
  --input extension-permission-durability:toolkit/components/extensions/Extension.sys.mjs \
  --input extension-permission-durability:toolkit/components/extensions/ExtensionTaskScheduler.sys.mjs \
  patches/android/addon-state-durability.patch \
  patches/android/extension-permission-durability.patch \
  patches/android/extension-update-controls.patch \
  patches/android/global-privacy-controls.patch \
  patches/android/session-cleanup.patch \
  patches/android/translation-assets.patch
```

`recapture.py` is the 153.4.0esr generator with one addition, `--input`. It
works in five steps:

1. Extract every path any of the 63 stack patches touches from
   `firefox-157.0.source.tar.xz`, sha256
   `259c564dd4bbd56bbe8a9a6cf001fc8812853567fd3a78e77c9ddf10d7d4e982`.
   `gpg --verify firefox-157.0.source.tar.xz.asc` on 2026-10-02: good
   signature from Mozilla Software Releases, subkey
   `827E658608679618CD349F93678E455D76767AA3`, primary
   `14F26682D0916CDD81E37B6D61B7B526D98F0353`.
2. Apply `assets/patches/common.txt` and then `android.txt` with `patch -p1`,
   the order `check-patchfail.sh` and the patcher use.
3. Capture the touched paths just before each target patch, as
   `<stem>-before.tar.gz` (deterministic, mtime 0; absent paths recorded in the
   JSON).
4. Replay the target alone on that capture with `--fuzz=0`. It must show no
   offset and no fuzz, and its result must be byte-identical to the stack's.
5. Compare each touched path after the whole stack with an independently
   patched tree. The final run compares against `work/xpc/librewolf-157.0-1`,
   the test-enabled x86_64 tree in which the xpcshell tests below ran. `make
   dir` patched it, and the xpcshell fixes were made and run in it before
   they were ported back into the patches. The first capture, before those
   fixes, matched the release tree the 157.0-1 APKs were built from on all
   paths.

| patch | before files present | `--fuzz=0` replay | equals stack | xpcshell tree |
|---|---|---|---|---|
| addon-state-durability | 7 of 9 | exact (after the hunk-header fix below) | yes | 9/9 identical |
| extension-permission-durability | 5 of 6 (2 are `--input`) | exact | yes | 6/6 identical |
| extension-update-controls | 19 of 27 | exact (after the hunk-header fix below) | yes | 27/27 identical |
| global-privacy-controls | 9 of 21 | exact | yes | 21/21 identical |
| session-cleanup | 13 of 15 | exact | yes | 15/15 identical |
| translation-assets | 13 of 15 (2 are `--input`) | exact | yes | 15/15 identical |

The present/absent counts match the 153.4.0esr receipts. The predecessor sets
also match, except that `cookie-banner-controls.patch` drops out of the
extension-update-controls and global-privacy-controls lists. That patch was
retired at the 157 integration. session-cleanup's only overlapping
predecessor is still extension-update-controls, on `test-api.js` and
`test-schema.json`. Running `recapture.py` twice gives byte-identical archives
and JSON.

### `--input`: untouched files a test reads

LW-M7-16's 153.0esr inventory pinned two upstream files the patch does not
touch: `bergamot-translator/bergamot-translator.js` and its `moz.yaml`.
`test-translation-assets.js` loads the pinned WASM 4 into that glue. A receipt
of patch-touched paths alone would leave that test reading a file that is not
there. `--input STEM:PATH` captures such a path from the same stack state, so
its before and after hashes are equal, and `replay.py` requires the replay to
leave it unchanged. Both files are byte-identical to the 153.0esr pins.

LW-M7-31's inventory likewise pinned `Extension.sys.mjs` and
`ExtensionTaskScheduler.sys.mjs`, which `test-extension-permission-durability.js`
loads. `ExtensionTaskScheduler.sys.mjs` is unchanged since 153.0esr;
`Extension.sys.mjs` changed upstream.

### Hunk headers moved to in-order line numbers

On the 157 stack, extension-update-controls applied with offsets: +16 lines on
the three `mobile/android/geckoview/api.txt` hunks and +3 on
`GeckoViewStartup.sys.mjs`. The `--fuzz=0` replay refuses an offset, so no
honest receipt could pin it. Those four hunk headers now carry the in-order
line numbers. No `+`, `-` or context line changed, and the patched tree is
identical (27/27 against the release tree, which was patched with the old
headers).

addon-state-durability likewise applied with offsets on 157 (13 hunks in
`AddonTestUtils.sys.mjs`, `XPIInstall.sys.mjs`, `moz.build` and
`xpcshell.toml`). Its `XPIDatabase.sys.mjs` section was regenerated against
the 157 before tree for the fix below. Its other headers moved by the
reported offsets.

## Fixes the xpcshell run forced (2026-10-02)

None of these xpcshell tests had ever executed; the task evidence called them
pending. They ran on an x86_64 Android 11 emulator against a test-enabled
157 objdir (`../unit-tests/README.md`). Four patches changed:

- **addon-state-durability (product bug).** `_updateAddonDisabledState` set
  `pendingUninstall = AppConstants.platform == "android" &&
  aAddon.pendingUninstall`. For an add-on with no pending uninstall that is
  `undefined`, so enabling a disabled extension computed `isDisabled =
  undefined` and took the `onOperationCancelled` branch. The choice was saved
  but the extension was never started again until a restart. It is now
  `!!aAddon.pendingUninstall`. `test_android_addon_state.js` caught it
  ("Durable registry activity - false == true").
- **addon-state-durability (product bug).** The Android refresh of an
  existing add-on's disabled state in `startInstall` ran after the
  `onInstallStarted` listeners, so it overwrote a listener's
  `install.addon.disable()`. Upstream's `test_install.js` caught it. The
  refresh now runs before the listeners. See `../unit-tests/README.md` for
  the add-on manager manifest comparison.
- **addon-state-durability, extension-permission-durability (tests).** The
  failure-injection tests stubbed `IOUtils.writeJSON` on the test global.
  System modules use the shared module global's own `IOUtils`, so the stub
  was never called and no write failed. The stubs now target
  `Cu.getGlobalForObject(<module object>).IOUtils`.
  `test_addonStartup_save_failures.js` also spies on `_recordSaveError` on
  Android. Gecko hands Glean metrics to the embedder there
  (`MOZ_GLEAN_ANDROID`), and `testGetValue()` stays null even for a direct
  `record()` in xpcshell. `test_android_addon_state.js` finds the installed
  XPI by its profile path; `_sourceBundle` is undefined on the database entry
  there.
- **extension-update-controls (test).** `test_ext_android_update_settings.js`
  used `AddonManager` without importing it.
- **session-cleanup (test).** XPConnect reports 0x80070057 as
  `NS_ERROR_ILLEGAL_VALUE`, so the `/NS_ERROR_INVALID_ARG/` pattern never
  matched; the test now compares the result code. It also sets
  `network.cookie.cookieBehavior=0` and
  `network.cookieJarSettings.unblocked_for_testing`, as upstream's HTTP
  cookie tests do. Without them every `setCookieStringFromHttp()` positive
  control was refused.

## What each file proves

- `recapture.py` is the generator above. No test runs it, because it needs the
  814 MB tarball.
- `replay.py` is the verifier the four tests import. It checks the patch and
  archive digests, every before hash (absent included), the exact `--fuzz=0`
  replay and every after hash. It needs only repository files:
  `python3 docs/android/evidence/lw-m7-01/release-157.0/receipts/replay.py`.
- `<stem>.json` holds the patch sha256, the tarball sha256, the stack
  position, the predecessors and later patches that touch the same paths, the
  `--input` paths, the per-file before and after sha256, the stack and replay
  `patch` output, and the release-tree comparison.
- `<stem>-before.tar.gz` is the before tree for that patch.
- `stack-apply.json` records each stack patch's sha256 and its offset and fuzz
  counts on 157. None of the offset or fuzz hunks is in the six target
  patches.

## Two harness fixes in `test-translation-assets`

Firefox 157 changed two things the 153 harness assumed:

- 157 creates `TranslationsChild` on demand. The rebased patch therefore sends
  `Translations:WatchPageHide` from `translateFromUser()`. The JS harness's
  stand-in parent actor had no `sendAsyncMessage`, so it now records the
  messages. The tests assert one message per admitted call and none when the
  document is already stale. The stand-in child now defines
  `ChromeUtils.defineLazyGetter` and `console`, which 157's child uses at
  module scope.
- 157 packs the GeckoView modules at `modules/`, not `modules/geckoview/`.
  `--apk` therefore reads `modules/GeckoViewTranslations.sys.mjs` when the old
  path is absent. On the 157.0-1 x86_64 APK the packaged bytes equal the
  patched source.

## What was NOT re-captured or run

- No CI guest capture was made. As for 153.4.0esr, the before trees come from
  the signed tarball and the patch stack.
- `test-session-cleanup.py` still parses with the 153.0esr XPIDL/WebIDL parser
  sources in `lw-m7-37/native-parser-inputs.tar.gz`. They parse the 157 files
  without error.
- `test-global-privacy-controls.py` still verifies LW-M7-36's original
  153.0esr audit inputs (`verify_originals`), a check on repository evidence.
- `test-extension-update-controls.py --source <tree>` does not pass on a fully
  patched tree. global-privacy-controls and session-cleanup patch some of the
  same files later, so their after hashes differ. That was also true on
  153.4.0esr.
- The receipts compile nothing and run nothing. The xpcshell, Fenix and
  Android Components runs are recorded in `../unit-tests/`.
