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
Implementation updates below distinguish those old APK observations from new
source-bound unit results in `evidence/lw-m7-12/completed-fenix/`; new APK runtime
evidence is still pending.
The old `PARITY.md` and `POLICIES.md` are inputs to recheck, not proof of completion.

| ID | Feature / default / control | Current implementation and evidence | Required completion evidence / work |
|---|---|---|---|
| F01 | uBlock Origin enabled by default | LW-M3-07 now installs the pinned, unmodified AMO-signed 1.74.0 XPI and waits for its live blocking listener before navigation; cancellation, failure/retry and stored removal/disable choices are implemented. Source-bound full Fenix gate and 53 extension-support tests pass; see `evidence/lw-m7-12/completed-fenix/` | Built-APK offline first-navigation readiness, actual normal/private blocking and allowed control, managed filter bootstrap, signature/update prompts, cancellation and removal/disable/private-permission persistence remain pending |
| F02 | HTTPS-only, with exceptions and user control | LW-M7-09 defaults absent settings to enabled for all tabs, aligns XML/UI and preserves stored alternatives; final source-bound Fenix unit gate passes | Actual HTTP block/upgrade, HTTPS control, explicit HTTP exception, control and restart on the new APK remain pending; persisted old values are preserved, not silently migrated |
| F03 | Strict tracking protection and site exceptions | LW-M7-09 selects the effective strict policy and matching UI for absent settings, retaining stored Standard/Custom choices; policy/UI tests are included in the passing source-bound Fenix gate | Classified tracker block, allowed resource, site exception and actual cross-site cookie partition tests on the new APK remain pending |
| F04 | Cookie/site-data/cache cleanup, retention and exceptions | LW-M7-09 enables Quit cleanup for absent settings with only cookies/site data and cache selected; master-toggle changes retain existing categories. Source-bound Fenix gate passes | Seed cookie/localStorage/IndexedDB/cache/history/permission state and prove supported Quit retention/deletion and exempt sites. Task removal, process death and force-stop cleanup remain an implementation/lifecycle gap |
| F05 | Explicit DoH off; chosen providers and modes | LW-M7-09 uses explicit OFF (5), Quad9 URI, DNS4All fallback and seven desktop provider choices; existing provider URLs and stored modes remain selected. Source-bound Fenix gate passes | Resolver traffic, selected mode/fallback, custom URI, exceptions and restart on the built APK remain pending; no behavior claim follows from configured URIs |
| F06 | Password/card/address saving and autofill controls | LW-M7-09 disables absent save/autofill choices and aligns radio/XML defaults, preserving stored choices. Source-bound Fenix gate passes, including the previously failing autofill middleware class | Actual absence of default prompts/autofill, deliberate opt-in, effective engine state, exceptions and restart remain pending |
| F07 | Per-site WebGL permission | Missing Android prompt bridge; `webgl-prompt-default.patch` disables prompting to keep rendering functional | Add prompt/delegate/response before changing default; denial, allow, remember/temporary, revoke, private isolation and actual WebGL rendering |
| F08 | Protected canvas and site exceptions | RFP readback protection is present; desktop canvas exception UI has no demonstrated Android counterpart | Implement/verify permission bridge; protected and permitted readback, revocation, private isolation |
| F09 | RFP and coherent fingerprint behavior | Master RFP is effective; broad live coherence is unverified | Test language, UA, viewport, DPR, timezone and readback across settings/locales/device configurations; test deliberate opt-out |
| F10 | Optional letterboxing | Off by default on desktop, so no missing default; optional desktop feature still lacks a demonstrated Android counterpart | Implement a working mobile viewport adaptation or retain as an explicit unresolved platform/feature gap; an inert pref is insufficient |
| F11 | Translations and offline reuse | Enabled, but model/WASM collections excluded by security-only Remote Settings policy and Rust downloads blocked | Reproduce real first translation; provide narrow user-triggered data/model path consistent with owner decisions, test offline reuse and no unsolicited download |
| F12 | Cookie banner rejection | LW-M7-13 implements a pinned 558-rule Android local loader and packaging, with zero cookie RS client construction and both allowlists unchanged. Commit `81ecc2a`: 23 actual-source loader tests pass; see `evidence/lw-m7-13/README.md` | Integration/build, packaged hashes and Gecko tests; real reject callback or opt-out cookie with accept-only and allowed controls, exceptions, existing consent and normal/private lifecycle remain pending. Hidden banners are not rejection proof |
| F13 | Sync/accounts opt-in and disabled-by-default behavior | Fenix initializes account/Relay components; desktop enable switch has no demonstrated counterpart | Verify startup traffic and implement real off/opt-in controls, login/sync/logout behavior and restart persistence |
| F14 | Extension install/update controls and type restrictions | Extension operation exists; desktop language-pack restriction and user update controls unverified on Android | Reject restricted types while allowing normal extensions; actual update check/disable behavior, user consent for new permissions, uBO compatibility |
| F15 | Privacy search and suggestions | Four engines/default/no-attribution and off-on-off suggestions have runtime evidence for beta payload | Reuse only with unchanged inputs; verify final candidate, custom engines, private search behavior and typing transport controls |
| F16 | LibreWolf settings pane and network controls | Desktop `patches/pref-pane/librewolf.js` exposes extension updates, Sync, IPv6, cross-origin referrers, RFP, WebGL, optional letterboxing and desktop integration; Android lacks the pane | Implement applicable mobile controls with effective state, deliberate choices and restart behavior; account explicitly for userChrome/profile access/middle-click desktop integration |
| F17 | Feedback, support links and messaging | Much Mozilla messaging removed; actual reporter/menu/support routes still need review. `WebCompatFeature` is compatibility interventions, not a reporter | Remove/redirect actual feedback routes as desktop policies require, keep compatibility interventions working, verify visible menu targets |
| F18 | Telemetry/experiments/sponsored content/proprietary services | Existing compiled/runtime evidence for removals, no GMS/Adjust, no sponsored onboarding | Final candidate regression and transport checks; close stale P2/P3/P4/P6/P8 policy claims against actual code |
| F19 | TLS/revocation/HTTPS policy and network privacy | Configured CRLite2/OCSP off, TLS floor, no speculative connections, referer trimming; many behavior checks absent | Real positive/negative TLS/revocation/referrer/prefetch probes, including deliberate user overrides where desktop permits them |
| F20 | GPC, DRM, PDF scripting, IDN and local-network policy | Effective defaults exist; specific behavior coverage varies | Page/server observations: GPC, disabled/default and permitted DRM where applicable, PDF scripts, punycode, local-network permission/control behavior |
| F21 | About/config and identity | Release about:config and real autoconfig locks verified; release ID `org.redoubtbrowser` | Verify controls and persistence in new APK; preserve installed app identity and record distinct signing trust root |
| F22 | Site/process isolation and compiler protections | Existing Fission/isolatedProcess/RLBox/hardening evidence; Gecko desktop content sandbox absent | Recheck changed native builds; keep absent sandbox and desktop OS integrations explicit, never count explained gaps as implemented |
| F23 | Desktop patch/policy coverage | 24 common + 36 desktop patches; 22 policy keys need current effect mapping, not just source-path classification | Account for every policy and desktop patch, including functional counterparts, with implementation or explicit open item |
| F24 | Honest gates, build and upgrade | LW-M7-10 removes false live success: static results say CONFIGURED ONLY, unsupported live runs return PENDING. LW-M7-11 adds bounded live probes. VM compiled the combined uBO/default sources; source-bound Fenix gate reports 602 classes / 5468 tests, 90 failures = 87 environmental + 3 known-real + 0 unexpected; four extension classes ran 53 tests with zero failures | Final APK packaging/behavior, actual probe execution and old-beta upgrade remain pending. Absent old preferences inherit new defaults; ambiguous persisted defaults are preserved. An explicit apply-defaults action remains open |

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
