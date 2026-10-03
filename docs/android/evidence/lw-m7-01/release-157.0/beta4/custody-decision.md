# Beta 4 custody decision (2026-10-03)

**Manuel Gysin** (owner) signed Beta 4 on the Fedora build host with
`~/redoubt-release.p12` on **2026-10-03**. The owner ran `sign.sh` in their own
terminal and typed the passphrase there. The agent never read or operated the
release key; it has no authority to (see `../../../lw-m6-10/custody-decision.md`).

This is a candidate-specific exception to the offline-signing procedure. It
has the same form as Beta 2's and Beta 3's (`../../esr-153.4.0/beta3/custody-decision.md`)
and covers only the four hashes below.

## Candidate covered

Application ID `org.redoubtbrowser`, versionName `157.0-1-default`, source
`6202ee6d16bdc5cf9d9f2df4b5c311817fce1a8c` (rc3), settings `8a69936`,
MOZ_BUILD_DATE `20261002210000`.

| APK | versionCode | SHA-256 (signed) |
|---|---:|---|
| `fenix-arm64-v8a-release.apk` | 2016188074 | `7b6f2b738d3fbeadd4d502edc3c964454c6e415f6afa8b78ec735f3a6a83dd57` |
| `fenix-armeabi-v7a-release.apk` | 2016188072 | `97ceeeffb36d3d6729d7ff28c1d574dae2109c2779197951d5ff7a96e8d9520d` |
| `fenix-universal-release.apk` | 2016188079 | `f166e024ecc0db92d76c79997179ba927fad956f64d3533ddf5c5a11ad3470d3` |
| `fenix-x86_64-release.apk` | 2016188078 | `2ea63aed1cd0ff42573fb7721ffb8703fe0d0510d0b0d5932ffa290924a512a7` |

Every versionCode is above Beta 3's (2016187936–2016187943), so Beta 3 installs
upgrade in place. Two earlier candidates, rc1 and rc2, share these versionCodes
but never left the build host.

## Intake verification (by the agent, without the key)

- `sha256sum -c SHA256SUMS.signed`: all four OK.
- `android-verify-signature.sh --signing-doc SIGNING.md`: all four PASS (published
  fingerprint, v2 + v3, no v1). See `local-signature-verification.txt`.
- **Payload:** every ZIP entry, `META-INF/` included, of each signed APK is
  byte-identical to its unsigned input (`SHA256SUMS.unsigned`). Those inputs are the
  rc3 APKs that `../acceptance/` accepted.
- **Signing tools:** byte-identical to those that signed Beta 2 and Beta 3.

## Known limits, stated in the release notes

On-device acceptance ran on **x86_64 only** (emulator). The ARM APKs were checked
for hashes, native-library architecture and payload equality with the tested
build, but not run on hardware. This matches Beta 2 and Beta 3.
