# Initial cookie-controls composition

Root replayed the initial LW-M7-23 patch (`be33b14682940c88a86bb4c4f375d358b0c40068db4336c24514f984aca9e8e7`)
with the merged Sync patch against all 24 scoped source inputs. The archived
baseline was reconstructed by reversing its intersecting predecessors, applying
them again and matching every original hash. Sync and cookie controls then
applied in registry order. Nine alternate pair orders produced identical final
bytes. Graphics must precede the cookie controls UI hunks. The retained uBO
constraint follows the existing uBO-to-graphics composition: the alternate
attempt failed in graphics, before cookie controls, so it does not establish an
isolated uBO/cookie intrinsic conflict. See `cookie-controls-order.json` for all
steps, hashes and shared paths. Git apply used exact context; this receipt does
not claim zero line offsets.

Root ran the 13 actual JavaScript storage-handler tests and 41 cookie-runtime
harness host tests (`cookie-controls-root-replay.txt`, `cookie-runtime-host-tests.txt`).
These do not compile Android code or execute the harness on an APK.

The initial private-domain write can outlive the last private context during
native content-pref initialization. A native lifetime fence is being implemented
before guest application. This is an open defect, not accepted runtime behavior.
LW-M7-23 now depends on LW-M7-20 because both own SettingsFragment.kt; the board
checks 111 tasks, 26 waves and zero warnings. Scope/order checks report 96 patches,
20 enforced constraints and 117 classified shared-file pairs.
