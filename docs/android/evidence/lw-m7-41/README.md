# LW-M7-41 — uBO cookie-notice lists: build evidence

`apk-check.txt` / `apk-check.json`: `scripts/android-cookie-banner-smoke.py
--apk` on the scratch x86_64 release APK of 2026-10-02 (sha256
`cf5cddc5ce502ab4…`, see `../lw-m7-40/README.md` for how that tree was built
and what it is not). catalog, pref and bundled all PASS: the packaged
`omni.ja!/defaults/autoconfig/librewolf.cfg` leaves
`librewolf.uBO.assetsBootstrapLocation` at the Android catalog URL, and the
packaged `assets/extensions/ublock_origin.xpi` (uBO 1.75.0) lists
`fanboy-cookiemonster` and `ublock-cookies-easylist` under "EasyList/uBO –
Cookie Notices". The same APK's cfg ends with
`defaultPref("network.lna.allow_top_level_navigation", false)`.

Not run: `--fetch` (the URL answers 404 until Redoubt's `main` carries
`assets/uBOAssets.android.json`) and any on-device look at uBO's Filter
lists pane.

## One-time migration for existing profiles (2026-10-03)

`patches/android/ubo-cookie-lists-migration.patch` (owner decision
for Beta 5; mechanism and the rejected alternatives are in its header).
`scripts/tests/test-ubo-cookie-lists-migration.js` runs the JavaScript the
patch adds, taken from the patch's own `+` lines, against a fake
storage.local database, pref service and extension: 13 cases (upgrade
applies once and keeps every other entry, pref only after the commit, opt-out
kept, one list selected counts as a choice, fresh online/offline/shutdown,
bad shapes, failed open/write never block uBO). It is run by
`scripts/tests/test-ubo-cookie-lists.py`. The uBO facts it relies on were
read in the bundled uBO 1.75.0 XPI (sha256 `5b744158…`, extracted from the
rc3 APK): `js/storage.js` `loadSelectedFilterLists`, `restoreAdminSettings`
and `before-asset-updated`, `js/start.js` (selfie, emergency update),
`js/vapi-background.js` (`vAPI.storage`, `vAPI.adminStorage` cache, port
privilege). Not built and not run on a device.

`scripts/android-cookie-banner-smoke.py` gained a fifth check, `migration`:
the packaged `ExtensionStorageIDB.sys.mjs` (`omni.ja!/modules/` in an APK)
must carry the hook, both list keys and the pref. On the Beta 4 rc3 x86_64
APK it FAILs (catalog, pref and bundled PASS), as it must for a build without
the patch; on the patched file it PASSes. A build is still owed.

**Built and run on a device: `migration/README.md` (2026-10-03).** The hook
as committed in `fc846c48` could not run on a device: upstream
`Extension.sys.mjs` announces uBO's storage backend at startup, so
`selectBackend` is never called for it (measured on Beta 4). Fixed in
`cdeadd6c` (the backend stays unannounced for uBO while the migration is
pending); the Beta 5 candidate built from it passes the upgrade, opt-out,
Beta 3, fresh and offline scenarios and the regression smoke.
