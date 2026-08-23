# Signing key and custody

Owner: LW-M6-01. Read `IDENTITY.md` first — the applicationId and the signing
key are the two halves of Redoubt's Android identity, and both are one-way.

## The key

    applicationId          org.redoubtbrowser
    keystore format        PKCS12
    algorithm              RSA 4096, certificate self-signed SHA384withRSA
    generated              2026-08-23

    SHA-256 fingerprint
    64:14:EB:33:46:81:CF:6E:92:90:34:B5:6A:06:2D:2B:
    8D:A0:90:82:21:72:F7:A3:95:2C:85:FD:D1:28:3B:D0

**The fingerprint is public by design.** It is what a user checks to prove an
APK came from us, so it belongs on the download page, in the F-Droid repo
metadata, and in the Accrescent listing. Publishing it leaks nothing. The
keystore file and its passphrase are the secrets; the fingerprint is not.

Verify any APK against it with:

    apksigner verify --print-certs <apk> | grep -i 'SHA-256'

That command belongs on the download page next to every artefact
(`LW-M7-02` acceptance: "every channel lists its fingerprint and verification
command").

## Why this cannot be re-done

Losing this key is not recoverable. There is no reset, no appeal and no
authority to ask. Concretely:

- Android refuses an update signed by a different key. Every existing user
  must uninstall and reinstall, losing their profile.
- F-Droid and Accrescent will not accept a re-signed app under the same
  `applicationId`, and the `applicationId` cannot change either.
- Anyone who verified the old fingerprint has no way to distinguish a
  legitimate new key from an attacker's.

It is the same severity as losing the `applicationId`, which is why the
acceptance criteria demand at least two holders rather than a single backup.

## Custody

**TO BE COMPLETED BY THE OWNER — this section is the deliverable, not
decoration.** `LW-M6-01` is not done until every line below is filled in with a
real answer, and a placeholder left here is a worse outcome than an ugly truth.

    holders (>= 2)         TODO — who physically holds a copy
    storage medium         TODO — encrypted volume? hardware token? paper?
    locations              TODO — must be geographically separate; two copies
                                  in one building is one copy
    passphrase custody     TODO — stored SEPARATELY from the keystore. On the
                                  same medium it adds nothing.
    restore last tested    TODO — an untested backup is a belief, not a backup
    review cadence         TODO — when is holder access re-confirmed

### Rules that are already settled

1. **The key never touches CI.** `.github/workflows/android-release.yaml`
   contains no signing step and no release step, by construction. CI emits an
   unsigned APK plus sha256 sums and stops. Signing happens offline, by a
   holder, on a machine that is not the CI runner.
2. **The key never touches this repository.** `.gitignore` blocks `*.p12`,
   `*.jks`, `*.keystore`, `*.pem`, `*.pk8` and `keystore.properties`. Git
   history is not somewhere a private key can be deleted from.
3. **The key does not live on the build machine.** That host runs a
   self-hosted GitHub Actions runner for a public repository. Fork-PR workflows
   require approval from all external contributors, but the correct posture is
   that the key is not reachable there at all.

## Release procedure

1. CI builds the release variant unsigned and publishes the APK plus
   `SHA256SUMS` as a workflow artifact.
2. A holder downloads that artifact on an offline-capable machine.
3. The holder verifies the artifact's sha256 against the CI-published sum.
4. The holder signs with `apksigner`, using the keystore and passphrase.
5. The holder verifies the signed APK reports the fingerprint above.
6. The signed APK is published. CI never sees any of steps 2-6.

## If the key is compromised

Compromise means someone else can sign an APK that devices will accept as an
update. Treat it as a channel compromise — `SECURITY.md` covers the disclosure
path.

1. Announce it, prominently and immediately, before doing anything else. Users
   holding a device that will accept attacker updates need to know first.
2. Publish the last known-good artefact hashes so users can check what they have.
3. Rotate (below), understanding what rotation does not fix.
4. Post-mortem in the open: how it was held, how it leaked, what changed.

## If the key is lost

Distinct from compromise: nobody can sign, including us.

There is no procedure that preserves continuity. The app is discontinued under
`org.redoubtbrowser` and a new identity must be published, with existing users
told plainly that they must uninstall and reinstall and why. Say it in those
words; do not dress it up.

This is why the custody table above exists.

## Rotation, and its limits

Android supports key rotation through APK Signature Scheme v3
(`SigningCertificateLineage`), but it is narrower than it sounds:

- It requires the **old key** to sign the lineage. It is therefore useless for
  a lost key — it is a compromise-response tool, not insurance.
- F-Droid and Accrescent support for rotated keys is uneven. Confirm with both
  before relying on it.
- Devices below API 28 ignore lineage entirely and keep enforcing the original
  key.

Do not treat rotation as a reason to hold the key less carefully.
