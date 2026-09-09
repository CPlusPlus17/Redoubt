# Marionette readiness and window-handle correction

The account-process runtime invocation `a172ec824e2a4e94a4dd467627f6a0d0`
failed before completing uBO and graphics acceptance. This correction changes
the host harness only. Source167 and the APK are unchanged; no corrected device
run has been performed by this task. The old failed result remains a failure.

`failed-runtime-binding.json` names the retained actual runtime/graphics archives,
the APK set and source manifest. It verifies that the three original script
hashes in the runtime configuration equal the retained before bytes. The
successful x86_64 APK is `7ce0d286a108d4434267e4377f4d82720c29e841c8d65c5a32612a8017857146`;
its build and configuration are not rewritten.

The failures have separate causes, demonstrated by the retained source:

- `remote/marionette/server.sys.mjs:323–350` lists `GetWindowHandles` among
  commands whose response body is the raw result. `ExecuteScript` and
  `ExecuteAsyncScript` use a `value` wrapper. The existing shared script decoder
  is correct and remains byte-identical. Both graphics call sites incorrectly
  called `.get("value", [])` on the raw list, including the private-close path
  not reached by this failed run.
- `actors/MarionetteCommandsParent.sys.mjs:395–451` excludes `executeScript`
  from automatic retries: a destroyed/inactive actor returns null on
  `AbortError`/`InactiveActor`. Its `sendQuery` dialog-open path can also return
  undefined, which the server represents as wrapped null. These establish that
  null is a valid protocol outcome; the failed run did not capture enough actor
  diagnostics to identify which path produced its null.
- `evaluate.sys.mjs` separately emits a `Document was unloaded` JavaScript
  error. The existing narrowly matched retry for that error is preserved.

`before-and-protocol.tar.gz` retains all five original capsule inputs and the
four full frozen source files. `source-inputs.json` hashes each member and names
the frozen source directory. No registered patch contains a Marionette source
file hunk. This is source inspection, not a new target protocol trace.

The readiness wait treats null as not ready within the existing 60 attempts
and 250 ms polling interval. It still requires the exact requested URL, exact
document URI and `readyState == "complete"`. It reports a last null after the
budget expires; malformed non-null types fail immediately. Only this read-only
observation is retried. Script writes, clicks and the shared codec are unchanged.

The graphics helper requires a raw list of distinct, nonempty string handles.
An empty list remains an observation with no matching window; it does not prove
readiness or private teardown. Both actual call sites use the helper and retain
their existing document, principal, private-mode and completion checks.

Host verification passed 13 new framed-protocol/call-site controls, 44 existing
smoke tests and 38 existing graphics tests. The three new success-path controls
run against the original retained scripts instead reproduce the exact three
AttributeErrors: one null readiness result and the two list call sites. That
negative replay is retained verbatim in `before-negative-replay.txt`.
`validation.json` records the commands, counts and source hashes. Replay:

```sh
python3 docs/android/evidence/lw-m7-12/protocol-recovery/test_protocol.py
python3 scripts/tests/test-android-smoke.py
python3 docs/android/evidence/lw-m7-18/test-android-graphics-smoke.py
bash -n scripts/android-smoke.sh
python3 docs/android/board.py --check
```

The new controls use framed in-memory transport responses with the actual
`cmd`, `script` and `async_script` implementations, plus actual graphics
`browser_document` and `close_private` methods. They do not simulate successful
target graphics rendering or add-on behavior.

`capsule-inputs.json` binds the corrected smoke/graphics scripts and unchanged
pref audit, expected prefs and mandatory-lock list. The separately reviewed
runtime retry must place these five files in the same `scripts/` and
`docs/android/` layout, use fresh work/evidence/service names, preserve the old
guest canonical scripts and successful APK proof, and require new complete
runtime reports. The new harness hashes must never be substituted into the old
runtime or build configuration. Target success remains pending.
