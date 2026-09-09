# Combined process correction staging

Root independently reproduced the six-file overlay from the actual failed-runtime
source167 `501d0461…` to `4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739`.
All161 other bindings remain unchanged. Task20 and Task26 full source replays
passed, including GNU zero-fuzz/no-offset checks, before guest writes.

`inputs.json` pins21 repository inputs and the exact six replacement bodies.
The guest stage checks all167 parent files, three native archives and eight old
APK hashes before writes and after, and retains six original source bodies.
It requires the recorded failed first runtime and completed emulator cleanup.

The actual targeted service `redoubt-account-process-diagnostic-20260909.service`,
invocation `6f12325cbb0d4a7a833126faeec509e6`, is running. It selects four Fenix
classes (application, account preference, Suggest policy and Home navigation),
three account/worker classes and the synced-tabs worker. The Gradle result and
all eight class XMLs must be inspected before the full Fenix/AC gate runs.
Targeted/full test success, new APK compilation and new runtime are still pending.
