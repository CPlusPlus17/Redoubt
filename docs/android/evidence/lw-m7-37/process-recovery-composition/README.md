# Process-recovery source composition preparation

This is a new Task37-owned staging version for the corrected account/Suggest
process candidate. The frozen `../current-composition/` 501d/9a911 candidate and
`../composition-fifth-fixture/` history remain unchanged.

The corrected current167 source manifest is
`4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739`.
The final245 manifest is
`40da1bf9c42187b1e037fba5b443e4b26fd2758ffa7b07212710df72693eb806`.
The 107-body archive is
`4ff529867fb992b2db259d7dec95bffabce459aac60e3cc564a38e16d102bbc9`;
the retained receipt is
`fb7ca4f5c93aab3ea089380d6ca8d8ca4e9e3e24a258f65cee45b24f2691493e`.
The plan checks 200 existing hashes and 45 absences, replaces 43 files, creates
45 and retains 19 materialized inputs plus 138 unchanged manifest-only bindings.
All 101 previous materialized bodies are unchanged; the six additional bodies
are process corrections already present in the corrected167 source.

The complete coverage handoff is retained byte for byte in `handoff/`.
`inputs.json` pins 212 current parent inputs plus six Task37 inputs, retained in
`frozen-repository-inputs.tar.gz`. Historical151 inputs remain separately bound
to the immutable prior157 archive. Forty consumed source/patch/asset/packaging
inputs and selected patch order must still match the live repository; historical
metadata is replayed only from its frozen version. No implementation or target
success is inferred from a plan or snapshot.

The eventual source-only stage will import the separate
`docs/android/evidence/lw-m7-12/current167-process-recovery/` checkpoint contracts.
It will require the actual successfully terminal full tests, APK build, all four
resource verdicts and complete runtime acceptance before writes. Preparing this
version does not authorize or claim guest staging, compilation or runtime.

Root owns all guest operations. Source/package/artifact identities, all current
167 source paths and every final existing/absent source path must be rechecked
immediately before staging, and native/APK/evidence identities preserved after.
