# Current245 source composition including Task37

This separate source review applies the exact15-file Task37 increment to the
final current167 / proposed232 parent. It preserves the original five-fixture
230 plan and Task37's historical243 plan, and retains the full232 parent handoff
in `parent-handoff.tar.gz`. It does not stage, compile or execute native code.

Final current167: `501d04614edbc847b416cd5b6f1dac42dd0728a63125a3d9902c90d07a579c8b`.
Final245 manifest: `9a911246fb9dcf2a55fdfe7827fd2eff000fdfecc97d8f1346c94dc018e0f995`.
101-body archive: `17f902935a133f3f7ea9e7f3292071e2ffac9eef5d59b0177e7565df39cfe37f`.

The two shared GeckoView test-support files match exact Task35 output before
Task37 applies. Eleven additional existing inputs match Task37's retained actual
guest capture; two new tests have captured absence. Every before/after hash
matches and the complete patch applies with zero fuzz and offsets. All unrelated
bodies, all13 Suggest generated resources and Task30's empty raw resource are
preserved. The previous97 materialized bodies in historical243 are byte-identical
in the101 current bodies; only the four Task20/23/26 correction rows differ or
are added to the full manifest.

There are245 total bindings and101 materialized bodies;144 native bindings lack
local bodies and require live validation. The full proposed preflight has200
existing hashes and45 absences (78 additional checks beyond current167).
Staging actions are43 replacements,45 creates and13 retained materialized inputs.
The shared test-support rows preserve their actual current167 live-before hashes
and their35 → 37 history, rather than expecting an unstaged232 intermediate.

The current HomeActivity routing correction, its final four-case navigation
fixture and the cookie/startup-metrics fixtures enter through the exact parent
archive. Earlier compiled APK and failed test manifests remain historical;
source composition supplies no target success verdict. Task37 still implements
only frame/cookie primitives: complete writer/cache admission and cleanup journal
success integration remain pending alongside all target compilation/runtime.

Reproduce:

```sh
python3 compose.py --repo /path/to/retained-repository --output /new/private/output
```

`inputs.json` pins the full parent archive and exact Task37 inputs. All10
outputs match across two fresh runs, recorded in `repeat-check.json`.
`historical-comparison.json` independently compares the preserved243 snapshot.
`preflight.py` is a read-only verifier carried from the original reviewed Task37
helper; invoking it against a live tree is a separate explicitly authorized step.
It has not been run on the guest here. Use the final receipt SHA when binding it.
