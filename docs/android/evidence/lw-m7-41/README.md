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
