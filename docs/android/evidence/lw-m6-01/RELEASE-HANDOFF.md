# E7 hand-off — the unsigned artifacts are built and waiting

**Everything up to the signature is done.** This file exists so the remaining step
is a command rather than a project.

E7 is the last of `BETA.md`'s twelve entry criteria. It cannot be completed on the
build machine and should not be: the passphrase is the owner's, and `SIGNING.md`
custody rule 3 puts the signing machine somewhere other than the host running the
CI runner. So the work was taken as far as it goes without the key.

## What is ready

Built 2026-09-06 from the three-ABI tree, `MOZ_BUILD_DATE=20260906190000`, with R8
on and `--disable-debug-signing`, in `librewolf-android-apk-153.0esr-1-unsigned/apk/`:

    fenix-armeabi-v7a-release-unsigned.apk   117 MB
    fenix-arm64-v8a-release-unsigned.apk     121 MB
    fenix-x86_64-release-unsigned.apk        127 MB
    fenix-universal-release-unsigned.apk     278 MB
    SHA256SUMS

Verified to carry **no signature at all** — no v1 block, no v2/v3 signing block —
which is what the CI custody model publishes and what a holder then signs.
Checksums are copied next to this file so a transfer can be checked at the other
end.

These are the same inputs the reproducibility check used, and that check passed
with R8 on: two independent builds byte-identical, negative control good
(`docs/android/evidence/lw-m6-02/`).

## The remaining step, in full

On a machine that is **not** this one, holding the keystore:

    # 1. check what you received
    sha256sum -c SHA256SUMS

    # 2. sign each artifact -- v1 off, v2 on, v3 on
    for a in fenix-*-release-unsigned.apk; do
      apksigner sign --ks redoubt-release.p12 --ks-type PKCS12 \
        --v1-signing-enabled false --v2-signing-enabled true --v3-signing-enabled true \
        --out "${a%-unsigned.apk}.apk" "$a"
    done

    # 3. check the result -- one command, all four properties
    ./scripts/android-verify-signature.sh fenix-*-release.apk

Step 3 passes only when every APK is v2 **and** v3, has no v1, and reports the
fingerprint published in `SIGNING.md`. It reads that fingerprint out of the
document rather than carrying a copy, and its own `--self-test` has confirmed it
both detects a correct signature and rejects a correctly-signed APK bearing the
wrong key.

Accrescent (LW-M6-04) rejects v2-only, which is why v3 is not optional.

## Two things to carry into that session

1. **The key is currently readable by CI.** It lives on the build host and the
   Actions runner executes as its owner, so any job reaching that runner can read
   it (`SIGNING.md` custody rule 3, which records the violation). Moving it is the
   fix; signing elsewhere while it still sits there addresses only half.
2. **Redoubt ships single-holder**, decided 2026-09-06. Losing both machines and
   the passphrase ends the app under `org.redoubtbrowser`. The signing session is
   a reasonable moment to make the offline third copy that decision left open.
