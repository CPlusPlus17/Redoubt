# LW-M7-51: port of the 2026-09-24 gaps branch onto Firefox 158 main

Owner decision 2026-10-14, verbatim: **"go"** — review the branch and port what is still
worth having onto current main, cleanly, under the owner identity; then the branch can be
deleted.

| | |
|---|---|
| Old branch | `origin/claude/librewolf-gaps-ublock-setup-k0ri3t`, tip `a11a2306`, 11 commits dated 2026-09-24, author `Claude <noreply@anthropic.com>`, merge base with main `c72764c4` (the 153.0esr Beta 2 era). Never merged. **Not deleted by this task**; the orchestrator deletes it after owner review. |
| Port branch | `port/sept24-gaps`, worktree `~/redoubt-artifacts/port-sept24/repo`, cut from `origin/main` `7b6db7fc` (released 158.0-2). Commits `d60622f7` (LW-M7-38), `e9ddf406` (LW-M7-39 held back), then this documentation commit. **Not pushed.** The tested build with LW-M7-39 listed is kept on the local branch `backup/port-sept24-drm-listed` (`c414e7b6`, not pushed). |
| Settings | unchanged: the port branch keeps main's gitlink `008b87fd`. The held-back LW-M7-39 settings half is the local Redoubt-settings branch `android-drm-permission` (`bddc198f`, parent `008b87fd`), **not pushed** and referenced only by `backup/port-sept24-drm-listed`. It lives in this worktree's submodule repository and was also fetched as a local branch into the main checkout's `settings/` repository, so removing the worktree does not lose it. |
| Method | every branch commit read in full and checked against main; nothing cherry-picked. The two ported patches are rewritten against the Firefox 158.0 tree (Fenix 158 differs from 153: new menu code, "Site settings" screen, Gecko-side broken-site report). |
| Task ids | the branch's `LW-M7-37` is a **different** task on main ("Await cleanup and recover interrupted sessions with retention", `session-cleanup.patch`), so its interrupted-session work could not keep that id (and is not ported, see below). `LW-M7-38` and `LW-M7-39` were free on main (main jumps from 37 to 40) and keep the branch's meaning. This review/port task is `LW-M7-51` (main had up to `LW-M7-50`). |

## 1. Verdict per commit

| Branch commit | What it did (153 ESR) | Verdict | Where on main / this branch |
|---|---|---|---|
| `85be1a5c` LW-M3-07 uBO "setup failed" on every relaunch | `ubo-readiness.patch` started uBO's delayed background itself; awaited the settled extension policy; 30 s → 45 s Kotlin timeout; harness hang detection; smoke `ubo-enabled-restart` | **Already fixed on main, differently** — not ported | main `388df549` (2026-10-02): the preinstaller opens a speculative GeckoView window before it waits, so Gecko's `extensions-late-startup` fires on a launcher cold start, and an AMO update during first run restarts the wait (bounded); `14436e67`/`efc20698` LW-M7-44 (user disable during the wait). Device-proven by `--check-launcher-start`, `--check-ubo-lifecycle`, `--check-ubo-user-disable` in every acceptance since 157.0-1 (158.0-2: `evidence/lw-m7-01/release-158.0-2/acceptance/`). `scripts/tests/test-ubo-readiness.js` on main already fails a run that never reaches its summary (`process.on('exit')` count). The "temporary policy stub" race does not apply: main's readiness signal is the exact version's live blocking-listener registration, which a stub cannot produce. |
| `a0d0bb41` docs: gaps to LibreWolf vs Beta 2 (`LIBREWOLF-GAPS.md`) | review of Beta 2 against LibreWolf | **Obsolete as a document** — not ported | Its live findings are fixed on main (ESR lag: Android moved to the release track, now 158.0; uBO catalog on LibreWolf's servers: LW-M7-41; delete on close: LW-M7-45) or ported here (DRM, Report broken site, PARITY row 6). Items still open are listed in section 4. |
| `8bcf6acc` rebase to 153.3.0esr | `version.android` 153.3.0esr, four patches re-ported | **Obsolete** | main went to 153.4.0esr (`b458dbc6`), then to release 157 and 158.0 (`version.android` = 158.0). |
| `bb19808b` LW-M3-07 uBO list registry without LibreWolf's servers | `assets/uBOAssets.android.json` + `scripts/gen-ubo-assets-android.py` | **Superseded on main** | LW-M7-41 `61699510`, `612fac02` (2026-10-02): same file names, derived from LibreWolf's catalog with the cookie-notice lists on and no self-update URL, served from a **commit-pinned** Redoubt URL (owner decision 2026-10-02: "a branch URL is a mutable trust anchor"). |
| `be3dec6e` LW-M3-07 point Android's uBO registry at Redoubt; 90 s / 120 s waits | settings gitlink to the branch's catalog URL; Gecko wait 30 → 90 s, Kotlin 45 → 120 s | **Superseded** (pointer) / **not ported** (timeouts) | The pointer is LW-M7-41's pinned URL. The longer waits answered a slow-network first run that no acceptance run has shown; main keeps 30 s with the AMO-update restart. Open question in section 4. |
| `a0510101` PARITY rows 5-8 | rows 5/7/8 no longer "cfg unapplied"; row 6 describes the Beta 2 DoH fix | rows 5/7/8 **superseded**; row 6 **ported (rewritten)** | Rows 5/7/8/9: LW-M7-49 measured them on the emulator (`5613eb44`), owner kept 5/7/8 Partial until the phone check (`eac1e10b`). Row 6 on main still described Beta 1 ("Absent — Fenix overrides it (DoH off)", desktop "ON"); rewritten in this branch's docs commit with 158.0-2 evidence, see section 3. |
| `fb955fc8` LW-M7-37 clean an interrupted session on the next start | `interrupted-session-cleanup.patch`: on every cold start with delete-on-quit on, delete before any engine session | **Superseded by main's LW-M7-45** — not ported | main `726ded4c`, `f44de75e` (`delete-on-quit-swipe.patch`, 2026-10-06/07): a marker file makes the next cold start after any non-Quit exit delete the selected categories before restore; a hard gate holds every engine session (restore, link, custom tab, PWA, widget); HISTORY purge; bounded 20 s fail-open with retries; best-effort `onTaskRemoved` for the last task. Device-proven (swipe, force-stop, kill -9, Quit, setting off, link and custom-tab cold starts). Main's version is stricter (skips the deletion after a confirmed Quit) and covers more entry points. |
| `5497ba60` LW-M7-38 remove "Report broken site" | `no-webcompat-reporter.patch` (153: one menu entry) | **Ported, rewritten for 158** | `d60622f7` on this branch. Fenix 158 has two menus offering it; see section 2. |
| `6027a88b` docs: gap verdicts, Beta 3 notes draft | `LIBREWOLF-GAPS.md` verdicts, `RELEASE-NOTES-BETA3-DRAFT.md` | **Obsolete** | Beta 3 was published 2026-10-02 from 153.4.0esr with its own notes. Verdicts reused here: Kurdish is not a gap, link preview is desktop-only, the DRM finding (ported), JPEG XL (section 4). |
| `c58094c7` review fixes | interrupted cleanup keeps incoming-link tabs; uBO registry URL on Redoubt's main branch | **Superseded** | Link tabs: LW-M7-45 deletes the session file before restore, and the link's tab is created after the gate opens, so it survives (device case c11/c12). Registry URL: LW-M7-41 pins a commit instead of a branch, by owner decision. |
| `a11a2306` LW-M7-39 DRM off by default through a Settings switch | `drm-permission-default.patch` + `android.cfg` drops `media.eme.enabled=false` | **Rewritten for 158, built and measured, then held back** (on disk, in no list) | `e9ddf406` on this branch; settings half on the local branch `android-drm-permission` (`bddc198f`). Addition: the DRM screen marks Blocked, not "Ask to allow", as Recommended. On 158 it crash-loops isolated tabs on Android 12+; see section 2. |

## 2. What was ported

### 2.1 LW-M7-38: no "Report broken site" (listed, `d60622f7`)

LibreWolf's `DisableFeedbackCommands` policy removes the feedback commands on desktop.
What the entry does in Fenix 158 (traced in the 158.0 source and on 158.0-2):

- with `Settings.isTelemetryEnabled` true (Fenix's default, Redoubt does not change it)
  it opens the WebCompatReporter form (`device-api34-c414e7b6/menu/ctl-158.0-2-after-tap.png`: "What's not
  working?", eight reasons, "Report broken site"). Send calls
  `GeckoEngineSession.sendGleanBrokenSiteReport`, Gecko's broken-site-report **Glean
  ping**, which Redoubt cannot upload (`no-glean.patch`), so the report is silently
  discarded while the UI says it was sent;
- with it false, `MenuNavigationMiddleware` skips the form, calls
  `sendMoreWebCompatInfo` and opens `https://webcompat.com/issues/new?url=<page>`, i.e.
  hands the page address to a third party.

`patches/android/no-webcompat-reporter.patch` removes the entry from both menus that
offer it: `MoreSettingsSubmenu` (the main menu's "More", what every user sees) and
`BrowserMenuBuilder`'s default configuration (the customizable menu behind
`isMenuCustomizationEnabled`, off by default). The 153 branch patch had only the first;
the second is new in Fenix 158. The reporter code and its navigation targets stay
(unreachable), so does `WebCompatFeature` (`webcompat@mozilla.org`, site interventions,
reports nothing). The two unused parameters of `MoreSettingsSubmenu` stay so that
`MenuDialogFragment.kt`, which `delete-on-quit-swipe.patch` also edits, is untouched;
the Fenix Kotlin build (`-Werror`) accepts it.

Unit tests (new): `BrowserMenuBuilderTest` "WHEN building any default menu THEN it has no
report broken site item" (toolbar top/bottom x expanded or not) and
`MoreSettingsSubmenuTest` "GIVEN the page could be reported, THEN no report broken site
option renders" (`isWebCompatEnabled = true`). Both pass with the patch and fail with its
`src/main` hunks reverted (section 6).

### 2.2 LW-M7-39: DRM switch, rewritten and measured, held back (`e9ddf406`)

The finding is real on 158.0-2 (API 34 and API 30 emulators, `runs*/drm/ctl-*`):
`android.cfg`'s `media.eme.enabled=false` keeps DRM off as on desktop, but Gecko checks
it in `MediaKeySystemAccessManager::RequestMediaKeySystemAccess` **before** it asks the
app, so Settings > Site settings > DRM-controlled content, which reads "Ask to allow
(Recommended)", has no effect: after choosing **Allowed**, `requestMediaKeySystemAccess`
for Widevine still rejects with `NotSupportedError: EME has been preffed off`. Desktop's
off is a checkbox the user can tick.

What Fenix 158 offers natively, and the least invasive design: GeckoView sets
`media.eme.require-app-approval`, so once the key system and configuration are
supported Gecko asks the app (`PERMISSION_MEDIA_KEY_SYSTEM_ACCESS` ->
`SitePermissionsFeature`). That permission already has Ask to allow / Blocked / Allowed
and per-site exceptions. `drm-permission-default.patch` makes its default Blocked
(`PhoneFeature.getDefault()`, read by `Settings.getSitePermissionsCustomSettingsRules()`
through `PhoneFeature.getAction()`), moves the "Recommended" tag to Blocked on that
screen, and pairs with dropping the `android.cfg` line (settings `bddc198f`). Stored
choices are kept. Clear Key stays off (`librewolf.eme.gmp-clearkey.enabled=false` +
`eme-permission-common.patch`: "CDM is not installed" in every run).

Measured with both halves (build of `c414e7b6`, section 6):

| | API 30 `default` image (no isolation) | API 34 `google_apis` (158.0-2 isolates content) |
|---|---|---|
| fresh profile, DRM screen | Blocked, marked Recommended | Blocked, marked Recommended |
| probe, default | Widevine **rejected** (`EME has been preffed off`, the LibreWolf wording of `eme-permission-common.patch` for an app denial) in 183 ms, no prompt | **content process crash**, the tab reloads and crashes again |
| after "Allowed" | Widevine **resolved** | crash loop |
| after "Ask to allow" | promise pending, prompt "Allow http://127.0.0.1:18765 to play DRM-controlled content?" | crash loop |
| after "Blocked" | rejected again | crash loop |
| control 158.0-2, after "Allowed" | rejected, `EME has been preffed off` | rejected, `EME has been preffed off` |

The API 34 crash: with `media.eme.enabled` true, `GetSupportedConfig` runs in the content
process and calls `MediaDrmProxy.isSchemeSupported` ->
`MediaDrm.isCryptoSchemeSupported`; SELinux denies `isolated_app` the
`android.hardware.drm.IDrmFactory/widevine` lookup, the call throws
`IllegalArgumentException: Failed to query crypto scheme support` on the Gecko thread,
the isolated content process dies (`zygoteTab ... has died`), Fenix reloads the tab and
the page probes again: **836 crashes in about 7 minutes** of the probe flow
(`runs/drm/crash-excerpt.txt`). The app is never asked, so no setting can prevent it.
Any page that probes EME (video sites commonly do so on load; not measured here) would
crash-loop on Android 12+ if this shipped on 158. 158.0-2 is safe because the pref stops the request before
`GetSupportedConfig`. A user who sets `media.eme.enabled` in `about:config` on Android
12+ reaches the same code path (not measured separately).

Decision taken here: the patch is kept on disk, rewritten and tested, in **no list**
(PATCH-SCOPE "Pending"), `android.cfg` and the gitlink are unchanged, and LW-M7-39 stays
open for an owner decision: re-measure on the 159 rebase (the isolation study lists
upstream bugs 2067689 and 2075686, FIXED in 159, as EME work on this path; whether they
cover this crash is unmeasured), or an SDK-gated variant (EME on only where content is
not isolated). Unit tests: `PhoneFeatureTest` (default Blocked; stored choice kept) and
`SettingsTest` (fixture default Blocked; default and "Ask to allow" honoured) pass with
the patch, 14 fail with its `src/main` hunks reverted. The seven pairs it would form
with `Settings.kt`/`SettingsTest.kt` patches are order-free at `--fuzz=0`
(`ordering-swap.py`, `ordering-swap.txt`); listing it needs these rows in
`scripts/check-patch-order.py`:

```
no-onboarding, no-suggest, privacy-defaults       -> Settings.kt + SettingsTest.kt
no-gms, search-config, firefox-suggest-policy,
disable-157-cloud-features                        -> Settings.kt
```

LibreWolf desktop, for comparison: `EncryptedMediaExtensions {"Enabled": false}` sets
`media.eme.enabled=false` on the default branch (unlocked) and `desktop.cfg` sets it too;
`eme-permission-desktop.patch` adds the doorhanger; Clear Key is off. PARITY.md has no
DRM row; FEATURE-PARITY F20 now records the measurement.

## 3. PARITY row 6 (DoH)

Main's row 6 described Beta 1: "Absent — Fenix overrides it (DoH off)", with the desktop
column "ON (mode 5 ...)". Mode 5 is DoH **off by choice**, on desktop and Android.
`privacy-defaults.patch` (LW-M7-09, in every build since Beta 2) makes Fenix's own
defaults LibreWolf's (mode 5, LibreWolf's provider catalog with the dns4all default;
Mullvad removed by `doh-mullvad-migration.patch`), so the startup rewrite of
`network.trr.mode`/`network.trr.uri` by Fenix now writes LibreWolf's values. Measured:
the 158.0-2 acceptance pref dump (API 34; `network.trr.mode` 5, `network.trr.uri`
Quad9, unlocked, no user value), the same rows in this branch's builds (section 7), and
Settings showing "DNS over HTTPS: Off" on a new profile of the port build (section 7). The new row says
**Partial — defaults match, resolver not measured**, in line with the owner's rule for
rows 5/7/8 (no upgrade without the phone check), and the README/site wording is left
alone (section 4).

## 4. Not ported, still open

These came out of the branch's review and are **not** fixed by this port. None is a
regression; they are recorded so the branch can be deleted without losing them.

- **uBO first-run wait on a slow network** (from `be3dec6e`). On first install uBO may fetch
  its catalog and the unpackaged lists, each bounded by its own 30 s fetch timeout, while
  the startup gate waits 30 s for the live blocking listener. No acceptance run has shown a
  setup failure from this (the listener registers before the lists finish), and main's
  design retries on an AMO update only. A capture on a throttled network would settle it.
- **Per-site cookie retention** during delete-on-quit (LibreWolf's
  `allow_cookies_for_site`): neither the branch nor main has it (FEATURE-PARITY F04,
  main's LW-M7-37 scope).
- **Support-menu URL** half of POLICIES.md P1 (LibreWolf's `SupportMenu` policy).
- **JPEG XL**: the decoder is compiled in and `image.jxl.enabled` is off, as on desktop,
  switchable only in `about:config`; there is no Settings switch. No FEATURE-PARITY row
  names it.
- **Hide password manager** (`librewolf.hidePasswdmgr`): saving and autofill are off by
  default (F06), but there is no option to hide the feature.
- **Drift from LibreWolf upstream** (patches and settings since the vendored base) was not
  measured by the branch (Codeberg unreachable there) and is not by this task.
- **Public wording on DoH** (README "the DNS-over-HTTPS setting in the configuration is
  overridden by the app"; `site/privacy.html`; PARITY section 5 and 7.4): still true as
  written (Fenix rewrites the two prefs on every start), but since Beta 2 it rewrites them
  with LibreWolf's values. Left for the owner: this task changes only PARITY row 6.

## 5. Gates (Firefox 158.0 tarball)

Tarball: the GPG-verified Firefox 158.0 source used for 158.0-1/158.0-2,
`~/redoubt-artifacts/ff158/final/firefox-158.0.source.tar.xz`, sha256
`fc77f7801d7580a600af683cc367e261eb1ec74647e84a91b4a1e3c1dd5aa2bb` (`sha256sum`, this
session). Final branch state (`e9ddf406` + this documentation commit; `gates/`):

| check | result |
|---|---|
| `check-patchfail.sh --targets=android` | exit 0, 71 patches. Against the 158.0-2 release-day output the only difference is the added `no-webcompat-reporter.patch`, which applies without offset or fuzz (`patchfail-android-vs-158.0-2.diff`) |
| `check-patchfail.sh --targets=desktop` | exit 0, 66 patches, identical to 158.0-2's (`patchfail-desktop-vs-158.0-2.diff` empty) |
| `check-patch-order.py` | ok, 39/39 constraints, 172 shared-file pairs (no new pair: LW-M7-38 shares no file) |
| `lint-patch-scope.py` | OK, 116 patch files (the pending one included) |
| `board.py --check` / `--check-scope` / `--check-cfg-split` / `--diff-mozconfig --strict` | ok: 137 tasks; 22/44/49 + 1 overlay, with the expected warning "pending, not in any list: drm-permission-default.patch"; 182/199/15 cfg calls, librewolf.cfg regenerates; 0 differences |
| `site-check.py` | PASS, 9 pages |
| `scripts/tests/test-*` (`.py`, `.sh`) | same exit codes as main `7b6db7fc` (`scripts-tests.txt`, `scripts-tests-main-7b6db7fc.txt`): 17 pass; `test-android-signing.py`, `test-android-version-code.py`, `test-update-check-jvm.sh` need an APK, Gradle classes or a tree, as on release day |

With LW-M7-39 listed (`c414e7b6`, superseded): check-patchfail android exit 0, 72 patches,
the DRM patch applied without offset or fuzz; check-patch-order ok with the seven
measured pairs added (179 pairs); `--check-cfg-split` 14 android calls.

## 6. Build

Both builds: x86_64, release variant, C/C++ `--enable-warnings-as-errors` with
`RUSTFLAGS="--cap-lints warn"` (the in-tree app-services `remote_settings` crate has dead
code; the remaining `warning:` lines in the Gecko log are capped Rust lints and swgl's
cargo build notes), Fenix's Kotlin `-Werror` as shipped, throwaway signature
(`CN=Redoubt throwaway test key 2026-10-02, O=NOT A RELEASE KEY`, cert sha256
`31e9a40f…b760`), container `localhost/librewolf-android-build:fx158` (`98e61be72eec`).
`android-apk.sh` exits 1 on the single-ABI universal APK check, as documented; the x86_64
APK's `libxul.so` is sha256-identical to the AAR input. Scripts: `scripts/build/` (home
paths shortened to `~`).

| | `c414e7b6` (LW-M7-38 + LW-M7-39 listed, settings `bddc198f`) | `e9ddf406` (final: LW-M7-38 listed, LW-M7-39 pending) |
|---|---|---|
| how | fat AAR from `6809f6b8` (same Gecko inputs; the commits differ in Fenix Kotlin, docs and an `android.cfg` comment), APK pass on a fresh `make android-dir` tree of `c414e7b6` (it rebuilds Gecko for the host ABI and packages that omni.ja) | full chain: `make android-dir`, fat AAR, APK (`scripts/build/chain.sh`) |
| MOZ_BUILD_DATE / versionCode | 20261014180000 / 2016190358 | 20261014220000 / 2016190390 |
| unsigned x86_64 APK sha256 | `e3469e96d799c6901a9e208e13608e874c4ad4cb56e5ceaa29daee1fa1638324` | `524daffa4fa1aed197de1fcb75b5f10418fb75738f532e23629d37b877a6b533` |
| throwaway-signed APK sha256 | `aad1a62c43679ee15b75ce17c7ee2146fcd9cbf009de70c1098a7b1bb384fc7e` | `85dba922633fb9e67b5c1b639ab4a41bbc3d224ae3f602db43ba7e5954c5757f` |
| `fenix:testDebugUnitTest`, 4 classes | 160 tests, 0 failures (BrowserMenuBuilderTest 18, MoreSettingsSubmenuTest 4, PhoneFeatureTest 9, SettingsTest 129) | 157 tests, 0 failures (18, 4, 7, 128: the DRM tests are not applied) |
| negative control | the `src/main` hunks of both patches reverse-applied, same 4 classes: 16 failures (the 2 menu tests, the 2 PhoneFeature DRM tests, 12 SettingsTest rules tests through the Blocked fixture); hunks re-applied afterwards (`scripts/build/mutant-tests.sh`) | — |

Kept outside the repository (`~/redoubt-artifacts/port-sept24/keep/`): both APKs, logs,
JUnit XMLs. Build trees deleted.

## 7. Device (API 34 emulator)

One emulator at a time, every command addressed to the emulator serial; the physical
devices attached to the host were not touched. Images: API 34 `google_apis` x86_64
(`google/sdk_gphone64_x86_64/emu64xa:14/UE1A.230829.050/12077443`, Widevine HAL present;
158.0-2 runs content isolated there) and API 30 `default` x86_64
(`Android/sdk_phone_x86_64/generic_x86_64:11/RSR1.210722.013.A2/10067904`, no isolation,
Widevine HAL present). The harness booted each with `-dns-server 9.9.9.9 -tcpdump`. Probe
pages are served from the host and reached as `http://127.0.0.1:18765` through
`adb reverse`, so they are secure contexts (EME requires one) and exempt from
HTTPS-only. Control APK: 158.0-2 x86_64, throwaway-signed, sha256 `0080b12f…b3b9` (the
acceptance file). Scripts: `scripts/device/`.

### 7.1 Final branch state `e9ddf406` (API 34, `device-api34-e9ddf406/`)

| check | result |
|---|---|
| `--check-launcher-start` | PASS |
| Report broken site (`menu-check.py`: plain page, main menu, More) | **absent**; More lists Translate page, Add to Home screen, Save to collection, Open in app, Save as PDF, Print. 158.0-2 on the same image lists "Report broken site" between Translate page and Add to Home screen, and tapping it opens the reporter form (`device-api34-c414e7b6/menu/`) |
| EME probe, default and after "Allowed" | Widevine rejected `EME has been preffed off`, Clear Key `CDM is not installed`, no crash: unchanged from 158.0-2 (LW-M7-39 not applied) |
| Settings | "DNS over HTTPS: Off" on the new profile (DoH never touched) |
| first-run capture x2, interleaved with 158.0-2 x2 (Wi-Fi off, as in the release acceptance) | 107/107 counted events vs 107/109 for 158.0-2. Named hosts of the port build not seen in either 158.0-2 run: only `www.google.com`, one ClientHello in run 1, right after Wi-Fi was switched off. It is Android's network validation: with Redoubt force-stopped (`pidof` empty), switching Wi-Fi on and off again produced two more `www.google.com` ClientHellos, and one fell in a 158.0-2 window too (`harness/www.google.com-attribution.txt`). 158.0-2 hosts not seen in the port runs: `android.googleapis.com` (OS), `curbengh.github.io` (a uBO list mirror; the list hosts vary run to run on both builds). No webcompat.com, no Widevine/Google DRM host |
| default smoke suite | 9/10; the one failure is `webgl` ("No org.redoubtbrowser window is in the input dispatcher's window list"), the known API 34 harness limit; 59 curated prefs, all equal to `expected-prefs.txt` (`network.trr.mode` 5, `network.trr.uri` Quad9, `media.eme.enabled` false) |
| `--check-isolation` x2 | 12/12 PASS both (content `isolated_app`, H.264 in `:rdd`, AAC in `:utility`, remote refusal row) |
| `--check-video` x2 | 3/3 PASS both |

### 7.2 With LW-M7-39 listed, `c414e7b6` (`device-api34-c414e7b6/`, `device-api30-c414e7b6/`)

API 34: first-run captures x2 (interleaved with 158.0-2 x2) added no named host;
`--check-isolation` 12/12 x2, `--check-video` 3/3 x2, smoke 9/10 (webgl, as above);
prefs equal to 158.0-2's except `media.eme.enabled` true. Report broken site absent. The
DRM flow crash-looped (section 2.2, `drm/crash-excerpt.txt`). API 30: smoke 10/10 including
`webgl`; DRM flow as in section 2.2 with no crash (`drm/no-crash.txt`); 158.0-2 control
rejects before and after "Allowed".
