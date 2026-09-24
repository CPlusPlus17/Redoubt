This read-only current-parent capture refreshes only the 30 paths in
`next-work-plan/source-inputs.json` that are absent from its proposed245 inventory.
All 30 actual guest bodies match the older plan bodies byte for byte. No plan,
patch, helper, manifest, source file, service, emulator or UI was changed.

The capture ran as the existing runner user through `scripts/ci-vm/ssh.sh` on
2026-09-09 at 07:08:29 UTC while the separate runtime was active. It streamed a
343,126-byte gzip archive to the host in 0.191 seconds. Guest Python only read
30 source files (1,319,472 bytes total) and the actual
`evidence/account-process-source/source-sha256.txt` file. It issued no subprocess,
service or device command and created no guest files. The script hashes each
selected body twice, and checks the actual manifest before and after capture.
Both manifest hashes are
`4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739`.
All 30 before/after body hashes are equal.

`guest-source.tar.gz` SHA256 is
`17e7aab088810895349dd7636be1003e7d7bbc326bf606985c0df32b72914000`.
Its 32 regular members contain the 30 complete source bodies, the actual parent
manifest and the capture receipt. `source-inputs.json` is an exact copy of that
receipt. `capture.py` is the exact stdin script; `capture-command.json` records
its digest, command, timestamps, exit status and output digest. The capture's
stderr was empty.

`request.json` fixes the selected old rows, expected parent and source directory.
`plan-source-inputs.json` and `candidate245-source-sha256.txt` retain the exact
inputs used to derive the 30-path difference, without editing those originals.
The proposed245 hash remains `40da1bf9…` and its 107-body candidate remains intact.

Run this independent host verifier from the repository root:

    python3 docs/android/evidence/lw-m7-37/current-parent-refresh/verify.py

It checks all archive member hashes/sizes, exact membership, the captured script
request, command/output binding, the actual parent manifest, every before/after
row, and each older source archive's hash and original member bytes. It derives
all 30 equality comparisons from body bytes. `host-verification.json` retains its
result. The source groups include service workers, quota/client admission, cache
completion, clear-data interfaces, app storage/deletion and desktop Sanitizer.

These bodies are outside both the proposed245 and current167 partial manifests.
The checked current167 manifest supplies explicit parent context; this light
capture does not rehash its other 167 source bodies or claim a complete tree
inventory. The new receipts establish current inputs for future scoped work.
They do not establish compilation, cleanup behavior, a writer barrier, journal
completion, runtime acceptance or F04 completion. Additional implementation
ownership and the existing target gates still apply.
