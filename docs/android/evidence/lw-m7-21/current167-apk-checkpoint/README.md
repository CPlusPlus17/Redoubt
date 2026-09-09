# Current167 APK build and resource checks passed

Actual retained VM service `redoubt-fenix-regression-apk-20260909.service`,
invocation `7a054c6290054e568f626c13bf8704a1`, completed successfully. Its reviewed
config binds source167 `501d0461…`, successful full unit gates, all three native4
archives, exact container image/date and a new output directory.

All four development-signed release-variant APKs compiled. Each actual resource
checker exited0 and resolved `raw/initial_shortcuts` through the APK resource
table to the exact empty17-byte JSON payload. Per-ABI `libxul.so` matches the
native input; source, native inputs and the historical APKs remained unchanged.

Root verified all47 members of `apk-success.tar.gz`; `result.json` retains
individual hashes, full logs, metadata, resource receipts and configuration.
The new x86_64 APK SHA-256 is
`4391d56d18dcb34951c79d23b0b1db30278ed621afc2e3bbd27f17634825b6a7`.
APK binaries remain in the guest's fresh `fenix-regression-apk-output/apk`.
Actual browser runtime is a separate checkpoint. This build excludes the later
245-file native/API composition and is not a release publication.
