Fourth beta of Redoubt for Android, and the first built on **Firefox 157**. Redoubt for Android now follows Firefox's regular releases instead of ESR, so new Gecko versions and Firefox for Android's security fixes arrive with each release. It installs over Beta 3 as an update and keeps your settings. Requires Android 8.0 or later. This is a prerelease.

## What changed since Beta 3

**Firefox 157.** The engine and app move from Firefox ESR 153.4 to Firefox 157.0. That brings four major versions of fixes and features, including Android-only security fixes that ESR never received.

**Cookie banners are handled by uBlock Origin.** Firefox 156 removed its built-in cookie-banner service, and Beta 3's cookie-banner settings went with it. Fresh installs of Beta 4 now get uBlock Origin's "EasyList/uBO – Cookie Notices" filter lists switched on, and you can switch them off in uBO's Filter lists pane.
- **If you're updating from Beta 3:** turn them on yourself in uBO → Filter lists → Cookie notices. uBO only applies Redoubt's default list selection on its very first run, and the same applies if your first launch was offline.
- **How it differs:** filter lists hide or block banners. They don't click "Reject".

**New Firefox 157 cloud features are switched off.** Firefox 157 turns on several features that send data to Mozilla or Google. Redoubt switches off:
- **Shake to Summarize:** AI page summaries through Mozilla's LLM service.
- **IP Protection:** Mozilla's VPN, with its setup prompt and its start at launch.
- **Shortcut icons:** "Add shortcut" icons fetched from Mozilla's Merino servers.
- **Google Lens:** Lens image upload.

**Fixed**
- **Default-browser prompt:** Android's "Set Redoubt as your default browser?" dialog no longer appears on the fourth cold start. Beta 3 also has this bug.
- **Add-on re-enable:** re-enabling a disabled extension now starts it right away, instead of after a restart. Betas 2 and 3 also have this bug.
- **Add-on disable at install:** a "disable" choice made while installing an extension is no longer overwritten.
- **WebGL and canvas permissions list:** it no longer opens empty after a restart.

**Unchanged:** local-network protection for top-level navigations stays on, as in every beta, and uBlock Origin is still 1.75.0.

## Verify what you downloaded

    sha256sum -c SHA256SUMS.signed
    apksigner verify --print-certs fenix-<abi>-release.apk | grep -i SHA-256

The certificate digest must be:

    64:14:EB:33:46:81:CF:6E:92:90:34:B5:6A:06:2D:2B:8D:A0:90:82:21:72:F7:A3:95:2C:85:FD:D1:28:3B:D0

Signed with APK signature schemes v2 and v3, no v1, with the same key as earlier betas.

## Which file

`fenix-arm64-v8a-release.apk` suits almost any phone from the last several years. Use `armeabi-v7a` for older 32-bit devices and `x86_64` for emulators. The universal APK carries all three and is much larger, so prefer a per-ABI build.

## Known limitations

- **Testing coverage:** the automated on-device tests ran on an x86_64 emulator only. The ARM builds contain the same app with ARM engines and were checked, but not run on a physical phone. Reports from real devices are especially welcome.
- **Faster release cadence:** Redoubt now follows Firefox releases, so expect more frequent updates.
- **No content-process sandbox on Android:** Redoubt ships the same privacy configuration and Gecko security patches as LibreWolf desktop, on a platform with weaker process containment. `docs/android/PARITY.md` says exactly where.
- **DNS over HTTPS:** DoH configuration from preferences doesn't apply. Use the DoH screen in Settings.
- **First-run network traffic:** the first run contacts Remote Settings (revocation, blocklists, tracking-protection lists), uBlock Origin's filter-list hosts, and GitHub for Redoubt's pinned uBO list catalog. Nothing telemetry-, ads- or crash-reporting-shaped is contacted.
- **Single signing key:** one person holds the signing key. If it is lost, this applicationId can no longer be updated.

## Provenance

Built from `6202ee6d16bdc5cf9d9f2df4b5c311817fce1a8c` against Firefox 157.0. Three ABIs come from one fat AAR, with R8 on. Signed by the maintainer; CI never sees the key. The evidence is in `docs/android/evidence/lw-m7-01/release-157.0/`.
