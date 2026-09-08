# Completed feature-candidate unit suites

Root ran the complete Fenix suite inside the isolated QEMU guest. The run ended
2026-09-08 22:16:20 UTC. The original log, XML archive, guest gate and resource
receipts are in `../../lw-m7-15/parity-third-combined/`.

The checked-in board gate reports:

```text
# 602 classes / 5468 tests from /home/runner/work/feature-parity-20260908/src/obj-x86_64/gradle/build/mobile/android/fenix/app/test-results/testDebugUnitTest
# newest result written 2026-09-08 22:16:18 — check this against the change you are testing
# failing 90 = 87 environmental + 3 known-real + 0 unexpected
warn:  org.mozilla.fenix.settings.autofill.ui.AutofillSettingsMiddlewareTest ran and passed — drop the entry (this is how AutofillSettingsMiddlewareTest left the list)

ok: no failures beyond the documented allowlist
```

Gradle exits 1 for the documented failures; the gate exits 0. Root independently
extracted the copied XML into a temporary directory and reran the same gate on
the host; `host-replayed-fenix-gate.txt` records its output. No allowlist entry
was added or enlarged. The now-passing AutofillSettingsMiddlewareTest entry is
still present and the warning remains visible.

`source-comparison.json` compares all 31 resulting source files against the
committed uBO and privacy-defaults inventories at repository commit `32a8463`.
Every hash matches, including the nullable readiness-error fix. This binds the
completed suite to the final source rather than the earlier interrupted or
compile-failing runs.

The four extension-support classes ran 53 tests with zero failures/errors/skips
at 21:07:11 UTC during the prior invocation. Their source did not change. Gradle
reported that task UP-TO-DATE in the completed invocation; it did not rerun it.
`support-webextensions-junit-xml.tar.gz` preserves those original results, and
`junit-summary.json` records counts, suite timestamps and archive hashes for
both modules.

The tested candidate includes uBO installation/readiness and privacy defaults.
Cookie-rule loading and graphics permission changes were not in this source.
APK compilation and browser behavior checks are separate requirements and
remain pending at this receipt.
