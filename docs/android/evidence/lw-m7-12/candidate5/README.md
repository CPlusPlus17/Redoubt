# Candidate5 APK and unit checkpoint

This is a future CI driver, not a target result. No APK, VM, emulator or native
build was run while preparing it. It packages an already successful native build
and runs the complete Fenix/support-webextensions units plus the retained targeted
A-C suite and the added classes below. Native tests and actual browser behavior
remain separate acceptance gates even when this checkpoint exits zero.

`checkpoint.py` has a read-only default plan. `--run` requires runner UID 1001 in
the KVM guest, no active container/emulator, an immutable image ID, and the exact
successful terminal native systemd invocation supplied in its receipt. No native
build invocation, future AAR hash, manifest count or new Task37 scope is guessed.

The reviewed source manifest is an explicit `{path, sha256, count}` launch input.
It can describe the reviewed 230-file composition, its subsequent test overlays,
or a separately reviewed expanded composition. The corresponding native receipt
must name that same manifest; all source rows are checked before packaging and
after packaging/units. Selected unit bodies and the empty Task30 shortcut input
must already be bound to the manifest. This driver does not invoke native4's
shortcut staging helper or change source. A new feature's inclusion in that
manifest does not assert its individual test coverage: `reviewed_scope_note` must
identify the included/excluded increments; the output explicitly limits its
required-method coverage to the baseline and `unit-inventory.json`. Extend and
review that inventory when an added increment needs additional required methods.

Each run gets a new `$work/candidate5-<name>/{out,evidence}` directory. Existing
run IDs are refused; old native4 APK/evidence directories are never reused. The
Gradle cache is seeded by the packaging script from the explicitly chosen cache;
unit execution disables build-cache reuse. The eight existing/new XML result
directories in the shared source objdir are moved into that new evidence directory
before units run, so stale output cannot be graded. This is an intentional unit
result mutation only when root later invokes `--run` in the idle guest.

The APK output set must contain exactly the three ABI APKs and universal APK.
Every APK goes through Task30's aapt2 resource-table lookup, with an explicitly
hashed build aapt2 executable, and every APK/AAR/source hash is checked again.
Per-command logs/results are recorded incrementally. Packaging/resource failure
stops before units. The full Fenix command may exit 1 only when its sole failed
Gradle task is `:fenix:testDebugUnitTest` and both the unchanged allowance gate and
the fresh XML gate pass. Compiler errors cannot use that exception. All targeted
A-C failures, missing/duplicate/stale XML, missing required methods and required
skips fail. The checkpoint launches no browser/device.

## Actual added target selections

The inventory was read from the composed source and binds each listed source
body hash. No Kotlin definitions were authored for this driver. It preserves all
seven prior suite selections/minimums and adds an eighth A-C addon selection.

| Task | Gradle suite | Required class | Added methods |
| --- | --- | --- | --- |
|35|full Fenix|`org.mozilla.fenix.settings.addons.ExtensionUpdatePreferenceTest`|7|
|36|full Fenix|`org.mozilla.fenix.settings.GlobalPrivacySettingsModelTest`|13|
|29|full Fenix|`org.mozilla.fenix.settings.search.SuggestDataCatalogTest`|3|
|29|full Fenix|`org.mozilla.fenix.settings.search.SuggestDataInstallerTest`|7|
|35|`:components:browser-engine-gecko:testDebugUnitTest`|`mozilla.components.browser.engine.gecko.GeckoEngineTest`|1 new; whole class selected|
|36|same|`mozilla.components.browser.engine.gecko.preferences.GeckoGlobalPrivacyControllerTest`|5|
|35|`:components:feature-addons:testDebugUnitTest`|`mozilla.components.feature.addons.update.AddonUpdaterWorkerTest`|1 new; whole class selected|
|35|same|`mozilla.components.feature.addons.AddonManagerTest`|1 new; whole class selected|
|29|`:components:feature-fxsuggest:testDebugUnitTest`|`mozilla.components.feature.fxsuggest.PinnedSuggestIngestionTest`|3|

`AddonManagerTest.kt` is located directly under `src/test/java` but its actual
package is `mozilla.components.feature.addons`; using its filesystem placement
as the class filter would miss it. The nine classes have 41 explicitly required
methods. New classes require every authored method; modified existing classes
run in full and specifically require the new method, at least the declared
source test count, and complete passing class XML. The changed existing classes
have no ignored test annotations in the inspected source.

Task31 adds xpcshell tests, not Gradle tests. Its permission/uninstall durability
checks remain in Task27's native inventory. Task35 real profile save/shutdown,
Task36 native/GeckoView API cases, Task29 Rust remote-settings tests and all APK
lifecycle/fixture controls are also explicitly pending separate gates. They
cannot be claimed from this unit checkpoint. Future Task37 coverage must be
reviewed separately when its composition is selected.

## Run-input preparation

Generate the template after integrating this driver, so it captures the exact
current checker/grader/script/allowlist dependency hashes:

```sh
python3 docs/android/evidence/lw-m7-12/candidate5/checkpoint.py --template > /private/candidate5-inputs.json
```

The null fields are intentionally incomplete. Fill them only from reviewed,
measured future artifacts: a new run ID beginning `candidate5-`, the reviewed
source manifest path/hash/count, scope note, immutable image ID, native receipt
path/hash, and exact aapt2 path/hash. The build date must match the actual native
build. Existing copied build aapt2 `2.20-14304508` had SHA256
`c9f30b34c02fd48165251541125c3b7f21b98624e0f8341436fc65a84095e5d6`; this is historical
measured input, not a fabricated future tool receipt. Resolve/check the chosen
executable at launch. Template generation does not query the guest or select a
native build automatically.

The native receipt must be written by the native build/capture owner after
successful completion. Launch that native service with `RemainAfterExit=yes`
(for example, `systemd-run --user --property=RemainAfterExit=yes ...`) and retain
it until the APK checkpoint has verified its exact invocation. A successful
transient unit without that property may be collected before verification;
missing invocation evidence is rejected. Do not stop/reset the retained unit
before the checkpoint. Its terminal `active/exited` state is accepted only with
matching invocation, `Result=success` and `ExecMainStatus=0`.

Run inputs and the native receipt keep the canonical `sha256:` image ID.
Podman's inspected ID may be either a bare 64-character lowercase hexadecimal
digest or the same digest with `sha256:`. The guard validates the entire digest
before canonicalizing and comparing; another digest or malformed output fails.

The receipt has these fields (all paths absolute):

```json
{
  "schema": 1,
  "status": "PASS",
  "service_name": "ACTUAL-NATIVE-SERVICE.service",
  "invocation_id": "ACTUAL_32_HEX_INVOCATION",
  "source_dir": "/actual/work/src",
  "build_date": "ACTUAL_14_DIGIT_BUILD_DATE",
  "container_image_id": "sha256:ACTUAL_IMAGE_ID",
  "source_manifest": {"path": "/actual/source-sha256.txt", "sha256": "ACTUAL_SHA256"},
  "build_exit": {"path": "/actual/build-exit.txt", "sha256": "ACTUAL_SHA256"},
  "started": {"path": "/actual/started.txt", "sha256": "ACTUAL_SHA256"},
  "finished": {"path": "/actual/finished.txt", "sha256": "ACTUAL_SHA256"},
  "build_log": {"path": "/actual/native-build.log", "sha256": "ACTUAL_SHA256"},
  "source_before": {"path": "/actual/source-before.txt", "sha256": "ACTUAL_SHA256"},
  "source_after": {"path": "/actual/source-after.txt", "sha256": "ACTUAL_SHA256"},
  "aars": {
    "armeabi-v7a": {"path": "/actual/aar/armeabi-v7a/target.maven.zip", "sha256": "ACTUAL_SHA256"},
    "arm64-v8a": {"path": "/actual/aar/arm64-v8a/target.maven.zip", "sha256": "ACTUAL_SHA256"},
    "x86_64": {"path": "/actual/aar/x86_64/target.maven.zip", "sha256": "ACTUAL_SHA256"}
  }
}
```

This example is documentation, not executable proof. The hash-pinned exit file
must contain 0, started/finished files must contain ordered timezone-aware ISO
timestamps, and each source-before/after log must contain exactly one
`relative/source/path: OK` line per reviewed manifest entry. The receipt's AAR
paths must have the declared ABI directories and a common parent. Native date,
source, image and invocation must match the APK launch configuration. Required
absent files return PENDING (exit 3); wrong or missing identity fields fail (exit 1).

After inputs are fully populated:

```sh
python3 docs/android/evidence/lw-m7-12/candidate5/checkpoint.py --inputs /private/candidate5-inputs.json
# Only root later invokes this in the idle CI guest:
python3 docs/android/evidence/lw-m7-12/candidate5/checkpoint.py --inputs /private/candidate5-inputs.json --run
```

The plan reads/validates inputs and prints exact packaging/unit commands without
creating a run workspace. Successful execution returns 0 for the bounded APK/unit
scope; its result still explicitly marks native tests and APK behavior pending.
No native or unit target was run during this host-only preparation.

## Host validation

All 26 host driver/grader controls passed; `host-tests.txt` retains the run. They
cover valid bare/prefixed and wrong/malformed image identity, wrong native
source/exit/time/AAR identities, incomplete source checks,
missing artifacts, APK set mismatch, preserved prior selections, source-declared
class counts, missing/duplicate/skipped/stale XML, compiler-error rejection, a
failed-build stop, and a plan that cannot invoke target execution or create its
workspace. Board validation passed with 122 tasks and no warnings. These tests
use explicitly identified host fixtures for the evidence parser and execution
boundaries, and do not establish any target pass.
