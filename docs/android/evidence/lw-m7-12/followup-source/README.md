# Followup source application

The host reviewed and replayed the final LW-M7-19 add-on durability patch,
including both root-requested recovery/notification corrections: all 36 source
tests pass. LW-M7-24's two-path home patch also replays, including both orders
of its shared FML file, with target tests still unexecuted.

`input-plan.json` binds those final patches and all eleven before/after paths.
They are queued after the 89-source native attempt 2. That run was interrupted
by a controlled VM shutdown after measured guest memory pressure (LW-M7-25).
`apply.py` refuses to run while that service or a build container is active;
it requires the archived interruption receipt and a new, matching boot identity.
It verifies the unchanged parent source, preserves original files, applies without
fuzz/offsets and creates a new combined manifest. A prior compile success is not
claimed. The revised driver ran after reboot: all 89 parent hashes, eleven
before/after patch hashes and 100 combined final hashes matched. Both patches
applied with zero fuzz/offsets. `guest-application.tar.gz` retains the full source
application evidence and originals. The first invocation failed before mutation
because Podman inherited the administrator's inaccessible working directory;
the revised driver explicitly enters the runner repository.

Native attempt 3 is running with the new combined manifest; its successful result
is required before the extended APK/test/smoke drivers. Earlier 89-source receipts remain
separate. The prepared full Fenix grader also requires the new home test class.
No current APK includes either followup, and the observed restart bug remains
open until the actual immediate-force-stop probe passes on matching new bytes.
