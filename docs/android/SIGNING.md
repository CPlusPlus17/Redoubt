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

> **2026-10-05, Google Play (LW-M6-12).** The owner decided to upload this key to
> Play App Signing ("Google holds a copy of the app signing key" below). Once that
> upload has happened, Google holds a second copy. That copy is a **custodian's
> copy, not a second holder**. Google signs Play's APKs with it, but it will not hand
> it back for signing GitHub or F-Droid APKs, so it does not change the loss case
> above for those channels. It does change the compromise case.

The LW-M6-01 acceptance criterion "at least two holders" is therefore **not met,
and is not going to be met before launch**. It is an accepted risk of a solo
project. Revisit it when there is a second maintainer, or when an offline copy in
a third location becomes practical — that option is still open and still reduces
the loss risk, and taking it later does not require re-deciding this.

This decision says nothing about custody rule 3 below. The former host runner's
key access was removed by the 2026-09-08 QEMU migration; the signing history and
the rule's requirement to move the key off the physical build host remain separate.

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

   > **Historical violation, observed before the QEMU migration; not a file-mode issue.**
   > Observed 2026-09-06 on the build host: the keystore is at
   > `~/redoubt-release.p12`, and the GitHub Actions runner
   > (`~/actions-runner`, agent `redoubt-fedora`, label `librewolf-android`)
   > ran **as the same user that owns it**. Any job that reached that runner could
   > read the key — a `chmod 600` changed nothing about that, and would only make
   > it look addressed. `/home` being `0700` with one account means the exposure
   > is to *workflows*, not to other local users.
   >
   The original rule requires moving the key off this physical host, which is a
   maintainer action and has not been performed by this audit. No additional
   external-contributor workflow trigger has been enabled. The dated exception
   below applies only to the four accepted 2026-09-08 beta APKs; the original
   rule remains the default for future candidates and public releases.

### Verified update: CI moved to QEMU on 2026-09-08

At the owner's request, the Fedora host runner `redoubt-fedora` (ID 2) was
unregistered and its service stopped, disabled and masked. GitHub now reports
only `redoubt-ci-qemu` (ID 22). The real Android release preflight passed on
that guest. See the [migration evidence](evidence/lw-m6-09/README.md).

The guest has fresh runner credentials and no host directory shares. QEMU's
mount namespace has no `/home`, its IP network namespace is separate, and guest
checks prove the host home and known keystore path are absent. Guest user
`runner` has no sudo grant; new connections to a positively tested host-network
listener are administratively rejected. The administration key is outside
QEMU's namespace. These checks close the former runner's direct file access;
they do not establish physical separation or erase earlier access.

The four returned beta APKs were signed on Fedora before this migration,
according to the owner. Their signatures and exact candidate payloads verify,
but offline/off-runner signing was not established. The existing key was not
read, moved, copied or used by the migration. E7 is closed for this candidate by
the owner's separate, explicit decision below; the single-holder decision alone
does not supply that exception.

### Decision: accept the 2026-09-08 beta candidate with the QEMU boundary

**Approved 2026-09-08 by Manuel Gysin.** The owner answered **"yes"** to using
the four existing signed APKs for this beta while accepting their pre-migration
Fedora signing and retention of the key on Fedora outside the VM. The
[decision and exact artifact hashes](evidence/lw-m6-10/custody-decision.md)
are normative for this exception. The
[owner confirmation](evidence/lw-m6-10/owner-confirmation.json) also records
that no release-key APK has ever been distributed.

This accepts the earlier custody risk and the present shared physical host for
these four beta artifacts only. It does not establish historical offline signing,
erase the former runner's access, authorize the agent to operate the key, or
change the default signing procedure for later candidates/public releases.
Cryptographic, exact-payload and current CI-isolation checks remain required and
have passed. This is a dated custody exception, not an assertion that the original
offline/physical-separation procedure was followed.

### Decision: stable-release custody, both keys stay on the Fedora host (2026-10-04)

    DECIDED       2026-10-04
    DECIDED BY    Manuel Gysin (owner)
    SCOPE         the first stable release, Redoubt 157.0-2, and later releases
                  until the owner decides otherwise
    CHOICE        the APK release key (~/redoubt-release.p12) and the update-signing
                  key (~/redoubt-update-key/) both stay on the Fedora host (box A);
                  offline backups of both exist and the restore test was done
                  (owner-reported); builds run in CI on box B; the owner signs on
                  box A

This is a **standing owner decision for the stable release**, in the place of the
candidate-by-candidate exceptions recorded for Betas 1-5 (above, and
`evidence/lw-m7-01/release-157.0/beta*/custody-decision.md`). It is **explicitly
not offline signing**: settled rule 3 ("the key does not live on the build
machine") and the release procedure below describe an offline holder machine,
and that is not what happens. What is true instead:

- **Box B builds, box A signs.** The unsigned APKs come from
  `.github/workflows/android-release.yaml` on box B's VM (`CI-VM.md`, "Box B"),
  which has no copy of, path to or credential for either key. Box A's own runner
  VM (`redoubt-ci-qemu`) has no host home directory (the 2026-09-08 QEMU
  boundary above). The keys sit on the Fedora host itself, outside both VMs.
- **The owner signs, by hand.** `sign.sh` and `sign-update-manifest.sh` run in the
  owner's own terminal on box A, with the passphrases typed there. The agent does
  not read, copy or operate either key, and verifies only the results (published
  fingerprint, v2+v3/no v1, payload identical to the unsigned artifact, document
  signature against `assets/update-check.android.pubkey`).
- **Backups and restore are owner-reported**, for both keys, on 2026-10-04. The
  agent has not seen them; this file records the owner's statement, not a
  measurement. The APK key's 2026-08-23 table above (two copies, restore tested)
  still describes that key's older copies.
- **Single holder, unchanged.** The 2026-09-06 decision stands; backups reduce the
  loss risk, not the compromise risk, and do not add a holder. For the update key
  the owner's choice is the same single holder (custody rule 2 below: two
  copies, restore-tested, one holder).

The risk accepted is the one rule 3 exists for: a compromise of the Fedora host
reaches both keys at once. Moving the keys to an offline machine remains open and
does not require re-deciding anything else.

## Release procedure

> **For the stable release (2026-10-04 decision above):** step 1 runs on box B;
> steps 2-5 run on the Fedora host (box A), in the owner's terminal, not on an
> offline machine. The steps and their checks are otherwise unchanged. The
> GitHub-release and update-document steps are in `DISTRIBUTION.md`, "Stable
> release".

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
   PUBLISHABLE. The unsigned beta candidate also needs the offline signing step;
   its build and test evidence is linked from `BETA.md`.

   **The checker has been checked**, because one that has only ever said no is
   a habit rather than a test:

       ./scripts/android-verify-signature.sh --self-test <any apk>

   That signs a throwaway copy with a key generated on the spot and asserts both
   halves — that a correctly signed APK is detected as v2 *and* v3, and that the
   same APK is still rejected because the key is not the published one. The
   second half is the one a release process cannot survive without. It passed on
   2026-09-06, which also makes the `apksigner sign` invocation above a verified
   command rather than an aspirational one.

   The underlying command, if you want to read the raw output:

       apksigner verify --verbose --print-certs fenix-<abi>-release-signed.apk
       # expect: Verified using v2 scheme (APK Signature Scheme v2): true
       #         Verified using v3 scheme (APK Signature Scheme v3): true
       #         Signer #1 certificate SHA-256 digest: 6414eb33...

   Debug and throwaway-key rehearsal APKs are not release artifacts; do not hand
   them to testers. The candidate handoff contains unsigned APKs. After signing,
   use `--unsigned-dir <candidate apk directory>` on the build host to verify
   that the returned APK payloads match that exact candidate as well as its
   published signing identity. See `evidence/lw-m6-01/RELEASE-HANDOFF.md`.
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

## Google holds a copy of the app signing key (Google Play, LW-M6-12)

    DECIDED       2026-10-05
    DECIDED BY    Manuel Gysin (owner)
    CHOICE        publish on Google Play with THIS key uploaded to Play App Signing
                  (PEPK, "use existing app signing key"), so that the fingerprint
                  above is the same on every channel; Google holds a copy
    STATE         decided, NOT YET DONE -- no Play account exists and nothing has
                  been uploaded (2026-10-05). Fill in the date of the PEPK upload
                  here when it happens:  uploaded: ____-__-__
    RUNBOOK       docs/android/PLAY.md section 4, steps 3-4

This reverses LW-M6-04's "the Play Store is out of scope -- its signing model
conflicts with LW-M6-01". The conflict is accepted, not resolved. Once the
upload has happened, the following is true and must be said that way:

- **Google can sign an update for `org.redoubtbrowser` that every install
  accepts**, including the installs that came from GitHub Releases, Obtainium or the
  F-Droid repository and never touched Play. Android checks the key, not the channel.
  Such an update still has to reach the device: through Play, which can update any
  install it is allowed to update, or as an APK handed to someone. Once there, the
  device does not ask where it came from, only who signed it.
- **The trust root is no longer one person.** It is the owner **and Google**. Every
  sentence that says "one person holds the signing key" (README "Honest limits",
  `site/privacy.html` "A different signing identity") becomes false on the day of the
  upload. The corrected wording is prepared outside the repo and goes in with the
  Play launch (PLAY.md section 9), not before.
- **The compromise surface grows.** A Google-side compromise, a legal order addressed
  to Google, or a takeover of the Play Console account combined with an upload-key
  reset can all produce a validly signed update. The Play Console account therefore
  needs 2-step verification, and its upload-key reset is a security event (PLAY.md,
  step 4).
- **What Google gets is the encrypted export.** PEPK encrypts the private key to
  Google's public key on box A, and only Google can decrypt the zip. The keystore
  passphrase is not sent. The owner runs PEPK. No agent does, and the encrypted zip is
  deleted after the upload.
- **The upload key is separate** (`~/redoubt-play-upload.p12`, owner-held). This key
  is used once, for the PEPK export, and never signs an upload. `sign-aab.sh` refuses
  it as the upload signer. A lost upload key is reset by Google. A lost app signing
  key is still the end of the identity for every channel that is not Play.
- **Key upgrades on Play.** Play offers a "key upgrade", and from Android 17 a
  quantum-ready hybrid signing upgrade, both with keys that **Google generates**.
  Accepting either makes Play installs on newer Android verify against a key the
  other channels do not have. **Do not accept them**: PLAY.md step 3 says the same.
  The v3 rotation described under "Rotation, and its limits" still works only with
  this key, so a rotation on Play and on the other channels would have to be one
  joint act.
- **Losing access to Play does not return the key.** Unpublishing the app or losing
  the account leaves Google's copy where it is.

The channels stay interchangeable: a Play install and a GitHub or F-Droid install of
a later build update each other in place (PLAY.md section 3, "versionCode, and
moving between channels").

## The update-signing key (LW-M6-06)

Everything above is about the **APK release key**. The in-app update check
(`DISTRIBUTION.md`) needs a second, separate key: the one that signs
`update/android/latest.json`. This section is its custody record.

    purpose                signs the update-check document (latest.json.sig)
    algorithm              ECDSA P-256 (prime256v1), signatures SHA256withECDSA
    private key file       redoubt-update-signing.pem  (PKCS#8, passphrase-encrypted)
    public key, committed  assets/update-check.android.pubkey
                           (base64 DER SubjectPublicKeyInfo, one line)
    generated              2026-10-04, by the owner (Manuel Gysin), on the Fedora host
    SHA-256 of public DER  ecba7d19ada187d18cb6df84230ec90b40c6de7ed41e2f674f0958f715551d62
    copies / holders       1 holder (the owner); working copy in ~/redoubt-update-key/ on the
                           Fedora host (box A), where it stays for the stable release (owner
                           decision 2026-10-04, above); offline backup copies made (owner-
                           reported 2026-10-04; location not recorded here)
    restore tested         2026-10-04, owner-reported: restore test done from the backup.
                           Not witnessed by the agent, which does not read either key.

Record the public-key digest as plain lowercase hex (what `openssl dgst -sha256`
prints), not in the colon form or under the words "SHA-256 fingerprint":
`scripts/android-verify-signature.sh` reads the APK fingerprint out of this file
by exactly that label and format, and must keep finding only the APK one.

Until the public key is committed, `scripts/android-apk.sh --update-check`
refuses to build and every build has the check compiled out, exactly as Betas
1-5 did. Nothing in the repository enables the check before that.

### Why it is not the APK key

- **The verifier needs EC P-256.** The client verifies with `SHA256withECDSA`,
  which every supported Android release has (Ed25519 needs API 33). The APK key is
  an RSA 4096 PKCS12 keystore used through `apksigner`; reusing it would mean a
  different client algorithm and a second tool path to the most valuable key.
- **Different blast radius.** The APK key *is* the app's identity: losing it ends
  `org.redoubtbrowser`. The update key only vouches for a pointer: whoever holds
  it can make opted-in installs show "a newer version is available" with an https
  link of their choosing, but cannot make Android install anything (an APK still
  has to carry the APK key's signature to update the app). Losing it is
  recoverable with a client release. Separate keys keep the cheap risk from
  touching the expensive one.
- **Different cadence.** The update document may be re-signed more often than APKs
  are (a withdrawn or corrected announcement). Every use of the APK key is a
  custody event; this keeps those to APK releases.
- **Separate tools, separate bundle.** `evidence/lw-m6-01/sign.sh` (the APK signer)
  is unchanged and still requires exactly its four tools; the document is signed by
  `scripts/sign-update-manifest.sh`, staged in its own `update/` directory of the
  bundle (`DISTRIBUTION.md`, "Publishing a release with the check").

### One-time generation (owner, on the key machine)

Not on the build host (rule 3 above applies to this key too), not in CI, and never
inside the repository checkout (`.gitignore` blocks `*.pem`, but do not rely on it).

    # OpenSSL 3 (Fedora). Prompts for a new passphrase.
    openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 \
        -pkeyopt ec_param_enc:named_curve -aes-256-cbc -out redoubt-update-signing.pem

    # macOS (LibreSSL) equivalent:
    #   openssl ecparam -name prime256v1 -genkey -noout \
    #     | openssl pkcs8 -topk8 -v2 aes-256-cbc -out redoubt-update-signing.pem

    # The public half, in the form the build embeds, and its fingerprint:
    openssl pkey -in redoubt-update-signing.pem -pubout -outform DER | openssl base64 -A \
        > update-check.android.pubkey
    openssl pkey -in redoubt-update-signing.pem -pubout -outform DER | openssl dgst -sha256

    # Prove key + passphrase + public file belong together before anything ships
    # (any small JSON with those two fields will do; the script refuses on mismatch):
    printf '{"latest_version": "test", "download_url": "https://example.org/"}\n' > t.json
    ./sign-update-manifest.sh redoubt-update-signing.pem t.json update-check.android.pubkey
    rm t.json t.json.sig

Then: make the offline backup copy and repeat the last step from it (that is the
restore test), and commit **only** `update-check.android.pubkey` as
`assets/update-check.android.pubkey`, with its fingerprint and the custody facts
filled into the table above. The public key and its fingerprint are public by
design, like the APK fingerprint.

### Custody rules

The APK key's settled rules 1-3 apply unchanged: never in CI, never in this
repository, not on the build host. In addition:

1. **Passphrase-encrypted at rest**, passphrase held separately from the file.
   `sign-update-manifest.sh` never sees either: openssl reads the file and asks
   for the passphrase itself.
2. **At least two copies, restore-tested**, recorded in the table above. Two
   machines of one person are still one holder; say so if that is the case, as
   the APK key section does. (Whether the 2026-09-06 single-holder decision
   extends to this key is the owner's call; it is not assumed here.)
3. **Signs only `latest.json` documents produced by `scripts/update-manifest.py`**
   for a release that is published or about to be. It signs nothing else, and is
   never used as a TLS, SSH or code-signing key.
4. **Re-confirm at each release**, with the APK key.

### If it is compromised

Someone else can make opted-in installs announce an arbitrary https link. They
cannot push an APK (Android enforces the APK key), so the realistic attack is a
lure to a malicious download.

1. Delete `site/update/android/latest.json` and `.sig` and redeploy: a 404 is "no
   update", so no install shows anything further.
2. Announce it (release notes, site, `SECURITY.md` channel): installs that saw a
   prompt since the compromise should not have followed it.
3. Generate a new key, commit its public half, and ship a client release built with
   it. Installs on the old client stay silent until users update by other means;
   the announcement must say so.

### If it is lost

Nobody can sign a document the shipped clients accept. They fall silent, which is
safe but means opted-in users stop hearing about updates. Generate a new key, ship
a client with it, and tell users on the release page and the site that the in-app
check needs one manual update to resume. There is no lineage mechanism: a client
embeds exactly one key, so rotation is always "new key in the next client".
