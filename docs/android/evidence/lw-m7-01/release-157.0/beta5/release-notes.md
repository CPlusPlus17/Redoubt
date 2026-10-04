Fifth beta of Redoubt for Android, on **Firefox 157**. It installs over Beta 4 as an update and keeps your settings. Requires Android 8.0 or later. This is a prerelease.

## What changed since Beta 4

**Cookie-notice lists for everyone.** Beta 4 switched on uBlock Origin's "EasyList/uBO – Cookie Notices" lists only for fresh installs that were online on first launch. Beta 5 also switches them on, **once**, for:
- profiles updated from Beta 3 or earlier;
- installs whose first launch was offline.

After that, your choice is kept. If you switch the lists off in uBO → Filter lists, they stay off across restarts and updates.

> **One exception:** if you already had these lists in Beta 4 and switched *both* of them off, Beta 5 turns them on one more time. Switch them off again and they stay off. uBO's saved settings can't tell "switched off" apart from "never had them".

**Version shown in About.** The app still shows **157.0-1**, the same as Beta 4. The internal version number is higher, so the update installs normally. The release tag tells the builds apart.

Everything else is unchanged from Beta 4: the Firefox 157 engine, the disabled 157 cloud features (Shake to Summarize, IP Protection, Merino shortcut icons, Google Lens), and the fixes for the default-browser prompt, add-on state and WebGL/canvas permissions.

## Verify what you downloaded

    sha256sum -c SHA256SUMS.signed
    apksigner verify --print-certs fenix-<abi>-release.apk | grep -i SHA-256

The certificate digest must be:

    64:14:EB:33:46:81:CF:6E:92:90:34:B5:6A:06:2D:2B:8D:A0:90:82:21:72:F7:A3:95:2C:85:FD:D1:28:3B:D0

The APKs are signed with APK signature schemes v2 and v3 (no v1), using the same key as earlier betas.

## Which file

- `fenix-arm64-v8a-release.apk`: almost any phone from the last several years.
- `armeabi-v7a`: older 32-bit devices.
- `x86_64`: emulators.
- The universal APK carries all three and is much larger, so prefer a per-ABI build.

## Known limitations

- **Testing coverage:** the automated on-device tests ran on an x86_64 emulator only. The ARM builds were checked but not run on a physical phone. Reports from real devices are welcome.
- **Release cadence:** Redoubt follows Firefox's regular releases, so expect frequent updates.
- **Process sandbox:** Android has no content-process sandbox. Redoubt ships the same privacy configuration and Gecko security patches as LibreWolf desktop, on a platform with weaker process containment (see `docs/android/PARITY.md`).
- **DNS over HTTPS:** DoH settings from preferences don't apply. Use the DoH screen in Settings.
- **First-run network traffic:** first run contacts Remote Settings, uBlock Origin's filter-list hosts, and GitHub for Redoubt's pinned uBO list catalog. Nothing telemetry-, ads- or crash-reporting-shaped is contacted.
- **Signing key:** one person holds the signing key.

## Provenance

Built from `cdeadd6cebed214a05085899930d7dd269fa5a5a` against Firefox 157.0. Three ABIs come from one fat AAR, with R8 on. Signed by the maintainer; CI never sees the key. The evidence is in `docs/android/evidence/lw-m7-41/migration/` and `docs/android/evidence/lw-m7-01/release-157.0/beta5/`.
