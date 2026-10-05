**Redoubt 157.0-2 is the first stable release** of Redoubt for Android: a privacy-hardened browser built on **Firefox 157** with LibreWolf's privacy configuration. It installs over any Redoubt beta as an update and keeps your settings. Requires Android 8.0 or later.

Redoubt is an independent project. It is not affiliated with or endorsed by LibreWolf or Mozilla. Website: **https://redoubtbrowser.org**

## What's new since Beta 5

**In-app update check (opt-in, off by default).** Settings → *Check for updates*. When you turn it on, Redoubt asks `redoubtbrowser.org` at most once a day whether a newer version exists, and shows a notice with a link if there is one. It never downloads or installs anything by itself. The request carries no identifier, not even your version, and every answer must be signed with Redoubt's update key, or it is ignored. The site is hosted on GitHub Pages, so GitHub sees your IP address and the time of the request.

**Release builds come from CI.** This release was built by Redoubt's CI on a dedicated build machine, then signed by the maintainer.

Everything from the betas carries over:
- Firefox 157, with Firefox 157's Android security fixes.
- uBlock Origin 1.75.0, with the cookie-notice filter lists on by default.
- AI page summaries, IP Protection, Google Lens and Merino shortcut icons switched off.
- Local-network and storage-access protections kept strict.

## Verify what you downloaded

    sha256sum -c SHA256SUMS.signed
    apksigner verify --print-certs fenix-<abi>-release.apk | grep -i SHA-256

The certificate digest must be:

    64:14:EB:33:46:81:CF:6E:92:90:34:B5:6A:06:2D:2B:8D:A0:90:82:21:72:F7:A3:95:2C:85:FD:D1:28:3B:D0

Signed with APK signature schemes v2 and v3, no v1, using the same key as every beta.

## Which file

- `fenix-arm64-v8a-release.apk`: almost any phone from the last several years.
- `armeabi-v7a`: older 32-bit devices.
- `x86_64`: emulators.
- The universal APK carries all three and is much larger.

Updates: use the in-app check, [Obtainium](https://github.com/ImranR98/Obtainium) with this repository, or watch the Releases page.

## Known limitations

These are stated plainly; see `docs/android/PARITY.md`.
- **Device testing:** automated device testing ran on an x86_64 emulator. Real-device feedback comes from early adopters like you, and reports are welcome.
- **No content-process sandbox on Android:** Redoubt ships the same privacy configuration and Gecko security patches as LibreWolf desktop, on a platform with weaker process containment.
- **DNS over HTTPS:** DoH configuration from preferences doesn't apply. Use the DoH screen in Settings.
- **Signing key:** one person holds the signing key.

## Provenance

- **Source:** built from `27240eb6d0140704f637135c7985c778a9f46e51` against Firefox 157.0.
- **Build:** CI run 37248744119, with MOZ_BUILD_DATE 20261005000000.
- **Signing:** signed by the maintainer; CI never sees the key.
- **Evidence:** `docs/android/evidence/lw-m7-01/release-157.0-2/`.
