No concrete blocker found in the bounded smoke/graphics protocol correction.

The four retained Marionette source files match the frozen source bytes. server.sys.mjs explicitly excludes GetWindowHandles from value wrapping; driver.sys.mjs returns an array of unique string handles. The MarionetteCommands actor proxy lists executeScript as nonretryable and returns null when that actor call fails with AbortError/InactiveActor. Script/async-script decoding remains unchanged.

The readiness function retries only its read-only URL/documentURI/readyState observation. A decoded null cannot pass; success requires both exact requested strings and readyState complete. Other non-dictionary snapshots fail immediately. Existing document-unloaded retry remains; unrelated Marionette errors propagate. Both graphics call sites use the same raw-list validator, rejecting wrapped objects, null, nonstrings, empty handle strings and duplicates. Empty lists cannot establish document readiness or private teardown.

Independent controls:13 new protocol tests,44 existing smoke tests and38 existing graphics tests passed. A focused replay on the exact retained old scripts reproduces the observed null.get readiness failure and both raw-list.get graphics failures. Parsed-AST comparison shows no change outside wait_for_initial_document, browser_document, close_private and the new window_handles helper. The shared protocol codec and acceptance definitions are unchanged.

comparison.json binds candidate script/test hashes, original evidence and control counts. old-byte-regression.txt preserves the three expected old failures. No device, guest command, production patch or current pin was changed. A complete target runtime remains required.
