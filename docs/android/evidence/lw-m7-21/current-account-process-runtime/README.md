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

The run finished **FAIL**, retained invocation `a172ec…`, main exit1. uBO exited1
before recording any check: `wait_for_initial_document` called `.get` on a null
script result. Baseline recorded actual passing HTTPS-only interstitial, HTTP
exception and HTTPS page checks, then its graphics runner failed on a list
decoded as a dictionary. The baseline recovery path hit the same null-readiness
exception. Neither uBO nor graphics acceptance completed.

The independent preference audit exited0:58 curated prefs were dumped;20 of the
137 must-lock keys were in that universe, with zero violations.117 keys remain
outside this audit's runtime coverage. The WebGL prompt differed from the older
non-must-lock baseline; that note is not a preference violation. Emulator cleanup
exited0. The subsequent read-only logcat request found no device, so no startup
logcat was captured and no absence-of-crash claim is made from it.

`capture.py` retained55 members, all independently hash-checked by root in
`result.json`. `runtime-failure.tar.gz` SHA-256:
`7be5d87a93ac83c983bbe93dd28679b101d6c381fce564627cdb16cc011382b1`.
The nested graphics report and both failure screenshots are retained separately
with their actual hashes in `graphics-failure.tar.gz`:
`a7811e1792a973837227dd67b6acb453a15b23035a40c43841eb884033966dec`.
The graphics report contains no completed graphics checks and names the exact
installed APK. No target source or APK change followed this harness failure.

This failed run cannot admit the future245 source stage. A separately reviewed
harness correction and fresh complete runtime are required; passing early
browsing checks or the independent preference audit does not waive that gate.
