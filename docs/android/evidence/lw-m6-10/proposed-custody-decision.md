# Proposed beta custody decision — NOT APPROVED

Owner decision requested from Manuel Gysin. No exception is in force, and E7
remains open. This proposal concerns only the four already-returned artifacts
below; it does not publish them or change public-release requirements.

## Exact proposed decision

> For this beta candidate only, I accept that I signed the APKs on Fedora before
> the host Actions runner was retired, and that offline signing was not
> established. I accept keeping the existing release key on the Fedora physical
> host while CI runs in the isolated QEMU guest. This is an explicit exception
> to E7's earlier signing circumstances and SIGNING.md rule 3's physical-host
> exclusion for this candidate. I accept the risk from the key's earlier
> readability by the host runner and the remaining trust in the physical host.
> The verified QEMU boundary is the mitigation; it is not proof that earlier
> signing was offline or that earlier key access never happened.

All other beta requirements remain in force, including exact candidate binding,
release fingerprint, v2+v3 with no v1, and the established single-holder decision.
This proposal does not authorize the agent to read or operate the release key.
Future candidates retain the documented offline-signing procedure unless the
owner separately changes it. On 2026-09-08 the owner confirmed that no APK signed
with this release key has ever been distributed ("no never distributed"). There
is therefore no previously distributed release-key version code to supersede.
This confirmation does not approve the custody exception.

## Candidate covered

Files are in `/home/mgysin/redoubt-signed/`, application ID `org.redoubtbrowser`,
version `153.0esr-1-default`, pinned build date `20260906190000`.

| APK | versionCode | SHA-256 |
|---|---:|---|
| `fenix-arm64-v8a-release.apk` | 2016183066 | `921e84b9cf0c2dbacce4ca2f733df3f8f0abdcc6859b38d3cd6df17e66092d19` |
| `fenix-armeabi-v7a-release.apk` | 2016183064 | `4ac4bd1a1e6bbef4011227769b4cc18d05744ebd1f7853e9e206cfa50afd6161` |
| `fenix-universal-release.apk` | 2016183071 | `65cc2cf32c70602586af6668b81fe97c63290609e0533debfef186a8f3a85468` |
| `fenix-x86_64-release.apk` | 2016183070 | `eb8319bc03f96e13ba274ba67f41502c6150a7985dba4e3a2bdeaebef07f14fd` |

The published signing fingerprint is
`64:14:EB:33:46:81:CF:6E:92:90:34:B5:6A:06:2D:2B:8D:A0:90:82:21:72:F7:A3:95:2C:85:FD:D1:28:3B:D0`.

Evidence: [fresh candidate verification](returned-candidate-verification.txt),
[original intake](../lw-m6-08/returned-signing-intake.json), and
[deployed VM acceptance](../lw-m6-09/acceptance-after-cutover.txt).

If the owner declines this exception, keep E7 open and use a holder-operated
offline signing machine outside the build host, together with removal of the
build-host key copy under the existing custody rule. Do not claim that repeating
signature verification resolves custody.

Decision: **pending**. Decision date: **not supplied**.
