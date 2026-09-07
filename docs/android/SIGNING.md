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

State as of 2026-08-23, reported by the owner.

    copies                 2 — the build machine and the owner's Mac
    holders (people)       1 — see "The single-holder gap" below
    restore tested         2026-08-23. The Mac copy was opened with keytool and
                           printed the fingerprint published above, so both the
                           file and the passphrase are known good, not assumed.
    passphrase custody     owner-held, separate from the keystore file
    review cadence         re-confirm at each release

### The single-holder gap

The acceptance criterion for LW-M6-01 says "at least two holders". Redoubt has
one person, so it is **not met**, and this file records that rather than
counting two machines as two holders. They are not: one person's laptop and one
person's desktop share a threat model, sit in one building, and are lost to the
same fire, theft or compromise.

What this actually means, stated plainly: if the owner loses access to both
machines and the passphrase, Redoubt ends under `org.redoubtbrowser`. There is
no co-holder to recover from and no authority to appeal to. That is an accepted
risk of a solo project, not an oversight, and it is written here so that a
future reader — or the owner in two years — does not mistake "two copies" for
"two holders".

Closing it needs one of:

  * a second person holding an encrypted copy, with the passphrase conveyed
    separately, or
  * an offline copy in a third location the owner controls (safe deposit,
    another address) — which reduces the loss risk without reducing the
    compromise risk, and still leaves one holder, or
  * an explicit decision to ship single-holder, recorded here with a date.

The one thing not to do is leave this section reading as though the criterion
were satisfied.

### Decision: Redoubt ships single-holder

    DECIDED       2026-09-06
    DECIDED BY    Manuel Gysin (owner)
    CHOICE        ship with one holder; do not block the release on finding a second

Recorded here because this section offered exactly three ways out and one of them
was "an explicit decision to ship single-holder, recorded here with a date". This
is that decision, not an oversight and not a deferral.

What it means, in the words this file already uses: **if the owner loses access
to both machines and the passphrase, Redoubt ends under `org.redoubtbrowser`.**
There is no co-holder to recover from, no authority to appeal to, and no
key-recovery mechanism outside Play App Signing, which this project does not use.
Every installed user would have to uninstall and reinstall, losing their profile.

The LW-M6-01 acceptance criterion "at least two holders" is therefore **not met,
and is not going to be met before launch**. It is an accepted risk of a solo
project. Revisit it when there is a second maintainer, or when an offline copy in
a third location becomes practical — that option is still open and still reduces
the loss risk, and taking it later does not require re-deciding this.

This decision says nothing about custody rule 3 below, which is a separate and
still-open problem: the key is currently reachable by the CI runner.

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

   > **This rule is currently violated, and the violation is not the file mode.**
   > Observed 2026-09-06 on the build host: the keystore is at
   > `~/redoubt-release.p12`, and the GitHub Actions runner
   > (`~/actions-runner`, agent `redoubt-fedora`, label `librewolf-android`)
   > runs **as the same user that owns it**. Any job that reaches that runner can
   > read the key — a `chmod 600` changes nothing about that, and would only make
   > it look addressed. `/home` being `0700` with one account means the exposure
   > is to *workflows*, not to other local users.
   >
   > What actually closes it is moving the key off this host, which is a
   > maintainer action and deliberately not automated. Until then, treat every
   > build this machine produces as coming from a host that holds the release
   > key, and do not add a workflow trigger that a non-maintainer can fire.
   > `BETA.md` carries this as entry criterion E7.

## Release procedure

1. CI builds the release variant unsigned and publishes the APK plus
   `SHA256SUMS` as a workflow artifact.
2. A holder downloads that artifact on an offline-capable machine.
3. The holder verifies the artifact's sha256 against the CI-published sum.
4. The holder signs with `apksigner`, using the keystore and passphrase. Both
   scheme v2 and v3 are required: Accrescent (LW-M6-04) rejects v2-only, and v3
   is what carries a rotation lineage if one is ever needed. v1 is left off — it
   is redundant on every supported API level and doubles the signing surface.

       apksigner sign --ks redoubt-release.p12 --ks-type PKCS12 \
           --v1-signing-enabled false --v2-signing-enabled true --v3-signing-enabled true \
           --out fenix-<abi>-release-signed.apk fenix-<abi>-release-unsigned.apk

5. The holder verifies the signed APK reports the fingerprint above and both
   schemes. **Use the script, not your eyes** — the three ways this goes wrong
   are all silent, and one of them is a 64-character hex string:

       ./scripts/android-verify-signature.sh <apk> [<apk> ...]

   It reads the expected fingerprint out of this file (so there is only ever one
   copy of it), and fails on a v2-only APK, on a missing v3, on an unexpected
   v1, and on the wrong key. Run against a debug build it reports NOT
   PUBLISHABLE, which is what every APK this project has produced so far is.
   The underlying command, if you want to read the raw output:

       apksigner verify --verbose --print-certs fenix-<abi>-release-signed.apk
       # expect: Verified using v2 scheme (APK Signature Scheme v2): true
       #         Verified using v3 scheme (APK Signature Scheme v3): true
       #         Signer #1 certificate SHA-256 digest: 6414eb33...

   Every APK built on the build machine so far is signed `CN=Android Debug`,
   v2 only. None of them is a release artefact; do not hand one to a tester.
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
