# Security disclosure — Redoubt (Android)

Redoubt is a fork that ships on the Firefox **release** track (since
2026-10-02, `157.0-1` from Beta 4 on; Betas 1 to 3 were on ESR 153, see
`docs/android/TRACK.md`), so its security posture and its disclosure process differ from both desktop LibreWolf and from
the stock browser it is built from. This page is the disclosure process, and it
is written for the three failure modes the Android port adds: an **APK
signature** problem, a **distribution-channel** problem, and a **device-specific**
attack surface.

It extends — it does not replace — the process inherited from the source tree
(`mobile/android/fenix/SECURITY.md`): for a bug in Gecko or Fenix itself,
Mozilla's own security path still stands. What is added here is the part that
is specifically Redoubt's.

## Reporting a vulnerability

**The tracker for this project is GitHub.** A private report needs no account
at all: email works.

- **A bug in Gecko, or in Fenix (the Android app layer), inherited from upstream**
  — use Mozilla's process, as the source tree's `SECURITY.md` directs:
  Bugzilla `Fenix::Security`, or Mozilla's client security reporting / bug-bounty
  pages. This is the same path any downstream of Firefox uses, and it is not
  this project's to gate.
- **A bug in Redoubt specifically** — in the port, the patch set as applied here,
  the packaging, the signing, or the distribution channel — report it privately,
  so it is not public before a fix ships:
  - by email to **security@redoubtbrowser.org** (no account needed), or
  - through GitHub's private vulnerability reporting for this repository:
    <https://github.com/CPlusPlus17/Redoubt/security/advisories/new>.

  Non-security bugs go to the public tracker:
  <https://github.com/CPlusPlus17/Redoubt/issues>.

Please include: the affected Redoubt version and the Firefox version underneath it,
the device and Android version, where the APK came from (which channel, which
build), and — for a suspected compromised build — the APK's sha256 and its
signature. The triage template in `docs/android/TRIAGE.md` collects exactly this.

## What this process covers that desktop does not

### 1. Signature compromise

The APK signing key is a **one-way trust root**. It is the same severity as
losing the key itself: a replacement key is a *different app* to Android — no
upgrade path, no data migration, every install reinstalls by hand (see
`docs/android/PARITY.md` §3.2 and `docs/android/IDENTITY.md`). There is no
"roll the key and push an update" move on this platform the way there is on
desktop.

So the response is about containment, not silent rotation:

1. **Stop signing** with the compromised key; do not publish another build from it.
2. **Pull / flag** every build signed by it on every channel (F-Droid repository,
   direct download, any third party that mirrored it) and say so to users, with
   the sha256 of the affected build(s) so they can check what they have.
3. **State the upgrade path honestly.** A new key is a new install. Tell users
   what they must do by hand rather than implying an in-place update.
4. **Record the incident** (key fingerprint, affected builds, channel, date) in a
   dated note so the next incident can be diffed against it.

**Google never gets this key (decided 2026-10-14).** Redoubt is not on Google
Play. The 2026-10-05 plan to upload the release key to Play App Signing was
reversed before anything was uploaded (`SIGNING.md`, "Google Play"). If Redoubt is
ever published on Play, it uses a separate, Play-only key, so nothing that happens
on Google's side can produce an update that GitHub or F-Droid installs accept.

### 2. Distribution-channel compromise

A malicious or tampered APK served under the project's name — on the F-Droid
repository, the GitHub release, or a mirror — is a supply-chain event even if the
signing key itself is intact. The channels today: the APKs on GitHub Releases
(since 2026-10-05), the Redoubt F-Droid repository in a Hetzner Object Storage
bucket (since 2026-10-14), and the signed update document on `redoubtbrowser.org`
(GitHub Pages). Redoubt is not on Google Play or Accrescent.

- **F-Droid repository integrity first.** A F-Droid repository is signed and the
  client verifies it; a compromised *build* is caught by the repository signature
  if the signing key is safe. If the channel is compromised but the key is safe,
  the fix is to **republish from a known-good key and pull the bad build**, not to
  rotate the key.
- **Pinned, checksummed artifacts.** Every published APK ships with its sha256,
  and the client's update check compares against it (see `docs/android/DISTRIBUTION.md`).
  A tampered artifact does not match and is refused, independent of which channel
  served it.
- **Mirror discipline.** Mirrors are read-only copies of a single source of truth.
  If a mirror serves something different from the origin, the mirror is the
  incident: pull it and treat its audience as channel-compromised.
- **The own F-Droid repository (LW-M6-03, 2026-10-05).** It is served from the owner's
  Hetzner Object Storage bucket, so Hetzner and the Hetzner account (its S3 credentials, kept
  in a project of their own and in a mode-600 file outside any checkout) are part of this
  channel. The human page is on the GitHub Pages site. Its index is signed with a third key,
  the F-Droid repository key (`SIGNING.md`, "The F-Droid repository key"), which vouches for
  the index, not for the APKs. The APKs keep the release key, so a stolen repository key or
  stolen S3 credentials can withhold updates, or offer an older Redoubt (every release is kept
  in the archive), but cannot replace the app. A stolen S3 key cannot sign an index at all:
  clients refuse any index not signed by the pinned key. `deploy` never overwrites or deletes an
  APK in the bucket, uploads the index last, and refuses a local APK whose sha256 differs from
  the signed index. For an APK already in the bucket, `deploy` compares only size and MD5
  (size only for a multipart upload); `verify` checks every served APK byte for byte (`FDROID.md`). A lost or
  replaced repository key means every F-Droid user re-adds the repository by hand.

### 3. Device-specific surface

Android-specific bugs that do not exist on desktop (permission model, the Kotlin
app layer, the app zygote / process separation) are reported through the same
GitHub path. They are tracked with the device and Android version from the triage
template, because "reproduces on this device only" is a real and common outcome
here.

## Turnaround for a critical Gecko security release

This is stated honestly, in two layers, because confusing the two is how a
number that is not a promise starts to read like one.

**Mozilla's layer (a fact, not a promise).** Redoubt builds Firefox *release*
source (`version.android`), the same tree Firefox for Android ships from. A
Gecko security fix that Mozilla ships out of band as a Firefox dot release is
in that dot's source tarball the day it ships, and Firefox for Android fixes
(GeckoView, android-components, Fenix) are in the release tree like any other
fix. The ESR latency this section used to quote (median 14 days, worst 21,
`docs/android/TRACK.md` §3a-3b) no longer applies. One case is not covered by
a tarball: Mozilla sometimes ships an Android-only dot release with no
desktop source tarball (153.0.2 was one; see `docs/android/PARITY.md` §7.4).

**Redoubt's layer (the target, ours to set and ours to meet).** Once Mozilla
publishes the release source tarball carrying the fix:

- **Critical (public exploit, or active in-the-wild):** target a published,
  signed APK **within 72 hours** of the security tarball landing on
  `archive.mozilla.org`, on a warm build environment. If that cannot be met, the
  expected date is published within the same window rather than left silent.
- **High (no known exploitation):** the next Firefox release rebase (every two
  weeks since Firefox 155), or the dot release that carries it.
- **Android-only with no source tarball:** the fix is taken from Mozilla's
  release branch and the outcome is published.

The 72-hour figure is a target, not a guarantee, and the maintainer has not
ratified it yet, so the public pages give the record instead of a number. It is
ours alone: Mozilla's part is now the day the fix ships, not a separate ESR lag.
The record so far: Firefox 158.0 (2026-10-13) reached Redoubt as 158.0-1 the next
day; Firefox 157.0.1 (2026-10-06) reached Redoubt as 157.0.1-1 on 2026-10-10.

## The watch obligation

On the release track there is no backport obligation for Firefox for Android
advisories: they arrive with the rebase (`docs/android/TRACK.md`, "Decision
reversed 2026-10-02"). What remains is to rebase promptly and to check, per
advisory, that the shipped build is not behind it.
`scripts/firefox-release-watch.py` opens an issue for each new
`LATEST_FIREFOX_VERSION`, and one for each Android-only Firefox for Android
release in `mobile_versions.json`, saying whether it has a source tarball.
Since LW-M7-47 it also reads Mozilla's advisory files
(mozilla/foundation-security-advisories). An advisory fixed in a Firefox
newer than the published release is posted on the release issue (or opens
its own), with its impact and CVEs, label `security` and the owner assigned
and mentioned. The owner is reminded every 24 h until the issue closes
(`docs/android/RELEASE-WATCH.md`). Matching the version is automatic.
Reading the advisory is not:
every MFSA titled "Firefox for Android" is still read by the triage owner named
in `docs/android/TRIAGE.md`. The current coverage record, with the nine
Android CVEs the ESR tree lacked and how the move to 157 closed them, is
`docs/android/PARITY.md` §7.

## Disclosure timeline

A fix is not announced before it ships. The order is: fix available to build →
published signed APK on the channel → public note (advisory, affected versions,
the workaround if any, and the sha256 of the fixed build). A reporter is credited
only if they ask for it.

## Status (2026-10-14)

The channels are live: GitHub Releases since 157.0-2 (2026-10-05), the in-app update
check since 157.0-2 (opt-in), the Redoubt F-Droid repository since 2026-10-14. The
release key was generated on 2026-08-23 (LW-M6-01); where it lives, and the planned
move to a YubiKey, are in `SIGNING.md` and `YUBIKEY.md`. Private reports reach the
maintainer through GitHub's private vulnerability reporting or
security@redoubtbrowser.org. The 72-hour target above is not yet ratified.
