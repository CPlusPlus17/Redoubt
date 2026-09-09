# Native permission coverage and Android exclusions

Prepared read-only from root integration `248da5a`, the frozen Firefox153.0esr
source, and Task31's private source matching its committed `source-files.json`.
No guest, production source, native objdir or device changed. No target test ran.

The exact names are in `requirements.json`. The additional runnable selection is:

* `test_ext_permissions_android_durability.js`: four tasks. It is registered in
  `xpcshell.toml` with `run-if = ["os == 'android'"]`. It forces the real legacy
  backend for acknowledged disk/failure checks, then exercises both backends for
  stale derived-cache direction checks. Its uninstall task controls the emitted
  cleanup promise; it does not perform an ordinary installed-addon uninstall.
* `test_ext_permissions.js`: 26 tasks. `xpcshell.toml` includes
  `xpcshell-common.toml` on Android. The test's entry excludes Thunderbird only.
  The setup calls `ExtensionPermissions._uninit()`, whose test-only
  `_useLegacyStorageBackend` default is `false`; this selects KV independently
  of the ordinary non-Nightly production backend. Its one conditional task,
  `test_permissions_rkv_recovery_rename`, must therefore run, not skip.

The existing `test_ext_permissions_uninstall.js` defines
`test_permissions_removed`, `test_simulate_slow_storage` and
`test_ExtensionData_does_not_write_permissions`. `xpcshell-common.toml:523–529`
excludes the entire file on Android under Bug1350559. The separate
`xpcshell-legacy-ep.toml` also excludes Android in its defaults. These are real
coverage gaps preserved in `pending_xpcshell`, not unexpected failures waived by
the grader. Removing the exclusion or adapting this test requires a separate
reviewed target-test source change and actual execution. Neither this driver nor
Task31's controlled bridge test establishes that those three tasks passed.

Both selected permission files inherit `in-process-webextensions` from the normal
`xpcshell.toml`. The driver filters by that existing tag, and the grader requires
`xpcshell.toml:` IDs. `runxpcshelltests.py:1230–1243` prefixes IDs with the ancestor
manifest for duplicate-manifest entries; `:933` passes that same ID as `_TEST_NAME`.
Thus remote/legacy copies with identical task names cannot stand in for the
selected Android execution. The upstream manifests and head files remain intact.

Six Task31 source paths were added to the audited hashes after comparison with
its committed before/after receipt: both changed production modules, the new
native test, its manifest, and unchanged `Extension.sys.mjs` and
`ExtensionTaskScheduler.sys.mjs`. Ten unchanged frozen inputs additionally bind
the two existing test bodies, normal/remote/legacy include manifests, normal
head files, and the legacy backend selector. The original 17 build/harness pins
are retained, giving 33 audited files. The operator's reviewed integrated SHA
manifest must now contain 109 required product/test/source-dependency paths;
additional audited head/manifest inputs are independently rehashed by preflight.
Do not generate an unreviewed manifest merely to satisfy the driver.

All 51 runnable xpcshell tasks and 12 instrumented methods must pass with complete
fresh receipts. The aggregate result still returns PENDING/exit3 while the three
Android-excluded uninstall tasks remain open. A fully prepared driver is not an
executed target gate, and these separate test artifacts never establish release
APK behavior or private-permission durability after actual process death.
