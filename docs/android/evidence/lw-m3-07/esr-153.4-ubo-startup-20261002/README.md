# uBO startup: AMO update during first run, and launcher cold starts (2026-10-02)

Two "uBlock Origin setup failed" defects. Both are present in published Beta 2 and in the
first 153.4.0esr candidate. Both are fixed here in Fenix only (`ubo-preinstall.patch`), with
the pin bumped to uBO 1.75.0. Nothing in Gecko or omni.ja changed: the `ubo-readiness.patch`
edit touches only its header comment, above the first diff.

## Defect (b): every launcher cold start fails after 30 s

**Root cause.** On `APP_STARTUP`, Gecko delays persistent background pages until
`ExtensionParent.browserStartupPromise` resolves. On GeckoView that happens when the first
GeckoView window (`chrome/geckoview/geckoview.js`) sends `extensions-late-startup`.
`LibreWolfUboPreinstallMiddleware` holds every `CreateEngineSessionAction` until uBO is ready.
A launcher start lands on the home screen with no incoming URL, so it opens no window. That
means:

- uBO's background page never starts;
- its blocking `onHeadersReceived` listener is never registered;
- `awaitBlockingResponseListener` cannot resolve;
- the preinstaller's 30 s `withTimeout` fires.

It is a deadlock, ended only by the timeout. A VIEW intent goes through
`IntentReceiverActivity`, which calls `engine.speculativeCreateSession()`, and that opens a
GeckoSession window. So URL starts work. Tapping the toolbar would also have released it,
through `FenixSearchMiddleware.speculativeCreateSession`. A first run is not affected the
same way, because an `ADDON_INSTALL` startup is not delayed. It fails for defect (a) instead.

The logcat shows the mechanism. In `repro-before/02-restart-launcher.logcat` there is no
`GeckoSession: ... chrome startup finished` line, and `TimeoutCancellationException` comes
at START + 30.1 s. In `03-restart-view` the window opens 0.6 s after START and there is no
failure. `build/runtime/diag/amo-blocked-control/02,03` (stage C) shows the same thing with
AMO blocked and uBO still at 1.74.0.

**Fix.** Before the wait, `AndroidDependencies.awaitFilteringReady` calls
`engine.speculativeCreateSession(private = false)`. This is the same call
`IntentReceiverActivity` makes for every VIEW intent. It opens the window without loading
anything, and the first tab adopts it once the middleware releases sessions.

After the fix, `repro-after/02` and `04` (launcher restarts) open the window about 1.2–1.3 s after
START and log `startup ready` about 2.2–2.4 s after START.

**Why the harness never caught it.** Every device check starts with `App.start_url`, a VIEW
intent to `IntentReceiverActivity`, because Marionette's NewSession needs a Gecko window.
That speculative session is exactly what releases the delayed startup. The new
`--check-launcher-start` covers the gap (see SMOKE.md). It:

- resolves the launcher activity through the package manager;
- cold-starts it twice, on a fresh profile and then on a restart;
- waits 45 s;
- fails on the dialog, on a logged failure, or on a missing positive readiness line.

Results:

- `smoke-launcher-before/`: pre-fix APK `2d7db8ee…4f46`, **FAIL** in both phases.
- `smoke-launcher-after/`: fixed APK, **PASS**.

## Defect (a): AMO update during first run

**Root cause** (`repro-before/01-fresh-launcher.logcat`, AMO reachable and serving 1.75.0):

1. The bundled 1.74.0 installs.
2. `DefaultAddonUpdater.registerForFutureUpdates` runs `AddonUpdaterWorker` at once.
3. Gecko replaces uBO with the AMO-signed 1.75.0.
4. The shutdown of 1.74.0 rejects the version-bound wait: `Blocking extension stopped
   before becoming ready` (QueryException, 1.5 s after the update check started).
5. The preinstaller fails.

**Fix (1).** When a readiness wait fails, the preinstaller polls the registry for up to 5 s.
It restarts the attempt only if it finds a same-ID copy that is enabled and **strictly
newer** than the awaited version. That gives the restarted attempt a fresh timeout. It takes
the existing-installation path: no reinstall, `COMPLETE` recorded, and a wait on the new
version. This can happen at most twice.

Anything else keeps the original failure: absence, disablement, the same version, an older
version, a pre-release of the same version, or an unparseable version. The security
property does not change:

- the new copy reached the registry only through Gecko's own update install, with
  `xpinstall.signatures.required=true` (MOZ_REQUIRE_SIGNING);
- the trusted-permission override still matches only the hash-verified bundled file;
- the readiness signal is still the live blocking listener of the exact awaited version.

Unit tests in `LibreWolfUboPreinstallerTest` cover:

- replacement during the first run;
- replacement registered after the failure;
- replacement during a later startup;
- all the rejected cases;
- the replacement bound;
- the version comparator.

**Fix (2).** The pin is bumped to 1.75.0, AMO's current release (`ubo-1.75.0-review/review.txt`).
The 1.75.0 file was checked as follows:

- three independent downloads with identical SHA-256;
- `fetch-ubo-extension.py` validation;
- PKCS#7 chain to Gecko's AMO production root;
- JAR digests over every member;
- `js/start.js`, `js/traffic.js`, `background.js` and `vapi-background.js` are byte-identical
  to 1.74.0, so the listener-after-filters property `ubo-readiness.patch` relies on still
  holds;
- permissions are identical;
- the harness probe rule is present.

On device, `smoke-ubo-preinstall-after/` (fixed APK, fresh profile) shows:

- the bundled-list script is blocked on the first navigation and the allowed control runs;
- the installed add-on is 1.75.0, with `signedState` 2 (`SIGNED`, not builtin);
- private browsing is allowed;
- there is 1 live blocking listener.

The LW-M7-34 update-fixture pair moved to 1.74.0 → 1.75.0, because its verifier binds the
newer fixture to the packaged pin.

**Proof of fix (1) against a real AMO update.** With 1.75.0 pinned, AMO has nothing newer.
So a diagnostic variant was built from the same compiled Kotlin (`compileReleaseKotlin
UP-TO-DATE`; its `classes*.dex` are byte-identical to the fixed APK's, sha256 `a68ca719…d072`), differing only in the 1.74.0 asset, and run on a fresh profile with AMO
reachable (`repro-variant-pin174/01`):

```
06:38:01.303 AddonUpdaterWorker: Trying to update extension uBlock0@raymondhill.net
06:38:02.705 AddonUpdaterWorker: Extension uBlock0@raymondhill.net successfully updated
06:38:02.761 LibreWolfUboPreinstaller: uBlock Origin was updated to 1.75.0 during startup
06:38:05.902 LibreWolfUboPreinstaller: uBlock Origin startup ready: Ready(installed=true, enabled=true)
```

There is no dialog in any of its four phases. This is the situation Beta 2 testers are in
today. The variant is diagnostic only and must never be distributed.

## Runs

The emulator was a private AVD (android-30 default x86_64, swangle, `-dns-server 9.9.9.9`),
booted fresh with `-wipe-data`. It was the only emulator running. `repro.sh` does the
following:

- installs the APK;
- runs `pm clear`;
- then runs four phases: fresh launcher start, launcher restart, VIEW restart, and a second
  launcher restart.

Before each phase it runs `force-stop` and `logcat -c`. Each phase waits 45 s, then takes a
UI dump and a logcat. Each directory's `apk.sha256` names the exact signed APK.

| APK | sha256 | uBO pin |
| --- | --- | --- |
| pre-fix candidate (stage C) | `2d7db8ee8ebd15da82694734e152a9b1eb1a091cc3d464773f339a5464e54f46` | 1.74.0 |
| fixed, unsigned `fenix-x86_64-release.apk` | `ed86693b2766f760f65c9632154d221f697120b23a7b1e4f09ad78926522c196` | 1.75.0 |
| fixed, throwaway-signed | `71761a08aefe27664fdf614f4403654ede69df39c162cde016ea568cbc843b75` | 1.75.0 |
| diagnostic variant, throwaway-signed | `4a21d95084ff7ec1b2afbcf519f300fe881b66f3059ab64568657e8e1e8873b8` | 1.74.0 |

Every APK is signed with the stage-C throwaway key (cert sha256 `31e9a40f…b760`). It is not
the release key, and the key is not archived.

The fixed APKs were built with `android-apk.sh --skip-gecko` against the stage-C objdir
(build date 20261002000000). `:fenix:compileReleaseKotlin` executed; it was not up to date.

Fenix unit tests: the full `./mach gradle fenix:testDebugUnitTest --continue` ran in the build
container against this tree, and `board.py --check-fenix-tests` reports **0 unexpected**
(`check-fenix-tests.txt`). `LibreWolfUboPreinstallerTest` passed 23/23 and
`LibreWolfUboPreinstallMiddlewareTest` passed 4/4. That run used the final sources. An
earlier run of the same suite caught two mistakes in the new code before the final APK was
built: a pre-existing test needed the settle window advanced, and the comparator accepted
`1.75.*`.

Patch gates on the final tree, all green:

- `check-patchfail.sh --targets=android` (153.4.0esr);
- `lint-patch-scope.py`;
- `check-patch-order.py`;
- `board.py --check-scope` and `--check`;
- `node scripts/tests/test-ubo-readiness.js <tree>` (18);
- `test-ubo-extension.py` (22);
- `test-android-smoke.py` (52);
- `lw-m7-34/fixtures.py`.

