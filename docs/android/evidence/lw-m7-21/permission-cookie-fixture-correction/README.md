# Permission and cookie test fixture correction

The selected browser-engine-gecko target run on 2026-09-09 reported **57 tests,
7 failures, 0 errors and 0 skips**. Five failures occur during Mockito setup;
two occur in exception identity assertions. Fenix unit-test compilation also
fails on an unresolved `Called` symbol, so that run has no Fenix test results.
This candidate corrects the three test files. **The corrected target tests have
not run.** Production source, gate rules and allowlists are unchanged.

Task21 metadata `caed462` declared ownership before these edits. The original
reports, actual guest source and repository inputs are retained separately from
the candidate. Root owns guest staging, builds, target tests and runtime checks.
This followup used read-only guest tar streams and bytecode inspection.

## Diagnosis and correction

| Actual failure | Inspected cause | Test-only correction |
| --- | --- | --- |
| All five `OriginBoundPermissionsStorageTest` methods fail with `UnfinishedStubbingException` in `result()` | `whenever(controller.allPermissions).thenReturn(result(...))` evaluates a helper that starts another Mockito stub before the outer `thenReturn` completes. Two subsequent write-result stubs have the same defect. Production assertions have not yet run. | Construct all seven result mocks before starting the controller stubs. Explicit `ContentPermission`/`Void` types retain inference previously supplied by `thenReturn`. Preserve all five tests and their existing assertions, including delayed write acknowledgment. |
| `GeckoCookieBannersStorageTest`: `remove surfaces native failure instead of completing successfully` and `native token failure cannot fall back to unscoped private storage` | Both reports show equal `IllegalStateException` class/message but different object identity. The adapter propagates the native exception through `CompletableDeferred.await()` and `withContext`. The exact cached coroutines 1.11.0 bytecode allows stack-trace recovery to copy exceptions while retaining the message and original cause. | Require the same exception class and message and require the original native exception object in the cause chain. This accepts an unrecovered original or a recovery copy while rejecting success, a different error or lost causality. Preserve the no-fallback/no-extra-interaction assertions and all 16 tests. |
| Fenix `DefaultCookieBannerDetailsControllerTest.kt:199`: unresolved `Called` | `verify { engine wasNot Called }` lacks `import io.mockk.Called`. The production APK compile result does not compile this unit-test source. | Add the import. Preserve all four tests and the existing assertion. |

The exception-copy mechanism is supported by the captured runtime bytecode and
the observed identity-only failures. The original XML does not print the caught
exception's cause chain; the corrected assertion must still pass in the actual
rerun. No disabling of coroutine recovery or debug behavior is proposed.

These failures identify fixture defects, without establishing that production
behavior passes once execution reaches its assertions. The selected Gecko run
also reports 31 `GeckoSitePermissionsStorageTest` and 5
`OriginBoundPermissionRequestTest` cases passing. This is not a result for every
test in the module or for native permission behavior.

## Source and evidence bindings

- [inputs.json](inputs.json) binds the metadata revision, original/current patch
  hashes, three before/after test hashes, unchanged test counts, archive hashes,
  and the exact cached coroutines JAR/bytecode hashes.
- [before-repository.tar.gz](before-repository.tar.gz) preserves both original
  patches, Task14 source hashes/validation and Task23 source receipt.
- [before-source.tar.gz](before-source.tar.gz) retains eight actual guest files:
  the three tests, both storage implementations, the GeckoResult await adapter,
  module build file and dependency catalog.
- [target-test-reports.tar.gz](target-test-reports.tar.gz) retains the complete
  `target-tests.log`, `junit-summary.json` and `gecko-junit-xml.tar.gz` read from
  the terminal extended-test output. The Fenix compiler failure is at log lines
  4584–4585. Original reports are never rewritten into a passing result.
- [coroutine-recovery.javap.txt](coroutine-recovery.javap.txt) records read-only
  inspection of `StackTraceRecoveryKt`, `ExceptionsConstructorKt` and `DebugKt`
  from the guest's cached coroutines 1.11.0 JAR. This is bytecode inspection,
  not execution of a replacement fixture.
- [graphics-baseline.tar.gz](graphics-baseline.tar.gz) captures original sparse
  baseline bodies from the recorded `a759e38` objects. Applying the retained
  original graphics patch must reproduce all 36 historical final hashes before
  the corrected patch is accepted. Task23's existing source-baseline archive
  remains unchanged and is independently pinned here.
- [test-source-overlay.tar.gz](test-source-overlay.tar.gz) and
  [test-source-overlay.patch.gz](test-source-overlay.patch.gz) contain only the three
  corrected test bodies/diffs for root review and staging.

The complete original/corrected patches reconstruct 36 graphics and 37
cookie-control outputs with zero fuzz and zero offsets. Every production patch
section is byte-identical. Task14's current source hash/validation and Task23's
two current output hashes/Task14 predecessor digest are refreshed. Historical
receipts stay in their original archive. Subsequent shared source and coverage
pins must be refreshed against these final patch hashes by their owners.

## Verification and target handoff

Run the offline replay from this repository:

```sh
python3 docs/android/evidence/lw-m7-21/permission-cookie-fixture-correction/replay.py
python3 docs/android/board.py --check
```

`--output /new/private/directory` retains the reconstructed source and receipt.
The replay checks all original/current source hashes, exact patch-section scope,
actual failed-run source lineage, the three-file overlay, test counts and XML
failure counts. It executes the existing 37 graphics JS tests, 19 cookie event
JS tests and the cookie native-fence source harness (43 assertions with mocked
platform boundaries). See [replay-receipt.json](replay-receipt.json) and
[verification.txt](verification.txt).

Root must stage the exact three bodies after verifying their before hashes, then
rerun the selected Gecko tests and Fenix unit-test compilation/full suite using
the unchanged grading rules. The browser smoke, preference audit, native tests
and feature acceptance remain separate required gates. The accounts failures
from this same terminal run belong to Task20's independent correction.
