# Full target suite after the coroutine opt-in

The actual service invocation `1c9c192370c140e2b3f711828d8f4de1` ran the complete
Fenix task and all previously selected Android component tasks. The unchanged
failure allowance gate reported:

```text
# 609 classes / 5517 tests from /home/runner/work/feature-parity-20260908/src/obj-x86_64/gradle/build/mobile/android/fenix/app/test-results/testDebugUnitTest
# newest result written 2026-09-09 04:25:44 — check this against the change you are testing
# failing 30 = 18 environmental + 3 known-real + 9 unexpected
```

The unexpected failures were five CookieBannerSettingsTest setup failures, one
FenixApplicationTest metrics expectation, the two existing external/auth custom
tab no-op tests, and one CreditCardItemViewHolderTest click verification. All146
selected Android component cases passed. Fenix compiled, including all eight
permissions feature tests, which passed. The complete gate failed; runtime did
not run. These results bind the five-fixture165 manifest `659bf836…`, while the
compiled APK source remains `c53736e8…`.

`capture.py` retains full logs, the exact gate outputs, all seven XML archives,
test source, selected implicated production source and service metadata. Root
verified all95 member hashes and independently counted every XML case; the full
archive SHA-256 is
`9538161039d56e9ba0e452d955d4dcbc36988ba1ed965484e63cad09015b4fc8`.
See `root-verification.json` for the counts and hashes.

`run-creditcard-diagnostic.sh` runs the unchanged two-test credit-card class in
isolation after preserving the complete result directory. Its result is a
separate diagnostic and cannot replace the failed full-suite verdict.
