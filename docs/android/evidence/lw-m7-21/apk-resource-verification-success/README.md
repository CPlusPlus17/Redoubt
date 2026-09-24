# Compiled APK resource verification passed

Root ran the corrected Task30 checker against all four unchanged development
APKs in the isolated guest. Each resource table maps `raw/initial_shortcuts` to
`res/GA.json`, whose17 bytes exactly match the empty source JSON. This resolves
the fixed ZIP path failure retained in `../apk-bundle-resource-check-failure/`.
It does not establish home-screen or bookmark behavior.

The recovery is invocation `2ea3f25605b5412ebff203aa3b363653`. Before and after
verification, all165 source bindings, the three native AAR inputs and all four
APK hashes matched their preserved compilation evidence. No APK was rebuilt.
The parent compiler invocation remains `202a41bedcc148ef9faf7d2180eec463`.
The completed APK evidence records a separate resource recovery and preserves
the original failed checker output.

`guest-evidence.tar.gz` retains all four actual checker logs and JSON receipts,
their exact checker/tool/input hashes, completed APK metadata and source checks.
Root independently verified every archive member and each APK/resource mapping;
`root-verification.json` binds that inspection. The full Fenix/component suite
started afterward and was still running at capture. Its results and subsequent
runtime checks are excluded from this resource-only record.
