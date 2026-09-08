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
Runtime values refer to `evidence/lw-m7-06/beta-audit-2026-09-08/final-candidate/prefs-all.json`.
The old `PARITY.md` and `POLICIES.md` are inputs to recheck, not proof of completion.

| ID | Feature / default / control | Current implementation and evidence | Required completion evidence / work |
|---|---|---|---|
| F01 | uBlock Origin enabled by default | Missing; parked patch is not registered and fabricates installed state. Genuine AMO 1.74.0 archive verified against published size/hash; see `evidence/lw-m7-08/ubo-*.json` | LW-M3-07: real offline installation before first navigation, normal/private blocking with allowed control, custom filter bootstrap, updates, disable/removal persistence |
| F02 | HTTPS-only, with exceptions and user control | Missing default: Fenix `Settings.kt` defaults off, runtime main/private values false; desktop policy enables it without locking | LW-M7-09: default on with working UI; real HTTP block/upgrade, HTTPS control, explicit HTTP exception, restart |
| F03 | Strict tracking protection and site exceptions | Missing default: Standard selects `TrackingProtectionPolicy.recommended()`; runtime tracking/social protection false, convenience allowlist true, bounce mode standby despite locked category `strict` | LW-M7-09: effective strict policy and matching UI; classified tracker block, allowed resource, site exception and actual cross-site cookie partition tests |
| F04 | Cookie/site-data/cache cleanup, retention and exceptions | Missing Android default: quit master and every category false. Desktop keeps history/download records and site permissions | LW-M7-09 plus lifecycle work: seed cookie/localStorage/IndexedDB/cache/history/permission state, quit/restart/interrupted termination, verify correct categories and exempt-site retention |
| F05 | Explicit DoH off; chosen providers and modes | Off is intended by LibreWolf. Fenix overwrites explicit off mode 5 and configured Quad9/dns4all with mode 0, empty URI and Cloudflare defaults | LW-M7-09: match mode/provider defaults without locking controls; resolver traffic, selected mode/fallback, custom URI, exceptions and restart |
| F06 | Password/card/address saving and autofill controls | Gecko defaults disabled, Fenix save/autofill controls default enabled; real prompts unverified | LW-M7-09: align UI/defaults, no default save/autofill prompts, deliberate opt-in, exceptions and restart |
| F07 | Per-site WebGL permission | Missing Android prompt bridge; `webgl-prompt-default.patch` disables prompting to keep rendering functional | Add prompt/delegate/response before changing default; denial, allow, remember/temporary, revoke, private isolation and actual WebGL rendering |
| F08 | Protected canvas and site exceptions | RFP readback protection is present; desktop canvas exception UI has no demonstrated Android counterpart | Implement/verify permission bridge; protected and permitted readback, revocation, private isolation |
| F09 | RFP and coherent fingerprint behavior | Master RFP is effective; broad live coherence is unverified | Test language, UA, viewport, DPR, timezone and readback across settings/locales/device configurations; test deliberate opt-out |
| F10 | Optional letterboxing | Off by default on desktop, so no missing default; optional desktop feature still lacks a demonstrated Android counterpart | Implement a working mobile viewport adaptation or retain as an explicit unresolved platform/feature gap; an inert pref is insufficient |
| F11 | Translations and offline reuse | Enabled, but model/WASM collections excluded by security-only Remote Settings policy and Rust downloads blocked | Reproduce real first translation; provide narrow user-triggered data/model path consistent with owner decisions, test offline reuse and no unsolicited download |
| F12 | Cookie banner rejection | Modes enabled, but cookie-banner collection excluded by Android Remote Settings policy | Test supported real banner; package/update needed rules through a narrow defined path and verify rejection |
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
| F24 | Honest gates, build and upgrade | Network/RFP scripts falsely return success after printing live-test instructions; VM has preflight only | Replace false success with actual probes/inconclusive status; compile changes in VM, full applicable unit gate, final APK behavior and old-beta upgrade with idempotent migrations |

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
