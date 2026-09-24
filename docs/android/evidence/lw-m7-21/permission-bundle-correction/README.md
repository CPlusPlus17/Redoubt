# Typed permission-dialog arguments

Only the Fenix dialog argument construction changes: Bundle.putString for the
same nullable tab/context IDs and putBoolean for the same private-mode flag.
The deprecated AndroidX import is removed. All permission selection, IPC,
origin/private checks, native code and existing argument keys are unchanged.

The exact original graphics patch,36-path hash receipt and validation result
remain here. Source overlay records actual failed-source and corrected-file
hashes. Root compared the complete old/new new-file patch sections against
those actual bytes. This is a Kotlin constructor/compiler correction; the
existing37 native-module JS tests are unaffected and are not a substitute for
the required actual Fenix build and target UI/private-context tests.

A separate stage changes only this file on the prior165-file APK source after
checking the completed failed build and successful native4 AAR hashes. Earlier
three Kotlin corrections and the empty shortcut resource remain bound. All
prior compile failures remain retained. New target compilation/tests/runtime
are pending until the bundle-recovery checkpoint actually completes.
