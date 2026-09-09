# LibreWolf feature completeness on Android

Owner request, 2026-09-08: **"get feature complete with librewolf"**.
Tracking task: LW-M7-08. The first published beta is the baseline, not evidence
that this new goal is already complete.

## Completion standard

Inventory the current LibreWolf features, defaults, user controls, policy effects,
and behavior implemented by desktop-only patches. For each Android counterpart,
record implementation evidence and a test that exercises the actual behavior.
Neither a preference value nor a visible settings row alone proves the feature
works. Existing beta evidence can be reused only where its inputs and test scope
match the current implementation.

The goal remains open until the complete inventory is checked and missing
features are implemented and verified. A limitation described in documentation
does not count as an implementation. Android platform constraints and the fork's
separate signing identity must remain visible; they cannot be silently changed
into claims of desktop equivalence.

## Requirements and current evidence

The baseline combines the current [LibreWolf features](https://librewolf.net/docs/features/),
[FAQ](https://librewolf.net/docs/faq/), [settings](https://librewolf.net/docs/settings/),
and this repository's `settings/{common,desktop}.cfg`,
`settings/distribution/policies.json`, and 36 desktop patches. Android source
references below refer to the frozen `librewolf-153.0esr-1-beta-20260908/` tree.
Beta runtime values refer to `evidence/lw-m7-06/beta-audit-2026-09-08/final-candidate/prefs-all.json`.
Implementation updates distinguish the published beta, the compiled uBO/defaults
candidate, and later cookie/graphics/translation source. The uBO/defaults APK
passes all eight baseline smoke checks and the limited preference audit; its
immediate add-on restart test fails. See `evidence/lw-m7-12/runtime-sixth-attempt/`.
Native attempt 4 compiled all three ABIs. Collection then rejected a stale merged
publication beside the new x86_64 AAR. The repaired publication passed in53s;
the actual merge then passed at02:49:36UTC, with both ARM archives verified
against the original compilation. Evidence is retained in
`evidence/lw-m7-21/native4-success/`. The164-file native build includes graphics,
translations, Sync, cookie controls and Suggest admission. Three APK attempts
exposed Kotlin errors in Suggest copy visibility, nullable settings context and
deprecated permission-dialog Bundle construction; their corrected source compiled
successfully into four development APKs on 2026-09-09 at 03:21:56Z. The following
resource check stopped on an optimized ZIP filename; its failed checkpoint and
successful compiler evidence remain in `evidence/lw-m7-21/apk-bundle-resource-check-failure/`.
The corrected checker resolved the optimized resource table and verified the empty
shortcut payload in all four unchanged APKs; see
`evidence/lw-m7-21/apk-resource-verification-success/`. After four test fixture
corrections, all146 selected Android component cases passed, while Fenix test
compilation required a coroutine API opt-in. That failed run is preserved in
`evidence/lw-m7-21/second-current-target-failure/`. The third full run exposed
nine unexpected failures; the fourth resolved all nine after one custom-tab
routing correction and two test fixture corrections. Its full Fenix gate still
failed with610 classes/5521 tests and21 failures:17 environmental,3 known-real
and one new navigation test fixture failure. All146 component cases passed.
The complete terminal record is in `evidence/lw-m7-21/fourth-current-target-failure/`.
The corrected navigation fixture then passed all four actual targeted cases,
with no skips or errors (`evidence/lw-m7-21/fenix-navigation-correction/`). The new
full suite passed both gates on the167-file manifest `501d0461…`:610 classes,
5521 tests,20 failures =17 environmental +3 known-real +0 unexpected. All146
component cases passed and every required feature class passed without skips.
See `evidence/lw-m7-21/current-fenix-navigation-success/`. New APK compilation
is running; its resource and runtime checks remain pending. Later permission persistence, explicit
Suggest data import, global/extension controls and native cleanup primitives
require another candidate. These older APK results do not validate them.
The old `PARITY.md` and `POLICIES.md` are inputs to recheck, not proof of completion.

| ID | Feature / default / control | Current implementation and evidence | Required completion evidence / work |
|---|---|---|---|
| F01 | uBlock Origin enabled by default | Pinned ordinary AMO-signed 1.74.0 install and live listener wait are compiled; full Fenix and 53 extension-support tests pass. Fresh first navigation blocks the matching script before automation and loads its allowed control | Immediate force-stop after completed disable exposes stale addonStartup cache and resumes real blocking despite disabled registry state. LW-M7-19 source fix and 36 source tests are in the current native build; UI disable/removal, private permissions, update/upgrade, tamper/failure and broader lifetimes remain open |
| F02 | HTTPS-only, with exceptions and user control | New absent-setting defaults compile and pass Fenix gate. Candidate APK blocks the HTTP fixture with the actual Fenix error page; a visible Continue click loads HTTP, and a separate trusted HTTPS control loads securely | Normal/private controls, upgrade of eligible HTTP origins and restart remain pending; persisted old values are preserved, not silently migrated |
| F03 | Strict tracking protection and site exceptions | LW-M7-09 selects the effective strict policy and matching UI for absent settings, retaining stored Standard/Custom choices; policy/UI tests are included in the passing source-bound Fenix gate | Classified tracker block, allowed resource, site exception and actual cross-site cookie partition tests on the new APK remain pending |
| F04 | Cookie/site-data/cache cleanup, retention and exceptions | LW-M7-09 enables Quit cleanup for absent settings with only cookies/site data and cache selected; master-toggle changes retain existing categories. Source-bound Fenix gate passes. LW-M7-37 adds source-verified per-frame destruction completion and checked cookie scope/deletion APIs; native compilation and14 target cases remain pending | Root captured actual native4 source: Quit dispatches clear operations without awaiting callbacks, completion runs in finally, and GeckoView discards failed-category masks. Fix these boundaries and cookie-retention exceptions; verify seeded data and unrelated retention. Interrupted-session startup recovery remains missing (lw-m7-21/cleanup-source-audit) |
| F05 | Explicit DoH off; chosen providers and modes | LW-M7-09 uses explicit OFF (5), Quad9 URI, DNS4All fallback and seven desktop provider choices; existing provider URLs and stored modes remain selected. Source-bound Fenix gate passes | Resolver traffic, selected mode/fallback, custom URI, exceptions and restart on the built APK remain pending; no behavior claim follows from configured URIs |
| F06 | Password/card/address saving and autofill controls | LW-M7-09 disables absent save/autofill choices and aligns radio/XML defaults, preserving stored choices. Source-bound Fenix gate passes, including the previously failing autofill middleware class | Actual absence of default prompts/autofill, deliberate opt-in, effective engine state, exceptions and restart remain pending |
| F07 | Per-site WebGL permission | LW-M7-14 implements native page/worker checks, exact-origin parent validation, GeckoView/AC/Fenix quiet controls, acknowledgement and permission lifetimes. Source tests and all-ABI Gecko/Java builds pass; corrected Fenix production code compiles and required Fenix/AC unit tests pass in the current full gate | Run authored native target tests; exercise actual UI denial/allow, saved/temporary permission, revoke, private/frame/worker isolation and compositor pixels. Old prompt=false APK rendering does not validate this bridge |
| F08 | Protected canvas and site exceptions | Existing RFP readback protection is observed in the old candidate. LW-M7-14 adds exact-origin canvas review and engine-owned saved permissions alongside WebGL | Gecko/Java and corrected Fenix production compilation pass; actual protected/permitted readback, revocation, private/session lifetimes, stale-document and cross-origin checks remain pending |
| F09 | RFP and coherent fingerprint behavior | Master RFP has earlier effective-pref evidence. LW-M7-36 adds a native-authoritative global control with save/reset/lock/default state and separate private/FPP context;18 host JS checks pass, target checks remain pending | Test language, UA, viewport, DPR, timezone and readback across settings/locales/device configurations; test deliberate opt-out |
| F10 | Optional letterboxing | Off by default on desktop, so no missing default; optional desktop feature still lacks a demonstrated Android counterpart | Implement a working mobile viewport adaptation or retain as an explicit unresolved platform/feature gap; an inert pref is insufficient |
| F11 | Translations and offline reuse | LW-M7-16 packages a complete pinned catalog and WASM with verified local cache and scoped explicit native downloads; passive paths stay cache-only and both RS allowlists are unchanged. 6 packaging/45 source tests pass. All-ABI native/Java and Fenix production compilation pass after the cancellation API correction; target tests remain pending | Actual direct/pivot DOM translation, offline restart, native download/delete/cancel/error controls, normal/private lifetimes and passive traffic probes remain pending. Internal about:translations has no new explicit download path and requires cached models |
| F12 | Cookie banner rejection | LW-M7-13 packages 558 rules with no cookie RS client. LW-M7-23 adds independent normal/private reject-only controls, domain exceptions and canonical private-session lifetime fencing. Root runs 19 handler checks and 43 C++ source assertions; the164-file set passes all-ABI native/Java compilation, and Fenix production compilation passes; target tests remain pending | Exact APK assets and target tests; real reject callbacks/opt-out cookies with accept-only controls, existing consent, actual controls and normal/private lifecycle remain pending. Scoped source tests are not device rejection proof |
| F13 | Sync/accounts opt-in and disable | LW-M7-20 source implements off-by-default admission, explicit enable/disable and process restart, preserved account/engine/server data, and worker/callback gates. Root replay passes24 files;19 selected account/worker component tests and the existing Fenix account cases pass in the fourth target run. The custom-tab routing correction and all four new intent cases pass the complete suite; rebuilt APK and runtime remain pending | Compile and run target tests/full Fenix gate, then real login/Sync, PID replacement, private-session lifetime, failed persistence, disabled traffic and send/receive polling on the final APK |
| F14 | Extension install/update controls and type restrictions | Root source audit confirms Android XPI loading already rejects non-extension types, including language packs. Official unmodified uBO 1.73.0/1.74.0 update fixtures are retained and hash-verified. LW-M7-35 implements a native automatic-update switch, actual preference-write completion and periodic/explicit update routing;18 source JS checks pass, target checks remain open | Actual signed rejection/normal-extension controls and older-to-newer update remain pending, including Gecko signature state and retained choices. Android also rejects desktop-supported dictionary/theme/sitepermission types; existing locale-addon removal and update traffic/permission controls remain open |
| F15 | Privacy search and suggestions | Four engines/default/no-attribution and ordinary suggestion toggles have earlier beta runtime evidence. LW-M7-26 adds default-off Firefox Suggest controls, lazy service/transport admission and private/late-result guards; source replay passes and native attempt 4 includes it | Run 19 authored Kotlin tests, final APK controls and typing/network probes. LW-M7-29 explicit pinned dataset downloads and atomic local import are now source-implemented; nine host asset tests and scoped replay pass, while 16 Rust/13 Kotlin tests, target compilation and APK download/ingestion remain pending. Custom engines and ordinary engine suggestions remain separate regression checks |
| F16 | LibreWolf settings pane and network controls | Desktop `patches/pref-pane/librewolf.js` exposes extension updates, Sync, IPv6, cross-origin referrers, RFP, WebGL, optional letterboxing and desktop integration; LW-M7-36 adds five mobile native-backed controls for RFP, WebGL approval/quiet mode, IPv6 DNS and referrer0/1/2. Host replay passes; target compilation and26 authored target tests remain pending | Compile and test actual UI/native controls, deliberate choices, locks and immediate restart behavior; account explicitly for userChrome/profile access/middle-click desktop integration |
| F17 | Feedback, support links and messaging | Much Mozilla messaging removed; actual reporter/menu/support routes still need review. `WebCompatFeature` is compatibility interventions, not a reporter | Remove/redirect actual feedback routes as desktop policies require, keep compatibility interventions working, verify visible menu targets |
| F18 | Telemetry/experiments/sponsored content/proprietary services | Existing compiled/runtime evidence for removals, no GMS/Adjust, no sponsored onboarding | Final candidate regression and transport checks; close stale P2/P3/P4/P6/P8 policy claims against actual code |
| F19 | TLS/revocation/HTTPS policy and network privacy | Configured CRLite2/OCSP off, TLS floor, no speculative connections, referer trimming; many behavior checks absent | Real positive/negative TLS/revocation/referrer/prefetch probes, including deliberate user overrides where desktop permits them |
| F20 | GPC, DRM, PDF scripting, IDN and local-network policy | Effective defaults exist; specific behavior coverage varies | Page/server observations: GPC, disabled/default and permitted DRM where applicable, PDF scripts, punycode, local-network permission/control behavior |
| F21 | About/config and identity | Release about:config and real autoconfig locks verified; release ID `org.redoubtbrowser` | Verify controls and persistence in new APK; preserve installed app identity and record distinct signing trust root |
| F22 | Site/process isolation and compiler protections | Existing Fission/isolatedProcess/RLBox/hardening evidence; Gecko desktop content sandbox absent | Recheck changed native builds; keep absent sandbox and desktop OS integrations explicit, never count explained gaps as implemented |
| F23 | Desktop patch/policy coverage | LW-M7-17 audits all 36 desktop patches/46 effect groups, 22 policy keys/46 exact leaves and 16 copied-pane controls. Root's additional bookmark audit finds startup creates five folder roots and no URL bookmarks; no new bookmark-seeding patch is justified by that source | Close mapped functional gaps and run behavior checks. Verify the exact fresh APK bookmark DB without deleting entries, then create/open a bookmark through UI and retain its GUID/URL across restart/upgrade. Input coverage and source counterparts do not establish runtime parity |
| F24 | Honest gates, build and upgrade | VM compiled the uBO/defaults candidate: Fenix gate 602 classes/5468 tests, 90 failures = 87 environmental + 3 known-real + 0 unexpected; 53 support-extension tests pass. Four development-signed release-type APKs built; x86_64 passes 8 baseline checks and a 20-key live pref audit. uBO immediate restart still fails | The cookie/graphics/translation increment now compiles into four development APKs; all four optimized shortcut resources are verified and146 selected component cases pass. The current full Fenix gate passes with zero unexpected failures; rebuilt APK and behavior checks remain pending. Curated audit does not cover all locks or UI. New shipping version and old-beta upgrade remain pending; preserved ambiguous old defaults need an explicit apply-defaults option |

For settings changes, test four cases: fresh profile, upgrade with untouched old
defaults, explicit opposite user choice, and a second restart. Do not reset
explicit choices or delete existing history while correcting defaults.

## Existing decisions and artifacts

The published beta and its source tag remain fixed. New work produces a new
candidate and version code suitable for upgrading an installed beta. The Android
release key remains outside CI; the prior exception covered only the four
already-published APK hashes and does not authorize signing new candidates.

The seven-collection Android Remote Settings decision remains in force. Preserve
the actual desktop baseline when comparing defaults: a stronger setting is not
automatically parity, and a desktop preference implemented only in browser UI
needs a real Android counterpart where its behavior applies.

This inventory remains open to concrete findings from the patch/policy coverage
audit and runtime testing. Every row is part of the goal; completing uBO alone
does not complete feature parity.
