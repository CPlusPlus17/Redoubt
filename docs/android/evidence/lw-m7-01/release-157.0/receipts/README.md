# 157.0 source receipts for four hash-pinned Android patches (2026-10-02)

Four `scripts/tests` files replay a patch onto pinned "before" source and
check pinned "after" hashes:

- `test-extension-update-controls.py` (LW-M7-35)
- `test-global-privacy-controls.py` (LW-M7-36)
- `test-session-cleanup.py` (LW-M7-37)
- `test-translation-assets.py` (LW-M7-16)

On the 157 branch all four failed. `version.android` reads `157.0`, so the
lookup found no `esr-<version>` receipts, fell back to the 153.0esr chain and
stopped at its first patch digest. This directory is the 157.0 counterpart of
`../../esr-153.4.0/receipts`, produced the same way.

The lookup in the four tests now reads `esr-<version without esr>` for an ESR
`version.android` and `release-<version>` otherwise. Without a matching
directory it still falls back to the original 153.0esr chain, which is left
untouched as history. `test-translation-assets.py` had no per-version lookup
before; it now has the same one.

## How the receipts were produced

```sh
python3 docs/android/evidence/lw-m7-01/release-157.0/receipts/recapture.py \
  --out docs/android/evidence/lw-m7-01/release-157.0/receipts \
  --objdir <release tree>/librewolf-157.0-1 \
  --input translation-assets:toolkit/components/translations/bergamot-translator/bergamot-translator.js \
  --input translation-assets:toolkit/components/translations/bergamot-translator/moz.yaml \
  patches/android/extension-update-controls.patch \
  patches/android/global-privacy-controls.patch \
  patches/android/session-cleanup.patch \
  patches/android/translation-assets.patch
```

`recapture.py` is the 153.4.0esr generator with one addition, `--input`. It
works in five steps:

1. Extract every path any of the 63 stack patches touches from
   `firefox-157.0.source.tar.xz`, sha256
   `259c564dd4bbd56bbe8a9a6cf001fc8812853567fd3a78e77c9ddf10d7d4e982`.
   `gpg --verify firefox-157.0.source.tar.xz.asc` on 2026-10-02: good
   signature from Mozilla Software Releases, subkey
   `827E658608679618CD349F93678E455D76767AA3`, primary
   `14F26682D0916CDD81E37B6D61B7B526D98F0353`.
2. Apply `assets/patches/common.txt` and then `android.txt` with `patch -p1`,
   the order `check-patchfail.sh` and the patcher use.
3. Capture the touched paths just before each target patch, as
   `<stem>-before.tar.gz` (deterministic, mtime 0; absent paths recorded in the
   JSON).
4. Replay the target alone on that capture with `--fuzz=0`. It must show no
   offset and no fuzz, and its result must be byte-identical to the stack's.
5. Compare each touched path after the whole stack with the release tree
   `build/librewolf-157.0-1`. `make dir` patched that tree independently, and
   the four 157.0-1 APKs were built from it.

| patch | before files present | `--fuzz=0` replay | equals stack | release tree |
|---|---|---|---|---|
| extension-update-controls | 19 of 27 | exact (after the hunk-header fix below) | yes | 27/27 identical |
| global-privacy-controls | 9 of 21 | exact | yes | 21/21 identical |
| session-cleanup | 13 of 15 | exact | yes | 15/15 identical |
| translation-assets | 13 of 15 (2 are `--input`) | exact | yes | 15/15 identical |

The present/absent counts match the 153.4.0esr receipts. The predecessor sets
also match, except that `cookie-banner-controls.patch` drops out of the
extension-update-controls and global-privacy-controls lists. That patch was
retired at the 157 integration. session-cleanup's only overlapping
predecessor is still extension-update-controls, on `test-api.js` and
`test-schema.json`. Running `recapture.py` twice gives byte-identical archives
and JSON.

### `--input`: the Bergamot glue for translation-assets

LW-M7-16's 153.0esr inventory pinned two upstream files the patch does not
touch: `bergamot-translator/bergamot-translator.js` and its `moz.yaml`.
`test-translation-assets.js` loads the pinned WASM 4 into that glue. A receipt
of patch-touched paths alone would leave that test reading a file that is not
there. `--input STEM:PATH` captures such a path from the same stack state, so
its before and after hashes are equal, and `replay.py` requires the replay to
leave it unchanged. Both files are byte-identical to the 153.0esr pins.

### extension-update-controls.patch hunk headers

On the 157 stack, extension-update-controls applied with offsets: +16 lines on
the three `mobile/android/geckoview/api.txt` hunks and +3 on
`GeckoViewStartup.sys.mjs`. The `--fuzz=0` replay refuses an offset, so no
honest receipt could pin it. Those four hunk headers now carry the in-order
line numbers. No `+`, `-` or context line changed, and the patched tree is
identical (27/27 against the release tree, which was patched with the old
headers).

## What each file proves

- `recapture.py` is the generator above. No test runs it, because it needs the
  814 MB tarball.
- `replay.py` is the verifier the four tests import. It checks the patch and
  archive digests, every before hash (absent included), the exact `--fuzz=0`
  replay and every after hash. It needs only repository files:
  `python3 docs/android/evidence/lw-m7-01/release-157.0/receipts/replay.py`.
- `<stem>.json` holds the patch sha256, the tarball sha256, the stack
  position, the predecessors and later patches that touch the same paths, the
  `--input` paths, the per-file before and after sha256, the stack and replay
  `patch` output, and the release-tree comparison.
- `<stem>-before.tar.gz` is the before tree for that patch.
- `stack-apply.json` records each stack patch's sha256 and its offset and fuzz
  counts on 157: 102 offset and 11 fuzz hunks in total. None of them is in the
  four target patches.

## Two harness fixes in `test-translation-assets`

Firefox 157 changed two things the 153 harness assumed:

- 157 creates `TranslationsChild` on demand. The rebased patch therefore sends
  `Translations:WatchPageHide` from `translateFromUser()`. The JS harness's
  stand-in parent actor had no `sendAsyncMessage`, so it now records the
  messages. The tests assert one message per admitted call and none when the
  document is already stale. The stand-in child now defines
  `ChromeUtils.defineLazyGetter` and `console`, which 157's child uses at
  module scope.
- 157 packs the GeckoView modules at `modules/`, not `modules/geckoview/`.
  `--apk` therefore reads `modules/GeckoViewTranslations.sys.mjs` when the old
  path is absent. On the 157.0-1 x86_64 APK the packaged bytes equal the
  patched source.

## What was NOT re-captured or run

- No CI guest capture was made. As for 153.4.0esr, the before trees come from
  the signed tarball and the patch stack.
- `test-session-cleanup.py` still parses with the 153.0esr XPIDL/WebIDL parser
  sources in `lw-m7-37/native-parser-inputs.tar.gz`. They parse the 157 files
  without error.
- `test-global-privacy-controls.py` still verifies LW-M7-36's original
  153.0esr audit inputs (`verify_originals`), a check on repository evidence.
- `test-extension-update-controls.py --source <tree>` does not pass on a fully
  patched tree. global-privacy-controls and session-cleanup patch some of the
  same files later, so their after hashes differ. That was also true on
  153.4.0esr.
- Nothing here compiles anything or runs xpcshell, GeckoView or Fenix tests.
