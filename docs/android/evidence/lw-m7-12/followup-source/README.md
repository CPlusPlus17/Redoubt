# Followup source plan — not applied

The host reviewed and replayed the final LW-M7-19 add-on durability patch,
including both root-requested recovery/notification corrections: all 36 source
tests pass. LW-M7-24's two-path home patch also replays, including both orders
of its shared FML file, with target tests still unexecuted.

`input-plan.json` binds those final patches and all eleven before/after paths.
They are queued after the 89-source native attempt 2. `apply.py` refuses to run
while that service or a build container is active; it also requires terminal
native success, preserves original files, applies without fuzz/offsets and
creates a new combined manifest. It has not been copied to or run in the guest.

After application, rerun native packaging with the new combined manifest,
then the extended APK/test/smoke drivers. Earlier 89-source receipts must remain
separate. The prepared full Fenix grader also requires the new home test class.
No current APK includes either followup, and the observed restart bug remains
open until the actual immediate-force-stop probe passes on matching new bytes.
