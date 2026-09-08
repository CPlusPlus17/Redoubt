# Distribution and the update-check contract — Redoubt (Android)

## First Android beta on GitHub

The owner requested GitHub Releases distribution on 2026-09-08 for the four
approved signed beta APKs. The publication target is the public prerelease
[`android-153.0esr-1-beta.1`](https://github.com/CPlusPlus17/Redoubt/releases/tag/android-153.0esr-1-beta.1).
It contains the ARM64, ARM32, x86_64 and universal APKs under their existing
`fenix-*-release.apk` filenames, plus `SHA256SUMS.signed`. The release notes
include the signing fingerprint and verification commands.

This beta has no in-app update check or update notification; later APKs must be
obtained from Releases and installed over the current build. Obtainium integration
has not been verified. F-Droid and Accrescent publication remain separate work.
The following sections describe the future signed-endpoint contract; no such
endpoint is supplied by publishing a GitHub prerelease.

Redoubt is a fork that ships on the Firefox **ESR** track, and the direct-APK
distribution has no app store to tell its users an update is out. This page is
the contract for the one mechanism that fills that gap — an in-app version check
against a signed, static endpoint — and for the two channels that already have
their own updater (**F-Droid** and **Accrescent**), which must not double-notify.

It is the contract half of LW-M6-06. The code half is
`patches/android/update-check.patch` (`org.mozilla.fenix.lw.UpdateCheck`, landed
2026-09-02); the endpoint itself still depends on the distribution domain, which
is `redoubtbrowser.org` (`docs/android/IDENTITY.md`, decided 2026-08-23 — the
domain is registered and resolves; what does not exist yet is anything served on
it). **No path on this page is live**, and no verification key is checked in — a build made without one has
the check compiled out (see "F-Droid and Accrescent do not double-notify").

This page fixes the *shape* of the check and its privacy boundary so that the one
thing a privacy browser must not do (a silent, always-on phone-home) is ruled out
by design rather than by convention. Where the implementation sharpened the
contract, this page says so in place.

## What the check may do, and what it may not

Two lines from the task bound everything below:

- **Do not build a silent self-updater.** The check tells the user a new version
  exists and links to the download. It does not download, install, or apply
  anything.
- **Do not add a phone-home that runs without consent.** The check is off by
  default and, when on, sends nothing that identifies the client — not even the
  version string.

The risk the task names is the one that sets the defaults: *"an always-on update
ping is a periodic beacon with an IP address attached — exactly what users came
here to avoid."* So the check is **opt-in, foreground-only, and rate-limited** —
not a background timer.

## The three invariants this must satisfy

These are LW-M6-06's acceptance criteria, restated as things that must hold:

1. **The check sends no identifier beyond the version string.** No device id, no
   install id, no user id, no telemetry, no per-install value in any header. As
   implemented it sends less than the acceptance wording allows: not even the
   version string (see "What the client sends").
2. **It is disclosed in the UI and can be turned off.** A visible setting, a
   plain description of what it sends and where, and a switch that stops it
   entirely.
3. **F-Droid and Accrescent installs do not double-notify.** Those channels ship
   their own update notification; the in-app check is not present in those builds.

## The endpoint

The endpoint is a single static document, served over TLS, on the distribution
host:

    ENDPOINT  https://redoubtbrowser.org/updates/android/latest.json

`redoubtbrowser.org` is the decided domain (`docs/android/IDENTITY.md`, 2026-08-23);
it is registered and resolves to a parking page. **Nothing is served at this path
yet** — that is the open half, not the hostname. Earlier revisions of this page
called the domain "an open placeholder" and "not a real hostname", which
contradicted IDENTITY.md's "no placeholders remain"; the contradiction is the thing
to avoid restoring. The path is a contract constant both the client and the
server must implement (and can be renamed in one place when the layout is
decided); the host is the only undecided part, and the URL does not resolve until
`redoubtbrowser.org` does.

### The document

A small, signed JSON document. The client treats any field it does not understand
as absent, and any document that fails signature verification as if it were not
there at all.

    {
      "latest_version":    "153.0.4-2",
      "download_url":      "https://redoubtbrowser.org/downloads/redoubt-153.0.4-2.apk",
      "release_notes_url": "https://redoubtbrowser.org/releases/153.0.4-2/",
      "sha256":            "<hex digest of the APK the download link points to>",
      "published_at":      "2026-08-22T00:00:00Z"
    }

    ENDPOINT.sig   base64 of the DER ECDSA P-256 / SHA-256 signature over the
                   exact bytes of ENDPOINT

- **latest_version** — the string the client compares against its own. This is
  the only thing the check needs to decide that a newer version exists.
- **download_url** — where the user is sent if they choose to update. Same
  `redoubtbrowser.org` host. Offering the link, not fetching it, is the app's job.
- **sha256** — the digest of the artifact the link points to.
  `docs/android/SECURITY.md` §2 already relies on a published, checksummed
  artifact; the digest lives here so there is one source of truth rather than two.
- **published_at** — so the client can treat a document that has not changed in an
  implausible amount of time as suspect rather than authoritative.
- **the signature** lives *next to* the document, not inside it (`latest.json.sig`).
  The first draft of this page put a `signature` field inside the JSON; a
  signature over a JSON object needs a canonical form (whitespace, key order,
  number formatting) agreed between the signing script and the Kotlin verifier,
  and a mismatch there is a silent "no update" forever. Signing the served bytes
  and shipping the signature beside them has nothing to get wrong. An unsigned or
  mis-signed document is refused, full stop — see below.

### Signing

"Signed, static endpoint" is doing real work. The document is served static, but
the client must not trust it merely because it is on our host: a compromised or
confused channel could serve a stale or malicious one, which is exactly the
failure mode `docs/android/SECURITY.md` §2 exists to describe. So:

- The document is signed with a key whose **public** half is embedded in the
  client at build time. The private half never leaves the signing host and never
  appears in this page or in the patch. Concretely: ECDSA P-256 with SHA-256
  (`SHA256withECDSA`, present on every Android release Fenix supports, unlike
  Ed25519 which needs API 33); the client is handed the base64 DER
  SubjectPublicKeyInfo through the Gradle property `lwUpdateCheckPubkey`, which
  `scripts/android-apk.sh` forwards from the environment variable
  `LW_UPDATE_CHECK_PUBKEY`. The maintainer's side is two openssl lines:

      openssl ec -in update-key.pem -pubout -outform DER | base64 -w0     # -> LW_UPDATE_CHECK_PUBKEY
      openssl dgst -sha256 -sign update-key.pem latest.json | base64 -w0 > latest.json.sig
- The client verifies the signature before reading a single field. **On
  verification failure it behaves exactly as if the check had been turned off**:
  no prompt, no remote log, no crash. A bad signature is not an error the user is
  shown; it is a "no update."
- The key is secret material owned by one of the skipped (`agent_safe:false`)
  distribution tasks — the APK signing key is LW-M6-01 per
  `docs/android/SECURITY.md` — and whether the document uses that key or a
  dedicated one is an implementation decision. This page states the requirement
  (the client must verify a signature it cannot itself produce), not the key.

## What the client sends

Nothing that identifies the client — and, as implemented, not even the version
string: the comparison happens on the device, so the server learns only that some
Redoubt asked.

    GET <ENDPOINT>        User-Agent: Redoubt-UpdateCheck/1
    GET <ENDPOINT>.sig    User-Agent: Redoubt-UpdateCheck/1

- **In the request** — a static `User-Agent` that is the same literal on every
  install, and nothing else: no device id, no install id, no user id, no add-on
  list, no locale, no model, no cookies (`CookiePolicy.OMIT`), no cache validators
  (`useCaches = false`, so no `ETag` / `If-Modified-Since` that could act as a
  per-install token), no redirects followed. `UpdateCheckerTest` pins every one of
  those request fields, because a packet capture cannot see inside TLS.
- **In the response** — the document above and its signature. The client verifies
  the signature, reads `latest_version`, compares it to its own, and that is the
  whole transaction.
- **On error** — any network failure, parse failure, or signature failure is
  handled locally and silently. There is no retry storm, no remote log, no
  telemetry of any kind. The most a failed check produces is an optional local log
  line a user can read.

## When it runs, and what it does

- **Opt-in.** Off by default. Enabling it is the user's action, in Settings. That
  is the consent the task requires. A default-on-but-disclosed alternative is
  permitted by the task; this page recommends opt-in, because it is the position a
  user of a privacy build is least likely to resent. The cost is only that a
  direct-APK user who wants the prompt must turn it on — a user who would rather
  have an auto-updating store can install from F-Droid or Accrescent instead.
- **Foreground only, rate-limited.** When enabled, the check runs at most once per
  day and only while the app is in the foreground (on launch, or when the user
  opens the relevant screen). No background service, no timer, no work queue. This
  is what keeps it from being the "periodic beacon" the risk line describes.
- **It never installs.** The prompt says a new version exists and offers the
  download link. Downloading and installing is the user's explicit act. This is
  the "not a silent self-updater" requirement, and it also keeps the check
  compatible with a user who updates through their own channel.

## Disclosure and the off switch

- **A visible setting.** "Check for updates" as its own row in Settings, with a
  switch. Not buried, and not only on the About screen.
- **A plain-language description** beside it, stating exactly: what is sent (the
  nothing that identifies the device — not even the version string), where it goes (the endpoint on the distribution
  host), what it does (tells you a newer version exists and links to it), and what
  it never does (downloads, installs, or sends anything that identifies the device).
- **The off switch stops everything.** Turning it off makes no request at all —
  not a suppressed one, a made-none one. There is no "still check but do not show
  it" mode, because that is a phone-home with the label taken off.
- **First-run honesty.** Because it is off by default, the user must know it exists
  and why it is off. The setting's description carries that, and the download page
  (on `redoubtbrowser.org`, when it exists) says the direct APK has no store and how
  to get update awareness.

## F-Droid and Accrescent do not double-notify

F-Droid and Accrescent each notify their own users when a new build is on the
repository. A user on either of those channels therefore must not *also* get an
in-app prompt, or the same update is announced twice through two mechanisms.

- **The check is a property of the direct-APK distribution.** It is present in the
  build published for the direct download (the one Obtainium tracks) and **absent
  from the F-Droid and Accrescent builds**. Those two are built and published by
  separate pipelines and are signed with the same key (the same fingerprint, as
  `docs/android/SECURITY.md` and the triage channel labels assume) but carry a
  build flag that leaves the check compiled out.
- **No runtime detection, no identifier.** Because it is decided at build time per
  channel, the app never has to ask "which channel did I come from?" at runtime,
  and nothing about the channel is ever sent anywhere. The distinction the
  acceptance needs — "F-Droid and Accrescent installs do not double-notify" — is a
  property of the artifact, not a query.
- **No conflict to reconcile.** If a user moves the same install between the direct
  APK and a store, the build they end up with either has the check or does not, and
  the store's own updater is authoritative for a store install. There is nothing to
  arbitrate at runtime because the choice was made in the artifact.

## What this page does not decide

- **The origin layout.** The domain itself is decided and registered
  (`redoubtbrowser.org`). What is open is whether the update endpoint lives on that
  host or a separate origin, and what actually gets served there. This page names the
  shape so that decision is smaller when it happens.
- **The key.** The signing key belongs to the skipped distribution tasks. This page
  states the requirement, not the key; no key material appears here or in the patch.
- **The implementation.** `patches/android/update-check.patch` (the Kotlin, the
  setting, the signature verification) is the other half of LW-M6-06 and is not
  written here. It is blocked on the domain and the key, and it is verified by
  `./scripts/android-smoke.sh --check-update-privacy`, which cannot pass until the
  endpoint exists.
- **The default, finally.** This page recommends opt-in. If the maintainer chooses
  default-on instead, the two hard lines still hold: foreground-only and
  rate-limited (no background beacon), and disclosed with an off switch.

## Status

The contract and the code are done: `patches/android/update-check.patch` implements
every invariant above (`org.mozilla.fenix.lw.UpdateCheck` / `UpdateChecker`, with
`UpdateCheckerTest` pinning the request shape, the signature check and the version
comparison), and `./scripts/android-smoke.sh --check-update-privacy` measures the
network side on a running build: with the switch off, no traffic to the update host
across launch and the settings screens; with it on, the update host and nothing
else new. What still needs the world is the domain (`redoubtbrowser.org`) and the
key (LW-M6-01's custody): until both exist, every build is made without a key and
the check is compiled out — no row, no reachable code path — which is exactly the
store-build configuration. The domain is the load-bearing one: until it is decided,
the endpoint is a contract, not an address.
