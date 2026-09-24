# Integrated native build: first attempt failed

Guest service `redoubt-parity-native-20260909.service`, invocation
`6353935d4f434577b7f764bc21835e08`, ran 2026-09-08 23:11:33–23:16:42 UTC.
All 89 source/asset hashes matched before and after the run. The first
armeabi-v7a build failed in `:geckoview:compileDebugJavaWithJavac`:
`TranslationsController.java` used a lambda for `CancellationDelegate`, whose
only method is default. Java therefore does not treat it as a functional
interface. No architecture completed, and no new APK was produced.

The archive preserves the complete first-ABI log and driver receipts. The
correction and next source manifest are tracked under `lw-m7-21`; a passing
source test does not replace the pending target rebuild.
