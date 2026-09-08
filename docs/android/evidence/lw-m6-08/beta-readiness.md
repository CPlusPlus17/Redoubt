# Beta candidate audit — 2026-09-08

All twelve beta entry criteria are satisfied, including the owner's 2026-09-08
candidate-specific E7 custody exception.
The authoritative entry decision is [BETA.md](../../BETA.md). The earlier claim
that only release signing remained did not describe the actual candidate or
GitHub's live reporting state. This audit rebuilt and checked the candidate,
repaired the build and verification defects it exposed, and retained the original
artifacts and diagnostic results.

## Candidate and provenance

The current four unsigned APKs are in
`librewolf-android-apk-153.0esr-1-beta-20260908/apk/`, relative to the repository.
[SHA256SUMS.candidate](SHA256SUMS.candidate) identifies them. They use R8 and
`MOZ_BUILD_DATE=20260906190000`; version codes are 2016183064 (ARM32),
2016183066 (ARM64), 2016183070 (x86_64) and 2016183071 (universal).

- [candidate-build.log](candidate-build.log),
  [candidate-build-times.txt](candidate-build-times.txt) and compressed
  [full Gradle log](candidate-apk.log.gz): normal `make android-apk TARGETS=android`
  completed in 505 seconds, reusing the three native AAR inputs.
- [candidate-inputs.json](candidate-inputs.json): pinned source archive, native
  AAR hashes, image identity, configuration inputs and absent update-key/endpoint
  overrides.
- [patch-source-comparison.json](patch-source-comparison.json): all 248 paths
  touched by the 50 common/Android patches match the compiled source. The pinned
  archive was extracted and every patch reapplied for this comparison. The
  [recipe](check-built-patch-sources.py) and [patch application log](check-patchfail.log)
  are retained.
- [candidate-native-abis.json](candidate-native-abis.json): expected actual ELF
  architecture in every APK, with all three engines in the universal.

## Build and verification corrections

Fenix used the wall clock for Android version codes despite the pinned build date.
The normal APK builder also omitted Glean's timestamp pin, while the reproduction
script calculated its Glean property before parsing the supplied date. The new
patch and both scripts now derive these values from the same explicit UTC input.
The compiled old Config plugin failed 22 assertions; the patched compiled class
passes all five regression tests, including timezone and release-hour behavior.

[Two independent R8 builds](repro/README.md) pass and match every normal candidate
APK byte for byte. The comparator detects its deliberate one-byte corruption.
This establishes same-machine APK assembly reproducibility; the native Gecko
builds and cross-machine property remain unverified.

The full [Fenix suite evidence](../lw-m7-06/beta-audit-2026-09-08/fenix-README.md)
retains 598 classes / 5,426 cases, original JUnit XML and exact source linkage.
The required board gate exits 0: 93 failures = 90 environmental + 3 known-real
+ 0 unexpected. Seven ignored tests are unchanged; no allowlist was widened.

The [runtime candidate audit](../lw-m7-06/beta-audit-2026-09-08/final-candidate/)
uses the exact x86_64 payload signed with a disposable installation key. It
contains raw captures, complete pref dumps, baseline regeneration/diff and UI
results. Network and WebGL harness defects are corrected without changing the
browser's privacy configuration. E3 passes with the final about:config
edit/restart and search traffic controls; all 23 harness regression tests pass.
The strict
zero-Remote-Settings checks remain red under the recorded E12 decision.

## Signing and reporting handoffs

The [signing tools report](README.md), [29-test root run](signing-tests-root.out)
and [full four-APK signing rehearsal](full-bundle-rehearsal.txt) cover genuine
signatures and rejection controls. The verifier also binds returned signed ZIP
payloads to these exact unsigned APKs. No release key was used.

A 643,563,520-byte transfer archive is prepared at
`librewolf-android-apk-153.0esr-1-beta-20260908/redoubt-beta-20260908-offline-signing.tar`.
Its adjacent `.tar.sha256` and [transfer inventory](transfer-archive.json) record
SHA-256 `c4dfc7b186b3c740b4196bd1903dfbca24f0e5ddf7a5190be0b2b755b0a1251b`.
Every archived member was hashed and compared with its source. It contains only
the unsigned bundle and holder instructions. The
[holder handoff](../lw-m6-01/RELEASE-HANDOFF.md) requires confirmation that no
higher-version-code APK was previously distributed under the release key.

**E7 is satisfied with the approved beta-only custody exception.** The four signed APKs have been returned and copied to
`~/redoubt-signed/`; signature, published fingerprint and exact candidate payload
checks pass. The [intake record](returned-signing-intake.json) preserves their
signed hashes. The user confirms signing happened on Fedora before the
[completed QEMU migration](../lw-m6-09/README.md). The old host runner is now
unregistered and masked; its guest replacement has no host home or key path.
The owner explicitly accepted these four APKs and physical host key retention
with the verified QEMU boundary in the
[dated decision](../lw-m6-10/custody-decision.md). No earlier off-host signing
claim is made. The exception does not alter future/public-release requirements.
The owner also confirmed that no release-key APK has ever been distributed.

**E10 is met.** Following user approval, both form files are on default `main`
at `c65d2e4`, and all eleven labels have the approved definitions. The
[publication record](github-publication.md) verifies the remote state and GitHub’s
public rendered preview, including parsed controls and required markers.
Authenticated issue submission remains the separate, unperformed LW-M7-04 manual
check. Dated solo-triage, single-holder and parity wording decisions remain intact.

[Final local gates](final-local-gates.txt) pass: board ownership/scope, patch
order and scope lint, configuration split, generated pref policy, hardening
comparison and shell syntax.

No closed-beta tester results, second-build installs, public release, or final
GO/NO-GO are claimed by this preparation audit.
