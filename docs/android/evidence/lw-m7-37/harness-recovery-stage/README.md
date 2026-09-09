# Stage the same245 source after the corrected harness checkpoint

This is a separately versioned staging helper. The entire prior
`../process-recovery-composition/` directory remains unchanged, including its
prepared helper, verifier,107-body archive, historical inputs and source
manifests. No source composition was regenerated or repinned.

The new helper requires the `lw-m7-12/harness-process-recovery` runtime
checkpoint from `a255ba5`. That checkpoint runs the five-file corrected harness
capsule on the same source167/APK/full-test set while retaining the original
guest canonical scripts and the failed earlier runtime. This task prepared
source and host controls only; it did not access a guest, stage source, launch
native builds or claim corrected runtime acceptance.

The selected source remains:

| Input | SHA-256 or count |
| --- | --- |
| Before source167 | `4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739` |
| Final source245 | `40da1bf9c42187b1e037fba5b443e4b26fd2758ffa7b07212710df72693eb806` |
|107-body archive | `4ff529867fb992b2db259d7dec95bffabce459aac60e3cc564a38e16d102bbc9` |
| Preflight |200 existing files,45 required absences |
| Mutation |43 replacements,45 creations;19 retained payloads |

`version-inputs.json` records the previous helper/verifier/input bytes, the
runtime predecessor and13 exact checkpoint files: three new runtime/manifest
files, all five capsule files, the actual55-member failed-runtime archive and
the four original recovery modules/input metadata. There is no `build.py` in the
runtime-only checkpoint. Build authority stays in the original unchanged module.
The captured stage configuration binds39 unique source inputs, including both
helper versions, the retained full handoff and historical archives.

The12 existing functions other than `own_inputs` remain byte-identical, including
all runtime admission, source preflights, backup, write, receipt and error paths.
The changes are explicit module loading, a new version/pin check and the input
inventory. Module loading preserves each original module's own `HERE`/`REPO` and
temporarily binds `common` only while importing its corresponding runtime.

Before configuration capture, and again before any writes, the helper requires
the actual corrected-harness runtime to be successful and its same recorded
service invocation to be successfully terminal. Its original APK/full-test
authority is revalidated. All10 uBO checks,8 baseline checks, the pref dump,
pref-audit process exit and successful emulator cleanup are required. Reports
are regraded against the corrected capsule hash and exact APK. Source167 and
the full245 existing/absent plan are checked before writes. The source/native,
APK, successful and failed runtime evidence, capsule and service identities are
preserved through the write phase. The stage must remain blocked if that runtime
has not passed.

The unexecuted service and output identities intentionally remain compatible
with native5's strict admission:

- Kind: `account-process245-source-stage`
- Service: `redoubt-account-process245-source-stage-20260909.service`
- Evidence: `/home/runner/work/feature-parity-20260908/evidence/account-process245-source-stage`

The configuration and receipt pin this new `stage.py` and its new version
metadata, so retaining these identities does not substitute new code into an
old prepared configuration. Existing evidence prevents automatic reruns. A
partial write or later failed preservation check produces a failed receipt;
native5 requires both a successful receipt and its successful terminal service,
even if all final source hashes happen to match.

Replay the host controls from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s docs/android/evidence/lw-m7-37/harness-recovery-stage -p 'test_*.py' -v
python3 docs/android/board.py --check
```

The14 unchanged filesystem/archive tests exercise real temporary files,
replacement failures and progress receipts. The12 additional version/checkpoint
tests exercise actual frozen inputs and report graders with mocked guest/service
admission. They do not prove runtime or native acceptance. `validation.json`
records the exact host outcome and unchanged-function/source receipts.

For an authorized guest invocation, configuration capture is a distinct step:

```sh
python3 docs/android/evidence/lw-m7-37/harness-recovery-stage/stage.py --print-config
```

It must succeed only after runtime acceptance. Review and retain the resulting
JSON, then use its exact path and SHA-256 with `--config` and
`--config-sha256`. Without `--run`, the helper repeats validation only. An
explicit `--run` under the named retained service performs the reviewed writes.
These guest operations have not been executed by this task.
