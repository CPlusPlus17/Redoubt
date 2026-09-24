# Same-APK runtime retry with a corrected harness

This version prepares another runtime attempt on the exact successful APK build
`598783f0987b4c139fb0053c501f5628`, source167 `4ff8b616…`, and full-test invocation
`c02a8b984fae45dc859eff2b556b82f0`. It does not rebuild or resign an APK. The four
APK files/resources, original build configuration, source/native before/after
checks and successful test/build services remain mandatory through the original
`current167-process-recovery` contracts.

The fixed five-file capsule comes from `9f936d3`. Its repository-shaped layout
preserves the scripts' existing dirname imports and preference baseline lookup.
Only the bounded null readiness polling and actual window-handle result parsing
changed in those upstream harness files. Every capsule file is pinned by hash
and size; missing, additional or linked files fail. Commands execute capsule
paths, and reports must name the exact capsule smoke hash and same APK.
No repository-path environment override or product-pref change is introduced.

The original guest repository remains `base.REPO`. Do not replace its canonical
scripts with the host's corrected scripts: their original bytes are dependencies
of the successful APK and failed runtime configurations. Transfer only these new
files under this directory: `common.py`, `runtime.py`, `capsule-files.json` and
the five capsule files. Also retain root's exact failure archive at
`docs/android/evidence/lw-m7-21/current-account-process-runtime/runtime-failure.tar.gz`.
The wrapper imports the original common/runtime code without editing it. Full
original configuration validation runs before adding the separate new-code and
capsule checks.

The failed `a172ec824e2a4e94a4dd467627f6a0d0` attempt remains a failure. Its archive
SHA256 is `7be5d87a93ac83c983bbe93dd28679b101d6c381fce564627cdb16cc011382b1`.
All 55 archived members are verified, and the original checkpoint, captured
runtime-work files and original configuration files are compared with their
actual retained bytes. Preserve the same terminal failed service through retry
and subsequent stage review. A missing/replaced/running service or changed old
evidence blocks this version; the archive never substitutes for new acceptance.

The new output paths are `evidence/harness-process-runtime` and
`harness-process-runtime` beneath the existing guest work directory. Both must be
absent. The service is `redoubt-harness-process-runtime-20260909.service`, launched
with `RemainAfterExit=yes` so later staging can verify its successful invocation.
There must be no existing emulator or container.

After root has copied and rehashed only the nine required files, capture a
concrete configuration in the idle guest:

```sh
python3 docs/android/evidence/lw-m7-12/harness-process-recovery/runtime.py --print-config
```

Review and retain the exact JSON/hash before launching that named service with
`runtime.py --config /absolute/inputs.json --config-sha256 ACTUAL_SHA --run`.
Without `--run`, the same configuration is validated without creating output.
No actual future invocation or result is supplied by this preparation.

All 10 uBO lifecycle checks, all 8 baseline checks, the pref dump/lock audit and
owned-emulator cleanup remain required. The baseline and pref audit still run
after a failed uBO check when the created emulator is available. Any failed gate,
missing/failed report check, tainted report, unexpected pref injection or cleanup
failure leaves the attempt failed. Final validation repeats source/native,
original history, same-APK and capsule checks even after an earlier failure.
The 15 host controls exercise these boundaries using explicit fixtures; they do
not establish any APK runtime pass.

The new `common` exposes the runtime namespace/service plus `load_config`,
source/native/base APIs, and `runtime.checked_build`/`grade_smoke` for a later
separately reviewed245 staging helper. That helper must preserve its current
version before changing its import and own-input inventory. Source245 `40da1bf9…`
and native249 `84da9b40…` remain separate inventories. This retry cannot admit
native5 until its own runtime result and live terminal service pass.
