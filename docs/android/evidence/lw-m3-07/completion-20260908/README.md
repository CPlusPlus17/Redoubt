# LW-M3-07 implementation evidence — 2026-09-08

The parked catalogue stub is replaced by a real installer for the unmodified,
AMO-signed uBlock Origin 1.74.0 XPI. **Final Kotlin compilation, the full Fenix
test suite, and APK runtime acceptance are still required.** Registration and
the local checks below do not mark LW-M3-07 complete.

## Pinned input and installed state

`assets/ubo-extension.json` pins the specific
[AMO download](https://addons.mozilla.org/firefox/downloads/file/4981431/ublock_origin-1.74.0.xpi):
4,617,614 bytes, SHA-256
`175756d74468c9ba45863f7fc333d3be670f82d5b066314e915814dd547d1652`,
GUID `uBlock0@raymondhill.net`, Android Gecko minimum 115.0. The fetcher checks
these values and ZIP structure for downloaded, cached and explicitly supplied
files. It copies the XPI without modifying or unpacking its signed contents.
Signature-file presence is a packaging check; Gecko performs cryptographic
signature verification during ordinary `AddonManager.installAddon` installation.

Fenix copies its APK asset to a uniquely named private file, checks the actual
copied size/hash again, marks the file read-only, and installs its `file:` URI.
Only the active verified transaction with the exact GUID, version and file URI
receives a one-shot install approval. Initial private-mode permission matches the
desktop policy; subsequent user permission changes are preserved. Other installs,
optional permissions and update permissions retain their normal prompt paths.

The real Gecko registry supplies installed/enabled state. No fabricated catalogue
entry or AMO catalogue request is needed for preinstallation. Ordinary
AddonManager update registration remains in place. Existing extensions are never
reinstalled, downgraded, enabled, or given private permission by reconciliation.

An `attempted` decision is durably written before installing. An interrupted
attempt with no extension requires explicit Retry; it is not silently repeated
at the next launch. `complete` survives changes to the bundled version, so later
removal and disabling survive app restarts and upgrades. Clearing app data creates
a fresh provisioning state. The failed state holds browsing and offers Retry or
Close; no failure is represented as successful protection.

## Readiness and cancellation

uBO 1.74.0 starts an asynchronous IIFE in `js/start.js`; first installation
explicitly unsuspends requests before filter initialization. Its later
`webRequest.start()` call registers the blocking `onHeadersReceived` listener
through `js/traffic.js` only after filter loading. Neither installation success,
background-page DOM readiness, nor a fixed sleep proves this sequence finished.

`ubo-readiness.patch` tracks live blocking response listeners, excludes primed
startup listeners, and exposes a bounded GeckoView wait for an active matching
ID/version with `webRequestBlocking`. Session creation waits for that signal.
This proves listener activation for an updated extension; the stronger internal
filter-initialization relationship is established for the inspected 1.74.0 input.
Future uBO pin updates require that relationship to be reviewed again.

Cancellation is bound to a native UUID, extension ID and expected version. The
request is registered before the first async lookup. Cancellation, timeout,
shutdown and success all remove the active request and its timer/listeners.
Completed/cancelled UUIDs cannot be reused during the runtime's lifetime, so a
late cancellation cannot target a later waiter. Kotlin propagates coroutine
cancellation to both the install operation and the readiness result.

The existing common `custom-ubo-assets-bootstrap-location.patch` remains active.
The actual XPI reads `storage.managed`'s `adminSettings.assetsBootstrapLocation`
and uses it as its filter assets JSON location. This Gecko preference is not an
XPI installation path. Runtime verification must exercise the genuine extension's
managed-storage and filter behavior, not merely read the preference.

## Checks and remaining acceptance

- `packaging-unit-tests.txt`: 22 Python tests passed, including corrupted bytes,
  wrong identity/version/Android support, offline cache validation and dry runs.
- `readiness-unit-tests.txt`: 18 tests execute the actual patched JS methods,
  including primed/nonblocking controls, shutdown, timeout, version replacement,
  cancellation before lookup, unrelated cancellation and request-ID reuse.
- The replacement patch contains 17 coordinator/hash tests, four navigation
  queue tests and two additional A-C trust-routing tests. They are written and
  reviewed but have not yet been compiled or executed in the Android build.
- `preinstall-patch-dry-run.txt`: all 11 files apply to the isolated baseline at
  fuzz zero. Seven shared-file pairs replay identically in either order;
  `no-adjust` must precede the new HomeActivity hunk. The two order-replay JSON
  files retain successful results and unsuccessful alternate-baseline attempts.
- `gecko-readiness-first-build.log`: the initial readiness bridge compiled in
  the VM. It predates cancellation changes and does not validate the final bridge
  or Kotlin installer. A combined rebuild remains required.
- `implementation-inputs.json` records hashes of the final local implementation
  and test inputs at this evidence checkpoint. `generated-source-sha256.json`
  records resulting source bytes independently of patch-context formatting; the
  post-transfer whitespace normalization changed no source behavior or bytes.

APK acceptance must cover a clean offline first launch with an incoming URL;
actual normal/private blocking plus an allowed control request; a customized
managed filter bootstrap; removal and disable across restart and APK upgrade;
preservation of private-mode choices and newer installed versions; ordinary
untrusted install/update prompts and signature rejection; and failure/retry
without opening browsing before readiness. Existing smoke `--check-ubo` alone
does not establish those behaviors.
