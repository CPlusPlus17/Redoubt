# Native4 compilation and packaging checkpoint

The combined GeckoView AAR passed on 2026-09-09 at02:49:36UTC. This closes
native compilation and packaging for the pinned164-file source snapshot only.
The APK job has separately staged the empty shortcut resource (165 bindings).
APK compilation, full Fenix/target suites and device behavior remain pending.
Tasks29,31,35 and36 are absent from this compiled snapshot.

The recovery invocation was `ccc5207e78634d29bcb93761796c9542`. The original
invocation compiled all three ABIs, then correctly failed collection because a
stale merged Maven publication sat beside the new x86_64 publication. Its
failure and original artifacts remain in `../native4-packaging-failure/` and
separate guest storage. The recovery reused the two hash-verified ARM archives,
rebuilt x86_64 in53seconds after preserving its prior Maven directory, and ran
the real merge (1354seconds). It did not report reused ARM builds as new ones.

`guest-evidence.tar.gz` SHA256
`3a5ac834d998c2d65d76536f2321eff52d7a8cd980626dea50a1fc7bf8cb4557`
retains full native logs, resource profiles, source checks, driver/configuration,
service identity, parent receipt and memory state. `capture.json` binds the
archive; `result.json` is the exact enclosed result. Root independently verified
the archive digest,164-file manifest, before/after checks and all four success
logs against their recorded hashes (`root-verification.json`).

The merged AAR is250062431bytes, SHA256
`49a7a3319710f733ccb59acdd25fa46919acb7b7f722df4e5950432afdfe1b11`.
All four artifacts remain under the guest's
`/home/runner/work/feature-parity-20260908/native4-artifacts/` with exact paths,
ZIP entry names, JNI members, sizes and hashes in `result.json`. The evidence
archive contains the logs and receipts, not these large artifacts.

Recorded cgroup OOM counters remain the inherited3events/1kill from native3;
this invocation introduced none. Optimization, fat LTO, PHC and compiler
hardening remained enabled; debug symbols were disabled for memory headroom.
The recovery packaging change does not relax upstream single-ABI validation or
the merge comparison.
