# Google Play store listing, en-US (paste-ready)

Owner: LW-M6-12. Used by `docs/android/PLAY.md` step 9. Each field below is the exact
text to paste; the fenced blocks hold it so nothing is re-wrapped. Lengths are
checked by `python3 docs/android/play/check-listing.py` (title <= 30, short <= 80,
full <= 4000 characters, no Firefox/LibreWolf name in the title or short description).

**Trademark rule applied here.** Mozilla's trademark policy lets a project say it "is
based on Mozilla open source technology" and requires saying it is not officially
associated with Mozilla; it forbids Mozilla marks in the app name
(https://www.mozilla.org/en-US/foundation/trademarks/policy/, read 2026-10-05). So the
title and short description name neither Firefox nor LibreWolf; the full description
names them once each, factually, next to the non-affiliation statement. Play's metadata
policy forbids ranking or promotional claims ("best", "#1", "free") and emoji
(https://support.google.com/googleplay/android-developer/answer/9898842, read
2026-10-05); none is used.

## App name (title)

```text
Redoubt Browser
```

## Short description

```text
A privacy-hardened web browser: no telemetry, strict tracking protection.
```

## Full description

```text
Redoubt is a privacy-hardened web browser for Android, built from source.

It changes the defaults of a modern Gecko-based browser so that privacy is the starting point, not a setting you have to find:

• No telemetry, no experiments, no crash-report upload, no advertising and no advertising ID. The developer collects no data about you.
• Resist-fingerprinting on, strict tracking protection and cookie partitioning locked on, Global Privacy Control on.
• uBlock Origin preinstalled, with its cookie-notice lists turned on.
• Search suggestions off by default; sponsored shortcuts removed and cloud features turned off.
• Per-site process isolation locked on for high-value sites.
• No Google Play Services inside the app.

Honest limits, stated up front:

• Android has no Gecko content-process sandbox. Per-site isolation and isolated processes recover most of that protection, not all of it. The full, measured comparison is published on redoubtbrowser.org.
• Redoubt is a small, independent project with one maintainer.

What leaves your device, and when:

• Security lists (certificate revocation, add-on blocklist) and add-on update checks go to Mozilla's servers, as in every Gecko-based browser. They carry no identifier for you.
• uBlock Origin updates its filter lists from the sites that publish them.
• Sync is off by default. If you sign in with a Mozilla account, your bookmarks, history, passwords and tabs are synced end-to-end encrypted.
• Everything else goes only to the websites you visit and the search engine you choose.

Same app on every channel: the Google Play version is signed with the same key as the APKs on GitHub Releases, so the certificate fingerprint published on redoubtbrowser.org matches on every install. The Play version is updated by Google Play and has no in-app update check.

Source code, build instructions, the privacy policy and security reporting: redoubtbrowser.org and github.com/CPlusPlus17/Redoubt.

Redoubt is based on Mozilla open source technology and uses the privacy configuration and patch set of the LibreWolf project under the Mozilla Public License 2.0. Redoubt is not officially associated with Mozilla or with the LibreWolf project, and neither has reviewed or endorsed it. Firefox is a trademark of the Mozilla Foundation.
```

## Other listing fields

| field | value |
|---|---|
| App category | Communication (the category Google Play files web browsers under; pick "Communication" if the Console offers no "Browser" category) |
| Tags | Web browser; Privacy (choose from the Console's fixed list; at most 5) |
| Contact email | the owner's project address (owner to choose; Play shows it publicly) |
| Website | `https://redoubtbrowser.org` |
| Privacy policy | `https://redoubtbrowser.org/privacy-policy.html` |

## Graphics

| asset | file | spec (support.google.com/googleplay/android-developer/answer/9866151, read 2026-10-05) |
|---|---|---|
| App icon | `graphics/icon-512.png` | 512 x 512, 32-bit PNG with alpha, <= 1024 KB |
| Feature graphic | `graphics/feature-graphic-1024x500.png` | 1024 x 500, JPEG or 24-bit PNG, no alpha |
| Phone screenshots (>= 2) | `screenshots/phone-*.png` | JPEG or 24-bit PNG, no alpha, each side 320-3840 px, long side <= 2x short side |

Both graphics are rendered from the launcher mark by `graphics/make-graphics.py`.
The screenshots are taken from the API 34 emulator with the Play build
(`docs/android/evidence/lw-m6-12/README.md` says which build and how).
