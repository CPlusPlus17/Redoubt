# What Redoubt is — and what it is not

*Updated 2026-10-14, for Redoubt 158.0-2.*

**Redoubt is not the LibreWolf project.** It is an independent fork of
LibreWolf's source, maintained by someone who is not a LibreWolf developer;
LibreWolf has not built, endorsed, or supported it. That one sentence is the
whole of the naming question, and this page exists to support it with the
honest detail rather than to soften it.

## What Redoubt is

Redoubt is a privacy-hardened browser for **Android**, built from Firefox's
source with LibreWolf's privacy configuration and the patch set LibreWolf's
desktop build shares with it. The current release is 158.0-2, on Firefox's
regular release track; the first stable release was 157.0-2 on 2026-10-05.

It is doing the Android work LibreWolf has explicitly declined: LibreWolf's own
FAQ says nobody is working on an Android version and **recommends IronFox as the
alternative**. That is the gap this fork tries to fill, and precisely why it has
to be clear that it is not LibreWolf.

## Where the work actually comes from

The privacy configuration is the product, and it is **LibreWolf's**, not this
project's. Roughly 260 preference decisions in LibreWolf's `librewolf.cfg` (from
which Redoubt's `settings/common.cfg` and `android.cfg` are derived) and the patch
set that makes them enforceable are LibreWolf's work, under MPL-2.0. Installing
Redoubt for its privacy posture means installing LibreWolf's work, ported to a
platform LibreWolf does not ship, by someone who is not LibreWolf.

While porting, this fork also found three defects in the upstream source (a
supply-chain gap in the l10n fetch, a fails-open patch test, and a beta-tarball
naming bug) and documented them as reproductions; no upstream filing is recorded
yet. See [`UPSTREAM-REPORTS.md`](UPSTREAM-REPORTS.md).

## How Redoubt is made

Redoubt has one maintainer. AI coding agents (Claude Code, Codex and local
models) write and check most of the code, patches, tests and documentation, run
the gates (the build, the Fenix unit-test suite, emulator acceptance) and record
the evidence in [`evidence/`](evidence/). The maintainer sets direction, decides
the trade-offs, tests on devices and signs releases.

What anyone can check without trusting that process: the preference
configuration and the shared patch set are LibreWolf's; Gecko and Firefox for
Android are Mozilla's; Redoubt's own changes are the 48 Android patches listed in
`assets/patches/android.txt` (files in `patches/android/`); every release names its
source commit and the SHA-256 of Mozilla's source tarball; and the test evidence
for every release is in `docs/android/evidence/`.

## Redoubt and IronFox

IronFox (<https://ironfoxoss.org>) is a maintained, privacy-hardened Firefox for
Android that people already use, and it is the browser LibreWolf points Android
users to. If you want the established option, use IronFox.

**Where IronFox is ahead**, as of 2026-10-14:

- **Maturity and users.** IronFox is a fork of Divested Computing Group's Mull
  ([IronFox README](https://gitlab.com/ironfox-oss/IronFox), read 2026-10-14), with
  that project's history behind it. Redoubt's first stable release was 2026-10-05.
- **People.** Redoubt has one maintainer and one signing-key holder.
- **Channels.** IronFox is on Accrescent as well as its own F-Droid repository and
  direct download ([IronFox FAQ](https://ironfoxoss.org/docs/faq), read 2026-10-14).
  Redoubt is on GitHub Releases, its own F-Droid repository and Obtainium, not on
  Accrescent.
- **Push notifications.** IronFox removes Firebase messaging and adds UnifiedPush
  (IronFox FAQ). Redoubt removes Firebase messaging and has no replacement, so web
  push does not work.
- **Exploit-surface defaults.** IronFox disables the JavaScript JIT and WebGL by
  default (IronFox FAQ). Redoubt keeps the JIT on, as LibreWolf desktop does, and
  blocks WebGL per site until you allow it.
- **Dot-release speed so far.** Firefox 157.0.1 came out on 2026-10-06; IronFox
  shipped it on 2026-10-07, Redoubt on 2026-10-10 (dates from the IronFox GitLab
  releases and Mozilla's product-details). Firefox 158.0 came out on 2026-10-13;
  Redoubt shipped 158.0-1 on 2026-10-14, and IronFox had not released 158 by then.
  Two data points are not a pattern.

Both build Gecko from Firefox's source (IronFox pins Gecko 158.0 by commit and
SHA-512 in `scripts/versions.sh` on its `dev` branch, read 2026-10-14), so building
from source is not a difference.

**What Redoubt does differently:**

- **LibreWolf's configuration and patch set**, measured row by row against
  LibreWolf desktop in [`PARITY.md`](PARITY.md), including where Android falls short.
- **Resist-fingerprinting on by default**, with a switch in Settings.
- **Isolated content processes on by default on Android 12 and newer** (since
  158.0-2), with H.264 and AAC video still playing ([`ISOLATION-MEDIA.md`](ISOLATION-MEDIA.md)).
  This is a statement about Redoubt, not a claim that IronFox lacks it.
- **Sync with LibreWolf desktop** through a Mozilla account, off until you sign in
  ([`SYNC.md`](SYNC.md)).
- **An opt-in, signed update check**, off by default ([`DISTRIBUTION.md`](DISTRIBUTION.md)).

### Why not contribute to IronFox instead?

Because the point of Redoubt is a different base: LibreWolf's own preference file
and patch set, kept in step with LibreWolf desktop so that the two behave alike and
can share a Sync account, with every difference written down in `PARITY.md`.
IronFox has its own configuration and its own decisions, which is a legitimate and
different choice. Folding LibreWolf's configuration into IronFox would make it a
different browser from the one its users chose.

## What Redoubt is and is not

- **The privacy configuration and the Gecko-level security/privacy patches are
  the shared set LibreWolf desktop uses** (the common `settings/` tree and the
  shared patch list).
- **Platform containment is weaker than desktop, and it is published exactly
  where.** Redoubt has **no Gecko content-process sandbox** (`MOZ_SANDBOX` is off
  on Android and the upstream port is unfinished). Per-site process isolation,
  RLBox JS/WASM sandboxing, compiler memory hardening and, on Android 12 and newer,
  Android's isolated processes recover part of it — not all of it. On Android 8–11
  isolated processes are not used.
- **Not everything is proven on a live page.** [`PARITY.md`](PARITY.md) marks each
  row *Equivalent*, *Partial* or *Pending* with its evidence.
- **It cannot carry LibreWolf's signing-key identity.** A fork is a distinct
  trust root — a platform fact, not a configuration choice. Redoubt's own key,
  its fingerprint and its custody are in [`SIGNING.md`](SIGNING.md).
- **Testing is mostly on emulators.** Every release passes an emulator acceptance
  (for 158.0-2: Android 11, 12 and 14). On 2026-10-14 the signed 158.0-2 arm64 release was also
  run on a Pixel 9a (Android 17) and a Xiaomi Mi 8 (LineageOS, Android 15); the
  maintainer earlier tested an arm64 development build on a Pixel 10 Pro
  (Android 17). Phones with 4 GB of RAM or less, Android 8–11 hardware and real
  password managers are untested.

## Relationship to Mozilla / Firefox

Redoubt is not affiliated with, endorsed by, or a product of Mozilla. It builds
on Mozilla's Firefox (Gecko) source, and its name, logo and icons are its own.
Two Firefox leftovers are still in 158.0-2 and are to be removed: the fox
illustration in the site-protection panel, and a "Rate on Google Play" entry in
Settings → About. The same MPL-2.0 reasoning that keeps this project out of
the LibreWolf name also keeps it out of the Firefox name.
