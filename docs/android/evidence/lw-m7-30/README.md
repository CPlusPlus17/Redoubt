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
checks with zero fuzz/offset. With `--apk` and `--aapt2`, it resolves
`org.redoubtbrowser:raw/initial_shortcuts` through the actual compiled resource
table, checks every configuration's referenced ZIP member, and requires exact
source bytes plus the empty schema. It rejects missing/duplicate entries,
non-file values, absent defaults, unsafe paths, tool diagnostics and concurrent
APK replacement. Finding equal bytes at an unrelated ZIP path cannot pass.
`aapt2` may also be selected from PATH; an absent tool fails the APK check.
No Kotlin or storage code was changed.

On 2026-09-09, the actual release APK compiled successfully, but the checkpoint
stopped when the original checker assumed the literal ZIP path
`res/raw/initial_shortcuts.json`. Release resource optimization retained the
resource identity and shortened its archive path. The actual build's aapt2
reports:

```text
Package name=org.redoubtbrowser id=7f
    resource 0x7f130005 raw/initial_shortcuts
      () (file) res/GA.json
```

`res/GA.json` has exactly 17 bytes, SHA256
`3b459147c8170c320545247d8ba79c22d55408311adafa4ad737f02c7aa78700`, and the expected
empty JSON. The corrected checker passed against a read-only, byte-identical
host copy of the x86_64 APK, SHA256
`b9ba874882bbf3258adab739d52b0e86af63aef43e7df5e4e283b22485913ff2`.
The copied build aapt2 is version `2.20-14304508`, SHA256
`c9f30b34c02fd48165251541125c3b7f21b98624e0f8341436fc65a84095e5d6`.
`apk-resource-recovery.json` binds these inputs, the resource-table and complete
dump hashes, command, and observation scope. `apk-resource-check.txt` and
`resource-table-entry.txt` retain the result and selected actual table lines.
The source receipt/patch are unchanged; no new APK build is needed for this
checker correction. The original failed checkpoint remains historical evidence.

Run the packaged-resource check with the actual build tool:

```sh
python3 docs/android/evidence/lw-m7-30/check-source.py \
  --apk /path/to/fenix-x86_64-release.apk --aapt2 /path/to/build/aapt2
python3 -m unittest discover -s docs/android/evidence/lw-m7-30 -p 'test_*.py'
```

The 15 host tests cover optimized and original paths, unrelated equal bytes,
incorrect regional variants, missing/duplicate mappings and ZIP entries,
incorrect package/resource identity, unsupported values, unsafe paths, failed
aapt2, tool diagnostics and concurrent APK replacement. They test the checker;
they do not establish device behavior. The retained `resource-check-host-tests.txt`
records their actual run. Board validation passed with 122 tasks and no warnings.

Only the x86_64 packaged resource was verified in this followup. Other APKs and
fresh/region-change, retained-data and manual-add device checks remain pending.
NoDefaultBookmarks concerns the separate bookmark database and is not established
by this shortcut change. APK signature/release acceptance is also separate.
