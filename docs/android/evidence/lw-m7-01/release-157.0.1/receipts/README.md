# 157.0.1 source receipts for six hash-pinned Android patches (2026-10-09)

This directory holds the 157.0.1 counterpart of `../../release-157.0/receipts`.
It was produced with the same `recapture.py` and checked with the same
`replay.py`. The two copies here differ from 157.0's only in their usage text.
The six receipt tests look up `release-<version.android>`, so without this
directory they fail on 157.0.1 with "patch changed since source receipt".

```sh
python3 docs/android/evidence/lw-m7-01/release-157.0.1/receipts/recapture.py \
  --out docs/android/evidence/lw-m7-01/release-157.0.1/receipts \
  --objdir librewolf-157.0.1-1 \
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

`--objdir` is the tree `make android-dir TARGETS=android` made from
`firefox-157.0.1.source.tar.xz` (sha256 `483bedee…241c4c`). All six receipts
replay exactly at `--fuzz=0`. Each replay is byte-identical to the stack, and
the result matches that tree (9/9, 6/6, 27/27, 21/21, 15/15 and 15/15 paths).
The log is in `../gates/recapture.log`.

## Before trees compared with the 157.0 receipts

Four of the six before archives are byte-identical to the 157.0 ones. The
other two, extension-update-controls and global-privacy-controls, differ in
two files:

- `fenix/settings/SettingsFragment.kt`
- `res/xml/preferences.xml`

The same two files are byte-identical in the 157.0 and 157.0.1 tarballs. The
difference therefore comes from earlier patches on the stack that changed on
main after the 157.0 capture of 2026-10-02, not from Firefox 157.0.1.
