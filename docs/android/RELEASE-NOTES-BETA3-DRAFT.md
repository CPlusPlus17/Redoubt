# Draft — Redoubt Android 153.3.0esr — Beta 3

For the owner to edit and publish. It corrects Beta 2's notes, which still carried
Beta 1's DoH statement and did not mention uBO's first-run fetch. Every claim below
is sourced in [`LIBREWOLF-GAPS.md`](LIBREWOLF-GAPS.md); nothing here has been
run on a device yet, so publish only after the candidate passes its checks.

---

Third beta of Redoubt for Android, built from Firefox ESR **153.3.0** with
LibreWolf's patch set. **Replaces Beta 2.**

## What changed since Beta 2

**uBlock Origin no longer says "setup failed" after the first launch.** In Beta 2
every later start waited for uBO while uBO waited for the first tab, and the wait
timed out. First-run setup also waits longer on slow networks.

**Security updates.** Beta 2 was built on 153.0esr. Beta 3 is on 153.3.0esr and
carries Mozilla's three ESR security releases since.

**Delete-on-close now works when the app is swiped away or killed.** With
"Delete browsing data on quit" on (the default: cookies, site data and cache),
Redoubt now clears that data at the next start, before any page loads, as
LibreWolf does when it closes. Previously only the Quit menu item cleaned up.

**uBO's filter lists come from Redoubt, not LibreWolf's servers.** On first run
uBO fetches its list selection once, from a fixed file in Redoubt's repository
(LibreWolf's selection, unchanged). It no longer contacts Codeberg.

**"Report broken site" is gone.** Reports went nowhere: the upload path is removed.

**DRM can be switched on in Settings.** It stays off by default; in Beta 2 the
Settings entry could not enable it.

## Verify what you downloaded

    sha256sum -c SHA256SUMS.signed
    apksigner verify --print-certs fenix-<abi>-release.apk | grep -i SHA-256

The certificate digest must be:

    64:14:EB:33:46:81:CF:6E:92:90:34:B5:6A:06:2D:2B:8D:A0:90:82:21:72:F7:A3:95:2C:85:FD:D1:28:3B:D0

## Known limitations

- **The Gecko content-process sandbox is absent on Android.** Redoubt ships the
  same privacy configuration and the same Gecko-level security patches as
  LibreWolf desktop, on a platform whose process containment is weaker — and we
  publish exactly where, in `docs/android/PARITY.md`.
- **DNS-over-HTTPS is off by default, as in LibreWolf,** with LibreWolf's
  providers (Quad9, DNS4All fallback) offered in Settings. *(Beta 2's notes said
  the configuration did not apply; that was true of Beta 1.)*
- **DRM:** off by default, as in LibreWolf. Turn it on in Settings > Site
  permissions > DRM-controlled content, for all sites or per site.
- Delete-on-close has no per-site "keep cookies" exceptions yet.
- First run contacts: the Remote Settings collections recorded in
  `settings/android.cfg`, uBO's list file on `raw.githubusercontent.com`, and the
  hosts of the three uBO lists LibreWolf enables that are not bundled.
- One key holder. Losing that key ends the app under this applicationId.
