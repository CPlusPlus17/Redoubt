# The Redoubt website — content spec (`redoubtbrowser.org`)

Owner: **LW-M7-02** ("Publish the Android pages on redoubtbrowser.org"). `redoubtbrowser.org`
is the decided domain (see `docs/android/IDENTITY.md`). **The site is now a GitHub Page built
from `site/`** (owner decision 2026-10-04); this file is the content spec it is written to and
checked against. The page is written to one rule above all: **it must not overclaim.** The
whole point of putting the parity statement on the download page is that a user reads the
honest version *before* they install.

## 0. The published site

    source          site/  (plain HTML + one stylesheet; no build step)
    workflow        .github/workflows/pages.yaml  (GitHub-hosted runner)
    check           scripts/site-check.py  (runs before every deploy and on PRs)
    domain          site/CNAME = redoubtbrowser.org

| page | content | source of truth |
|---|---|---|
| `index.html` | what Redoubt is, a one-line not-LibreWolf/not-Firefox notice, the install buttons (F-Droid first, then the APK, then the IronFox comparison) above the fold on a 375 px phone, the §1 statement, the full notice, app screenshots, status and testing, known issues, download, verify, how Redoubt is made, attribution | `README.md`, this file |
| `install.html` | F-Droid, then Obtainium, then the direct APK; verification (both digest forms, the `SHA256SUMS.signed` note, an AppVerifier block); the opt-in in-app check; other stores (not on Google Play, Accrescent or f-droid.org) | this file §5–6, `DISTRIBUTION.md`, `SIGNING.md` |
| `faq.html` | short answers to the questions a launch thread asks: LibreWolf, IronFox, how Redoubt is made, the maintainer, security-fix record, the signing key, stores, the update check, telemetry, extensions, push, JIT, site breakage, memory, known issues, reproducibility, reporting | `README.md`, `POSITIONING.md`, `SIGNING.md`, `SECURITY.md`, `REPRODUCIBLE.md` |
| `privacy.html` | the §1 statement, what changes, honest limits, link to the full matrix | `PARITY.md` §1, §5 |
| `privacy-policy.html` | the privacy policy (what the developer collects: nothing; each connection the app makes; the website and download channels and who sees what there; permissions; contact `security@redoubtbrowser.org`) | `PARITY.md`, `DISTRIBUTION.md`, `FDROID.md` |
| `sync.html` | sync with LibreWolf desktop | `SYNC.md` |
| `passkeys.html` | password managers, autofill and passkeys: what works, known gaps | `README.md` "Passwords and passkeys", `PARITY.md` §8 |
| `security.html` | private reporting (e-mail `security@redoubtbrowser.org`, no GitHub account needed, or GitHub private vulnerability reporting), fingerprint, the security-fix record (no promised turnaround), who holds the signing key, where bugs go | `SECURITY.md`, `SIGNING.md`, `README.md` |
| `fdroid.html`, `fdroid-qr.svg` *(live since 2026-10-14)* | how to add Redoubt's F-Droid repository: its `fdroidrepos://` link, QR code, address and fingerprint, why F-Droid shows the `Tracking` anti-feature, the archive, and that the repository itself is in a Hetzner Object Storage bucket | `FDROID.md`; rendered from `assets/fdroid/fdroid.html.in` by `fdroid-repo.sh publish-page`, never edited by hand |
| `.well-known/security.txt` | RFC 9116 contact file: `security@redoubtbrowser.org`, the GitHub reporting link, `Expires:` (renew before it lapses; the checker fails on an expired one) | `SECURITY.md` |
| `og.png`, `favicon.png`, `favicon.ico`, `apple-touch-icon.png` | link-preview image (1200×630) and icons, drawn from the launcher mark the way `docs/android/play/graphics/make-graphics.py` draws the Play graphics | `scripts/gen-android-brand.py` (FORT, SLATE) |
| `screenshots/*.png` | three 540×1137 screenshots of 158.0-2 (home, privacy and security settings, global privacy controls), taken 2026-10-14 on a Pixel 9a | the app |
| `update/**` | the signed update-check endpoint | `DISTRIBUTION.md` — published verbatim; the site neither writes nor edits it |

Rules the checker enforces, so they do not depend on review:

- **Nothing third-party.** No `<script>` at all (the site works without JavaScript), no web
  fonts, no CDN, no analytics, no image or stylesheet from another origin. A
  Content-Security-Policy meta (`default-src 'none'`, `img-src`/`style-src 'self'`) backs
  this up in the browser.
- **External links only to** `github.com/CPlusPlus17/Redoubt` (releases, docs, issues,
  reporting), `librewolf.net` (attribution), `mozilla.org` (trademark notice) and
  `f-droid.org` (where users get the F-Droid client). The one `mailto:` link allowed is the
  security contact, `mailto:security@redoubtbrowser.org`. Other projects (IronFox, Obtainium,
  AppVerifier, password managers) are named, not linked. **One exception, on `fdroid.html`
  only:** links to the F-Droid repository's bucket named in `assets/fdroid/deploy.conf`,
  `fdroidrepos://<bucket>.<location>.your-objectstorage.com/repo?fingerprint=<pinned>` and
  `https://<bucket>.<location>.your-objectstorage.com/repo` or `/archive`. The repository
  cannot live on this domain (`FDROID.md`, "Hosting"), so the page must point at Hetzner's.
  The fingerprint in the link must equal `assets/fdroid/repo-fingerprint`.
- **No repository files.** No `.apk` anywhere under `site/` and no `site/fdroid/` directory:
  the F-Droid index and APKs live only in the bucket.
- **One fingerprint.** Every fingerprint on the site must equal the one in `README.md`, which
  equals `SIGNING.md`.
- Every internal link and `#anchor` resolves; the HTML is well formed.
- **`security.txt`.** `site/.well-known/security.txt` names `mailto:security@redoubtbrowser.org`
  and has an `Expires:` date in the future.

Link previews: every page carries `og:*` and `twitter:card` tags pointing at
`https://redoubtbrowser.org/og.png`. They are `<meta>` content, which the checker does not
treat as a load; there is deliberately no `<link rel="canonical">`, which it would.

DNS, Pages (source: GitHub Actions) and "Enforce HTTPS" are set up; the site is served at
`https://redoubtbrowser.org`. Download links point at `releases/latest`; the current release
(158.0-2) is a stable release.

---

## 1. The parity statement (verbatim — do not soften)

This is the agreed public wording from **LW-M5-06** (`docs/android/PARITY.md`). It appears
**on the download page itself** (LW-M7-02 acceptance #1), in full, unrewritten. It is not a
marketing tagline and it is not paraphrased:

> **Redoubt ships the same privacy configuration and the same Gecko-level security patches
> as LibreWolf desktop, on a platform whose process containment is weaker — and we publish
> exactly where.**

LW-M5-06 is explicit: *"Do not soften it."* Do not shorten it, do not add adjectives, and do
not move it into the fine print. It is the first substantive thing on the page.

### What that sentence does and does not say (keep the page consistent with `PARITY.md`)

- **Redoubt has no Gecko content sandbox on Android.** `MOZ_SANDBOX` is off,
  `toolkit.mozbuild:37` never compiles `security/sandbox`, and every `security.sandbox.*`
  pref is inert (upstream never finished the port). Do **not** claim process containment
  equal to desktop. The page says "process containment is weaker" — that is the honest half
  of the sentence, and it must stay.
- **The two irreducible gaps** (`PARITY.md` §1) are the Gecko content-process sandbox and
  the loss of the desktop signing-key identity. Name them if the page explains the sentence;
  do not imply they are closed.
- **Several `PARITY.md` rows are PENDING, not verified** (they need a physical device;
  e.g. the live-resistance-to-fingerprinting coherence check, and the network-posture floor).
  A download page that presents a PENDING row as verified **contradicts `PARITY.md`** and
  fails acceptance #3. Link to `PARITY.md` for the full, dated matrix instead of restating
  individual rows as settled.

---

## 2. The channels

Two live channels, Redoubt's own F-Droid repository and GitHub Releases (with Obtainium as
an optional watcher). Both carry the same APKs, signed with the **same** APK signing key — one
trust root (`docs/android/SECURITY.md`) — so there is **one fingerprint**, published in §3.
F-Droid carries its own updater, so the app hides its in-app check there (see §5 and
`docs/android/DISTRIBUTION.md`). Accrescent and Google Play are not channels today.

| channel | what it is | how it updates | in-app check present? |
|---|---|---|---|
| **F-Droid** | **Redoubt's own F-Droid repository**, hosted in the owner's Hetzner Object Storage bucket (`https://<bucket>.<location>.your-objectstorage.com/repo`; how to add it: `fdroid.html` on this site; `FDROID.md`), not f-droid.org's main repo (LW-M6-03) | F-Droid's own updater, once our repo is added | in the APK (the repository serves the direct APKs), **not offered** when F-Droid installed or last updated the app (from the build after 157.0-2) |
| **direct APK** | the APKs on GitHub Releases (`releases/latest`) | the opt-in in-app version check (`DISTRIBUTION.md`) or the user's own tool (e.g. Obtainium, untested by the project) | **yes** (opt-in, off by default) |
| **Accrescent** *(not published)* | — | — | — |
| **Google Play** *(not published)* | the 2026-10-05 plan to upload this key to Play App Signing was **reversed on 2026-10-14**: the release key is never uploaded to Google. If Redoubt is ever on Play, it uses a separate Play-only key, and Play installs and GitHub/F-Droid installs cannot update each other (`PLAY.md`, `SIGNING.md`) | — | — |

The site says exactly that on `install.html` ("Other stores") and in the FAQ.

The direct-APK row is the one with no store, which is exactly why it has the opt-in version
check and why the page must tell the user that, and how to get update awareness otherwise.

---

## 3. Fingerprint

- The APK signing key was generated in **LW-M6-01** (2026-08-23, `docs/android/SIGNING.md`).
  Its SHA-256 certificate fingerprint is published on the site's home, install and security
  pages, copied from `README.md` and checked equal by `scripts/site-check.py`. It is the same
  key for every channel, so there is one fingerprint. The pages also show it the way
  `apksigner` prints it (lower case, no colons), which the checker does not compare.
- A user who installs from any of the three channels should see the **same** fingerprint on
  the device; a different one is a signal the artifact is not what we published
  (`SECURITY.md` §1 treats the key as a one-way trust root).

---

## 4. How to verify what you downloaded

The APKs live on GitHub Releases, with `SHA256SUMS.signed` beside them, so the site does not
repeat per-file digests (they change every release and would go stale). It gives the two
commands from `README.md`:

    sha256sum -c --ignore-missing SHA256SUMS.signed
    apksigner verify --print-certs fenix-<abi>-release.apk | grep -i SHA-256

and the certificate fingerprint (§3) the second must print. `SHA256SUMS.signed` lists the
hashes of the signed APKs and is **not itself signed**: it catches a corrupted download, and
the certificate check is what proves the APK is Redoubt's. The pages say so. **If either
differs, do not install**, and report it privately (`security@redoubtbrowser.org` or GitHub
private vulnerability reporting, `SECURITY.md`) with the sha256 of what you have.

- The certificate check is the binding one: it is what Android itself enforces on every
  later update, so a verified first install protects the updates after it.
- On a phone without `apksigner`, the site names a certificate-viewing app (AppVerifier) as
  an after-install check, without linking it, and gives the package name plus digest in the
  form such an app accepts.

---

## 5. Install guide, per channel

- **F-Droid.** Install F-Droid. Then **add Redoubt's own repository** — its URL and
  fingerprint are on `fdroid.html` and `install.html` — and install **Redoubt** from it. F-Droid tells you when a new build lands; there is no in-app check to
  configure. The address is a Hetzner Object Storage bucket, not `redoubtbrowser.org`; the
  fingerprint is what proves it is ours. Older releases are in the repository's archive.

  Redoubt is **not** in f-droid.org's main repository and an earlier draft of this
  page said to use it. f-droid.org can publish developer-signed APKs only if it
  reproduces the build bit for bit; Redoubt's build is not reproduced across machines
  yet (`REPRODUCIBLE.md`), so f-droid.org would sign it with *its* key — a different
  app to Android, which would break the single-fingerprint promise in §3 and the
  custody model in `SIGNING.md`. That is the whole reason LW-M6-03 runs our own repo.
  Do not restore the shorter instruction.
- **Obtainium.** Point it at `https://github.com/CPlusPlus17/Redoubt` with the APK filter
  `arm64-v8a` (or the device's ABI). Not tested by the project yet; if Obtainium offers the
  version already installed, install it once, after which it tracks releases by tag.
- **direct APK.** Download the APK from the GitHub release. In your browser, allow installs
  from that source when Android asks. Install. There is no store behind this one: use
  Obtainium, or enable the opt-in in-app version check in Settings (see §6). Obtainium does not compare the signing certificate
  with ours, so the page tells the user to verify the first install themselves; Android's
  same-key rule then covers every update.

---

## 6. Update awareness, stated honestly

- **F-Droid:** the repository notifies you. The app hides its own check when F-Droid
  installed or last updated it.
- **direct APK:** there is no store. The app has an **opt-in** version check — **off by
  default**, foreground-only, at most once a day, and it sends nothing that identifies
  you beyond the request itself, not even the version string. The request is answered by
  GitHub Pages, so GitHub sees the IP address and the time (`docs/android/DISTRIBUTION.md`,
  the full contract). The page says: this APK has no store; here is how to turn the check on if you
  want a nudge, or how to use Obtainium instead. It does **not** say the app phones home,
  and it does **not** say the check is on by default.

---

## 7. What this page deliberately does not say

- It does not claim a Gecko content sandbox on Android (there is none — `PARITY.md` §1, §3.1).
- It does not present any `PARITY.md` PENDING row as verified (no device yet).
- It does not print any fingerprint other than the one in `SIGNING.md` / `README.md`.
- It does not promise a security-fix turnaround; it gives the dated record (`security.html`).
- It does not say the signing keys are offline or on a hardware key: today they are
  passphrase-encrypted files on the maintainer's workstation; the YubiKey move is "planned".
- Obtainium is pointed at the GitHub repository, not at `redoubtbrowser.org`.
- It does not soften the parity sentence in §1.
