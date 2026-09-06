# Remote Settings allowlist — the LW-M4-08 decision, laid out

**Non-normative.** This changes nothing. It exists so the decision LW-M4-08 owns
can be made in one sitting instead of re-derived. The values live in
`settings/common.cfg:709` and `:713`, shared with desktop, and that file already
says *"these two lists are Android's as well; LW-M4-08 owns their Android
contents"*.

Read off the **running** Android build on 2026-09-06 (not from the cfg source):
33 entries in `allowedCollections`, 11 in `allowedCollectionsFromDump`. Both
prefs are present and populated, so the cfg layer is applied and this list is
what Android actually honours today.

## Why this is a decision and not a bug

`allowedCollections` is the set permitted to **sync over the network**.
`allowedCollectionsFromDump` is the set permitted to load from the copy compiled
into the binary — no network either way. So the entire first-run traffic
(`docs/android/evidence/lw-m7-06/`: 10 events, 690 KB) comes from the first list,
and the second list costs nothing.

The tension is between two of this project's own commitments:

- **M4's headline claim** — no outbound request between install and first
  navigation — which cannot hold while any collection may sync;
- **not silently degrading security** — several of these lists are how a browser
  learns about revoked certificates, malicious add-ons and new trackers between
  releases. Freezing them means a stale list until the next build ships, which
  `LW-M4-08`'s own notes already call "a release-cadence problem now".

Both are defensible. What is not defensible is shipping desktop's list unexamined
and describing the result as zero-network.

## `allowedCollections` — the 33 that may sync

Grouped by what the maintainer is actually deciding. "Keep" costs first-run
traffic; "drop" costs freshness of that one list.

**Security-relevant, and the strongest case for keeping.** Dropping these trades
a privacy property for a security one, which is the trade this project usually
refuses to make silently.

    security-state/*                     cert revocation (CRLite). LibreWolf runs
                                         CRLite in enforce mode with OCSP off, so
                                         this IS the revocation path. Dropping it
                                         freezes revocation at build time.
    blocklists/addons                    Mozilla's add-on blocklist
    blocklists/addons-bloomfilters       the same, in the compact form
    blocklists/gfx                       driver denylist (crash/security)
    blocklists/plugins                   legacy plugin blocklist
    main/tracking-protection-lists       the ETP lists themselves
    main/hijack-blocklists               search-hijack protection

**Privacy features whose data ages.** Keeping them is defensible; dropping them
degrades a feature rather than a protection.

    main/anti-tracking-url-decoration    URL-parameter stripping rules
    main/bounce-tracking-protection-exceptions
    main/third-party-cookie-blocking-exempt-urls
    main/partitioning-exempt-urls
    main/fingerprinting-protection-overrides
    main/url-classifier-exceptions
    main/cookie-banner-rules-list        cookie-banner handling
    main/content-classifier-lists

**Desktop or Mozilla-account features. Strong candidates to drop on Android** —
several are for products Redoubt does not ship at all.

    main/fxrelay-denylist                Firefox Relay
    main/fxrelay-allowlist               Firefox Relay
    main/fxmonitor-breaches              Firefox Monitor
    main/vpn-serverlist                  Mozilla VPN
    main/ml-model-allow-deny-list        the ML features this build strips
    main/mfcdm-origins-list              Media Foundation CDM — Windows-only
    main/translations-models             translation model index
    main/translations-wasm
    main/translations-models-v2
    main/translations-wasm-v2
    main/webcompat-interventions         webcompat shims
    main/addons-data-leak-blocker-domains

**Password-manager data.** Only useful if the built-in password manager is used.

    main/password-rules
    main/password-recipes
    main/change-password-urls
    main/websites-with-shared-credential-backends
    main/backup-common-passwords-list

**Other.**

    main/language-dictionaries           spell-check dictionary index

## `allowedCollectionsFromDump` — the 11 that load from the binary

No network. Leaving this list alone costs nothing, and **two entries must stay**:

    main/search-config-v2                LW-M4-06's engine set
    main/search-config-icons             its icons, incl. Mojeek and Startpage

The rest are inert-to-harmless on Android (`newtab-wallpapers*`, `tippytop`,
`ms-images`, `devtools-*`, `urlbar-persisted-search-terms`,
`moz-essential-domain-fallbacks`, `url-parser-default-unknown-schemes-interventions`).

## What to do with the answer

1. Put the Android values in `settings/android.cfg` rather than editing the
   shared `common.cfg` lines — the split is what `--check-cfg-split` enforces,
   and desktop's list must not move.
2. Write the reason **per dropped collection**. A future reader must be able to
   tell a deliberate omission from an oversight; that is the whole content of
   `must-not-lock.txt` as a precedent.
3. Re-run `./scripts/android-smoke.sh --first-run-capture` and
   `--check-no-remote-settings` and record the new number. If anything still
   syncs, M4's claim needs rewording rather than repeating.
4. Note that narrowing the list does **not** stop the 2-hourly WorkManager sync
   registered at `FenixApplication.kt:736` — it stops it having anything to
   fetch. If the goal is no periodic wakeup at all, that is a separate Kotlin
   change and a separate task.
