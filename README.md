<div align="center">

<img src="themes/android/main/ic_launcher-web.webp" alt="Redoubt logo" width="96">

# Redoubt

A privacy-hardened Android browser, built from Firefox's source and LibreWolf's
privacy configuration.

</div>

> **Redoubt is not LibreWolf.** It is an independent fork of LibreWolf's source,
> maintained by someone who is not a LibreWolf developer. The LibreWolf project
> has not built, reviewed, endorsed or supported it. Please do not report Redoubt
> problems to LibreWolf. See [Attribution](#attribution).

## Status

**Beta.** Builds are published as prereleases on
[GitHub Releases](https://github.com/CPlusPlus17/Redoubt/releases). The current
betas are based on Firefox 157 (Firefox's regular release track), need Android 8.0
or later, and install over the previous beta as an update.

Redoubt is not on F-Droid, Accrescent or any app store yet, and the app has no
update check: watch the Releases page and install new APKs over the old one.

## Install and verify

Download from the latest release on the
[Releases page](https://github.com/CPlusPlus17/Redoubt/releases):

| file | for |
|---|---|
| `fenix-arm64-v8a-release.apk` | almost any phone from the last several years |
| `fenix-armeabi-v7a-release.apk` | older 32-bit devices |
| `fenix-x86_64-release.apk` | emulators |
| `fenix-universal-release.apk` | all three ABIs; much larger, prefer a per-ABI APK |

(The `fenix-` prefix is the file name of the Android app build Redoubt is made
from; the installed app is Redoubt, `org.redoubtbrowser`.)

Check the download before installing:

    sha256sum -c --ignore-missing SHA256SUMS.signed
    apksigner verify --print-certs fenix-<abi>-release.apk | grep -i SHA-256

The signing certificate's SHA-256 digest must be:

    64:14:EB:33:46:81:CF:6E:92:90:34:B5:6A:06:2D:2B:8D:A0:90:82:21:72:F7:A3:95:2C:85:FD:D1:28:3B:D0

Every Redoubt APK is signed with this one key (APK signature schemes v2 and v3).
If the digest differs, do not install it, and report it privately (see
[Security](#security-and-bug-reports)). The key and its custody are documented
in [`docs/android/SIGNING.md`](docs/android/SIGNING.md).

## What it changes compared with Firefox for Android

The approved summary, and the full measured comparison behind it:

> Redoubt ships the same privacy configuration and the same Gecko-level security
> patches as LibreWolf desktop, on a platform whose process containment is
> weaker — and we publish exactly where.

That "where" is [`docs/android/PARITY.md`](docs/android/PARITY.md). In short:

- **Built from source.** Gecko and the Android app are compiled from Firefox's
  source with LibreWolf's shared patch set and preference configuration applied,
  rather than patching a prebuilt browser.
- **Telemetry and experiments removed**: the Glean upload path, Adjust, Nimbus
  experiments, crash-report uploads and Google Play Services are patched out;
  sponsored shortcuts are removed and search suggestions are off by default.
- **LibreWolf's privacy defaults**: resist-fingerprinting, strict Enhanced
  Tracking Protection and cookie partitioning (both locked), Global Privacy
  Control on.
- **Stronger site isolation than stock**: Fission is locked to isolate
  high-value sites; stock Firefox for Android ships with it off.
- **uBlock Origin preinstalled**, with its cookie-notice lists on by default.
- **Cloud features off**, such as Shake to Summarize, IP Protection and Google Lens.

### Honest limits

- **No content-process sandbox.** Firefox's Gecko content sandbox does not exist
  on Android (upstream never finished the port). Per-site process isolation,
  isolated processes and RLBox recover most, not all, of it.
- **Not everything is proven on a live page.** HTTPS-only, certificate revocation,
  the TLS floor and fingerprinting coherence are configured but marked *Partial*
  in `PARITY.md` until measured on a device. The DNS-over-HTTPS setting in the
  configuration is overridden by the app; use Settings > DNS over HTTPS instead.
- **Automated device testing so far covers an x86_64 emulator only.** ARM builds
  are checked but have not been run on a physical phone by the project. Reports
  from real devices are welcome.
- **One person holds the signing key.** There is no second key holder yet.
- **A small project.** If you want a mature, widely used hardened Firefox for
  Android today, [IronFox](https://github.com/ironfox-oss/IronFox) is that, and it
  is the browser LibreWolf itself recommends to Android users. How Redoubt differs
  is in [`docs/android/POSITIONING.md`](docs/android/POSITIONING.md).

## Attribution

**Redoubt is built on LibreWolf's work.** The privacy configuration that is the
point of this browser (LibreWolf's `librewolf.cfg`, from which Redoubt's
`settings/common.cfg` and `android.cfg` are derived, and the roughly 260 preference
decisions behind it) and the patch set that enforces it were written by the
[LibreWolf project](https://librewolf.net), and this repository is a fork of
[LibreWolf's source](https://librewolf.dev/librewolf/source), used under MPL-2.0.
Redoubt ports that work to Android, a platform LibreWolf does not ship.

Redoubt is **not affiliated with or endorsed by the LibreWolf project**, and the
app is branded Redoubt, not LibreWolf. File names such as `librewolf.cfg`,
`librewolf.*` preferences and `scripts/librewolf-patches.py` are inherited code
identifiers, kept so the fork can keep rebasing on upstream; they are not branding.

Redoubt is also **not affiliated with or endorsed by Mozilla**. It is built from
Mozilla's Firefox (Gecko and Firefox for Android) source code. Firefox is a
trademark of the Mozilla Foundation; Redoubt does not use Mozilla's trademarks in
its branding.

## Security and bug reports

- **Security vulnerabilities, signature mismatches or a suspicious download**:
  report privately via
  [GitHub private vulnerability reporting](https://github.com/CPlusPlus17/Redoubt/security/advisories/new).
  Process: [`docs/android/SECURITY.md`](docs/android/SECURITY.md).
- **Bugs in Gecko or Firefox for Android itself** belong with Mozilla
  (Bugzilla); the issue form asks whether stock Firefox shows the same problem.
- **Other bugs**: [open an issue](https://github.com/CPlusPlus17/Redoubt/issues/new/choose)
  using the Android bug form. Triage is described in
  [`docs/android/TRIAGE.md`](docs/android/TRIAGE.md).

## Where things are

| path | what |
|---|---|
| [`docs/android/`](docs/android/) | the Android work: plan, decisions, evidence ([`README.md`](docs/android/README.md) is the index) |
| [`docs/android/PARITY.md`](docs/android/PARITY.md) | what Redoubt does and does not match, measured |
| [`docs/android/IDENTITY.md`](docs/android/IDENTITY.md) | why this is called Redoubt, and what stays named `librewolf` |
| [`docs/android/BUILD.md`](docs/android/BUILD.md), [`REPRODUCIBLE.md`](docs/android/REPRODUCIBLE.md) | building GeckoView and the APK, and reproducing a release |
| [`patches/`](patches/), [`assets/patches/`](assets/patches/) | patches, and the common / desktop / android lists that select them |
| [`settings/`](settings/) | submodule with the preference configuration ([Redoubt-settings](https://github.com/CPlusPlus17/Redoubt-settings), from LibreWolf's settings) |
| [`.github/workflows/`](.github/workflows/) | Android test and release builds |

## The desktop patch set

This repository still carries upstream LibreWolf's desktop build: the
`Makefile`, the desktop patch list and the desktop theming. It is kept as the
base Redoubt rebases on, because the privacy configuration and the common
patches are shared between desktop and Android.

**Redoubt does not publish desktop builds.** For LibreWolf on desktop, use
LibreWolf's own releases from [librewolf.net](https://librewolf.net).

## Licence

[Mozilla Public License 2.0](LICENSE), like the LibreWolf and Firefox code it is
built from. The licence covers the code, not the LibreWolf or Firefox names and
logos (MPL-2.0 §2.3).
