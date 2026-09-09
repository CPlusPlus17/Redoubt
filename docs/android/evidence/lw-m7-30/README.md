# Empty default home shortcut seed

LibreWolf explicitly locks `browser.newtabpage.activity-stream.default.sites`
to an empty string (`settings/librewolf.cfg:1122`). Fenix does not use that input:
HomeActivity starts DefaultTopSitesBinding independently of home-section visibility.
That binding reads `R.raw.initial_shortcuts`, filters by region/experiment and
calls `addTopSites(..., isDefault=true)` only for a nonempty result. The frozen
resource contains Google, Wikipedia and five Japanese-region entries.

This candidate replaces that resource with the same JSON schema and an empty
`data` array. It changes no storage or migration code, no existing data, no saved
completion flag and no manual shortcut/bookmark control. The existing binding
unit tests use their own `raw/test_initial_shortcuts.json` fixture; they do not
prove the contents of the packaged production resource.

`source-baseline.tar.gz` retains the exact original resource, actual binding and
its existing tests. `source-files.json` pins all three plus the desktop setting,
patch and final JSON. `check-source.py` passes source reconstruction and schema
checks with zero fuzz/offset. With `--apk` it requires the exact compiled raw
resource bytes and prints the APK hash. No new Kotlin or storage tests were
written for this data-only change.

The resource has not been applied to the running native4 source. It can be staged
after that build is terminal, with a separate APK source manifest. Packaged APK
verification and fresh/region-change, retained-data and manual-add device checks
remain pending. NoDefaultBookmarks concerns the separate bookmark database and
is not established by this shortcut change.
