# Current167 runtime startup failed

Fresh emulator run `redoubt-fenix-regression-runtime-20260909.service`, invocation
`9513a070506a4a29baf9848b2ea7e8eb`, used the successfully rebuilt x86_64 APK
`4391d56d…` and source167 `501d0461…`. Android30 logcat records repeated fatal
isolated Gecko app-zygote process crashes: `FenixApplication.attachBaseContext`
reads SharedPreferences before its main-process guard, and Android's unavailable
UserManager produces a NullPointerException. This is an actual startup defect;
passing JVM tests and APK compilation did not validate isolated-child attachment.

The first uBO harness could not open Marionette within180s and exited2. No uBO
behavior check completed. After preserving the crash log, root sent SIGINT to
the checkpoint's main process to stop the now-started baseline. The checkpoint
recorded FAIL/KeyboardInterrupt and successful emulator cleanup. Baseline was
interrupted and the preference audit did not run. Root then stopped the owned
service to remove remaining harness processes. No runtime acceptance is claimed.

`runtime-failure.tar.gz` retains27 hash-verified members: failed checkpoint,
complete first-gate log, partial baseline, emulator logs, pcaps, input checks and
terminal service/journal. `startup-logcat-20260909T0523.txt` retains actual Java
stacks. `source-before.tar.gz` retains the actual guest application, account
admission and test source plus existing process detection after all167 bindings
were checked. `result.json` records every digest and the independent archive
verification. These are frozen historical inputs for the separate process fix.

The source remained unchanged. All later245/249 source staging, native builds,
APK/runtime and native tests need explicitly refreshed source identities after
the fix, and successful corrected runtime evidence; this failure cannot qualify.
