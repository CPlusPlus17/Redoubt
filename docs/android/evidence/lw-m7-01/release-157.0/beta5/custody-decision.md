# Beta 5 custody decision (2026-10-04)

**Manuel Gysin** (owner) signed Beta 5 on the Fedora build host with
`~/redoubt-release.p12` on **2026-10-04**. The owner ran `sign.sh` in their own
terminal and typed the passphrase there. The agent never read or operated the
release key.

This is a candidate-specific exception to the offline-signing procedure, in the
same form as Betas 2–4. It covers only the four hashes below.

## Candidate covered

Application ID `org.redoubtbrowser`, versionName `157.0-1-default` (kept at
157.0-1 by owner decision; only the versionCode increases), source
`cdeadd6cebed214a05085899930d7dd269fa5a5a` (verified with `git rev-parse`), settings
`8a69936`, MOZ_BUILD_DATE `20261003200000`.

| APK | versionCode | SHA-256 (signed) |
|---|---:|---|
| `fenix-arm64-v8a-release.apk` | 2016188258 | `e70a610431978081314e94c3e678d2a48cb18d46c84a1256ff6e6a60a7d76410` |
| `fenix-armeabi-v7a-release.apk` | 2016188256 | `25c36a409a6418185fe1bb7f25548daa95efd5dce1d0bb3cac75f29cdf487d66` |
| `fenix-universal-release.apk` | 2016188263 | `4fd919bf5a0446f3f9f2b0f201e477b4d80f03f1f9fb63da3da9d225b0d7c736` |
| `fenix-x86_64-release.apk` | 2016188262 | `34330b81778e6996032a397f66549ea961485c0773d74e282f871357e220d5b4` |

Every versionCode is above Beta 4's (2016188072–2016188079), so Beta 4
installs upgrade in place.

## Intake verification (by the agent, without the key)

- `sha256sum -c SHA256SUMS.signed`: all four OK.
- `android-verify-signature.sh`: all four PASS (published fingerprint, v2 + v3,
  no v1).
- **Payload:** every ZIP entry, `META-INF/` included, of each signed APK is
  byte-identical to its unsigned input (`SHA256SUMS.unsigned`). Those inputs are
  the build `../../../lw-m7-41/migration/` accepted.
- **Signing tools:** byte-identical to Beta 4's.

## Known limits and accepted decisions

- **Device testing:** on-device acceptance ran on x86_64 (emulator) only; the
  ARM APKs were checked statically.
- **Cookie-list migration edge case, accepted by the owner:** a Beta 4 user who
  had the lists and turned both off gets them on once more. The release notes say
  so.
