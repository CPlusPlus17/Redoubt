# 153.4.0esr source receipts for three hash-pinned Android patches (2026-10-02)

Three `scripts/tests` files replay a patch onto pinned "before" source and
check pinned "after" hashes:

- `test-extension-update-controls.py` (LW-M7-35)
- `test-global-privacy-controls.py` (LW-M7-36)
- `test-session-cleanup.py` (LW-M7-37)

Their receipts in `evidence/lw-m7-35`, `-36` and `-37` pin 153.0esr source and
the 153.0esr bytes of the patches. The rebase changed
`extension-update-controls.patch` (its `Preferences.cpp` port to upstream bug
2053962, and d0ae91de's test fix) and `global-privacy-controls.patch`
(d0ae91de). So all three tests failed on a hash check before they reached any
source check. `test-session-cleanup.py` pins extension-update-controls as a
predecessor.

This directory re-captures those receipts for 153.4.0esr. The 153.0esr
receipts are left untouched as history. Each test picks its receipts from
`version.android`. If `evidence/lw-m7-01/esr-<version>/receipts/replay.py`
exists, the test uses it. Otherwise it falls back to the original 153.0esr
chain.

## How the receipts were produced

The 153.0esr "before" trees were read-only captures of a CI guest's partly
patched source (`lw-m7-35/capture.json`, `lw-m7-37/current-capture`), or a
reverse-applied scoped pristine set (`lw-m7-36/scoped-pristine.tar.gz`). No
guest holds a 153.4.0esr tree. The re-capture therefore uses the same thing
those captures stood for: the real tree state that each patch meets on the
Android stack. It builds that state from repository artifacts only:

```sh
python3 docs/android/evidence/lw-m7-01/esr-153.4.0/receipts/recapture.py \
  --out docs/android/evidence/lw-m7-01/esr-153.4.0/receipts \
  --objdir <stage-B tree>/librewolf-153.4.0esr-1 \
  patches/android/extension-update-controls.patch \
  patches/android/global-privacy-controls.patch \
  patches/android/session-cleanup.patch
```

`recapture.py` works in five steps:

1. It extracts every path that any of the 67 patches touches from
   `firefox-153.4.0esr.source.tar.xz`. Its sha256 is
   `3082dec68030b4fbb46041c282e362e524c9d6d75e7c45e944d8d0e11c8ea2df`.
   REBASE.md Appendix D records the tarball's Mozilla signature as good.
2. It applies `assets/patches/common.txt` and then `android.txt` with
   `patch -p1`, in the same order as `check-patchfail.sh` and the patcher.
3. It captures the touched paths just before each target patch. That capture
   is `<stem>-before.tar.gz`: deterministic, mtime 0, absent paths recorded in
   the JSON.
4. It replays the target alone on that capture with `--fuzz=0` and requires
   no offset, no fuzz, and bytes identical to the stack's result.
5. It compares each touched path, after the whole stack, with the stage-B
   build tree. That tree was patched independently by `make dir` and is the
   tree the 153.4.0esr APK was built and runtime-tested from.

| patch | before files present | `--fuzz=0` replay | equals stack | stage-B tree |
|---|---|---|---|---|
| extension-update-controls | 19 of 27 | exact | yes | 27/27 identical |
| global-privacy-controls | 9 of 21 | exact | yes | 21/21 identical |
| session-cleanup | 13 of 15 | exact (after the context refresh below) | yes | 15/15 identical |

The present/absent counts match the 153.0esr receipts: 19 existing and 8 new;
nine retained pre-existing files; 15 outputs. The predecessor sets agree as
well. GPC's seven scoped predecessors are the same seven patches LW-M7-36
listed, and session-cleanup's only overlapping predecessor is still
extension-update-controls on `test-api.js` and `test-schema.json`. Running
`recapture.py` twice gives byte-identical archives and JSON.

`stack-apply.json` records each stack patch's sha256 and its offset and fuzz
counts. After the session-cleanup refresh, 14 hunks apply with fuzz.

### session-cleanup.patch context refresh

On 153.4.0esr, `session-cleanup.patch` applied with offsets in
`nsFrameLoader.cpp` and with **fuzz 2** in the `CookiePersistentStorage.cpp`
include block. Upstream added `#include "mozilla/AppShutdown.h"` there. The
receipt's `--fuzz=0` replay rejected that hunk, so no honest receipt could
pin the old bytes. The patch was refreshed in two parts:

- The two `nsFrameLoader.cpp` hunk headers move by the reported offsets
  (+6, +8).
- The `CookiePersistentStorage.cpp` section is regenerated against the
  captured before tree.

Every `+` and `-` line in the patch is byte-identical to before; only hunk
headers and context changed. The refreshed patch produces the same 15 files as
the fuzzy application, and those match the stage-B tree that was built and run.

## What each file proves

- `recapture.py` is the generator above. It is not run by any test, because
  it needs the 766 MB tarball.
- `replay.py` is the verifier the three tests import. It checks the patch and
  archive digests, every before hash (absent included), the exact `--fuzz=0`
  replay, and every after hash. It needs only repository files:
  `python3 docs/android/evidence/lw-m7-01/esr-153.4.0/receipts/replay.py`.
- `<stem>.json` holds the patch sha256, the tarball sha256, the stack
  position, the predecessors and later patches touching the same paths, the
  per-file before and after sha256, the stack and replay `patch` output, and
  the stage-B comparison.
- `<stem>-before.tar.gz` is the before tree for that patch.

## What was NOT re-captured or run

- No CI guest capture was made. The guest-capture provenance in lw-m7-35 and
  -37 is 153.0esr history. The before trees here are derived from the signed
  tarball and the patch stack, not captured from a guest.
- `test-session-cleanup.py` still parses with the XPIDL/WebIDL parsers pinned
  in `lw-m7-37/native-parser-inputs.tar.gz`, which are 153.0esr parser
  sources. They parse the 153.4.0esr files without error, but the parsers
  themselves were not re-captured.
- `test-global-privacy-controls.py` still verifies LW-M7-36's original
  153.0esr audit inputs (`verify_originals`). That is a check on repository
  evidence, not on 153.4.0esr source.
- The task-local replay tools are 153.0esr-only and still fail on the
  153.4.0esr patch bytes. They are `lw-m7-36/check-source.py`,
  `lw-m7-35/check-ordering.py`, `lw-m7-36/check-ordering.py`, and the lw-m7-37
  composition verifiers. They are not part of `scripts/tests`, and
  `scripts/check-patch-order.py` is the gate for ordering.
- Nothing here compiles C++, Java or Kotlin, or runs xpcshell, GeckoView or
  Fenix tests. The stage-B build and the runtime evidence in `../README.md`
  cover what was run.
