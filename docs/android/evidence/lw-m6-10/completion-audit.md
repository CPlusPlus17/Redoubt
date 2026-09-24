# Beta preparation completion audit — 2026-09-08

**Ready for the closed beta. All twelve entry criteria are satisfied, including
the owner's dated exception for E7.** The user goal's attachment defines readiness
against the entry table in [BETA.md](../../BETA.md). That full scope is retained;
the later 14-day beta execution and public-release decision are not claimed here.

The owner explicitly approved using the existing four APKs despite signing on
Fedora before the VM migration and retaining the key on Fedora outside the VM.
The [decision](custody-decision.md) records that as a beta-only exception, not as
historical offline signing. The separate [owner confirmation](owner-confirmation.json)
states that no release-key APK has ever been distributed.

## Requirement-by-requirement evidence

| Entry | Conclusion and authoritative evidence |
|---|---|
| E1 — complete compiled candidate | Normal `make android-apk TARGETS=android` completed in 505 seconds with R8 enabled and the recorded native AAR inputs. All 248 patched source paths and pinned build inputs remain unchanged. [Build log](../lw-m6-08/candidate-build.log), [timings](../lw-m6-08/candidate-build-times.txt), [source comparison](../lw-m6-08/patch-source-comparison.json), [inputs](../lw-m6-08/candidate-inputs.json). |
| E2 — real native ABIs | Actual current APK hashes and ELF identities match the candidate inspection; ARM32, ARM64 and x86_64 engines are present, with all three in the universal APK. [Native inspection](../lw-m6-08/candidate-native-abis.json), [runtime artifact binding](../lw-m7-06/beta-audit-2026-09-08/final-candidate/artifact-inspection.json). |
| E3 — runtime and feature gates | The exact candidate payload passed the 7/7 baseline, search, branding/strings, suggestions OFF→ON→OFF, release about:config edit/restart, compiled-out update privacy, no-GMS and no-Adjust checks. Frozen harness sources are unchanged. Both strict zero-Remote-Settings checks retain their failures under the approved E12 decision. [Named primary results and limits](../lw-m7-06/beta-audit-2026-09-08/final-candidate/README.md), [unchanged harness](unchanged-candidate-verifiers.txt). |
| E4 — generated pref audit | Generator and reviewed baseline diff exited 0; all 58 rows are byte-identical. Runtime audit has zero violations and zero other differences. It covers 20 of 137 must-lock keys; the remaining generated-policy coverage is recorded separately. [Generation](../lw-m7-06/beta-audit-2026-09-08/final-candidate/pref-baseline-regeneration.json), [audit output](../lw-m7-06/beta-audit-2026-09-08/final-candidate/pref-audit-final.out). |
| E5 — full Fenix gate | Archived JUnit XML independently confirms 598 classes, 5,426 tests, 93 allowed failures and 7 skipped tests. The subtraction gate reports 90 environmental + 3 known-real + 0 unexpected failures. All 13,142 source hashes and the retained Fenix evidence hashes are unchanged. [Gate](../lw-m7-06/beta-audit-2026-09-08/fenix-gate.txt), [candidate binding](../lw-m7-06/beta-audit-2026-09-08/fenix-final-candidate.json). |
| E6 — reproducible APK assembly | Two independent R8 builds match all four normal-candidate APKs byte for byte; wrapper exit 0 and the corruption negative control are retained. This establishes same-machine APK assembly with the recorded native inputs, not independent Gecko or cross-machine reproducibility. [Run and raw outputs](../lw-m6-08/repro/README.md), [comparison](../lw-m6-08/repro/candidate-comparison.json). |
| E7 — signed candidate and accepted custody | Fresh checks pass published fingerprint, v2+v3/no-v1 and exact unsigned-candidate payloads for all four files. Every file matches its owner-approved hash. Current host/guest isolation passes; old host runner is masked and unregistered. The owner explicitly accepts the recorded earlier signing and physical-host key retention for these artifacts. [Final signatures](final-signature-verification.txt), [manifest](final-signed-checksums.txt), [exact approval binding](final-candidate-binding.json), [live isolation](final-ci-isolation.txt), [decision](custody-decision.md). |
| E8 — holder decision | Manuel Gysin's dated 2026-09-06 single-holder decision remains in SIGNING.md. This is the permitted alternative in E8; it does not claim a second holder exists. [Decision](../../SIGNING.md). |
| E9 — parity approval | The exact parity wording and Manuel's dated 2026-09-06 approval remain recorded. Later public-page publication is not claimed. [Parity](../../PARITY.md). |
| E10 — live reporting and triage | Named solo triage arrangement remains dated. Current default `main` is still `c65d2e448124b570bf6acabcb3f99fd09a014300`; both approved form files and all 11 added labels match. GitHub's validated parsed preview is bound to that current blob. Authenticated submission testing remains the separate manual task. [Publication evidence](../lw-m6-08/github-publication.md), [triage owner](../../TRIAGE.md). |
| E11 — honest DNS capture | The candidate capture used Quad9 9.9.9.9; positive DNS controls resolve Mozilla names to public addresses. Original capture windows and raw packets remain available; the final result records 11 transport events and three complete security SNI names. This is not decrypted request or complete UID attribution. [Capture](../lw-m7-06/beta-audit-2026-09-08/final-candidate/first-run-capture-final.json), [DNS control](../lw-m7-06/beta-audit-2026-09-08/final-candidate/honest-dns-resolution.json). |
| E12 — Android Remote Settings decision | The dated seven-collection decision matches the current Android config and effective candidate runtime prefs; eleven packaged-only FromDump entries remain unchanged. The two strict zero-traffic checks are still red. [Effective decision](../lw-m7-06/beta-audit-2026-09-08/final-candidate/effective-remote-settings.json), [owner policy](../lw-m4-08/RESULT.md). |

## Deliverables and remaining scope

The accepted signed APKs and `SHA256SUMS.signed` are in
`/home/mgysin/redoubt-signed/`. Their exact four hashes are in the approved custody
decision and final binding JSON. The original unsigned candidate and signing
handoff remain intact; no private key or passphrase was accessed by the agent.

The requested CI migration is deployed, with fresh runner credentials and the
real [Actions preflight](https://github.com/CPlusPlus17/Redoubt/actions/runs/34257944277)
passing on guest runner 22. The [runbook](../../CI-VM.md) records operations and
limits. A full Android build inside this VM has not been demonstrated and is not
used as evidence for the candidate's already completed build.

Owner input is complete for preparation. Device recruitment/assignment, private
distribution, the 14-day test window, second-build upgrade testing and final
public-release GO/NO-GO remain their respective later beta activities.
