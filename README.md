<div align="center">

<img src="themes/android/main/ic_launcher-web.webp" alt="Redoubt logo" width="96">

# Redoubt

A privacy-hardened Android browser, built from Firefox's source and LibreWolf's
privacy configuration.

**[redoubtbrowser.org](https://redoubtbrowser.org)** · [FAQ](https://redoubtbrowser.org/faq.html)

</div>

> **Redoubt is not LibreWolf.** It is an independent fork of LibreWolf's source,
> maintained by someone who is not a LibreWolf developer. The LibreWolf project
> has not built, reviewed, endorsed or supported it. Please do not report Redoubt
> problems to LibreWolf. See [Attribution](#attribution).

## Status

**Stable.** The current release is **Redoubt 158.0-2**, published as the
[latest release](https://github.com/CPlusPlus17/Redoubt/releases/latest). It is
based on Firefox 158.0 (Firefox's regular release track), needs Android 8.0 or
later, and installs over any earlier Redoubt release as an update. Since 158.0-2,
web content runs in Android's isolated processes on Android 12 and newer.

Three ways to install and stay up to date:

- **The Redoubt F-Droid repository** (not f-droid.org's main repository). Add
  `https://redoubtbrowser.hel1.your-objectstorage.com/repo` in the F-Droid app
  and check that it shows the repository fingerprint
  `B0A8CDBB61AA4FC3CA1FED71F4CAECEB7B00E39D4E6E0583A637070862AC5567` (SHA-256 of
  the key that signs the index). The APKs inside are the release APKs, signed with
  the key below. The repository is a Hetzner Object Storage bucket, which is why
  its address is not redoubtbrowser.org. How-to and QR code:
  https://redoubtbrowser.org/fdroid.html
- **Obtainium**, tracking the GitHub releases (see below).
- **The APK from the [latest release](https://github.com/CPlusPlus17/Redoubt/releases/latest)**,
  installed over the old one. Redoubt has an opt-in update check
  (Settings → Check for updates), off by default.

## Install and verify

Download from the [latest release](https://github.com/CPlusPlus17/Redoubt/releases/latest):

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

`SHA256SUMS.signed` lists the hashes of the signed APKs; the file itself is not
signed. It catches a corrupted download. The signing-certificate check is what
proves an APK is Redoubt's. The certificate's SHA-256 digest must be:

    64:14:EB:33:46:81:CF:6E:92:90:34:B5:6A:06:2D:2B:8D:A0:90:82:21:72:F7:A3:95:2C:85:FD:D1:28:3B:D0

`apksigner` prints the same digest in lower case without colons:
`6414eb334681cf6e929034b56a062d2b8da090822172f7a3952c85fdd1283bd0`. To check on
the phone instead, an app such as AppVerifier compares package name
`org.redoubtbrowser` with that digest.

Every Redoubt APK is signed with this one key (APK signature schemes v2 and v3).
If the digest differs, do not install it, and report it privately (see
[Security](#security-and-bug-reports)). The key and its custody are documented
in [`docs/android/SIGNING.md`](docs/android/SIGNING.md).

**Updates with Obtainium.** To be told about new releases, add
`https://github.com/CPlusPlus17/Redoubt` as an app in
[Obtainium](https://github.com/ImranR98/Obtainium) and set **Filter APKs by
regular expression** to `arm64-v8a` (or your ABI). Obtainium does not check the
signing certificate for you: verify the first install as above. After that,
Android refuses any update not signed with the same key. The project has not yet
tested Obtainium itself; if it offers the version you already have, install it
once, and from then on it tracks releases by tag.

## What it changes compared with Firefox for Android

In one sentence, and the full measured comparison behind it:

> Redoubt ships the same privacy configuration and the same Gecko-level security
> patches as LibreWolf desktop, on a platform whose process containment is
> weaker — and we publish exactly where.

That "where" is [`docs/android/PARITY.md`](docs/android/PARITY.md). In short:

- **LibreWolf's configuration, built in.** Gecko and the Android app are compiled
  from Firefox's source with LibreWolf's shared patch set and preference
  configuration applied.
- **Telemetry and experiments removed**: the Glean upload path, Adjust, Nimbus
  experiments, crash-report uploads and Google Play Services are patched out;
  sponsored shortcuts are removed and search suggestions are off by default.
- **LibreWolf's privacy defaults**: resist-fingerprinting (with a switch in
  Settings → Privacy and security → Global privacy controls), strict Enhanced
  Tracking Protection and cookie partitioning (both locked), Global Privacy
  Control on, WebGL only for sites you allow.
- **Stronger site isolation than stock**: Fission is locked to isolate
  high-value sites; stock Firefox for Android does not turn it on by default.
- **uBlock Origin preinstalled**, with its cookie-notice lists on by default.
- **Cloud features off**, such as Shake to Summarize, IP Protection and Google Lens.

### Honest limits

- **No content-process sandbox.** Firefox's Gecko content sandbox does not exist
  on Android (upstream never finished the port). Per-site process isolation and
  RLBox recover part of it. On **Android 12 and newer**, web pages run in Android's
  isolated processes (since 158.0-2); H.264, HEVC and AAC are decoded in a separate,
  non-isolated decoder process, which is the remaining attack surface
  ([`docs/android/ISOLATION-MEDIA.md`](docs/android/ISOLATION-MEDIA.md)). On
  **Android 8–11** isolated processes are not used.
- **Not everything is proven on a phone.** HTTPS-only, certificate revocation,
  the TLS floor and fingerprinting coherence pass on emulators but stay marked
  *Partial* in `PARITY.md` until measured on a phone. DNS over HTTPS is off by
  default, as in LibreWolf, and since Beta 2 the app's DoH setting starts from
  LibreWolf's values (Quad9 preselected, LibreWolf's provider list). The app
  rewrites the `network.trr.*` prefs on every start, so turn DoH on in
  Settings > DNS over HTTPS, not in `about:config`. Which resolver is used once it
  is on has not been measured yet.
- **Testing is mostly on emulators.** Every release passes automated acceptance on
  Android 11, 12 and 14 emulators. On 2026-10-14 the signed 158.0-2 release also
  ran on two phones, a Pixel 9a (Android 17) and a Xiaomi Mi 8 (LineageOS,
  Android 15): isolated content processes, 1080p H.264, VP9 and AV1 video with no
  dropped frames, common sites, no crashes. The maintainer also tested an arm64
  development build on a Pixel 10 Pro. **Not yet tested:** phones with 4 GB of RAM
  or less, Android 8–11 hardware, and real password managers. Reports from real
  devices are welcome.
- **One person holds the signing key, and it is not offline.** The release key and
  the update-signing key are passphrase-protected files on the maintainer's
  workstation, with offline backups; CI builds on a separate machine and never has
  a key. Moving the keys to a hardware security key is planned
  ([`docs/android/YUBIKEY.md`](docs/android/YUBIKEY.md)). There is no second key
  holder. Redoubt is not on Google Play, and this key will not be given to Google.
- **Some password managers do not offer passkeys to Redoubt yet.** See
  [Passwords and passkeys](#passwords-and-passkeys).
- **A small project.** If you want a mature, widely used hardened Firefox for
  Android today, [IronFox](https://gitlab.com/ironfox-oss/IronFox) is that, and it
  is the browser LibreWolf itself recommends to Android users. How Redoubt differs
  is in [`docs/android/POSITIONING.md`](docs/android/POSITIONING.md).

### Known issues

- **Logging in on reddit.com does not work yet.** `reddit.com/login` stays blank
  (a white page), on a fresh profile and after visiting reddit.com; reading Reddit
  works. Turning off tracking protection for the site, allowing WebGL, turning off
  resist-fingerprinting or uBlock Origin, or requesting the desktop site did not
  fix it in our tests. Under investigation.
- **Two Firefox leftovers** are still in the app: the fox illustration in the
  site-protection panel, and a "Rate on Google Play" entry in Settings → About
  (Redoubt is not on Google Play). Both are to be removed in a coming release.

## How Redoubt is made

Redoubt has one maintainer. AI coding agents (Claude Code, Codex and local
models) write and check most of the code, patches, tests and documentation, run
the gates (the build, the Fenix unit-test suite, emulator acceptance) and record
the evidence. The maintainer sets the direction, decides the trade-offs, tests on
devices and signs the releases.

What you can check yourself:

- The preference configuration and the shared patch set are LibreWolf's; Gecko and
  Firefox for Android are Mozilla's.
- Redoubt's own changes are the 48 Android patches listed in
  [`assets/patches/android.txt`](assets/patches/android.txt) (files in
  [`patches/android/`](patches/android/)).
- Every release names its source commit and the SHA-256 of Mozilla's source tarball.
- The test evidence for every release is in
  [`docs/android/evidence/`](docs/android/evidence/).

## Sync with LibreWolf desktop

Sync is off by default. You can turn on Firefox Sync with a Mozilla account on
both Redoubt and LibreWolf desktop to share bookmarks, passwords, history and
open tabs. The maintainer tested this on 2026-10-04 with a 157 build; it has not
been re-tested on 158. There is no instant push, because Redoubt has no Google
services. See [`docs/android/SYNC.md`](docs/android/SYNC.md).

## Passwords and passkeys

**Passwords.** Redoubt works with any Android autofill service: Bitwarden,
KeePassDX, Proton Pass, Google Password Manager and others. Choose yours as
the autofill service in Android's settings. Normal login forms get
suggestions. Redoubt's own password saving is off by default.

Since 158.0-1, login fields inside open shadow roots (Reddit-style login forms,
for example) also reach your autofill service. This was tested with a test
autofill service, not yet with Bitwarden, KeePassDX or Proton Pass. Fields inside
closed shadow roots are still out of reach.

**Passkeys** need Android 14 or later. Redoubt passes passkey requests to
Android's Credential Manager, along with the site's address. Each password
manager then decides whether it trusts Redoubt as a browser:

- **KeePassDX**: works once you allow it. The first time Redoubt asks for a
  passkey, KeePassDX shows "App not recognized" and offers to add Redoubt to
  its privileged apps. You can also do this beforehand: Settings > Form
  filling > Passkeys settings > Privileged apps, then tick Redoubt.
- **Bitwarden**: when you pick a passkey, Bitwarden says Redoubt is an
  "Unrecognized browser". Choose **Trust** to add it to your own list of
  trusted apps. Redoubt is not on Bitwarden's community list of browsers yet;
  we plan to ask Bitwarden to add it, so that this step is no longer needed.
- **Proton Pass and Google Password Manager** check browsers against fixed
  lists that do not include Redoubt yet. Neither lets you add a browser
  yourself, so they offer no passkeys to Redoubt until their makers add it.

We took the KeePassDX and Bitwarden steps from their source code. The project
has not yet tested them with Redoubt on a phone.

**Passkey suggestions inside the username field** (WebAuthn "conditional
UI"; Reddit uses it) are not supported by Firefox for Android at all. Gecko
reports them as unavailable on Android, so Redoubt cannot offer them either.
Use the site's "Sign in with a passkey" button if it has one.

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
its branding (two leftovers in the app are listed under [Known issues](#known-issues)).

**Third-party components** shipped in the app: uBlock Origin 1.75.0 by Raymond
Hill (GPL-3.0; the unmodified addons.mozilla.org build, with its licence inside;
source at [github.com/gorhill/uBlock](https://github.com/gorhill/uBlock)), the
Firefox Translations engine and models (MPL-2.0; see
[`assets/translations/`](assets/translations/)), and Mozilla's localisation
strings (MPL-2.0, pinned by hash).

## Security and bug reports

- **Security vulnerabilities, signature mismatches or a suspicious download**:
  report privately via
  [GitHub private vulnerability reporting](https://github.com/CPlusPlus17/Redoubt/security/advisories/new)
  or by email to **security@redoubtbrowser.org** (no GitHub account needed).
  Process: [`docs/android/SECURITY.md`](docs/android/SECURITY.md).
- **Bugs in Gecko or Firefox for Android itself** belong with Mozilla
  (Bugzilla); the issue form asks whether stock Firefox shows the same problem.
- **Other bugs**: [open an issue](https://github.com/CPlusPlus17/Redoubt/issues/new/choose)
  using the Android bug form. Triage is described in
  [`docs/android/TRIAGE.md`](docs/android/TRIAGE.md). Questions go to
  [Discussions](https://github.com/CPlusPlus17/Redoubt/discussions).

## Where things are

| path | what |
|---|---|
| [`docs/android/`](docs/android/) | the Android work: plan, decisions, evidence ([`README.md`](docs/android/README.md) is the index) |
| [`docs/android/PARITY.md`](docs/android/PARITY.md) | what Redoubt does and does not match, measured |
| [`docs/android/IDENTITY.md`](docs/android/IDENTITY.md) | why this is called Redoubt, and what stays named `librewolf` |
| [`docs/android/SIGNING.md`](docs/android/SIGNING.md), [`YUBIKEY.md`](docs/android/YUBIKEY.md) | the signing keys, their custody, and the planned move to a hardware key |
| [`docs/android/BUILD.md`](docs/android/BUILD.md), [`REPRODUCIBLE.md`](docs/android/REPRODUCIBLE.md) | building GeckoView and the APK; reproducibility so far covers same-machine APK assembly only |
| [`patches/`](patches/), [`assets/patches/`](assets/patches/) | patches, and the common / desktop / android lists that select them |
| `settings/` | submodule with the preference configuration ([Redoubt-settings](https://github.com/CPlusPlus17/Redoubt-settings), from LibreWolf's settings) |
| [`.github/workflows/`](.github/workflows/) | Android test and release builds |

The repository is large (about 600 MB), mostly per-release test evidence. To read
the code without it:

    git clone --filter=blob:none --sparse https://github.com/CPlusPlus17/Redoubt.git
    cd Redoubt
    git sparse-checkout set --no-cone '/*' '!/docs/android/evidence/'

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
