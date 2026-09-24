# Modal-backed checkpoint for the unchanged245 source stage

This separately versioned helper selects the reviewed
`lw-m7-12/modal-process-recovery` adapter from `3fa2ef4a` (integrated as
`e0a14f70`). Both prior helper directories, `harness-recovery-stage` and
`process-recovery-composition`, remain byte-identical. No source composition,
production patch, manifest or payload was regenerated. This preparation did not
access the guest, capture staging configuration, stage source or run a native
build. Runtime acceptance remains pending its actual successful terminal result.

The unchanged source plan is:

| Selection | Exact identity |
|---|---|
| Before167 | `4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739` |
| Final245 | `40da1bf9c42187b1e037fba5b443e4b26fd2758ffa7b07212710df72693eb806` |
| 107-body archive | `4ff529867fb992b2db259d7dec95bffabce459aac60e3cc564a38e16d102bbc9` |
| Before checks | 200 exact existing files and45 required absences |
| Writes | 43 replacements and45 creations;19 other payloads retained |

`version-inputs.json` was committed before implementation. It pins all39 inputs
of the previous prepared helper and the complete18-record checkpoint inventory:
nine module/manifest/archive inputs from the adapter's expanded `runtime_inputs`,
five actual capsule files, and four original recovery modules/input metadata.
There is no invented `build.py` in a runtime-only checkpoint. Deduplication yields
51 exact inputs in the staging configuration, including both historical helpers,
the retained composition, both runtime histories and the new helper/version.

The adapter privately binds the frozen runtime functions to the new modal
checkpoint. The original current167 base and APK configuration remain authoritative.
The helper preserves an unrelated caller's `sys.modules['common']` entry, including
an explicitly present `None`, through both common and runtime imports. It neither
replaces guest canonical scripts nor edits a prior capsule.

Before configuration capture and again before writes, the unchanged admission
function requires the new modal runtime's PASS receipt and its same successfully
terminal invocation. It reloads the actual configuration through the new adapter,
which checks both failed histories and all inherited inputs. It revalidates the
original full-test/APK authority, regrades all10 uBO checks,8 baseline checks and
the pref dump against the exact APK/corrected capsule, requires pref-audit exit0,
and requires successful emulator cleanup. A successful subset from a prior failed
runtime is insufficient. All167 source receipts and full245 existing/absence checks
remain mandatory before writes.

The runtime service selected by this helper is
`redoubt-modal-process-runtime-20260909.service`. The unexecuted staging identities
remain intentionally compatible with native5's strict gate:

- Kind: `account-process245-source-stage`
- Service: `redoubt-account-process245-source-stage-20260909.service`
- Evidence: `/home/runner/work/feature-parity-20260908/evidence/account-process245-source-stage`

New configurations bind this new helper and version metadata. Reusing those
unexecuted identities does not authorize substituting code into an older prepared
configuration. Failed preservation after a partial write still yields FAIL, and
native5 requires a matching PASS receipt and successful terminal stage invocation.

Run the host controls from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s docs/android/evidence/lw-m7-37/modal-recovery-stage -p 'test_*.py' -v
python3 docs/android/board.py --check
```

All29 controls pass:14 byte-identical filesystem/archive tests and15
checkpoint/version tests, including actual95-member0189 failure-archive validation,
old-capsule drift, complete expanded input coverage and private module binding.
The tests mock guest/service admission and do not establish runtime success.
`validation.json` records hashes and14 function bodies unchanged from the immediate
predecessor; only `version_inputs` and `own_inputs` changed, alongside module setup.

After actual runtime acceptance, the root operator may separately capture:

```sh
python3 docs/android/evidence/lw-m7-37/modal-recovery-stage/stage.py --print-config
```

Retain and review that JSON, then supply its path and exact digest with `--config`
and `--config-sha256`. Without `--run`, validation performs no source writes. An
explicit `--run` under the named retained stage service performs the reviewed
writes. This task has performed neither operation.
