# Integrated compilation correction

The first extended native build failed because GeckoResult's cancellation
interface has a default method and cannot be used as a Java lambda target.
The correction uses an anonymous `CancellationDelegate` with an explicit
`cancel()` override. It preserves the private UUID, event and returned result.
No public API changes or broad download permissions were introduced.

`translation-cancellation-lineage.json` pins the old/new production patch,
old/new Java source and exact incremental correction. `translation-replay.log`
records all 6 packaging and 45 actual-source tests passing on the Fedora host,
with zero-fuzz/no-offset patch reconstruction. These tests do not compile Java.
The old integration receipts under lw-m7-16 remain pinned to their original
patch. Coverage pins now refer to the reviewed correction.

`guest-correction.tar.gz` preserves the guest's original Java file, dry/apply
logs and complete 89-entry before/after checks and new source manifest. The
original integrated source receipt remains unchanged. The next build copies
the revised manifest into its own evidence directory.

Guest service `redoubt-parity-native2-20260909.service`, invocation
`6ec57743c75748f49e10a0d155fb6366`, started 2026-09-08 23:21:38 UTC. It rebuilds
all three ABIs with the same bounded driver and no `--skip-existing` option.
At this receipt it is running; compilation and runtime acceptance are pending.
