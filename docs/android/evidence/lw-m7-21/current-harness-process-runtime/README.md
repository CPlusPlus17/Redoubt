# Same APK runtime: uBO succeeds, graphics blocked by install notice

Root executed and captured invocation `0189d8626a9a4a38b540d037781d3c45` of
`redoubt-harness-process-runtime-20260909.service` on the Fedora KVM guest.
Terminal state is **FAIL**, `failed/failed`, `ExecMainStatus=1`, with
`RemainAfterExit=yes`. The original failed attempts remain retained.

The current 167-source manifest is
`4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739`.
This run reused APK build invocation `598783f0987b4c139fb0053c501f5628`,
full-test invocation `c02a8b984fae45dc859eff2b556b82f0`, and native4 inputs.
The installed x86_64 APK hash is
`7ce0d286a108d4434267e4377f4d82720c29e841c8d65c5a32612a8017857146`.

Actual results:

- uBO lifecycle: **10/10 PASS**, including first-navigation blocking and signature,
  disabled state after restart, removal after restart and APK reinstall.
- Baseline: **7/8 PASS**. HTTPS-only, HTTP exception, HTTPS load, video,
  getUserMedia denial, extension execution and preference dump pass.
- Graphics: **FAIL**, acceptance incomplete. All 17 preliminary assertions passed
  (current document, 15 protected graphics operations and no automatic prompt),
  then the runner could not find Review or site-info controls.
- Pref audit: exit 0, **0 violations**, 58 dumped prefs and 20 audited must-lock
  keys. The remaining 117 keys are outside the dump universe. The unlocked
  WebGL prompt is enabled and differs from the older baseline, a reported
  non-must-lock difference rather than a violation.
- Emulator cleanup: exit 0. Source and native input checks pass before and after.

Root inspected `failure-ui.png`: a visible bottom sheet says “uBlock Origin was
added,” describes extension settings, and offers “OK”. The browser is dimmed
behind it. The XML and screenshot show why permission controls were unavailable;
this does not establish that the underlying graphics permission flow works.
The next harness correction must acknowledge only this identified informational
notice and rerun the full acceptance suite.

`runtime-failure.tar.gz` contains 95 regular, unique members. `result.json`
records its hash and inventories the captured files. Root independently verified
all 94 inventoried members, all 26 graphics artifact hashes, all four original
APK hashes in the guest, the 167 source files and all three native AAR hashes.
The archive includes original and capsule configuration bytes, terminal service,
journal, all runtime receipts/logs and the complete nested graphics run.

`capture.py` runs read-only in the guest and refuses a running service or a
different invocation/source. `capture-config.py` records the separately pinned
harness configuration. Additional extracted graphics files are convenient copies
of originals retained in the main archive.

`startup-logcat.txt.gz` is a separately recorded, read-only logcat stream. Its
reader exited 255 as the emulator was cleaned up, before the 180-second limit;
that reader status is not a runtime gate. Its 3,046,325 raw bytes and hashes are
recorded in `startup-logcat-capture.json`. No `FATAL EXCEPTION` line occurs in
that captured stream; this statement is limited to that stream.

No source staging, native rebuild, release signing or publishing occurred.
