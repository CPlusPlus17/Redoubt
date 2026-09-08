# Beta custody reconciliation — 2026-09-08

The preceding goal turn made progress by deploying and validating QEMU CI.
This follow-up re-read the goal attachment and current entry requirements,
rechecked returned APKs and live runner state, corrected stale custody claims,
and prepared a concrete owner decision. **Beta entry remains 11/12; E7 is open.**

## Fresh evidence

- [Returned-candidate verification](returned-candidate-verification.txt): all four
  current signed APKs pass v2, v3, no-v1, the published fingerprint and exact ZIP
  payload comparison against the final unsigned candidate.
- [Signed checksums](signed-checksums.txt): the complete four-file manifest passes.
- [Unchanged verification inputs](unchanged-candidate-verifiers.txt): frozen build,
  signing and runtime scripts, patch registration, expected prefs and Android
  configuration retain their audited hashes. No browser implementation changed
  during the migration or this follow-up.
- [Live runner state](runner-state.json), [host service state](host-runner-state.txt):
  only guest runner 22 is online; old host runner service is masked, inactive,
  PID 0. The [deployed isolation checks](../lw-m6-09/acceptance-after-cutover.txt)
  remain the actual filesystem/network acceptance evidence.
- [Known key-path metadata](key-path-metadata.txt): the Fedora keystore path
  still exists. This used `stat` only; no private-key content was accessed.

## Entry review

E1/E2 retain the candidate build and ABI evidence: the recorded normal build
completed in 505 seconds with native AAR reuse, and all 248 files touched by the
50 applied common/Android patches matched the compiled source. E3/E4 retain the
seven passing runtime baseline checks, named feature probes and zero-violation
pref audit with the byte-identical 58-row generated baseline. E5 retains the full
598-class/5,426-test Fenix gate: 93 allowed failures, zero unexpected. E6 retains
all four APKs matching both independent reproduction builds. Current candidate
hashes and unchanged verifier inputs bind those existing results; these tests
were not unnecessarily rerun for documentation and VM changes.

An independent read-only review confirmed E8 and E9's dated owner decisions, E10's
current default branch `c65d2e448124b570bf6acabcb3f99fd09a014300`, exact approved
issue-form files and all 11 labels. The parsed GitHub preview is tied to the same
published blob; authenticated submission remains a separate manual check.

E11 retains the honest-DNS capture and its measured transport-only scope. E12's
effective seven-entry allowlist still matches the Android configuration hash
`de7112285da87907f2b9674a5ffa90d731bb16148f7cbaad09bbea8b525a6c98` and runtime
prefs hash `f45839ace126673d46dd67f21f4ab12d71cfff8f73d059734646d13ee4b0a521`.
Both strict zero-traffic checks remain red under that recorded decision.

The actual sources for each retained result are linked from
[BETA.md](../../BETA.md), [candidate audit](../lw-m6-08/beta-readiness.md), and
[runtime audit](../lw-m7-06/beta-audit-2026-09-08/final-candidate/README.md).
The VM's workflow preflight is not used to claim a full VM build.

## Required owner input

The [candidate-specific custody proposal](proposed-custody-decision.md) is
**unapproved**. It explicitly covers pre-migration signing and continued key
storage on the physical Fedora host for these four beta artifacts. It does not
claim historical offline signing or change future/public-release requirements.
The owner may instead follow the existing offline signing and key-custody rules.

On 2026-09-08 the owner answered the distribution question: **"no never
distributed"**. The [confirmation](owner-confirmation.json) establishes that no
release-key APK has been distributed, so earlier higher debug/unsigned rehearsal
codes do not block this first beta. This was reported by the owner, not inferred
from local files.

The owner asked what else is needed; the custody exception remains unapproved.
No approval has been assumed. This is not a beta launch or a public-release
GO/NO-GO decision.
