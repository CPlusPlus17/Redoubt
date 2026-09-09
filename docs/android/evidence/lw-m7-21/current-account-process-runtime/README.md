# Runtime after process correction

Root reviewed configuration
`eedd411701f1305e9fcbc4b9a1697c1ca1dea80500e4e429e99d4ce96409e4b4`
and successfully ran the nonexecuting validation command before starting
`redoubt-account-process-runtime-20260909.service`, invocation
`a172ec824e2a4e94a4dd467627f6a0d0`, with `RemainAfterExit=yes` at06:11 UTC.

The configuration binds source167 `4ff8b616…`, full tests `c02a8b…`, successful
APK build `598783…`, all four actual resource verdicts, and20 SDK/image files.
The selected x86_64 APK is
`7ce0d286a108d4434267e4377f4d82720c29e841c8d65c5a32612a8017857146`.
The new workspace is `account-process-runtime`; evidence is under
`evidence/account-process-runtime`. This run creates a fresh Android30 x86_64
emulator and uses the unchanged canonical smoke/pref scripts.

The run is active. Complete uBO lifecycle, baseline, preference audit and emulator
cleanup are required. No runtime PASS is claimed yet. `capture.py` will preserve
the actual terminal outcome, including failures, without promoting partial work.
