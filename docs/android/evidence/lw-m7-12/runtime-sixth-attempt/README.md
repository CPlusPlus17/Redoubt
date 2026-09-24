# Baseline behavior passed; add-on restart remains failing

Guest service `redoubt-parity-smoke6-20260909.service`, invocation
`152c22364ad34195927bdc59f53e8366`, ran development APK SHA-256
`423cf7ad1b8bf713a64ef1362d57a63458b8d07ee3b9ede9ea6bee5613925451`.
The archived JSON binds the harness, APK and unmodified privacy configuration.

All eight baseline checks passed:

- The actual Fenix HTTPS-only resource error page blocked the HTTP fixture.
  A WebDriver click on its visible Continue to HTTP Site button invoked the
  native exception path. The HTTP page then completed with its marker and
  server requests; the separate HTTPS control completed in a secure context
  using the test profile's trusted throwaway CA. The native error document
  remains interactive before its load event finishes; the harness now validates
  its exact resource path/type and working control instead of relying on a load
  event alone. Its bounded navigation timeout remains in the evidence.
- WebGL2 shader/draw produced compositor pixel [51,102,153,255] while readPixels
  returned protected data. This candidate still has the historical prompt=false
  setting; it does not validate the newly implemented permission bridge.
- Video decoded 13 frames, camera/microphone denial settled after visible Android
  permission prompts, and the temporary smoke extension's content script ran.
- The curated/full pref dumps were written. The separate live pref audit passed:
  20 of 137 listed keys occur in its curated dump, zero violations and zero other
  diffs. This does not test every lock or traverse the settings UI.

Fresh first-navigation uBO blocking/signature/allowed-control checks passed again,
but immediate restart after disabling reproduced the measured startup-cache
inconsistency. That suite completed six checks with one failure and did not
continue to removal. The overall service therefore exits 1. Broader private,
upgrade, settings-control and lifecycle acceptance remains open.

This APK includes only uBO/defaults. Cookie, graphics and translation source was
integrated for a subsequent native rebuild; these runtime observations do not
validate those later changes.
