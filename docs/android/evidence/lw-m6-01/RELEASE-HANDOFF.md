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

## If the key machine has no `apksigner`

It probably does not, and it should not need an Android SDK just to sign — the key
machine is deliberately not a build machine. `apksigner` is a thin shell wrapper
around `lib/apksigner.jar`, and **that jar is pure Java**: copy the one file and
run it with any JDK 17+.

A copy is staged on the build host at:

    ~/redoubt-artifacts/signing-tools/apksigner.jar
    sha256 3716d9311e55d2b0918a2fd9d54ba9e406c5f6abeea700b287f11259bc163dec
    1,100,545 bytes   (from build-tools 36.0.0)

Verified 2026-09-07 to sign a real Redoubt APK this way, producing exactly
`v1=false, v2=true, v3=true`. Substitute `java -jar apksigner.jar` for `apksigner`
in the loop below, and pass the same path to the verifier, which accepts a `.jar`
as well as a binary:

    APKSIGNER=~/redoubt-artifacts/signing-tools/apksigner.jar \
      ./scripts/android-verify-signature.sh fenix-*-release.apk

The alternative, if you would rather have the real thing: on macOS
`brew install --cask android-commandlinetools`, then
`sdkmanager "build-tools;36.0.0"`. That pulls an SDK onto the key machine, which
is more than this needs.

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
