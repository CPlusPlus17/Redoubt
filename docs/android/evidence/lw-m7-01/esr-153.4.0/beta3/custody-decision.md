# Beta 3 custody decision (2026-10-02)

The owner, **Manuel Gysin**, decided on **2026-10-02** to sign Beta 3 on the Fedora
build host with `~/redoubt-release.p12`. The owner chose "Here on Fedora, new
exception" over offline signing. The owner ran `sign.sh` personally and typed
the passphrase; the agent did not read or operate the release key, and has no
authority to (see `../../../lw-m6-10/custody-decision.md`).

This is a candidate-specific exception to the offline-signing procedure. It
has the same form as Beta 2's and covers only the four hashes below. It does
not change the procedure for future candidates.

## Candidate covered

Application ID `org.redoubtbrowser`, versionName `153.4.0esr-1-default`, source
`0a134441b77a888f365e81da02beee71d6e3b9c4`, MOZ_BUILD_DATE `20261002044800`.

| APK | versionCode | SHA-256 (signed) |
|---|---:|---|
| `fenix-arm64-v8a-release.apk` | 2016187938 | `a6b71fb1c63f8d073e95b05d3633abaafd513d61af680d8b5c48ab3479ab57c1` |
| `fenix-armeabi-v7a-release.apk` | 2016187936 | `bf5ba82cee894ab03d6befa1c1739ae1635b2cab69afea3a3bd9fb1b96fa9238` |
| `fenix-universal-release.apk` | 2016187943 | `918852214260779c51882d46349329ea99f184e91f1a491687c21b0d2cb24355` |
| `fenix-x86_64-release.apk` | 2016187942 | `78d41c46d32e2c6b9b300a2418b132cff6209c5d5e168b8d9ad0f790a4bf62f8` |

All four version codes are above Beta 2's (2016183064–2016183071), so Beta 2
installs upgrade in place.

## Verification at intake (by the agent, without the key)

- `sha256sum -c SHA256SUMS.signed`: all four OK.
- `android-verify-signature.sh --signing-doc SIGNING.md`: PASS for all four
  (published fingerprint, v2 + v3, no v1). See `local-signature-verification.txt`.
- **Payload:** every ZIP entry, `META-INF/` included, of each signed APK is
  byte-identical to its unsigned input (`SHA256SUMS.unsigned`). Those inputs are
  the rc2 APKs that `../rc2/` and `../rc2/final-acceptance/` test.
- The signing tools are byte-identical to the ones that signed Beta 2. Their
  `SHA256SUMS.tools` hashes match `lw-m6-11`'s bundle.

## Known limits, stated in the release notes

On-device acceptance ran on **x86_64 only** (emulator, android-30). The ARM
APKs were checked for hashes, native-library architecture, and payload equality
with the tested build, but they have not been run on hardware. The owner
accepted this for Beta 3, which matches Beta 2's coverage.
