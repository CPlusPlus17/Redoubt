# Gaps to LibreWolf — review of 2026-09-24

What LibreWolf does that Redoubt Android, as published in **Beta 2**
(`android-153.0esr-1-beta.2`, source `764fc91c`, tree-identical to `main` at
`c72764c`), does not. Written for deciding what to do next, so it is ordered by
consequence, not by subsystem. The exhaustive inventories are
[`FEATURE-PARITY.md`](FEATURE-PARITY.md) (rows F01–F24),
[`PARITY.md`](PARITY.md) and the LW-M7-17 effect map
([`evidence/lw-m7-17/coverage-map.md`](evidence/lw-m7-17/coverage-map.md)); this
file cites them rather than repeating them.

"LibreWolf" here means the LibreWolf inputs vendored in this repository: the 24
common and 36 desktop patches, `settings/{common,desktop}.cfg`,
`settings/distribution/policies.json`, and the copied preference pane. How far
those inputs have fallen behind LibreWolf's own repository is §5; Codeberg was not
reachable from the review environment, so that part is not measured.

## 1. Defects in the published Beta 2

### 1.1 "uBlock Origin setup failed" on every launch after the first — fixed on this branch

The first run works; every later cold start ends in the setup-failed dialog, and
Retry repeats it.

At `APP_STARTUP` Gecko delays a persistent extension background until the first
browser window paints (`ext-backgroundPage.js`, `onManifestEntry`;
`geckoview.js` sends `browser-delayed-startup-finished` and
`extensions-late-startup` only for a GeckoSession window). The uBO startup gate
(`ubo-preinstall.patch`) holds every engine session until uBO's live blocking
listener exists (`ubo-readiness.patch`). Each waits for the other; after 30 s the
gate fails. A second, faster failure was possible too: the add-on manager
reports ready before `Extension.startup()` finishes, so the wait could judge the
temporary startup policy, whose permissions are not loaded yet.

Nothing caught it because no run ever relaunched with uBO enabled: the Kotlin
tests fake the readiness call, and `--check-ubo-lifecycle` restarts only after
disabling or removing uBO, where the gate does not wait.

Fix, in `ubo-readiness.patch`: wait for the settled policy, then start a delayed
background directly — the step install, enable and a primed request already take.
Six new cases in `scripts/tests/test-ubo-readiness.js` (four fail against the
Beta 2 patch); `--check-ubo-preinstall` now relaunches with uBO enabled
(`ubo-enabled-restart`). **Still required: a build and that smoke check on a
device.** Until then the fix is source-verified only.

### 1.2 Three ESR security releases behind — rebased on this branch

`version.android` is now `153.3.0esr`; all 66 common+Android patches apply to it
(four needed work, see [`evidence/esr-153.3/`](evidence/esr-153.3/README.md)).
Still required: `make check-patchfail TARGETS=android` on the real tarball and a
build.

Beta 2 is built on `153.0esr`. Mozilla has since shipped `153.1.0esr`,
`153.2.0esr` and `153.3.0esr` (tags on `mozilla-firefox/firefox`, checked
2026-09-24). [`TRACK.md`](TRACK.md) commits the Android track to "dot releases as
they ship". Each ESR dot release carries that cycle's security advisories, so this
is the largest security gap after the content sandbox — and unlike the sandbox it
is fixable by rebasing. LibreWolf desktop follows Firefox release, which is now
`156.0.1`.

### 1.3 uBO's filter configuration is fetched from LibreWolf's servers

`settings/common.cfg:703` sets `librewolf.uBO.assetsBootstrapLocation` to
`https://codeberg.org/librewolf/source/raw/branch/main/assets/uBOAssets.json`
— upstream LibreWolf's file, on LibreWolf's infrastructure, at a moving branch.
`custom-ubo-assets-bootstrap-location.patch` is in `common.txt`, so Android
honours it, and uBO 1.74.0 fetches that URL on first install when it has no cached
registry (`assets.js` `getAssetSourceRegistry`). The same file's own `assets.json`
entry points back at Codeberg, so later registry updates poll it as well.

Three consequences:

- **A runtime dependency on another project.** What lists Redoubt's uBO enables is
  decided by whatever LibreWolf's `main` says at the time of each fetch, and every
  Redoubt install contacts Codeberg. The XPI is hash-pinned; its configuration is
  not. [`IDENTITY.md`](IDENTITY.md) separates the two projects; this does not.
- **First-run timing.** In the copy vendored here (`assets/uBOAssets.json`; the
  live Codeberg file may differ) three enabled lists have no packaged copy
  (`adguard-spyware-url`, `curben-phishing`, `LegitimateURLShortener`), so first
  initialisation also fetches them. uBO's fetch timeout is 30 s per request
  (`assetFetchTimeout`); the gate's listener wait is 30 s in total. On a slow or
  filtering network the *first* run can therefore also end in "setup failed".
  Retry then usually succeeds, because uBO keeps initialising in the background.
- **Not in the first-run capture.** Beta 1's capture predates uBO; Beta 2's
  first-run traffic now includes Codeberg and those list hosts, and the release
  notes' first-run statement does not mention them.

Options, for the owner: serve a pinned copy from infrastructure Redoubt controls;
or leave the pref unset on Android and inject the LibreWolf list selection through
the managed-storage hook the patch already has (`adminSettings`), accepting that
the three unpackaged lists still download; or package those three lists. Any of
them should raise or reshape the first-run wait once measured on a slow network.

### 1.4 Stale public statements

- The Beta 2 release notes and [`PARITY.md`](PARITY.md) row 6 say LibreWolf's DoH
  configuration "does not apply" because Fenix overwrites it. That was Beta 1.
  `privacy-defaults.patch` (in Beta 2) makes Fenix default to mode 5 (off, which
  is LibreWolf's setting) and ships LibreWolf's provider list with Quad9 and the
  DNS4All fallback. Runtime resolver evidence is still pending (F05), but the
  statement as written is wrong.
- `PARITY.md` rows 5, 7 and 8 still treat cfg-only values as at risk because
  "the cfg layer is not packaged (LW-M3-08)"; it has been packaged and applied,
  with its locks, since `lw-fresh-2026-08-22` ([`README.md`](README.md)).

## 2. LibreWolf behaviour with no working Android counterpart

| LibreWolf does | Redoubt Android | Where |
|---|---|---|
| Deletes cookies, site data and cache every time the browser closes (`desktop.cfg`: `privacy.sanitize.sanitizeOnShutdown`) | Cleans up only on the explicit **Quit** menu action. Swiping the app away or the OS killing it keeps everything; recovering an interrupted session is not implemented (LW-M7-37 has only its native building blocks). This is the gap users would notice first. | F04, LW-M7-37 |
| Per-site "keep cookies for this site" exception, respected by cleanup (`allow_cookies_for_site.patch`) | No control; cleanup has no retention exceptions | F04, coverage map *cookie-exemption* |
| Gecko content-process sandbox | Absent: not compiled on Android upstream. Partly offset by site isolation, `isolatedProcess` and RLBox | PARITY §3.1 |
| Enterprise policies (`policies.json`) enforced by Gecko | No policy engine on Android; each key mapped by hand, residual gaps P1–P8 | [`POLICIES.md`](POLICIES.md) |
| Feedback and "report broken site" routed away from Mozilla; support menu points at LibreWolf's tracker | Fenix's reporter and support routes not yet audited or redirected | F17, P1 |
| Global EME (DRM) switch with a LibreWolf explanation | DRM off by default, but only a per-site permission; no global control | coverage map *eme* |
| Optional "hide password manager" (`librewolf.hidePasswdmgr`) | Save/autofill default off; no hide option | F06, *password* |
| Optional JPEG XL decoding | No verified decoder or control | *jxl* |
| Kurdish (`ku`) UI locale | Not shipped | *locale* |
| Link preview without the AI key-points | No equivalent | *link-preview* |
| Dictionary, theme and site-permission add-on types | Android installs extensions only | F14 |
| Distinct code-signing identity | Irreducible: a fork cannot carry LibreWolf's; Redoubt's key has one holder | PARITY §3.2, `SIGNING.md` |

Not gaps, and they should stay off this list: letterboxing (off by default on
desktop too), desktop-only integrations (D-Bus, MSIX, userChrome, profile
reveal, middle-click paste), and the language-pack removal patch (Android already
rejects locale add-ons at install).

## 3. Shipped in Beta 2 but never shown working on a running build

These are in the Beta 2 APK. Their source compiles and host tests pass, but no
check has exercised them on a device or emulator. §1.1 is what that state can
hide.

| Feature | Row |
|---|---|
| HTTPS-only defaults and exceptions | F02 |
| Strict tracking protection as the effective default | F03 |
| DoH off, LibreWolf's provider list | F05 |
| Password/card/address saving off | F06 |
| Per-site WebGL and canvas permissions, quiet mode | F07, F08 |
| RFP, WebGL, IPv6 and referrer controls in Settings | F09, F16 |
| Offline translations from packaged models | F11 |
| Cookie-banner rejection with normal/private controls | F12 |
| Sync off by default with explicit opt-in | F13 |
| Extension auto-update switch | F14 |
| Firefox Suggest off, explicit dataset import | F15 |
| TLS, revocation, referrer, GPC, PDF-scripting and local-network behaviour | F19, F20 |

## 4. Configuration that is set but may not act

- **Speculative connections.** `android.cfg` records that Fenix's
  `Engine.speculativeConnect` is not gated by LibreWolf's two desktop
  urlbar/places prefs. `common.cfg`'s `network.http.speculative-parallel-limit = 0`
  stops the socket for a plain speculative connect (`nsHttpConnectionMgr`
  compares against it before opening one), but an HTTPS-RR DNS lookup can precede
  that check. A capture of typing in
  the toolbar would settle it.
- **Prefs Fenix rewrites at startup.** Around 65 prefs are pushed by Fenix on every
  cold start after our cfg (AGENTS.md, landmine L2); only locked ones are safe. The
  runtime audit covers 20 of 137 `must-lock.txt` keys.

## 5. Drift from LibreWolf itself

- This repository's LibreWolf base is `153.0.4-1` (`version`, `release`), with
  settings forked from LibreWolf's `b403bfb` ("Remove search engine policies").
  Firefox release is at `156.0.1`, so upstream LibreWolf has very likely moved at
  least three releases on, with patch and settings changes this fork does not
  have.
- Not measured: `codeberg.org` is blocked in the environment this review ran in,
  and LibreWolf's GitLab mirror stops at `149.0.2-2`. To measure, from a machine
  that can reach Codeberg:

      git remote add librewolf https://codeberg.org/librewolf/source.git
      git fetch librewolf main
      git diff --stat HEAD librewolf/main -- patches/ assets/ scripts/ Makefile version release
      git -C settings remote add librewolf https://codeberg.org/librewolf/settings.git
      git -C settings fetch librewolf master
      git -C settings log --oneline b403bfb..librewolf/master

  Settings changes matter most: `common.cfg` reaches Android directly.

## 6. Suggested order

1. Build the §1.1 fix and run `android-smoke.sh --check-ubo-preinstall` on an
   emulator; ship it as Beta 3 so testers can use the app past the first launch.
2. Rebase to `153.3.0esr` in the same candidate (§1.2).
3. Decide §1.3 (where uBO's list configuration comes from) and measure the first
   run on a throttled network.
4. Correct the release notes and `PARITY.md` (§1.4).
5. Session cleanup on interrupted sessions and per-site cookie retention (§2,
   LW-M7-37) — the largest user-visible LibreWolf behaviour still missing.
6. Work through §3 on the Beta 3 APK; each row already names its evidence.
