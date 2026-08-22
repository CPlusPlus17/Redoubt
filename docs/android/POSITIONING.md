# What Redoubt is — and what it is not

**Redoubt is not the LibreWolf project.** It is an independent fork of
LibreWolf's source, maintained by someone who is not a LibreWolf developer;
LibreWolf has not built, endorsed, or supported it. That one sentence is the
whole of the naming question, and this page exists to support it with the
honest detail rather than to soften it.

## What Redoubt is

Redoubt is a privacy-hardened Firefox for **Android**. What sets it apart is
the build model: it compiles Gecko from source and applies LibreWolf's patch
set and preference configuration — the same shared set the desktop build uses
— rather than patching a prebuilt Fennec. That is a real difference, and it is
also the expensive one.

It is doing the Android work LibreWolf has explicitly declined: LibreWolf's own
FAQ says nobody is working on an Android version and **recommends using IronFox
as the alternative**. That is precisely the gap this fork fills, and precisely
why it has to be clear that it is not LibreWolf.

## Where the work actually comes from

The privacy configuration is the product, and it is **LibreWolf's**, not this
project's. Roughly 260 preference decisions in `settings/librewolf.cfg` and the
patch set that makes them enforceable are LibreWolf's work, under MPL-2.0. This
is stated up front, not buried in a licence footer: installing Redoubt for its
privacy posture means installing LibreWolf's work, ported to a platform
LibreWolf does not ship, by someone who is not LibreWolf.

While porting, this fork also found three defects in the upstream source (a
supply-chain gap in the l10n fetch, a fails-open patch test, and a beta-tarball
naming bug) and documented them as reproductions worth reporting back. See
`docs/android/UPSTREAM-REPORTS.md`.

## The space is already occupied

IronFox (<https://ironfoxoss.org>) already does what this project is reaching
for: a maintained, privacy-hardened Firefox for Android that people actually
install. As of 2026-08-22 it is **released and installable today** — through a
F-Droid repository (<https://fdroid.ironfoxoss.org/fdroid/repo>) and a public
download page (<https://ironfoxoss.org/download>) — and actively maintained
(source at <https://github.com/ironfox-oss/IronFox>). It is also the browser
LibreWolf itself points Android users to.

The honest gap, named plainly: **IronFox ships a browser people use. Redoubt
does not.** It has no public build, no download, and no users yet. A
positioning page that could not say that is marketing, not positioning, so it
is said here.

What Redoubt does that IronFox does not is the build model: it compiles Gecko
from source with LibreWolf's shared patch set and pref configuration. That is a
genuine difference, and it is not a reason to pretend the other gap away.

## What Redoubt is and is not

- **The privacy configuration and the Gecko-level security/privacy patches are
  the shared set LibreWolf desktop uses** (the common `settings/` tree and the
  shared patch lists).
- **Platform containment is weaker than desktop, and it is published exactly
  where.** Redoubt has **no Gecko content-process sandbox** (`MOZ_SANDBOX` is off
  on Android and the upstream port is unfinished). Per-site process isolation,
  RLBox JS/WASM sandboxing, and compiler memory hardening recover most — not all
  — of it.
- **Several properties are configured but not yet proven honoured on a live
  page** (HTTPS-only, certificate revocation, the TLS floor, resist-fingerprinting
  coherence, the enterprise-policy mappings). In `docs/android/PARITY.md` these
  are *Partial* or *Pending*, not *Equivalent*.
- **It cannot carry LibreWolf's signing-key identity.** A fork is a distinct
  trust root — a platform fact, not a configuration choice.
- **It is not published yet.** The applicationId and the hosting domain are still
  open placeholders, and the current build still ships in the `org.mozilla`
  namespace. Nothing here should be read as an available download.

The full measured matrix, including the rows still pending on a live device, is
in `docs/android/PARITY.md`.

## Relationship to Mozilla / Firefox

Redoubt is not affiliated with, endorsed by, or a product of Mozilla. It builds
on Mozilla's Firefox (Gecko) source, and no Mozilla trademarks appear in its
user-facing branding. The same MPL-2.0 / section-3.4 reasoning that keeps this
project out of the LibreWolf name also keeps it out of the Firefox name.

## Status

Not published. Before any public build: the `<PROJECT_ID>` applicationId and the
`<PROJECT_DOMAIN>` hosting domain must be decided (both one-way, both still open
placeholders), the branding must stop shipping as `org.mozilla`, and the final
public wording above must be approved by the owner. Until then this page
describes intent and measurement, not a product on a shelf.
