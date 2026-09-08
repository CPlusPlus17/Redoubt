# LW-M7-17 — semantic coverage audit

All 36 registered desktop patches, 22 policy keys (46 exact scalar/array leaves),
four copied preference-pane assets, 16 settings/buttons and 15 active preference
registrations now have an input-bound effect mapping. **This is not a browser
parity pass.** The audit ran no APK, emulator, network or native-build checks.

Start with [coverage-map.md](coverage-map.md), the readable effect map. Its
machine-readable counterpart is [coverage.json](coverage.json). Each Android
claim cites inspected source or a pinned repository patch and states what remains
missing or unverified. Concurrent graphics and translation implementations are
outside the pinned snapshot, `7c78e8a3a86d6feed5ea0517b9c824ce0cbfa8ae`.

Produced by the `coverage_map` agent in its isolated `android/LW-M7-17` worktree
on the Fedora host. Source inspection was read-only; no guest was accessed.

The most consequential distinctions found in the inspected code are:

- **Extension updates:** Fenix schedules updates every 12 hours. GeckoView does
  honor `extensions.update.enabled`, but refreshes stale add-on repository
  metadata before checking it. Its update/install path does not consult
  `extensions.update.autoUpdateDefault`. Desktop's combined two-pref control
  therefore needs an Android UI and network/scheduler treatment.
- **Sync:** removing sign-in onboarding does not gate Fenix's account manager.
  It starts when its lazy component is resolved; the bounded Fenix search found
  no `identity.fxaccounts.enabled` reader.
- **Home:** removing ads/Pocket does not implement `TopSites=false` or
  `Highlights=false`. Fenix's frozen home defaults enable ordinary top sites,
  recent tabs, bookmarks and recent activity. Shortcuts are not bookmark-database
  entries; `NoDefaultBookmarks` must be checked separately.
- **Firefox Suggest:** its persisted web/sponsored controls and FML release
  default are separate from ordinary search-engine query suggestions. The
  existing `no-suggest` patch alone cannot prove all three policy leaves.
- **Site-data retention:** desktop stores exact-principal, permanent cookie
  `ALLOW`. Fenix quit cleanup uses unscoped cookie/storage deletion. ETP exceptions
  and a clear-site-data button do not implement retention exceptions.
- **Translations:** global enable and automatic offer controls already exist in
  Fenix, with persistence code. Verified downloads/offline translation and the
  effective control/restart matrix remain separate obligations.
- **Other explicit gaps:** optional password-manager hiding, existing locale
  add-on removal as well as install-type restrictions, `ku` locale support
  (`ckb` is distinct), optional letterboxing, the JPEG XL control/actual decoding,
  IPv6/referrer controls, and appropriate support/repository links.
- **Feedback:** Fenix has a WebCompatReporter route enabled for ordinary URLs.
  `WebCompatFeature` is a separate bundled compatibility intervention extension;
  it must not be removed as if it were the reporter. No-telemetry source changes
  do not by themselves make remaining report UI accurate.

Desktop OS integrations are recorded individually: D-Bus command routing,
Windows MSIX/COM/manifest details, macOS relaunch/assets, GTK profile paths and XUL
presentation do not run in the Android frontend. Explaining that boundary never
marks a surviving functional requirement implemented. Likewise, the enterprise
policy service is omitted on Android; packaging `policies.json` is not policy
enforcement. The identical WebsiteFilter block/exception rule is a no-op in the
inspected desktop handler and must not turn into an Android localhost ban.

## Preserved evidence

[source-index.md](source-index.md) lists the inspected portions of 46 complete
files retained in [inspected-source.tar.gz](inspected-source.tar.gz). The archive
includes relevant Android/Gecko source, desktop policy handlers and the exact
settings inputs. Every file and the archive itself have SHA-256 bindings in
[source-evidence.json](source-evidence.json). Thirty repository counterpart files
are additionally pinned in `coverage.json`.

[bounded-searches.json.gz](bounded-searches.json.gz) preserves five search
patterns, their scopes, exit status/output, searched file hashes and the Fenix
resource-directory list. A zero-match result is only a bounded observation, not
proof of semantic absence throughout Android. The source tree name is not treated
as a revision identifier. The retained files are a frozen host input, while
newer M7 code is cited by its separate patch hash; neither is silently described
as the final APK source.

## Verification

Run from the repository root, without an SDK, VM, device or extracted source tree:

```sh
python3 docs/android/evidence/lw-m7-17/check-coverage.py
python3 docs/android/board.py --check
```

The checker compares the current desktop list and patch bytes, all changed
desktop paths, exact policy leaves/values, settings gitlink, copied pane
settings/buttons/registrations, counterpart references and evidence hashes. It
fails if a mapped input changes. It validates that the inventory is accounted
for; it cannot prove a human semantic interpretation or browser behavior.

The recorded successful output is in [verification.txt](verification.txt).
Seven deliberate negative controls rejected missing patches/subkeys/controls,
changed policy values, unknown counterparts, changed source hashes and a false
runtime verdict; see [checker-negative-controls.txt](checker-negative-controls.txt).
No target code was modified, so no APK/native/Fenix test suite was run for this
documentation task. Graphics, cookie rules, translations and the broader feature
goal still require their own implementation/build/runtime acceptance evidence.
