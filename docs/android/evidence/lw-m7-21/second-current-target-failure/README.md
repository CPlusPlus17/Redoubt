# Second current-candidate target run

The isolated QEMU guest ran the full Fenix task and the selected Android component
tasks with build-cache reuse disabled, after staging the four reviewed test fixture
corrections. The source manifest was
`46e33df9a7121a161af8e83151b44a2517b17d8609be59dc992e94e1335f4cbd`.

All 146 component cases passed: support-webextensions 53, engine-gecko 57,
browser-state 2, firefox-accounts 19, syncedtabs 1 and fxsuggest 14. Fenix failed
test compilation because six coroutine test API uses require an explicit opt-in
under the existing warnings-as-errors setting. No Fenix XML was produced; the
required Fenix gate failed and the runtime stage did not run.

`capture.py` collected the terminal service metadata, complete logs, XML archives,
all manifest-bound test sources, and the four-file staging receipt. Root verified
all 80 archive members and independently counted the XML results; see
`root-verification.json`. The archive SHA-256 is
`8f4ba4d13d5673f150da5db6e60dc4225c354aa6bfa12c5e79f8cdab96a185a8`.

The following opt-in correction preserves every test and assertion. Its separate
source receipt is in `../test-optin-correction/`; this failed run remains unchanged.
