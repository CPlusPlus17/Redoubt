# E7 offline signing handoff

**Intake update 2026-09-08:** the holder has returned all four signed APKs to
`~/redoubt-signed/`; published fingerprint, v2+v3/no-v1 and exact candidate
payload checks pass. The holder reports signing on Fedora before CI moved into
QEMU. The [migration](../lw-m6-09/README.md) removes current runner access to
host files but does not establish earlier offline signing. E7 still requires
matching custody evidence or an explicit owner exception; do not rerun `sign.sh`
against its existing signed outputs. Prior release-key distribution history
also remains unconfirmed. The instructions below describe the original handoff.

The final candidate directory for this handoff is
`librewolf-android-apk-153.0esr-1-beta-20260908/apk/`. Its build and validation
status is recorded in `BETA.md`; transfer it after the candidate gates pass.
The complete tools and current public signing document are staged there and
both checksum manifests pass. E7 still requires the holder to
sign offline on a machine other than the CI runner, and to ensure the release key
is no longer readable by that runner (`SIGNING.md`, custody rule 3). This handoff
does not claim that the other beta entry criteria are complete; use the current
`BETA.md` audit for their evidence.

## Bundle contents

```text
fenix-arm64-v8a-release-unsigned.apk
fenix-armeabi-v7a-release-unsigned.apk
fenix-universal-release-unsigned.apk
fenix-x86_64-release-unsigned.apk
SHA256SUMS
apksigner.jar
sign.sh
android-verify-signature.sh
SIGNING.md
SHA256SUMS.tools
```

`SHA256SUMS` covers exactly the four APKs. `SHA256SUMS.tools` covers exactly the
signing script, verifier, public signing document, and apksigner JAR. Transfer the
whole directory; no keystore or passphrase belongs in that transferred bundle.
Compare its manifests with the copies obtained from the trusted build handoff.
Checksums establish transfer integrity; build provenance and reproducibility are
separate beta gates.

The apksigner JAR is from Android build-tools 36.0.0:

```text
3716d9311e55d2b0918a2fd9d54ba9e406c5f6abeea700b287f11259bc163dec  apksigner.jar
```

## On the offline key machine

This candidate is intended as the **first release-key beta**. Its pinned build
date gives x86_64 versionCode `2016183070`; the earlier debug/unsigned rehearsals
used wall-clock codes as high as `2016183238`. Confirm that no higher-code APK
signed with the release key has already been distributed. If one has, report its
version code before signing this candidate so a newer candidate can be built.
Subsequent beta releases must use a later UTC build hour; builds within one hour
intentionally keep the same version code.

Required tools: Java 17+, Bash, `unzip` or the JDK `jar` command, and `sha256sum`
or `shasum`. No Android SDK is required. Check the files before execution:

```sh
cd /path/to/the/copied/apk
sha256sum -c SHA256SUMS
sha256sum -c SHA256SUMS.tools
# On macOS without sha256sum, use: shasum -a 256 -c <manifest>
./sign.sh /path/to/redoubt-release.p12
```

The script can also be called by its path from another directory. A relative
keystore argument is resolved from the caller's directory. Without an argument it
looks for `redoubt-release.p12` beside itself, but the key must never be included
when transferring this directory back to the build host.

The script prompts for the passphrase for each APK; it is not a command-line
argument. It verifies both complete manifests, signs each APK with v1 and v4 off
and v2 and v3 on, and verifies the published fingerprint, exactly one signer, and
absence of v1 signature entries. APKs stay in a temporary directory until all four
pass. Existing signed outputs are refused rather than overwritten. On success it
writes four `fenix-*-release.apk` files and `SHA256SUMS.signed` beside the inputs.

The verifier checks archive entries because apksigner's default report can say
`v1=false` even when v1 signatures are present on a minSdk 26 APK. Real signatures,
including this negative control, are covered by
`docs/android/evidence/lw-m6-08/signing-tests.out`.

## Return and verify

Copy only the four signed APKs and `SHA256SUMS.signed` to `~/redoubt-signed/` on
the build host. Keep the unsigned files and tool manifests unchanged. Intake from
this repository is:

```sh
(cd ~/redoubt-signed && sha256sum -c SHA256SUMS.signed)
candidate_apk_dir="$PWD/librewolf-android-apk-153.0esr-1-beta-20260908/apk"
APKSIGNER="$candidate_apk_dir/apksigner.jar" ./scripts/android-verify-signature.sh \
  --unsigned-dir "$candidate_apk_dir" \
  ~/redoubt-signed/fenix-arm64-v8a-release.apk \
  ~/redoubt-signed/fenix-armeabi-v7a-release.apk \
  ~/redoubt-signed/fenix-universal-release.apk \
  ~/redoubt-signed/fenix-x86_64-release.apk
```

The explicit `APKSIGNER` path works on a host without an SDK signer on `PATH`.
`--unsigned-dir` additionally needs Python 3 on the intake host. It verifies the
complete candidate checksum manifest, then checks every ZIP entry's name, size,
compression method, and uncompressed bytes against the corresponding unsigned
APK. Duplicate entries, missing counterparts, and changed payloads fail. A stale
APK signed by the correct release key therefore cannot pass intake for this
candidate. The optional check is not used by the offline signing helper, which
does not need Python.

Retain the command output with the signed artifact hashes. The holder must also
record the signing date, holder name, that signing happened offline on a machine
other than the CI runner, and that the release key is no longer readable on the
build host. A correct APK signature cannot prove either custody fact.

The 2026-09-06 single-holder decision remains in force. It does not waive the
separate rule excluding the release key from the build host. The test suite uses
only generated temporary keys and does not perform the release-signing step.
