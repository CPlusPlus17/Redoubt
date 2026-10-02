Third beta of Redoubt for Android, now built on **Firefox ESR 153.4** (from 153.0) with LibreWolf's patch set. It installs over Beta 2 as an update, and settings are kept. Requires Android 8.0 or later. This is a prerelease.

## What changed since Beta 2

**Security updates.** Gecko moves from 153.0esr to 153.4.0esr, which includes Mozilla's ESR security advisories MFSA 2026-77, 2026-85, 2026-93 and 2026-100.

**"uBlock Origin setup failed" is fixed.** Beta 2 showed it in two situations:
- **Fresh install:** uBlock Origin updated itself from addons.mozilla.org during first-run setup, and the setup check failed.
- **Launch from the home screen:** opening the app from the launcher, without a link, showed the same dialog after 30 seconds.

Both are fixed. uBlock Origin is now pinned at 1.75.0.

**Mullvad DNS over HTTPS is going away.** Mullvad is discontinuing its DoH service, so it has been removed from the provider list. If you had selected Mullvad, Redoubt moves you to the default provider (Quad9) once, keeps your protection level, and tells you about the change.

**about:config works again.** In Gecko 153.4 the page showed only a spinner. It now uses Firefox's own fix and still runs under the stricter security policy.

**Smaller changes**
- "What's new" and release notes now point to this project's releases page.
- The disk cache stays off, and if Gecko ever writes one, it is now encrypted.
- uBlock Origin downloads its filter-list bootstrap from librewolf.dev.

## Verify what you downloaded

    sha256sum -c SHA256SUMS.signed
    apksigner verify --print-certs fenix-<abi>-release.apk | grep -i SHA-256

The certificate digest must be:

    64:14:EB:33:46:81:CF:6E:92:90:34:B5:6A:06:2D:2B:8D:A0:90:82:21:72:F7:A3:95:2C:85:FD:D1:28:3B:D0

Signed with APK signature schemes v2 and v3, no v1. Same key as Beta 2.

## Which file

`fenix-arm64-v8a-release.apk` works on almost any phone from the last several years. Use `armeabi-v7a` for older 32-bit devices and `x86_64` for emulators. The universal APK carries all three and is much larger, so prefer a per-ABI build.

## Known limitations

- **Testing coverage:** the automated on-device tests for this beta ran on an **x86_64 emulator only**. The ARM builds are byte-for-byte the same app with ARM engines; they were checked but not run on a physical phone. Reports from real devices are especially welcome.
- **No content-process sandbox:** the Gecko content-process sandbox is absent on Android. Redoubt ships the same privacy configuration and Gecko-level security patches as LibreWolf desktop, on a platform whose process containment is weaker. `docs/android/PARITY.md` says exactly where.
- **Android-only security fixes:** Firefox for Android has fixed some security issues that have no ESR counterpart yet. These are tracked openly and are not all backported.
- **DNS-over-HTTPS configuration:** DoH configuration from preferences does not apply. Use the DoH screen in Settings.
- **First-run network requests:** first run contacts Remote Settings (revocation, blocklists, tracking-protection lists) and uBlock Origin's filter-list hosts. Nothing telemetry-, ads- or crash-reporting-shaped is contacted.
- **Single signing key:** one person holds the signing key. If that key is lost, this applicationId can no longer be updated.

## Provenance

Built from `0a134441b77a888f365e81da02beee71d6e3b9c4` against Firefox ESR 153.4.0. Three ABIs come from one fat AAR, with R8 on. Signed by the maintainer; CI never sees the key. The evidence is in `docs/android/evidence/lw-m7-01/esr-153.4.0/`.
