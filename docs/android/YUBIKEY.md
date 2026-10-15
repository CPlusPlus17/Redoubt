# Moving the signing keys to a YubiKey

**Status: planned, not done.** Prepared 2026-10-14. Until the maintainer has run
the steps below and recorded the result in [`SIGNING.md`](SIGNING.md), the keys
are passphrase-protected files on the maintainer's workstation, as SIGNING.md
says.

This is the maintainer's runbook. Every step that touches a key, a passphrase, a
PIN or the YubiKey is run by the maintainer in their own terminal. No agent runs
these steps, sees a PIN or passphrase, or holds the YubiKey.

## Why

Today a compromise of the workstation reaches the key files, and AI coding agents
run on that workstation under the same user. "The agent does not read the keys"
is a rule, not a barrier. On a YubiKey:

- **the private keys cannot be copied off the device**, by anyone, including the
  maintainer. A stolen file and passphrase sign forever; a YubiKey key signs only
  where the YubiKey is plugged in;
- **signing needs the PIN**, asked once per signing session.

**No touch requirement (decided 2026-10-15).** The keys are imported with touch
policy `never`, so signing does not need someone at the machine. The cost: while
the YubiKey is plugged into the workstation, anything running there that also has
the PIN can sign, and the PIN is typed on that workstation. The PIN is the barrier
against a compromised workstation signing; a touch would add physical presence.
To add it later, re-import the key with `--touch-policy=always` (or `cached`, one
touch valid for 15 seconds), from the offline backup, because the policy is fixed
at import. Signing on a machine you sit at, with the YubiKey plugged in there,
makes a touch practical and takes the key off the agent workstation.

It does not undo the weeks the keys spent as files on a networked machine. Those
files were passphrase-encrypted, and the passphrases were typed, never stored.

## What moves where

| key | algorithm | today | YubiKey PIV slot |
|---|---|---|---|
| APK release key | RSA 4096 | `~/redoubt-release.p12` | `82` (Retired Key 1), PIN once, no touch |
| update-signing key | EC P-256 | `~/redoubt-update-key/redoubt-update-signing.pem` | `83` (Retired Key 2), PIN once, no touch |
| F-Droid index key | RSA 4096 | `~/redoubt-fdroid/keystore.p12` | phase 2, see below (`84`) |

**Import, don't generate.** Android accepts an update only when it is signed by
the same key as the installed app, so the existing keys move onto the YubiKey.
A new on-device key would need APK Signature Scheme v3 rotation, and Android 8.0
and 8.1 (which Redoubt supports) do not understand rotation, so the old key
would have to keep signing anyway.

**Why retired slots.** Slot `9c` checks the PIN for every signature, which Java's
PKCS#11 provider does not handle well. Slots `82`–`95` take the PIN policy given
at import.

**Hardware.** RSA 4096 import needs YubiKey 5 firmware 5.7 or later. The
maintainer's YubiKey reports firmware 5.8.0, and all of its PIV slots were empty
on 2026-10-14.

## 0. Before you start

1. **Restore-test the offline backups of all three keys** (open each with its
   passphrase, check the fingerprints in SIGNING.md). After step 6 they are the
   only way back if the YubiKey is lost.
2. `sudo systemctl enable --now pcscd.socket`
3. `yubico-piv-tool -a version` must print 5.7.0 or later.
4. Optional, for nicer status output: `sudo dnf install yubikey-manager` (`ykman piv info`).

## 1. Secure the PIV application

Skip what you have already changed. Factory defaults: PIN `123456`, PUK
`12345678`, management key `010203040506070801020304050607080102030405060708`.

    yubico-piv-tool -a change-pin                 # current PIN, then the new one (6-8 characters)
    yubico-piv-tool -a change-puk                 # current PUK, then the new one
    openssl rand -hex 32                          # a new random management key; write it down
    yubico-piv-tool -a set-mgm-key -m AES256 -k   # asks for the current and the new management key

Keep the PUK and the management key with the offline key backups, not on the
workstation.

## 2. Import the APK release key (slot 82)

    yubico-piv-tool -k -a import-key -s 82 -K PKCS12 -i ~/redoubt-release.p12 \
        --pin-policy=once --touch-policy=never
    yubico-piv-tool -k -a import-certificate -s 82 -K PKCS12 -i ~/redoubt-release.p12

Each asks for the management key and the keystore passphrase. Check the
certificate now on the YubiKey:

    yubico-piv-tool -a read-certificate -s 82 | openssl x509 -noout -fingerprint -sha256

It must print `64:14:EB:33:46:81:CF:6E:92:90:34:B5:6A:06:2D:2B:8D:A0:90:82:21:72:F7:A3:95:2C:85:FD:D1:28:3B:D0`.

## 3. Let Java find it

Create `~/.config/redoubt/yubikey-pkcs11.cfg`:

    name = YubiKey
    library = /usr/lib64/libykcs11.so.2

List the token's keystore aliases (asks for the PIN):

    keytool -list -keystore NONE -storetype PKCS11 \
        -providerClass sun.security.pkcs11.SunPKCS11 \
        -providerArg ~/.config/redoubt/yubikey-pkcs11.cfg

Note the alias of the slot-82 entry, probably `X.509 Certificate for Retired Key 1`.

## 4. Prove it: re-sign 158.0-2 and compare byte for byte

APK signing with RSA (PKCS#1 v1.5) is deterministic. The same key and the same
apksigner must reproduce the published 158.0-2 APKs exactly, so this proves both
the key and the token path before any real release depends on them. Run this
from the repository root:

    B=~/redoubt-artifacts/release-158.0-2/signing-bundle
    T=$(mktemp -d)
    cp "$B"/fenix-*-release-unsigned.apk "$B"/SHA256SUMS "$B"/apksigner.jar \
       "$B"/android-verify-signature.sh "$B"/SIGNING.md "$T"/
    cp docs/android/evidence/lw-m6-01/sign.sh "$T"/
    (cd "$T" && sha256sum apksigner.jar sign.sh android-verify-signature.sh SIGNING.md > SHA256SUMS.tools)
    cd "$T"
    REDOUBT_SIGN_PKCS11_CFG=~/.config/redoubt/yubikey-pkcs11.cfg \
    REDOUBT_SIGN_KEY_ALIAS='X.509 Certificate for Retired Key 1' ./sign.sh
    for abi in arm64-v8a armeabi-v7a universal x86_64; do
        cmp fenix-$abi-release.apk "$B"/fenix-$abi-release.apk && echo "$abi: identical"
    done

`sign.sh` asks for the PIN once per APK. All four lines must say `identical`.

## 5. Import the update-signing key (slot 83)

    yubico-piv-tool -k -a import-key -s 83 -K PEM \
        -i ~/redoubt-update-key/redoubt-update-signing.pem \
        --pin-policy=once --touch-policy=never
    yubico-piv-tool -a read-public-key -s 83 -o /tmp/redoubt-update-pub.pem
    yubico-piv-tool -a verify-pin -a selfsign-certificate -s 83 \
        -S '/CN=Redoubt update signing/' -i /tmp/redoubt-update-pub.pem -o /tmp/redoubt-update-cert.pem
    yubico-piv-tool -k -a import-certificate -s 83 -i /tmp/redoubt-update-cert.pem
    pkcs11-tool --module /usr/lib64/libykcs11.so.2 --login --list-objects --type privkey

The certificate only lets PKCS#11 list the key; the app pins the public key, not
a certificate. Note the hex `ID` of the "Retired Key 2" private key. Prove it
against the key the app pins (`assets/update-check.android.pubkey`), from the
repository root:

    T=$(mktemp -d); cp site/update/android/latest.json "$T"/
    scripts/sign-update-manifest.sh pkcs11:id=<ID> "$T"/latest.json

It must end with `Verified OK`. (ECDSA signatures differ every time, so this one
cannot be compared byte for byte; the check against the pinned key is the proof.)

## 6. Remove the key files from the workstation

Only after steps 4 and 5 pass and step 0's backups are confirmed:

    shred -u ~/redoubt-release.p12 ~/redoubt-update-key/redoubt-update-signing.pem
    find ~ \( -name '*.p12' -o -name '*.jks' -o -name '*signing*.pem' \) 2>/dev/null

The home file system is ext4, where `shred` overwrites the file, but an SSD can
keep old blocks. Treat the old files as having existed. The `find` must list no
release or update key. Also deal with any other working copy: the 2026-08-23
custody table in SIGNING.md lists one on the maintainer's Mac. Keep it only as an
offline backup.

Then update SIGNING.md: the custody block at the top, the date, the slots, and
"key files removed from the workstation". Update the README "Honest limits" line
to match.

## 7. Signing from then on

- APKs: in the signing bundle, run

      REDOUBT_SIGN_PKCS11_CFG=~/.config/redoubt/yubikey-pkcs11.cfg \
      REDOUBT_SIGN_KEY_ALIAS='X.509 Certificate for Retired Key 1' ./sign.sh

  (no keystore argument). The rest of the release procedure is unchanged.
- Update document: `./sign-update-manifest.sh pkcs11:id=<ID> latest.json`, with
  the module from `$REDOUBT_PKCS11_MODULE` (default `/usr/lib64/libykcs11.so.2`).

## Phase 2: the F-Droid index key

`scripts/fdroid-repo.sh` runs fdroidserver in a container and signs the index
with `keystore.p12`. To use slot `84`, the container needs the PC/SC socket
(`/run/pcscd/pcscd.comm`) and a PKCS#11 module, and `config.yml` needs
fdroidserver's smartcard settings (`keystore: NONE` plus `smartcardoptions` for
SunPKCS11). That needs its own test run, so the index key stays a
passphrase-protected file for now. A stolen index key would let someone publish a
forged index for the Redoubt F-Droid repository. Updates to installed apps are
still checked by Android against the release key, but first installs from that
repository trust the index.

**The bucket credentials** (`~/redoubt-fdroid/s3.env`) cannot live on a YubiKey.
Keep them encrypted at rest and decrypt into memory only for a deploy, for
example with gpg:

    gpg -c ~/redoubt-fdroid/s3.env && shred -u ~/redoubt-fdroid/s3.env   # once
    umask 077; D=$(mktemp -d /dev/shm/redoubt-s3.XXXXXX)
    gpg -d ~/redoubt-fdroid/s3.env.gpg > "$D/s3.env"
    REDOUBT_FDROID_S3_ENV="$D/s3.env" ./scripts/fdroid-repo.sh deploy
    rm -rf "$D"

`fdroid-repo.sh` accepts that file: a regular file, mode 600, owned by you,
outside the checkout.

## If the YubiKey is lost or broken

A YubiKey cannot export its keys. Restore from the offline backups into a new
YubiKey (steps 1-5). Importing into a second YubiKey now, kept with the backups,
saves that step. Losing both the YubiKey and the backups ends the identity
(SIGNING.md, "Why this cannot be re-done").
