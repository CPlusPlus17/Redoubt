Run `python3 docs/android/evidence/lw-m7-35/check-ordering.py` to replay the measured orders. The script pins the retained before archive and every current predecessor patch, verifies the **complete shared path set** for each pair, and requires canonical replay to produce the Task35 final hashes before classifying an inverse failure. All six predecessor patch hashes also matched root's registered files at the main commit recorded in `ordering-inputs.json`.

| Predecessor | Shared files | Result |
| --- | ---: | --- |
| canvas-webgl-permissions | 2 | Order-free; both orders yield identical final bytes. |
| cookie-banner-controls | 4 | Order-free; both orders yield identical final bytes. |
| extension-permission-durability | 2 | Required before Task35: Task35's extension xpcshell manifest hunk uses the Task31 test registration as context. Its module hunk itself applies before31; the manifest failure establishes the pair constraint. |
| sync-opt-in | 1 | Required before Task35: its SettingsFragment cleanup hunk uses Task20's `accountUiView.isInitialized` teardown context. The inverse fails in Task35 hunk5, not while preparing an unrelated predecessor. |
| ubo-readiness | 4 | Order-free; both orders yield identical final bytes. |
| update-check | 2 | Order-free; both orders yield identical final bytes. |

`ordering-inputs.json` lists every shared path explicitly, and `ordering-receipt.json` retains every command role, scoped-patch hash, output, exit code, setup-base hash and final hash. Changing application order legitimately shifts line numbers: offsets are recorded, fuzz is prohibited, and order-free results require byte equality. Missing files, setup failures or output differences cannot produce a pass.

One setup dependency matters: cookie23 edits context introduced by graphics14, so graphics14 cannot be reversed directly from the final before tree. The graphics pair first removes cookie23 on **both** shared paths, then removes14. Canonical replay is14→23→35; inverse replay is35→14→23. Both produce identical final bytes. The initial reverse-context problem is therefore not a Task35 ordering constraint.

Central count and ordering declarations remain root-owned. These measurements only establish patch applicability/identity, not compilation or runtime behavior.

A separate subsequent audit established that ordinary Android xpcshell does not call `Preferences::InitializeUserPrefs`; `do_get_profile()` alone cannot provide this task's current-file test fixture. The original target tests were authored and unrun, never a target PASS. Their actual-runtime correction is a separate followup and must preserve this lineage.
