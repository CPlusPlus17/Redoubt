# Beta preparation — 2026-09-08

The beta is **not ready to start: eleven of twelve entry criteria are met**.
Release signing/custody (E7) remains open; live reporting (E10) is now verified. The entry audit is
[`BETA.md`](BETA.md), which retains all twelve criteria. The previous claim that
only signing remained was disproved by candidate-specific checks and GitHub's
live state.

## Current candidate

`librewolf-android-apk-153.0esr-1-beta-20260908/apk/` contains four unsigned release
APKs, built with R8 enabled and `MOZ_BUILD_DATE=20260906190000`. The normal
`make android-apk TARGETS=android` run completed in 505 seconds using the existing
three-ABI native inputs. ARM32, ARM64 and x86_64 ELF engines are present; the
universal contains all three. The source matches all 248 paths touched by the
50 common/Android patches applied to the pinned ESR tarball.

The new candidate replaces the earlier `...-unsigned/apk/` handoff for beta
verification. Its manifest is
[`evidence/lw-m6-08/SHA256SUMS.candidate`](evidence/lw-m6-08/SHA256SUMS.candidate).
The older artifacts are preserved, but their previous test reports do not prove
this candidate ready.

## Corrections and evidence

- Version codes now derive from the pinned UTC build date. The old implementation
  used the current hour, so two builds within one hour could pass reproducibility
  while later builds changed. Compiled-class regression tests fail against the old
  plugin and pass against the new one. Both normal and repro builds now also pin
  the Glean timestamp consistently.
- Two independent R8-on rebuilds completed in 1,426 seconds. The script exits 0,
  all four APKs match the normal candidate byte for byte, and its one-byte
  negative control is detected. [Logs and comparison](evidence/lw-m6-08/repro/README.md)
  retain the same-machine APK assembly scope; Gecko/AAR and cross-machine
  reproducibility remain unverified.
- The full patched-source Fenix suite produced 598 classes / 5,426 tests;
  `board.py --check-fenix-tests` exits 0: 93 failures = 90 environmental + 3
  known-real + 0 unexpected. Seven explicitly ignored tests are unchanged. XML,
  source hashes, and APK linkage are archived in the
  [candidate audit](evidence/lw-m7-06/beta-audit-2026-09-08/fenix-README.md).
- Signing helpers enforce complete manifests and signature checks. The verifier
  detects actual v1 signature entries, requires the published key and v2+v3,
  and optionally compares every returned APK payload with the exact unsigned
  candidate. The 29 real-signature integration tests pass.
- The local issue form now uses GitHub's required YAML schema and includes a
  closed-beta source and RAM field. Following user approval, both form files were
  published to default `main` at `c65d2e4` and all eleven labels were created.
  [Publication evidence](evidence/lw-m6-08/github-publication.md) verifies remote
  bytes, settings and GitHub’s rendered form preview. Authenticated submission
  validation remains an unperformed manual check.
- Scope, patch order, patch application, configuration split, pref policy and
  hardening checks pass. There are 90 board tasks and 86 listed patches:
  24 common, 26 Android and 36 desktop. `ubo-preinstall.patch` remains explicitly
  parked; no patch was dropped to make the build pass.

The [final runtime audit](evidence/lw-m7-06/beta-audit-2026-09-08/final-candidate/README.md)
passes the baseline 7/7, search, branding/UI, suggestion toggle/traffic,
update-privacy, release about:config edit/restart, no-GMS and no-Adjust checks.
The 23 harness regressions and deliberately wrong baseline controls pass.
The regenerated 58-row pref baseline is unchanged; the pref audit reports zero
violations and the effective seven-entry Remote Settings allowlist matches.

The final first-run capture through Quad9 records 11 outbound transport events,
including three complete security-host SNI names. The earlier 14-event capture is
a separate run. IPv4/IPv6 address refresh and payload counting fix the prior
capture gaps. These are transport observations; they do not decrypt requests or
provide complete app-UID attribution. A local control measured QEMU pcap timestamps
about one hour behind the agreeing host/guest clocks; byte offsets and command
records bind each captured window to its run. Both strict zero-Remote-Settings
checks remain red under the approved E12 decision.

## External entry work

**E7 remains open:** no returned signed APKs are in `~/redoubt-signed/`.
`~/redoubt-release.p12` remains on the build host, owned by the same user running
the live Actions runner. The holder must sign offline elsewhere and remove that
build-host copy after confirming the offline copy. No release key was used by
this audit. See the [signing handoff](evidence/lw-m6-01/RELEASE-HANDOFF.md).

**E10 is met:** the corrected form and private security contact are on default
`main`; all eleven approved labels are live, and GitHub’s public preview renders
the parsed form with its controls and required markers. Authenticated submission
validation is still unperformed. No further publication approval is needed.

The dated single-holder, parity-wording and solo-triage decisions remain as
recorded on 2026-09-06. The approved seven-entry Remote Settings security allowlist
also remains in force. Completing preparation does not complete the 14-day beta,
its device coverage, second-build upgrade test, or final public-release GO/NO-GO.
