# Navigation fixture correction and actual targeted result

Only `HomeActivityAccountSettingsTest.kt` changes. All167 source bindings and
all three native archives are checked before and after staging. The parent
failure is retained separately. The new complete manifest is
`501d04614edbc847b416cd5b6f1dac42dd0728a63125a3d9902c90d07a579c8b`.

The actual targeted VM service invocation `aea186042c534419b68a50f030c53f0e`
compiled and exited0. Root independently graded the retained XML: exactly the
four expected method names, four passes, zero failures/errors/skips. The shell
runner itself reports Gradle's exit; this separate XML inspection establishes
coverage. Full logs, XML, stage receipts and service records are retained in
`diagnostic-success.tar.gz`, with hashes in `diagnostic-result.json`.

The full suite service `redoubt-fenix-navigation-tests-20260909.service`,
invocation `98e7f2d2d31f4b318ba25d00c04fff54`, was launched only after that
inspection. Its full gate is pending; targeted success is not full-suite, APK
or runtime acceptance. Staging inputs remain frozen for this invocation.
