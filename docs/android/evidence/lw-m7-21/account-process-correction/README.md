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
invocation `6f12325cbb0d4a7a833126faeec509e6`, finished with exit zero. It selected four Fenix
classes (application, account preference, Suggest policy and Home navigation),
three account/worker classes and the synced-tabs worker. Root captured the actual
terminal service, stage receipt, sources, logs and three XML archives using
`capture-diagnostic.py`. All48 cases in eight classes passed with no failures,
errors or skips, including all three newly added process regressions. Root also
independently verified every archived member and regraded the XML on the host.
`diagnostic-success.tar.gz` SHA-256 is
`915c66150ea7582e8c6f6372c787b6374c0edd117ff488b67df67216526a1680`;
`diagnostic-result.json` records every class, method and retained file hash.

The full Fenix/AC run started separately under
`redoubt-fenix-account-process-tests-20260909.service`, invocation
`c02a8b984fae45dc859eff2b556b82f0`. Full test success, new APK compilation and new
runtime are still pending. Diagnostic success does not establish them.
