# Distribution and the update-check contract — Redoubt (Android)

## First Android beta on GitHub

**Release channel (owner decision 2026-10-04):** each beta is published as a full GitHub
release marked **Latest** (`gh release create ... --latest`, not `--prerelease`), so
`releases/latest` and Obtainium's defaults find it; "Beta" stays in the title and notes, and the
superseded beta keeps its prerelease flag and gets a "superseded" banner. Beta 5
(`android-157.0-1-beta.5`) was the first switched over.

The owner requested GitHub Releases distribution on 2026-09-08 for the four
approved signed beta APKs. They are published in the public prerelease
[`android-153.0esr-1-beta.1`](https://github.com/CPlusPlus17/Redoubt/releases/tag/android-153.0esr-1-beta.1).
It contains the ARM64, ARM32, x86_64 and universal APKs under their existing
`fenix-*-release.apk` filenames, plus `SHA256SUMS.signed`. The release notes
include the signing fingerprint and verification commands. Downloaded APKs pass
the approved hashes, release signature and candidate payload checks; public access
is verified in the [publication record](evidence/lw-m6-11/README.md).

Betas 1-5 have no in-app update check (it is compiled out: no key was given to
those builds); later APKs must be obtained from Releases and installed over the
current build. Obtainium integration has not been verified. F-Droid and Accrescent
publication remain separate work.

**Status 2026-10-04 (owner decision: in-app check from the next build).** The
publishing side now exists in the repository; what is still missing is owner-held:

| part | state |
|---|---|
| client (`patches/android/update-check.patch`) | implemented; **revised 2026-10-04**: the versionCode decides (see "The document"), default endpoint `/update/android/`; **fixed 2026-10-05**: the Settings switch now writes the file the check reads. In the 157.0-2 build it did not, so the check could never be turned on ("The switch defect" below) |
| document generator + verifier (`scripts/update-manifest.py`) | implemented |
| owner's signer (`scripts/sign-update-manifest.sh`) | implemented; refuses any key but the pinned one |
| build wiring (`scripts/android-apk.sh --update-check`) | implemented; refuses to build until the public key is committed |
| tests (`scripts/tests/test-update-manifest.py`, `test-update-check-jvm.sh`) | implemented, throwaway keys only |
| hosting (`site/update/android/` on `redoubtbrowser.org`, GitHub Pages) | the site publishes `site/update/**` verbatim; **nothing is there yet** |
| update-signing key | generated 2026-10-04 by the owner; custody in `SIGNING.md` "The update-signing key" (stays on the Fedora host, owner decision 2026-10-04) |
| `assets/update-check.android.pubkey` | committed 2026-10-04 (merge `7c724f60`); builds made with `--update-check` carry it |
| first signed document | published with the first build made with `--update-check`: the stable release **Redoubt 157.0-2** (see "Stable release" below), not a Beta 6 |

Redoubt is a fork that ships on the Firefox **release** track (since 2026-10-02; see
`TRACK.md`), and the direct-APK
distribution has no app store to tell its users an update is out. This page is
the contract for the one mechanism that fills that gap — an in-app version check
against a signed, static endpoint — and for the two channels that already have
their own updater (**F-Droid** and **Accrescent**), which must not double-notify.

It is the contract half of LW-M6-06. The code half is
`patches/android/update-check.patch` (`org.mozilla.fenix.lw.UpdateCheck`, landed
2026-09-02); the endpoint is served from `redoubtbrowser.org`
(`docs/android/IDENTITY.md`), which the owner decided on 2026-10-04 to publish as a
GitHub Page from `site/` (`docs/android/WEBSITE.md`). **No document is published
yet.** The verification key is checked in since 2026-10-04; a build made without
`--update-check` still has the check compiled out (see "F-Droid and Accrescent do
not double-notify").

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
  default and, when on, sends nothing that identifies the client beyond the
  request itself — not even the version string.

The risk the task names is the one that sets the defaults: *"an always-on update
ping is a periodic beacon with an IP address attached — exactly what users came
here to avoid."* So the check is **opt-in, foreground-only, and rate-limited** —
not a background timer.

## The three invariants this must satisfy

These are LW-M6-06's acceptance criteria, restated as things that must hold:

1. **The check sends no identifier beyond the version string.** No device id, no
   install id, no user id, no telemetry, no per-install value in any header. As
   implemented it sends less than the acceptance wording allows: not even the
   version string (see "What the client sends"). What no client can hide is the
   request itself: the host that answers it sees the IP address and the time.
2. **It is disclosed in the UI and can be turned off.** A visible setting, a
   plain description of what it sends and where, and a switch that stops it
   entirely.
3. **F-Droid and Accrescent installs do not double-notify.** Those channels ship
   their own update notification; the in-app check is not present in those builds.

## The endpoint

The endpoint is a single static document, served over TLS, on the distribution
host:

    ENDPOINT  https://redoubtbrowser.org/update/android/latest.json
              https://redoubtbrowser.org/update/android/latest.json.sig

    in the repository: site/update/android/latest.json and latest.json.sig

`redoubtbrowser.org` is the decided domain (`docs/android/IDENTITY.md`, 2026-08-23).
The site is a GitHub Page built from `site/` (`.github/workflows/pages.yaml`), so
**GitHub answers the update check**: GitHub sees the requesting IP address and the
time, once a day per install while the switch is on. The setting's description and
the install page say so. The workflow
publishes `site/update/**` verbatim and never generates or rewrites it; the files
there are written only by the release procedure below. The path changed on
2026-10-04 from `/updates/android/` to `/update/android/`, the URL agreed for the
site; the patch's default (`-PlwUpdateCheckEndpoint`) moved with it. **Nothing is
served at this path yet**, and until the first signed document is committed the
URL is a 404, which the client treats as "no update".

Two properties of the hosting matter to the client and are easy to break from the
site side:

- **No redirect.** The client follows none (`Request.Redirect.MANUAL`). The
  document must be served `200` at exactly this URL: the custom domain must be the
  apex `redoubtbrowser.org` (`site/CNAME`), not `www.`, or the apex answers `301`
  and every check is a silent "no update". `scripts/update-manifest.py fetch`
  refuses redirects for the same reason; run it after every publish.
- **Byte-exact.** The signature covers the served bytes. Nothing in the pipeline
  may reformat, minify or re-encode the two files (GitHub's transport compression
  is undone before the client sees the bytes, and is fine).

### The document

A small, signed JSON document, written by `scripts/update-manifest.py generate`
from the release's `apk/output-metadata.json` and its tag. The client treats any
field it does not understand as absent, and any document that fails signature
verification as if it were not there at all.

    {
      "latest_version": "157.0-1-beta.6",
      "version_code": 2016188448,
      "download_url": "https://github.com/CPlusPlus17/Redoubt/releases/tag/android-157.0-1-beta.6",
      "release_notes_url": "https://github.com/CPlusPlus17/Redoubt/releases/tag/android-157.0-1-beta.6",
      "published_at": "2026-10-05T00:00:00Z"
    }

    ENDPOINT.sig   base64 of the DER ECDSA P-256 / SHA-256 signature over the
                   exact bytes of ENDPOINT (one line; surrounding whitespace is
                   trimmed by the client)

(Illustrative values; the version code above is the test fixture's, not a real
build's.)

- **latest_version** (required) — the release tag without `android-`. Shown in the
  dialog title ("Redoubt 157.0-1-beta.6 is available") and remembered so each
  release is offered once. It decides "newer" only when `version_code` is absent.
- **version_code** (added 2026-10-04) — the **lowest** versionCode among the
  release's APKs. When it is present the client offers the update **iff the
  install's own versionCode is known and `version_code` is greater**; an install
  that cannot read its own code (0) is told it is up to date, never handed to the
  string comparison, which would offer a beta its own release. Why not the
  version string: every Redoubt APK's versionName is `<firefox>-<release>-default`
  and betas share it (beta.4 and beta.5 are both `157.0-1-default`), so a string
  comparison could never announce the next beta; and the string comparison reads
  the `-1` of `157.0-1-default` as a Firefox component, which orders a respin
  (`157.0-2`) above the next Firefox dot release (`157.0.1-1`). The versionCode is
  Fenix's build-hour code (`0x78200000 | hours << 3 | abi bits`), which Android
  itself requires to increase on every update; taking the lowest of the four APKs
  means any APK of an older build (built at least one hour earlier) is below it and
  any APK of the same build is not. The generator refuses to write a document that
  would offer a build its own release. Nothing new is sent: the comparison is on
  the device.
- **download_url** (required, https) — where the user is sent if they choose to
  update: the release's GitHub page, which carries all four APKs,
  `SHA256SUMS.signed` and the verification commands. Offering the link, not
  fetching it, is the app's job. `--download-url` overrides it (for example, once
  the website has a download page).
- **release_notes_url** (optional, https) — the same release page by default.
- **published_at** — informational. The client does not read it; it lets a reader
  of the document see when it was signed.
- **no `sha256`.** The first draft had one; a release has four APKs, and one digest
  field would name one of them arbitrarily. The digests live in one place, the
  release's `SHA256SUMS.signed`, next to the files they describe.
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
  client at build time. The private half never leaves the key machine and never
  appears in this page, the patch or the repository. Concretely: ECDSA P-256 with
  SHA-256 (`SHA256withECDSA`, present on every Android release Fenix supports,
  unlike Ed25519 which needs API 33); the client is handed the base64 DER
  SubjectPublicKeyInfo through the Gradle property `lwUpdateCheckPubkey`.
  `scripts/android-apk.sh --update-check` reads it from the committed file
  `assets/update-check.android.pubkey` (or any key from the environment variable
  `LW_UPDATE_CHECK_PUBKEY`, for smoke builds), and refuses a key that is not
  P-256. The maintainer's side is `scripts/sign-update-manifest.sh`, which signs
  with openssl and refuses to write a signature that does not verify against the
  pinned public key; underneath it is one openssl line:

      openssl dgst -sha256 -sign redoubt-update-signing.pem latest.json | openssl base64 -A > latest.json.sig
- The client verifies the signature before reading a single field. **On
  verification failure it behaves exactly as if the check had been turned off**:
  no prompt, no remote log, no crash. A bad signature is not an error the user is
  shown; it is a "no update."
- **The key is a dedicated update-signing key, not the APK release key**
  (decided 2026-10-04). The APK key is an RSA keystore for `apksigner`; this
  verifier needs EC P-256; and the two have different blast radii — a lost update
  key costs a client release with a new embedded key, a lost APK key ends the app
  identity. Generation, custody and loss/compromise handling are in
  `docs/android/SIGNING.md`, "The update-signing key".

## Publishing a release with the check (step list)

For every direct-APK release from the first one built with `--update-check`.
Paths are examples; `<tag>` is e.g. `android-157.0-1-beta.6`.

1. **Build** the direct-APK release with the check compiled in:

       make android-package TARGETS=android ... \
           ANDROID_APK_FLAGS="--variant=release --disable-debug-signing --update-check ..."

   `--update-check` fails at once if `assets/update-check.android.pubkey` is not
   committed. The dry run prints `update check: COMPILED IN` or `compiled out`.
   Confirm on the artifact that the key is in it (R8 inlines the BuildConfig
   constant into the dex):

       unzip -p <apkdir>/fenix-arm64-v8a-release-unsigned.apk 'classes*.dex' \
           | grep -c "$(cat assets/update-check.android.pubkey)"   # >= 1

2. **Generate** the document on the build host, from that build's metadata:

       ./scripts/update-manifest.py generate --metadata <apkdir>/output-metadata.json \
           --tag <tag> --published <UTC time of the release> --out <bundle>/update/latest.json

   It checks the tag against the APKs' versionName, takes the lowest versionCode,
   refuses a non-https URL, and prints the document's sha256.
3. **Stage it for the key machine** in its own `update/` directory of the signing
   bundle, next to `scripts/sign-update-manifest.sh` and a copy of
   `assets/update-check.android.pubkey`. Keep it out of `SHA256SUMS.tools`: the APK
   signer (`evidence/lw-m6-01/sign.sh`) requires exactly its four tools, and the
   two signing steps stay independent.
4. **Sign on the key machine** (after or before `sign.sh`; they do not interact):

       ./update/sign-update-manifest.sh /path/to/redoubt-update-signing.pem update/latest.json

   Compare the sha256 it prints with step 2's. It asks for the key's passphrase,
   verifies the new signature against the pinned public key, and writes
   `latest.json.sig` only if that passes.
5. **Intake on the build host:**

       ./scripts/update-manifest.py verify <bundle>/update/latest.json \
           --metadata <apkdir>/output-metadata.json

   (uses the committed public key; checks the signature exactly as the app does,
   and that no APK of this release would be offered its own release).
6. **Publish the GitHub release first** (APKs, `SHA256SUMS.signed`), and make sure
   the `download_url` page is public. A document must never point at a page that
   does not exist yet.
7. **Publish the document:** copy `latest.json` and `latest.json.sig` into
   `site/update/android/`, commit (signed) and push to `main`; the Pages workflow
   deploys `site/` as is.
8. **Confirm it live**, without redirects, as the app sees it:

       ./scripts/update-manifest.py fetch --expect-tag <tag>

To withdraw an announcement, delete the two files (a 404 is "no update"). A
document can never be rolled back to an older release: the client only offers a
higher versionCode, so a document naming an older build is simply ignored.

**F-Droid and Accrescent builds never pass `--update-check`** and run without
`LW_UPDATE_CHECK_PUBKEY` in the environment; their artifacts have the check
compiled out (no key string in the dex, no Settings row). The same `classes*.dex`
grep returning 0 is the check for those.

## Stable release: Redoubt 157.0-2 (owner decision 2026-10-04)

The owner decided GO on 2026-10-04 (`BETA.md` §7): the first stable release is
**Redoubt 157.0-2**, Firefox 157 based, a new build from `main` with the update
check compiled in; early adopters replace the beta's device slots. Builds run in
CI on box B; the owner signs on box A (`SIGNING.md`, "Decision: stable-release
custody"). The step list above applies unchanged; this is the delta.

| | betas (above) | stable release |
|---|---|---|
| tag | `android-157.0-1-beta.N` | `android-157.0-2` |
| title | "Redoubt 157.0-1 Beta N" | `Redoubt 157.0-2` |
| flags | `--latest` (Betas 1-4: `--prerelease`) | `--latest`, **not** `--prerelease` |
| versionName / release.android | `157.0-1-default` / 1 | `157.0-2-default` / 2 |
| update check | compiled out | compiled in (`update_check=true`) |
| update document | none | `site/update/android/latest.json` + `.sig`, after the GitHub release |

1. **Build** on box B, from `main` after the release branch is merged, with a
   pinned build date later than Beta 5's `20261003200000` (versionCodes
   2016188256-63) and not in the future:

       gh workflow run android-release.yaml --repo CPlusPlus17/Redoubt --ref main \
           -f mode=full -f update_check=true -f build_date=20261005000000

   The workflow refuses a malformed or future date, checks the AAR used it, and
   fails unless every dex carries the committed update-check key and all four
   APKs are unsigned. With `20261005000000` the versionCodes are
   2016188480-2016188487 (8 codes per build hour), above Beta 5's and above the
   REJECTED first 157.0-2 build (run 37234607054, `20261004200000`, 2016188448-55,
   never published: its update-check switch was never read). Never reuse a rejected
   build's date. The artifact
   `redoubt-android-unsigned` holds the four APKs, `output-metadata.json` and
   `SHA256SUMS`. Record the run URL and the checked-out commit (`git rev-parse`).
2. **Accept the exact payload** before signing: the emulator smoke on the x86_64
   APK of this run, including `--check-update-privacy` with the switch on and the
   document reachable (the opt-in half not measured so far, "Status" below), and
   `scripts/android-brand-check.py`. Fill BETA.md §7's BUILD line with the commit
   and MOZ_BUILD_DATE.
3. **Generate, sign and verify** as in steps 2-5 above with `--tag android-157.0-2`;
   the APKs are signed with `sign.sh` and the document with
   `sign-update-manifest.sh`, both by the owner on box A.
4. **Publish the GitHub release** (step 6 above) as the latest, full release:

       gh release create android-157.0-2 --repo CPlusPlus17/Redoubt \
           --title 'Redoubt 157.0-2' --latest --notes-file <notes.md> \
           fenix-*-release.apk SHA256SUMS.signed

   The notes carry the signing fingerprint and verification commands, the parity
   sentence with its link to `PARITY.md`, and the known limits from `BETA.md` §7
   (what was not tested on real devices). Verify the downloaded assets against
   `SHA256SUMS.signed` and `scripts/android-verify-signature.sh`.
5. **Publish the update document** (steps 7-8 above): commit `latest.json` and
   `latest.json.sig` to `site/update/android/` only after the release page is
   public, then `./scripts/update-manifest.py fetch --expect-tag android-157.0-2`.
   Beta 1-5 installs have no update check and will not see it; the release notes
   and the site tell them to install 157.0-2 over their beta.
6. **Supersede the previous beta:** prepend a banner to Beta 5's notes, e.g.
   `> **Superseded** by [Redoubt 157.0-2](https://github.com/CPlusPlus17/Redoubt/releases/tag/android-157.0-2).
   Install that release over this one; it keeps your data.` (`gh release edit
   android-157.0-1-beta.5 --notes-file ...`). `--latest` on 157.0-2 already moves
   the Latest marker; Beta 5 is not deleted.
7. **Site:** `site/index.html` and `site/install.html` still say "beta" and "no
   update check of their own"; update them for the stable release in the same
   publishing pass. The parity sentence and the fingerprint stay verbatim.

## The switch defect (found 2026-10-05)

Device acceptance of the 157.0-2 build (CI run 37234607054, commit `0ef74fad`) failed
`--check-update-privacy`'s ON half. The switch was turned on through the UI, but no request
reached `redoubtbrowser.org`. A probe inside Gecko confirmed this (branch
`release/157.0-2-acceptance`, `docs/android/evidence/lw-m7-01/release-157.0-2/acceptance/`).
**That build must not be published.**

- **Cause.** The row was a plain `SwitchPreferenceCompat`. `SettingsFragment` sets no
  `sharedPreferencesName`, so androidx persisted the switch to the default SharedPreferences
  file (`org.redoubtbrowser_preferences.xml`). `UpdateCheck.isEnabled` reads
  `components.settings.preferences` (`fenix_preferences`). The switch showed ON, and the
  check stayed off.
- **Fix** (`update-check.patch`, 2026-10-05). It uses upstream's own pattern for switches
  that live in `fenix_preferences` (`CustomizationFragment`'s gesture switches):
  `UpdateCheck.bindSwitch` sets the row's checked state from `isEnabled` and installs
  `SharedPreferenceUpdater`, which writes `fenix_preferences` under the row's key. The row is
  `android:persistent="false"`, so androidx keeps no second copy. Binding writes nothing, so
  the check is off until the user taps the row. A value that 157.0-2 left in the default file
  is ignored, not migrated.
- **Why nothing caught it.** `UpdateCheckerTest` drives `UpdateChecker` with every input
  injected and never touched the switch. `test-update-check-jvm.sh` runs those tests on a
  plain JVM. The patch gates do not compile. The 2026-09-06 opt-in device run
  (`evidence/lw-m7-06`) saw no request after the switch was turned on. It blamed that on
  nothing being published, but the cause was this defect. **`UpdateCheckSwitchTest`**
  (Robolectric, 4 tests) now taps the row through its change listener and asks `isEnabled`.
  It checks four things: on after a tap, off after a second tap, off by default, and off when
  a value exists only in the default file. With the listener removed, the test fails. The JVM
  harness cannot run it (there is no Android runtime) and instead fails if the wiring is
  missing from the patch. Runs: `evidence/lw-m6-06/switch-fix-2026-10-05/`.
- **Before release.** A new CI build from a commit that has this fix needs a new acceptance,
  and its ON half of `--check-update-privacy` must show the request. Whether that build is
  still called 157.0-2 (nothing was published) or gets a new release number is the owner's
  decision. It is not made here.

## Testing it

- `python3 scripts/tests/test-update-manifest.py` — generate → sign (with
  `sign-update-manifest.sh`, throwaway keys, including a passphrase-protected one
  driven through a terminal) → verify; tampered documents and signatures, other
  keys, non-P-256 keys, oversize input, a signer handed the wrong key, and `fetch`
  refusing a redirect. Needs python3 and openssl.
- `scripts/tests/test-update-check-jvm.sh --tree <firefox tree> --gradle-home
  <a Fenix build's gradle-home> --android-jar <android.jar>` — compiles the
  patch's own `UpdateCheck.kt` with `-Werror` on the host JVM (Kotlin compiler from
  the gradle-home, real concept-fetch sources from the tree, compile-only stubs
  for the Fenix classes it touches), runs `UpdateCheckerTest` (11 tests), and
  cross-checks the patch's `UpdateChecker` against documents made by the tools
  above: same verdict from the Kotlin and from `update-manifest.py` for older
  installs, every APK of the same build, an install that cannot read its own
  versionCode, tampering, another key and a malformed signature. Run 2026-10-04 against the pristine 157 tree with Kotlin 2.3.20 and
  2.4.0: 10/10 tests, 13/13 cross-checks; re-run the same day after the
  unknown-own-code fix with Kotlin 2.3.20: 11/11 tests, 14/14 cross-checks (the
  new test fails against the previous `offers`). It does not replace
  `./mach gradle fenix:testDebugUnitTest` or a build of the Fenix module. Since
  2026-10-05 it also compiles against `androidx.preference` and greps the patch for the
  switch wiring ("The switch defect" above). It does **not** run `UpdateCheckSwitchTest`,
  which needs Robolectric. Re-run 2026-10-05 on the 157 tree (Kotlin 2.4.0): 11/11 tests,
  14/14 cross-checks. Against the 0ef74fad patch it exits 2 at the wiring check.
- `./mach gradle fenix:testDebugUnitTest --tests 'org.mozilla.fenix.lw.*'` —
  `UpdateCheckerTest` and `UpdateCheckSwitchTest`. It drives `UpdateCheck.bindSwitch` on a
  stand-in switch and then asks the check whether it is on; it does not inflate
  `preferences.xml` or run `SettingsFragment`, so the real Settings row is proven only by the
  device acceptance's `--check-update-privacy` ON half. Run 2026-10-05 on the Firefox 158
  tree, the only one on the build host with a GeckoView AAR, with the fixed files copied in:
  15/15, `-Werror` compile clean.
- `./scripts/android-smoke.sh --check-update-privacy` on a device, with a build
  made with a key, is still the only measurement of the request itself.

## What the client sends

Nothing that identifies the client beyond the request itself — and, as
implemented, not even the version string: the comparison happens on the device, so
the server learns only that some Redoubt asked, from the connection's IP address,
at that time. The server is GitHub Pages: that is what GitHub sees, once a day
while the switch is on.

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
  nothing that identifies you beyond the request itself — not even the version
  string), where it goes (`redoubtbrowser.org`, hosted on GitHub Pages, so GitHub
  sees the IP address and the time), what it does (tells you a newer version exists and links to it), and what
  it never does (downloads, installs, or sends anything else about you).
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

- **The key itself.** The owner generates and holds it (`SIGNING.md`, "The
  update-signing key"); no private key material appears here, in the patch, or
  anywhere in the repository. Only the public half is committed, once, at
  `assets/update-check.android.pubkey`.
- **The implementation.** `patches/android/update-check.patch` (the Kotlin, the
  setting, the signature verification) is the other half of LW-M6-06 and is not
  written here. Its device-side measurement,
  `./scripts/android-smoke.sh --check-update-privacy`, needs a build made with a
  key and a published document to exercise the opt-in half.
- **The default, finally.** This page recommends opt-in. If the maintainer chooses
  default-on instead, the two hard lines still hold: foreground-only and
  rate-limited (no background beacon), and disclosed with an off switch.

## Status

The contract, the client and the publishing side are done:
`patches/android/update-check.patch` implements every invariant above
(`org.mozilla.fenix.lw.UpdateCheck` / `UpdateChecker`, with `UpdateCheckerTest`
pinning the request shape, the signature check and the version decision);
`scripts/update-manifest.py`, `scripts/sign-update-manifest.sh` and
`scripts/android-apk.sh --update-check` are the release side (table at the top);
and `./scripts/android-smoke.sh --check-update-privacy` measures the network side on
a running build. The update-signing key exists and its public half is committed
(2026-10-04); a build made without `--update-check` still has the check compiled
out — the row is hidden and `isEnabled` returns false (Settings search still
indexes the row's title statically; a known, harmless cosmetic gap in store builds) —
which is exactly the store-build configuration. The first build with it compiled in
(run 37234607054) was rejected in acceptance (the switch defect); the stable release
157.0-2 is the rebuild with the fix ("Stable release" above).

Not yet measured on a device: the opt-in half of `--check-update-privacy`. The
2026-09-06 run with a throwaway-key build saw no request to the update host after
the switch was turned on (`evidence/lw-m7-06/README.md`), and so did the 157.0-2
acceptance. Both were the switch defect ("The switch defect" above), fixed
2026-10-05, and not only the missing document. It must be re-run against
the first `--update-check` build with the document live, before that build is
called done.
