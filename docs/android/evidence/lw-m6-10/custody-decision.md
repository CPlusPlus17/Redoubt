# Approved beta custody decision — 2026-09-08

Approved by **Manuel Gysin** on **2026-09-08**. The owner answered **"yes"**
to approving these four existing signed APKs for this beta, accepting that
signing preceded the CI migration and the key remains on Fedora outside the VM.
This decision closes E7 by a candidate-specific owner exception. It does not
publish the APKs or change future/public-release requirements.

## Approved scope

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
This decision does not authorize the agent to read or operate the release key.
Future candidates retain the documented offline-signing procedure unless the
owner separately changes it. On 2026-09-08 the owner confirmed that no APK signed
with this release key has ever been distributed ("no never distributed"). There
is therefore no previously distributed release-key version code to supersede.
The distribution confirmation and the subsequent custody approval are separate
owner statements, recorded in [owner-confirmation.json](owner-confirmation.json).

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

Evidence: [final candidate verification](final-signature-verification.txt),
[original intake](../lw-m6-08/returned-signing-intake.json), and
[deployed VM acceptance](../lw-m6-09/acceptance-after-cutover.txt).

The historical signing circumstances remain unchanged. No earlier offline
signing or absence of earlier key access is claimed. The exception applies only
to the four hashes above, while the verified CI isolation remains in place.

Decision: **approved**. Decision date: **2026-09-08**.
