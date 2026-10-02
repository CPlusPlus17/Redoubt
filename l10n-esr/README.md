# l10n-esr/ - the pre-157 overlay, for Android

A byte copy of `l10n/` as it was before the Firefox 157 desktop merge
(commit c72764c4). `scripts/librewolf-patches.py` applies it instead of
`l10n/` on an android-only run (`--targets=android`), so the 153.0esr
Android tree gets exactly the overlay it got before the merge. Desktop
(and a desktop+android run) applies `l10n/`.

Do not edit these files; translation fixes go into `l10n/`. Delete this
directory, and the `l10n-esr` branch in `librewolf-patches.py`, when
Android moves to an ESR >= 157. `.md` files are not copied by the overlay.
