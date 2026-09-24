# Restricted copy visibility without changing admission equality

Root read the actual failing Kotlin source, the guest Kotlin2.3.21 version
catalog and the existing `PocketResponse.Success` annotation pattern. The fix
adds `@ConsistentCopyVisibility` to `Snapshot`. Its data class, internal
constructor, generation and structural comparison remain unchanged. The existing
stale-generation test now first asserts the unchanged snapshot is current.
A plain class with the same equality expression would reject every snapshot.

The complete original policy patch/source receipt remain here. The failed
build archive retains the actual before files, version catalog and annotation
example. `source-overlay.json` binds exactly two changed Android Components files
and the resulting patch. The20-file Task26 replay passes, and Task29's17 code plus
13 generated files replay unchanged after its predecessor digest is updated.
The19 authored Kotlin tests still need target execution.

`../stage-admission-copy.py` requires the exact terminal failed APK source,
checks all165 source files, verifies the successful native4 AAR hashes and stages
only these two Kotlin files. Its separate receipt distinguishes the new APK/test
source from the immutable164-file native compilation contract. The Kotlin files
belong to the Gradle APK/test stage, so the successful native GeckoView binaries
are reused. No compiler warning policy or native validation is weakened.

The retry runs `run-apk-copy-recovery.sh`, then full target suites, then the
candidate runtime checks via `run-copy-recovery-checkpoint.sh`. Every failure
stops the sequence. Actual compilation/tests/runtime are still pending.
