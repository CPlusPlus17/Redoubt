# Distribution and the update-check contract — Redoubt (Android)

Redoubt is a fork that ships on the Firefox **ESR** track, and the direct-APK
distribution has no app store to tell its users an update is out. This page is
the contract for the one mechanism that fills that gap — an in-app version check
against a signed, static endpoint — and for the two channels that already have
their own updater (**F-Droid** and **Accrescent**), which must not double-notify.

It is the **unblocked half of LW-M6-06**. The half that is still open is the code
(`patches/android/update-check.patch`) and the endpoint itself; both depend on the
distribution domain being decided. That domain is the open placeholder
`<PROJECT_DOMAIN>` (`docs/android/IDENTITY.md`), and it is left literal here on
purpose. **Nothing on this page is a real URL, hostname, or address.**

This page is a specification, not a shipped feature. It fixes the *shape* of the
check and its privacy boundary so that when the domain exists and the patch is
written, the decisions are already made — and so that the one thing a privacy
browser must not do (a silent, always-on phone-home) is ruled out by design rather
than by convention.

## What the check may do, and what it may not

Two lines from the task bound everything below:

- **Do not build a silent self-updater.** The check tells the user a new version
  exists and links to the download. It does not download, install, or apply
  anything.
- **Do not add a phone-home that runs without consent.** The check is off by
  default and, when on, sends nothing but the current version string.

The risk the task names is the one that sets the defaults: *"an always-on update
ping is a periodic beacon with an IP address attached — exactly what users came
here to avoid."* So the check is **opt-in, foreground-only, and rate-limited** —
not a background timer.

## The three invariants this must satisfy

These are LW-M6-06's acceptance criteria, restated as things that must hold:

1. **The check sends no identifier beyond the version string.** No device id, no
   install id, no user id, no telemetry, no per-install value in any header. The
   only thing in the request that identifies anything is the version string.
2. **It is disclosed in the UI and can be turned off.** A visible setting, a
   plain description of what it sends and where, and a switch that stops it
   entirely.
3. **F-Droid and Accrescent installs do not double-notify.** Those channels ship
   their own update notification; the in-app check is not present in those builds.

## The endpoint

The endpoint is a single static document, served over TLS, on the distribution
host. The host is the open placeholder:

    ENDPOINT  https://<PROJECT_DOMAIN>/updates/android/latest.json

`<PROJECT_DOMAIN>` is **not a real hostname**. It is the placeholder from
`docs/android/IDENTITY.md`, left literal on purpose — this page does not invent a
domain, hostname, or URL. The path is a contract constant both the client and the
server must implement (and can be renamed in one place when the domain is
decided); the host is the only undecided part, and the URL does not resolve until
`<PROJECT_DOMAIN>` does.

### The document

A small, signed JSON document. The client treats any field it does not understand
as absent, and any document that fails signature verification as if it were not
there at all.

    {
      "latest_version":    "153.0.4-2",
      "download_url":      "https://<PROJECT_DOMAIN>/downloads/redoubt-153.0.4-2.apk",
      "release_notes_url": "https://<PROJECT_DOMAIN>/releases/153.0.4-2/",
      "sha256":            "<hex digest of the APK the download link points to>",
      "published_at":      "2026-08-22T00:00:00Z",
      "signature":         "<base64 detached signature over this document>"
    }

- **latest_version** — the string the client compares against its own. This is
  the only thing the check needs to decide that a newer version exists.
- **download_url** — where the user is sent if they choose to update. Same
  `<PROJECT_DOMAIN>` host. Offering the link, not fetching it, is the app's job.
- **sha256** — the digest of the artifact the link points to.
  `docs/android/SECURITY.md` §2 already relies on a published, checksummed
  artifact; the digest lives here so there is one source of truth rather than two.
- **published_at** — so the client can treat a document that has not changed in an
  implausible amount of time as suspect rather than authoritative.
- **signature** — a detached signature. An unsigned or mis-signed document is
  refused, full stop — see below.

### Signing

"Signed, static endpoint" is doing real work. The document is served static, but
the client must not trust it merely because it is on our host: a compromised or
confused channel could serve a stale or malicious one, which is exactly the
failure mode `docs/android/SECURITY.md` §2 exists to describe. So:

- The document is signed with a key whose **public** half is embedded in the
  client at build time. The private half never leaves the signing host and never
  appears in this page or in the patch.
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

Exactly one thing: the current version string. Nothing else identifies the client.

    GET <ENDPOINT>   with the current version string and nothing else

- **In the request** — the version string (the same one shown on the About
  screen) and nothing else: no device id, no install id, no user id, no add-on
  list, no locale, no model. A static, non-identifying `User-Agent` is permitted
  if the HTTP stack requires one; a per-install value in any header is not.
- **In the response** — the document above. The client reads `latest_version`,
  compares it to its own, and that is the whole transaction.
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
  version string, nothing else), where it goes (the endpoint on the distribution
  host), what it does (tells you a newer version exists and links to it), and what
  it never does (downloads, installs, or sends anything that identifies the device).
- **The off switch stops everything.** Turning it off makes no request at all —
  not a suppressed one, a made-none one. There is no "still check but do not show
  it" mode, because that is a phone-home with the label taken off.
- **First-run honesty.** Because it is off by default, the user must know it exists
  and why it is off. The setting's description carries that, and the download page
  (on `<PROJECT_DOMAIN>`, when it exists) says the direct APK has no store and how
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

- **The domain.** `<PROJECT_DOMAIN>` is the open placeholder. The exact host, and
  whether the endpoint is a separate origin, wait on that decision. This page names
  the shape so that decision is smaller when it happens.
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

This is the specification and the invariants, and it is complete on its own terms:
the check's privacy boundary, its frequency, its disclosure, and the channel split
are all decided. What is not done is the half that needs the world — the domain
(`<PROJECT_DOMAIN>`), the key (the skipped distribution tasks), the patch
(`patches/android/update-check.patch`), and the smoke-test pass against a live
endpoint. The domain is the load-bearing one: until it is decided, the endpoint is
a contract, not an address.
