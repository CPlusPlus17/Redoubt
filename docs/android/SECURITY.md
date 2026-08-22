# Security disclosure — Redoubt (Android)

Redoubt is a fork that ships on the Firefox **ESR** track, so its security
posture and its disclosure process differ from both desktop LibreWolf and from
the stock browser it is built from. This page is the disclosure process, and it
is written for the three failure modes the Android port adds: an **APK
signature** problem, a **distribution-channel** problem, and a **device-specific**
attack surface.

It extends — it does not replace — the process inherited from the source tree
(`mobile/android/fenix/SECURITY.md`): for a bug in Gecko or Fenix itself,
Mozilla's own security path still stands. What is added here is the part that
is specifically Redoubt's.

## Reporting a vulnerability

**The tracker for this project is GitHub, not Codeberg. No path below requires
a Codeberg account.**

- **A bug in Gecko, or in Fenix (the Android app layer), inherited from upstream**
  — use Mozilla's process, as the source tree's `SECURITY.md` directs:
  Bugzilla `Fenix::Security`, or Mozilla's client security reporting / bug-bounty
  pages. This is the same path any downstream of Firefox uses, and it is not
  this project's to gate.
- **A bug in Redoubt specifically** — in the port, the patch set as applied here,
  the packaging, the signing, or the distribution channel — open it on GitHub:
  <https://github.com/CPlusPlus17/Redoubt/issues>, or use GitHub's private
  vulnerability reporting for this repository so the report is not public before
  a fix ships. Either needs only a GitHub account; neither needs Codeberg.
- **If you do not have any account and need to report privately**, say so in the
  report and the maintainer will give an out-of-band channel rather than ask you
  to create one first.

Please include: the affected Redoubt version and the ESR version underneath it,
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

### 2. Distribution-channel compromise

A malicious or tampered APK served under the project's name — on the F-Droid
repository, the direct-download host, or a mirror — is a supply-chain event even
if the signing key itself is intact. The channel is currently an open
placeholder (`<PROJECT_DOMAIN>`), so the controls are stated generically and the
concrete host is filled in when it is decided:

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

### 3. Device-specific surface

Android-specific bugs that do not exist on desktop (permission model, the Kotlin
app layer, the app zygote / process separation) are reported through the same
GitHub path. They are tracked with the device and Android version from the triage
template, because "reproduces on this device only" is a real and common outcome
here.

## Turnaround for a critical Gecko security release

This is stated honestly, in two layers, because confusing the two is how a
number that is not a promise starts to read like one.

**Mozilla's layer (a fact, not a promise).** Redoubt is on the ESR track, so a
Gecko security fix that Mozilla ships out of band to Firefox *release* reaches
Redoubt only when it reaches Firefox ESR. Measured from Mozilla's advisory
history (`docs/android/TRACK.md` §3a–3b): roughly half of release-channel fixes
land in ESR the same day; the rest have a **median of 14 days, worst observed 21
days**. Some fixes do not backport to ESR at all and wait for the next ESR major
(up to ~13 months). And because **there is no Firefox for Android ESR channel**,
an Android-only advisory has no ESR counterpart and is triaged individually — a
named obligation, not an automatic uplift.

**Redoubt's layer (the target, ours to set and ours to meet).** On top of
Mozilla's ESR latency, once the ESR security tarball is published:

- **Critical (public exploit, or active in-the-wild):** target a published,
  signed APK **within 72 hours** of the ESR security tarball landing on
  `archive.mozilla.org`, on a warm build environment. If that cannot be met, the
  expected date is published within the same window rather than left silent.
- **High (no known exploitation):** the next scheduled ESR dot release, with the
  backport decision documented.
- **Android-only (no ESR counterpart):** triaged individually; the outcome
  (backported / not applicable / not backported and why) is published.

The 72-hour figure is a target to be met, not a guarantee, and it is the
maintainer's to ratify; it is deliberately not folded together with Mozilla's
14-day ESR latency into a single number, because that single number would look
like a promise Redoubt does not control.

## The watch obligation

Because there is no Firefox for Android ESR channel, the standing obligation is
that **a named owner reads every "Firefox for Android" MFSA and decides per
advisory whether to backport it into this tree** (`docs/android/TRACK.md` §3c).
That owner is the same named triage owner in `docs/android/TRIAGE.md` — a
placeholder until one is named; this page names the *role*, not a person.

## Disclosure timeline

A fix is not announced before it ships. The order is: fix available to build →
published signed APK on the channel → public note (advisory, affected versions,
the workaround if any, and the sha256 of the fixed build). A reporter is credited
only if they ask for it.

## Status

Not all of this is operational yet, and it is not pretending to be. The
distribution channel is `<PROJECT_DOMAIN>` (open placeholder — see
`docs/android/DISTRIBUTION.md`), the signing key is generated in LW-M6-01, and
the 72-hour target is the maintainer's to ratify. What this page fixes now is the
*shape* of the process and the two failure modes that are specific to Android,
so that when an incident actually happens the steps are already written down.
