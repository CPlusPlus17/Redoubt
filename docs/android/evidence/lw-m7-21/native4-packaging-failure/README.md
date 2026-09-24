# Native4: successful compilation, failed publication collection

The original native4 invocation `367f4a0c473843b4832ee42f0c9e2ff2` compiled
armeabi-v7a, arm64-v8a and x86_64 successfully. Their actual mach exits were zero
at 01:22:48, 01:52:48 and 02:18:58 UTC on 2026-09-09. Collection failed at
02:19:00, before the merge: the warmed x86_64 Maven directory contained both
the new ABI publication and an older unqualified merged publication. The
upstream packer includes every publication it finds, so the resulting ZIP had
two AARs and correctly failed the exactly-one-AAR check. Driver exit was 1.

`guest-evidence.tar.gz`, SHA256
`d668cd1cfec21df31dff0a1f96fe6a7c3bf049d9c5d93875bb7a1443cf08820f`,
retains the complete three compilation logs, Maven logs, original driver/config,
source checks, resource profiles, service journal and failure classification.
`result.json` binds every original archive, including the rejected mixed ZIP.
Original archive bytes are also retained separately in the guest. All 164 source
hashes matched after the failure. The cgroup OOM-kill counter remained at its
inherited value 1; this failure was publication collection, not another OOM.

The driver now moves an existing Maven publication directory aside before a
fresh per-ABI build, preserving it under a unique directory. Gradle publishes
into an empty destination. The upstream packer and ABI/merge integrity checks
remain in place. Four executed regression tests cover cold output, mixed warm
output with old metadata, repeated preservation and failed-move abort.

The bounded recovery starts with exact hashes for all three failed-run archives
and the same source manifest. It reuses the two good ARM inputs, retains the
mixed ZIP, and reruns the x86_64 incremental build/publication plus actual merge.
The original native evidence is preserved as `native4-before-packaging-recovery`.
Recovery began at 02:26:04 UTC, service invocation
`ccc5207e78634d29bcb93761796c9542`; no browser source changed.

The first queued checkpoint stopped on the failed native service. A replacement
checkpoint, invocation `9538ef413fbf4a1daaeb0a74e4adb845`, waits for recovery and
then captures the successful parent/recovery evidence before APK, full unit tests
and runtime checks. These later stages remain pending at this record's creation.
