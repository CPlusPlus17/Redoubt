First public beta of **Redoubt for Android**, based on **153.0esr-1**.
Requires **Android 8.0 or later (API 26+)**. Physical-device testing and feedback
are ongoing; this is a prerelease.

Choose one APK:

| Download | Device |
|---|---|
| `fenix-arm64-v8a-release.apk` | Most modern Android phones and tablets |
| `fenix-armeabi-v7a-release.apk` | Devices running 32-bit ARM Android |
| `fenix-x86_64-release.apk` | x86_64 devices and emulators |
| `fenix-universal-release.apk` | All three supported architectures; choose this if unsure |

The application ID is `org.redoubtbrowser`. Android may display the installed
version as `153.0esr-1-default`; the beta designation is on this release.
**In-app update checks are disabled in this beta.** Download later beta APKs
from this Releases page and install them over this build to retain your profile.

Android process containment differs from desktop. DNS over HTTPS is not enabled
by default, and locked privacy preferences can make some settings ineffective.
Approved security Remote Settings connections remain enabled. Please include
device model, Android version, RAM, APK architecture and reproduction steps when
[reporting an Android bug](https://github.com/CPlusPlus17/Redoubt/issues/new?template=android-bug.yml).
Report vulnerabilities through
[private security reporting](https://github.com/CPlusPlus17/Redoubt/security/advisories/new).

Download `SHA256SUMS.signed` alongside the APK. On a system with GNU coreutils:

```sh
sha256sum --ignore-missing -c SHA256SUMS.signed
```

All four APKs use the Redoubt release certificate and APK signature schemes
**v2 and v3, with no v1**. With Android's `apksigner`, for example:

```sh
apksigner verify --verbose --print-certs fenix-universal-release.apk
```

Expected certificate SHA-256 fingerprint:

```text
64:14:EB:33:46:81:CF:6E:92:90:34:B5:6A:06:2D:2B:8D:A0:90:82:21:72:F7:A3:95:2C:85:FD:D1:28:3B:D0
```

These exact APKs are covered by the documented
[beta signing-custody exception](https://github.com/CPlusPlus17/Redoubt/blob/android-153.0esr-1-beta.1/docs/android/evidence/lw-m6-10/custody-decision.md).
See the [candidate build and test evidence](https://github.com/CPlusPlus17/Redoubt/blob/android-153.0esr-1-beta.1/docs/android/evidence/lw-m6-10/completion-audit.md)
and [beta test plan](https://github.com/CPlusPlus17/Redoubt/blob/android-153.0esr-1-beta.1/docs/android/BETA.md).

The source tag is `android-153.0esr-1-beta.1`. To include the pinned settings
submodule when obtaining source:

```sh
git clone --branch android-153.0esr-1-beta.1 --recurse-submodules https://github.com/CPlusPlus17/Redoubt.git
```
