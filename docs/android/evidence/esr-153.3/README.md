# Android rebase: 153.0esr → 153.3.0esr

`version.android` moves from `153.0esr` to `153.3.0esr`. Beta 2 was built on
`153.0esr`; Mozilla has since shipped three ESR security releases (153.1.0esr,
153.2.0esr, 153.3.0esr). [`TRACK.md`](../../TRACK.md) commits this track to taking
them as they ship.

## What changed

| patch | 153.3.0esr conflict | resolution |
|---|---|---|
| `fix-canvas-extraction-permission` | Upstream ships the identical `HTMLCanvasElement::CaptureStream` change (`ImageExtractionResult(this, nsContentUtils::GetCurrentJSContext(), &aSubjectPrincipal)`), so the hunk rejects | Moved from `common.txt` to `desktop.txt`. Desktop (153.0.4) still lacks the fix and keeps it; on Android it is now upstream code. `PATCH-SCOPE.md` records the move |
| `android/ubo-readiness` | Upstream rewrote `ext-webRequest.js` `registerEvent`: the stream-filter `remoteTab` plumbing is gone and `convert(_fire)` no longer receives a context | Same hooks re-ported: `isLiveListener` parameter, the `markLive` registration set, `markLive()` in `convert`, and `!!context` from the registrar (primed listeners are still registered with `{fire, isInStartup}` and no context, `ExtensionCommon.sys.mjs:461-464`). The other four files apply unchanged |
| `android/extension-update-controls` | Upstream added a standalone `PWRunnable` for backup writes and a `DispatchWriteComplete` helper, beside the `sPendingWriteData` coalescing the patch removes | Redoubt's per-request writer (own snapshot, exact result, explicit cancel) replaces the class and `WritePrefFile`'s dispatch exactly as on 153.0esr; upstream's backup branch is subsumed by it and removed. The resulting `Preferences.cpp` differs from the 153.0esr result only by upstream's unrelated type-change fix (`ClearUserValue` in `SetDefaultValue`) |
| `android/session-cleanup` | One include hunk fuzzed: upstream added `mozilla/AppShutdown.h` in its context | Context refreshed; applies with `--fuzz=0` |

`ext-backgroundPage.js` and `Extension.sys.mjs` are byte-identical between the two
tags, so the readiness fix's reasoning (delayed background at `APP_STARTUP`,
temporary startup policy) holds unchanged.

## Verified here

- `replay-series.py FIREFOX_153_3_0esr_RELEASE`: all 66 common+Android patches apply,
  0 failures — [`replay-153.3.0esr.txt`](replay-153.3.0esr.txt). The same replay on
  `FIREFOX_153_0esr_RELEASE` with the pre-rebase lists also had 0 failures.
- `scripts/tests/test-ubo-readiness.js` on the fully patched 153.3.0esr files: 24/24.
- `fix-canvas-extraction-permission.patch` applies to `FIREFOX_153_0_4_RELEASE`
  (`--fuzz=0`, offset 7), so desktop is unaffected by the move.
- `board.py --check`, `--check-scope`, `lint-patch-scope.py` green;
  `check-patch-order.py` reports the same 7 pre-existing unclassified pairs as before.
- `scripts/tests/*.py`: the same results as on Beta 2's tree.

## Not verified

No Gecko, GeckoView or Fenix build ran; no device run. `replay-series.py` fetches
only the touched files from GitHub and does not replay `librewolf-patches.py`'s
out-of-patch mutations. `make check-patchfail TARGETS=android` against the real
`firefox-153.3.0esr.source.tar.xz` is the authoritative check and must run before a
candidate is built.

## Historical receipts

`test-session-cleanup.py` and `test-extension-update-controls.py` replay LW-M7-35
and LW-M7-37 source receipts captured on 153.0esr, pinned by patch hash.
[`rebase.json`](rebase.json) binds each rebased patch's hash to its stored
pre-rebase copy in [`patches-153.0esr/`](patches-153.0esr/); the tests replay the
receipt with that copy, and only if both hashes match. The receipts are not
re-captured, and say nothing about 153.3.0esr.
