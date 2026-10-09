# 158.0 source receipts for six hash-pinned Android patches (2026-10-09)

The 158.0 counterpart of `../../release-157.0/receipts` (read that README for
what the receipts are and how `recapture.py` works). `version.android` now
reads `158.0`, so the six receipt tests in `scripts/tests` look up this
directory.

`recapture.py` and `replay.py` are copies of the 157.0 ones (only the
docstring of `replay.py` names 158.0). Command, from the repository root with
`firefox-158.0.source.tar.xz` present and `make android-dir TARGETS=android`
done:

```sh
python3 docs/android/evidence/lw-m7-01/release-158.0/receipts/recapture.py \
  --out docs/android/evidence/lw-m7-01/release-158.0/receipts \
  --objdir librewolf-158.0-1 \
  --input translation-assets:toolkit/components/translations/bergamot-translator/bergamot-translator.js \
  --input translation-assets:toolkit/components/translations/bergamot-translator/moz.yaml \
  --input extension-permission-durability:toolkit/components/extensions/Extension.sys.mjs \
  --input extension-permission-durability:toolkit/components/extensions/ExtensionTaskScheduler.sys.mjs \
  patches/android/addon-state-durability.patch \
  patches/android/extension-permission-durability.patch \
  patches/android/extension-update-controls.patch \
  patches/android/global-privacy-controls.patch \
  patches/android/session-cleanup.patch \
  patches/android/translation-assets.patch
```

Tarball: `firefox-158.0.source.tar.xz`, 814889676 bytes, sha256
`fc77f7801d7580a600af683cc367e261eb1ec74647e84a91b4a1e3c1dd5aa2bb`, taken
from `candidates/158.0-candidates/build2/source/` and verified against the
pinned `assets/mozilla-release-key.asc` (GOODSIG, primary
`14F26682D0916CDD81E37B6D61B7B526D98F0353`); see
`../release-day/tarball-158.0-build2.txt`. The release tarball is compared
with it in `../release-day/README.md`.

| patch | before files present | `--fuzz=0` replay | equals stack | `make android-dir` tree |
|---|---|---|---|---|
| addon-state-durability | 7 of 9 | exact | yes | 9/9 identical |
| extension-permission-durability | 5 of 6 (2 are `--input`) | exact | yes | 6/6 identical |
| extension-update-controls | 19 of 27 | exact | yes | 27/27 identical |
| global-privacy-controls | 9 of 21 | exact | yes | 21/21 identical |
| session-cleanup | 13 of 15 | exact | yes | 15/15 identical |
| translation-assets | 13 of 15 (2 are `--input`) | exact | yes | 15/15 identical |

This is the same result as the b3 dry run (`../prebase/receipts-trial-recapture.log`).
A second run without `--objdir` gave byte-identical `*-before.tar.gz` and
`stack-apply.json`; the per-patch JSON differs only in the two `objdir`
fields. All six receipt tests pass (`../release-day/gates/scripts-tests.txt`).

**android/158-beta2 (2026-10-09).** Recaptured on the Beta 2 copy branch,
which carries LW-M7-46's new `canvas-webgl-permissions.patch`, with the same
command and the same RC build2 tarball. All six patches are again exact at
fuzz 0, equal to the stack and to the `make android-dir` tree. The
`*-before.tar.gz` files are byte-identical; only the recorded sha256 of
`canvas-webgl-permissions.patch` changed (in `stack-apply.json`,
`extension-update-controls.json` and `global-privacy-controls.json`), to
`27243749bfcc844a4af772b5058b83c20791c2d5427704fb57028148524c81fa`.
