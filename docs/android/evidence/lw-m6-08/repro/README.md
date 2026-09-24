# Final beta APK reproducibility — 2026-09-08

E6 passes for the four APKs in `../SHA256SUMS.candidate`. The normal candidate
build and both independent reproduction builds are byte-identical for every ABI.
`candidate-comparison.json` records their SHA-256 hashes and all eight successful
`cmp -s` comparisons. The wrapper exited 0 after 1,426 seconds, finishing at
14:39:09 UTC.

The exact invocation is in `command.sh`. It uses the patched isolated source,
`MOZ_BUILD_DATE=20260906190000`, R8 enabled, and the same three prebuilt native
AARs as the normal candidate. `../candidate-inputs.json` identifies the source
archive, AAR hashes and image. Each reproduction uses its own fresh container and
Gradle home; shared Gradle build outputs are wiped between runs. Dependency
artifacts are seeded for offline availability. No APK build-cache output is reused.

`run.log`, `summary.txt`, `compare.log` and `negative-control.log` preserve the
wrapper outcome: both builds succeeded, every APK was rejected by `apksigner`
as unsigned, all four pairs matched, and one deliberately changed byte was
detected. Full build logs and ZIP listings are compressed losslessly here.
`build1-apk.sha256` and `build2-apk.sha256` are the original generated manifests.

These tests cover APK assembly on this machine. The native Gecko builds and
cross-machine reproducibility are still unverified. The fixed compiled Config
class separately passes date, timezone, next-hour, same-hour and ABI regression
checks in the [Fenix evidence](../../lw-m7-06/beta-audit-2026-09-08/fenix-README.md).
The old compiled class failed 22 assertions (`../version-code-before.txt`).

Signing changes the APK bytes. These are unsigned candidate hashes; future
returned release APKs need their own signed checksum manifest plus signature
and payload verification described in the holder handoff. Neither reproduction
nor test signing establishes release-key custody.
