# Actual full suite after process correction

Root ran `redoubt-fenix-account-process-tests-20260909.service`, invocation
`c02a8b984fae45dc859eff2b556b82f0`, against all167 source bindings in
`4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739`.
The retained unit finished with exit zero. `board.py --check-fenix-tests` reported:

```text
610 classes / 5523 tests
newest result written 2026-09-09 06:02:43
failing 20 = 17 environmental + 3 known-real + 0 unexpected
ok: no failures beyond the documented allowlist
```

The actual results directory is
`/home/runner/work/feature-parity-20260908/src/obj-x86_64/gradle/build/mobile/android/fenix/app/test-results/testDebugUnitTest`.
The full fresh-coverage gate also passed. All147 selected component cases passed:
extensions53, Gecko57, state2, accounts20, synced-tabs1, Suggest14. The seven
existing Fenix skips remain; all required feature classes and all three newly
added process regressions passed without skips. No allowance entry was added.

`capture.py` checks the named new regressions and captures terminal service,
source/stage records, full logs, exact gate inputs and all seven XML archives.
Root independently checked all96 archive members and recounted every XML case;
the resulting counts match the guest's seven suite summaries. Full retained
archive SHA-256:
`74dda16c2936cef56fa207abb234276eeb4236eab2a64f1e8688a008249a1bc5`.
`result.json` retains those independent counts and every member hash.

This proves the corrected source's unit-test gate. APK packaging, emulator
startup and feature behavior require the separately recorded recovery run.
