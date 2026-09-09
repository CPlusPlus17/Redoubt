# LW-M7-36: authoritative global privacy controls

**Source candidate; target compilation and runtime acceptance remain pending.**
Produced by `/root/coverage_map` on the Fedora host in an isolated worktree.
The implementation adds a Global privacy controls screen backed by a dedicated
GeckoView module/API and typed Android Components interface. No Fenix persisted
mirror or GeckoRuntimeSettings preference/reset declaration is added.

| Visible control | Native user preference | Meaning |
|---|---|---|
| Resist Fingerprinting | `privacy.resistFingerprinting` | Direct boolean; private-only RFP, FPP and configured exceptions remain distinct context. |
| Always allow WebGL | `librewolf.webgl.prompt` | Inverse boolean; bypass site approval while retaining stored site grants/blocks. |
| Hide WebGL popup | `librewolf.webgl.prompt.hide` | Direct boolean; disabled in the UI when approval is bypassed. |
| Enable IPv6 | `network.dns.disableIPv6` | Inverse boolean; permits IPv6 DNS addresses, without claiming OS networking or existing connections are disabled. |
| Cross-host referrers | `network.http.referer.XOriginPolicy` | 0=no added host restriction; 1=same base domain; 2=same host. Host comparison ignores scheme/port. Other referrer restrictions remain in force. |

These effects were **read in the retained original native/desktop source**, not
measured on an APK. See [original audit](original-audit/audit.md) and its 38
original files in `source-inputs.tar.gz`; the checker verifies every original
size/hash. Task14's current graphics patch establishes the Android permission
counterpart; the older frozen WebGL source alone does not. No letterboxing or
`webgl.disabled` setter is included: the latter still has a plain common config
write that would overwrite a saved user value at startup.

## State and save contract

The native module allowlists exactly five preference IDs, exact boolean values,
and integer referrer values 0 through 2. Unknown IDs, wrong types, mixed batches,
extra keys and locked writes are rejected before mutation. Existing unsupported
integer values remain visible and are not silently normalized. Missing native
preference types are unavailable. No preferences or permissions change on read.

Each snapshot contains effective/default values, lock and user-presence state.
A locked preference can retain a hidden user value while a normal native getter
returns its default. The API therefore returns `userValue=null` and
`userValueKnown=false` for that case; it never unlocks a preference to inspect it.
Boolean values use numeric 0/1 in the bridge to preserve nullable native values.
The screen displays the last read value, default, and custom/default/lock status.

Normal Gecko `SetUserValue` removes a non-sticky user value when the requested
value equals its default (`Preferences.cpp:905–938`, retained Task35 excerpt).
The controller honors that native behavior: setting the default can be saved
with `hasUserValue=false`. It does not invent a separate durable explicit-default
choice. Setting a non-default preserves the native user choice; reset clears the
user branch and rereads the actual default. An existing same-default user value
loaded by native initialization is shown as it exists until explicitly changed.

Reads, single-setting writes and resets share one queue. Writes validate, await
Task35's forced current-profile save **before mutation**, revalidate after the
await, mutate one user preference, await another actual save, and reread. The
preflight can reject missing-profile/shutdown/write-path errors before mutation;
it cannot guarantee a later write will succeed. Task35 owns the immutable disk
snapshot, serial I/O target and actual write-result promise. Its production
primitive is separately pinned by the complete predecessor patch and retained
source excerpts; the older audit's native file does not contain that primitive.

A final-save failure preserves and reports actual current memory. No inferred
rollback or assertion about unchanged disk is made. A per-setting in-memory
uncertainty marker survives a screen reread/reopen until an actual successful
save captures the same native state. An external writer/lock can supersede a
requested value during I/O; the result reports that state rather than claiming
the requested value was saved. Equality is used only to recognize a state
confirmed by a completed save, never to infer ownership for rollback. Already
started saves are not cancellable. A success concerns the setting's saved
snapshot, not every unrelated preference or indefinite future state.

Fenix preferences are explicitly nonpersistent and do not optimistically accept
widget values. Controls wait for the native result. Lock changes are rechecked
natively. Failed transport disables editing until an actual refresh succeeds.
Save failures/supersession have visible status and a dialog when the view is
active; a retry action can resave an unchanged displayed choice. Detaching the
view stops UI callbacks while an already authorized native save may finish.
Refreshing clears a previous operation's status rather than labeling later
external state as saved. Native uncertainty is still shown after refresh.

## Reproducible source lineage and checks

Base repository: `44b48ea`; Task36 metadata: `895cb7b`. Task35 metadata `569954b`
and implementation `b65686b`, corrected by `efff10f`/`2f479a4`, are separate
prerequisites. The local predecessor transplants are not Task36 deliverables;
root integrates its originals. Corrected35 only changes target fixtures and
metadata; the five shared production file hashes remain unchanged. The five shared Task35
inputs came from its captured active164 baseline, plus scoped31 where relevant;
this is recorded provenance, not an assumption that a repository commit alone
identifies the extracted source.

`source-files.json` pins nine retained preexisting files, seven scoped
predecessors and all 21 before/after outputs. Six predecessors were reversed from
inspected source to retain a scoped pristine archive, replayed, then final35 was
applied to the shared five files. The source replay uses only repository
artifacts, verifies scope and all hashes, and needs no guest/build tree.

Run:

```sh
python3 docs/android/evidence/lw-m7-36/check-source.py
python3 scripts/tests/test-global-privacy-controls.py
python3 docs/android/evidence/lw-m7-36/check-ordering.py
python3 docs/android/board.py --check
```

The host suite executes the actual replayed JS module in Node with explicit
preference and I/O doubles. Its 18 cases cover validation, native same-default
normalization, lock/type changes across awaits, serialization, failed saves,
supersession, retry and uncertainty, queued-input capture and error recovery.
This is not native disk or Android execution. Packaging/event/XML checks cover
wiring and preservation of list value1. The five authored xpcshell cases use real
native preference and permission services with an **injected save boundary**:
`do_get_profile` alone does not establish Preferences' current profile file.
They do not assert real persistence. Twenty-one authored Kotlin tests comprise
13 Fenix model/UI, five A-C bridge and three real-GeckoRuntime API tests.
All 26 target tests remain **unrun** here.

`ordering-review.json` retains both full inverse-composition attempts and a
shared-file position swap for each of seven pairs. All seven shared position
swaps produce identical final source. Deferring canvas or Sync to the end fails
in a later predecessor before reaching Task36; those failed full-composition
attempts are retained and are not passed off as pair failures or successes.
Task35 must still precede Task36 semantically because it supplies the save API.
Root owns global order/scope classification and target execution; the isolated
branch's central order gate intentionally reports unclassified35/36 pairs.

See [RUNTIME-ACCEPTANCE.md](RUNTIME-ACCEPTANCE.md) for completion gates. The scoped
candidate is ready for integration review; it does not satisfy the board's
compiled-and-tested definition of done yet.
