# LW-M2-09 — Expected test failures (megazord/appservices environmental)

**Date:** 2026-08-25
**Source run:** current objdir (`librewolf-153.0esr-1/obj-x86_64`), 5418 tests / 90 failed
**Root cause:** `libmegazord.so` (the appservices UniFFI native library) is absent
from the host JVM's library path. It is built as an **Android** native library
(cross-compiled ELF for ARM/x86 Android) and bundled in the APK under
`lib/<abi>/libmegazord.so`, but `testDebugUnitTest` runs on the **host** JVM
(Linux x86_64), where the Android `.so` cannot be loaded.

## Environmental failures (87 tests, 3 classes) — EXPECTED, subtract from results

| Test class | Count | Error | Reason |
|---|---|---|---|
| `org.mozilla.fenix.search.awesomebar.SearchSuggestionsProvidersBuilderTest` | 70 | `UnsatisfiedLinkError: Unable to load library 'megazord'` | All tests in this class construct a `SearchSuggestionProvider` that calls into the `megazord` appservices via UniFFI; the native library is not loadable on the host JVM |
| `org.mozilla.fenix.reviewprompt.ReviewPromptMiddlewareTriggerCriteriaTest` | 16 | `UnsatisfiedLinkError: Unable to load library 'megazord'` (all 16 in this run; the LW-M4-14 baseline recorded `NoClassDefFoundError: Could not initialize class ...UniffiLib` — see "Error type is not a stable key") | Every test calls `NimbusApi` methods that route through `UniffiLib`, whose static initializer loads `libmegazord.so`; the load fails on the host JVM |
| `org.mozilla.fenix.experiments.RecordedNimbusContextTest` | 1 | `UnsatisfiedLinkError: Unable to load library 'megazord'` | Single test that directly invokes a recorded `NimbusApi` event query, hitting the same missing native library |

**Total environmental: 87 tests across 3 classes.**

Machine-readable form: `docs/android/fenix-test-allowlist.yaml`, subtracted by
`python3 docs/android/board.py --check-fenix-tests`. This file is the evidence;
that file is the gate.

### Error type is not a stable key

Corrected 2026-08-25 after verification against the run's JUnit XML: this
document originally recorded `NoClassDefFoundError` for the 16 ReviewPrompt
tests. The XML for that run says `UnsatisfiedLinkError` for all 16
(`type="java.lang.UnsatisfiedLinkError"` x16, zero occurrences of
`NoClassDefFoundError`); `UniffiLib` appears 16 times, in the stack rather than
in the type, which is where the original reading came from.

The two are the same failure at different points in a JVM's life.
`mobile/android/fenix/app/build.gradle` sets `forkEvery = 80`, so the test JVM is
recycled every 80 tests: the first touch of `UniffiLib` in a fresh JVM raises
`UnsatisfiedLinkError` from the static initializer, and any later touch in the
same JVM raises `NoClassDefFoundError: Could not initialize class ...UniffiLib`.
Which one a given test reports depends on where the 80-test fork boundary falls
relative to it — and that moves whenever the patch set changes the test count,
as it did between the LW-M4-14 baseline (5435) and this run (5418).

Consequence: any gate over this list must key on the **class name**. An
allowlist keyed on error type would go red on a rebase that changed nothing.

### Note on `AutofillSettingsMiddlewareTest`

The LW-M4-14 baseline (2026-08-22) also had
`org.mozilla.fenix.settings.autofill.ui.AutofillSettingsMiddlewareTest` (5 tests)
failing with `NoClassDefFoundError: mozilla.appservices`. As of the current run
(2026-08-25), this class **passes** (7 tests, 0 failures). It is therefore
**not** in the current environmental set. If it regresses, add it back with the
same reason (UniFFI binding cannot initialize on host JVM).

## Non-environmental failures (3 tests) — NOT in the allowlist, real signal

| Test class | Count | Error | Note |
|---|---|---|---|
| `org.mozilla.fenix.components.lens.LensCameraFragmentTest` | 1 | `io.mockk.MockKException: no answer found for Context.getPackageManager()` | MockK stubbing gap; unrelated to megazord |
| `org.mozilla.fenix.settings.HomeSettingsFragmentTest` | 1 | `java.lang.AssertionError` | Assertion failure; unrelated to megazord |
| `org.mozilla.fenix.distributions.DefaultDistributionProviderCheckerTest` | 1 | `java.lang.AssertionError: expected:<myProvider> but was:<null>` | New failure not present in the LW-M4-14 baseline; unrelated to megazord |

These three are **real test failures** (or flaky tests) and must be investigated
separately. They are NOT subtracted by the allowlist.

## What a clean result looks like

Running `./mach gradle fenix:testDebugUnitTest` in the build container with the
full Android patch set applied:

- **Total tests:** ~5418 (varies with patch set)
- **Expected environmental failures:** the 87 tests in the 3 classes above
- **Clean result:** zero failures **beyond** those 87. Any additional failure
  is a real signal and must be investigated.
- **The 3 non-environmental failures** (LensCamera, HomeSettings,
  DefaultDistributionProviderChecker) are real signal and tracked separately.

## How to verify a clean result

```sh
# Inside the build container, with a patched tree and objdir:
./mach gradle fenix:testDebugUnitTest 2>&1 | tee /tmp/test-run.log

# Extract the failing classes:
grep "TEST-UNEXPECTED-FAIL" /tmp/test-run.log \
  | sed 's/.*TEST-UNEXPECTED-FAIL | //' \
  | awk -F'|' '{print $1}' \
  | sed 's/ \+.*//' \
  | sed 's/\.[^.]*$//' \
  | sort | uniq -c | sort -rn
```

A clean result shows **only** the 3 environmental classes (87 tests) in the
failure list, plus possibly the 3 non-environmental failures. Any **new**
class or **new count** in an existing environmental class is a real regression.

## Baseline history

| Date | Run | Tests | Failed | Environmental | Notes |
|---|---|---|---|---|---|
| 2026-08-22 | LW-M4-10 baseline | 5434 | 121 | ~100 | Pre-LW-M4-14 fix |
| 2026-08-22 | LW-M4-14 runB | 5435 | 94 | 92 | AutofillSettings (5) was failing |
| 2026-08-25 | Current (LW-M2-09) | 5418 | 90 | 87 | AutofillSettings now passes; DefaultDistributionProviderChecker new |
