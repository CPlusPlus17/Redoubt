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
| `index.html` | what Redoubt is, the not-LibreWolf/not-Mozilla notice, the §1 statement, status (beta), download, verify | `README.md`, this file |
| `install.html` | direct APK, verification, Obtainium step by step, the coming in-app check, stores | this file §5–6, `DISTRIBUTION.md`, `SIGNING.md` |
| `privacy.html` | the §1 statement, what changes, honest limits, link to the full matrix | `PARITY.md` §1, §5 |
| `privacy-policy.html` | the privacy policy (what the developer collects: nothing; each connection the app makes; permissions; contact). Its URL is the one Play's listing and Data safety form point to | `PLAY.md` §5/§7, `PARITY.md`, `DISTRIBUTION.md` |
| `sync.html` | sync with LibreWolf desktop | `SYNC.md` |
| `passkeys.html` | password managers, autofill and passkeys: what works, known gaps | `README.md` "Passwords and passkeys", `PARITY.md` §8 |
| `security.html` | private reporting, fingerprint, where bugs go | `SECURITY.md`, `README.md` |
| `fdroid.html`, `fdroid-qr.svg` *(not yet: written by `fdroid-repo.sh publish-page` after the owner's `init`)* | how to add Redoubt's F-Droid repository: its `fdroidrepos://` link, QR code, address and fingerprint, the archive, and that the repository itself is in a Hetzner Object Storage bucket | `FDROID.md`; rendered from `assets/fdroid/fdroid.html.in`, never edited by hand |
| `update/**` | the signed update-check endpoint | `DISTRIBUTION.md` — published verbatim; the site neither writes nor edits it |

Rules the checker enforces, so they do not depend on review:

- **Nothing third-party.** No `<script>` at all (the site works without JavaScript), no web
  fonts, no CDN, no analytics, no image or stylesheet from another origin. A
  Content-Security-Policy meta (`default-src 'none'`, `img-src`/`style-src 'self'`) backs
  this up in the browser.
- **External links only to** `github.com/CPlusPlus17/Redoubt` (releases, docs, issues,
  reporting), `librewolf.net` (attribution), `mozilla.org` (trademark notice) and
  `f-droid.org` (where users get the F-Droid client). Other projects (IronFox, Obtainium,
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

Not yet done by the site, and owned elsewhere: the DNS records pointing `redoubtbrowser.org`
at GitHub Pages and enabling Pages (source: GitHub Actions) and "Enforce HTTPS" in the
repository settings are owner actions. Until DNS is set the Page is reachable only at the
repository's `github.io` address, and docs keep linking to GitHub rather than the domain.

Download links point at `releases/latest`. Since 2026-10-04 (owner decision) each beta is
published as a full GitHub release marked **Latest**, not as a prerelease, so that shortcut and
Obtainium's default settings find it. "Beta" stays in the title and notes; this is not a
stable-release declaration.

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

Three channels. All three are signed with the **same** APK signing key — one trust root
(`docs/android/SECURITY.md`) — so there is **one fingerprint** for all of them, published in
§3. F-Droid and Accrescent each carry their own updater, so they must **not** also run the
in-app check (see §5 and `docs/android/DISTRIBUTION.md`).

| channel | what it is | how it updates | in-app check present? |
|---|---|---|---|
| **F-Droid** | **Redoubt's own F-Droid repository**, hosted in the owner's Hetzner Object Storage bucket (`https://<bucket>.<location>.your-objectstorage.com/repo`; how to add it: `fdroid.html` on this site; `FDROID.md`), not f-droid.org's main repo (LW-M6-03) | F-Droid's own updater, once our repo is added | in the APK (the repository serves the direct APKs), **not offered** when F-Droid installed or last updated the app (from the build after 157.0-2) |
| **Accrescent** | the Accrescent repository | Accrescent's own updater | **no** (compiled out) |
| **direct APK** | the download on `redoubtbrowser.org` | the opt-in in-app version check (`DISTRIBUTION.md`) or the user's own tool (e.g. Obtainium) | **yes** (opt-in, off by default) |
| **Google Play** *(pending, LW-M6-12; owner decision 2026-10-05)* | `org.redoubtbrowser` on Google Play, same key via Play App Signing (`PLAY.md`) | Google Play | **no** (compiled out; Play forbids self-update) |

The Google Play row is **not on the site yet**: it goes on the home and install pages
the day the listing is public (`PLAY.md` §9), together with the corrected key-custody
wording. Google holds a copy of the signing key, so "one person holds the key" stops
being true then (`SIGNING.md`, "Google holds a copy of the app signing key").

The direct-APK row is the one with no store, which is exactly why it has the opt-in version
check and why the page must tell the user that, and how to get update awareness otherwise.

---

## 3. Fingerprint

- The APK signing key was generated in **LW-M6-01** (2026-08-23, `docs/android/SIGNING.md`).
  Its SHA-256 certificate fingerprint is published on the site's home, install and security
  pages, copied from `README.md` and checked equal by `scripts/site-check.py`. It is the same
  key for all three channels, so there is one fingerprint, not three.
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

and the certificate fingerprint (§3) the second must print. **If either differs, do not
install**, and report it privately (GitHub private vulnerability reporting, `SECURITY.md`)
with the sha256 of what you have.

- The certificate check is the binding one: it is what Android itself enforces on every
  later update, so a verified first install protects the updates after it.
- On a phone without `apksigner`, the site names a certificate-viewing app (AppVerifier) as
  an after-install check, without linking it.

---

## 5. Install guide, per channel

- **F-Droid.** Install F-Droid. Then **add Redoubt's own repository** — its URL and
  fingerprint go in §3 and on `fdroid.html` when LW-M6-03 stands it up — and install
  **Redoubt** from it. F-Droid tells you when a new build lands; there is no in-app check to
  configure. The address is a Hetzner Object Storage bucket, not `redoubtbrowser.org`; the
  fingerprint is what proves it is ours. Older releases are in the repository's archive.

  Redoubt is **not** in f-droid.org's main repository and an earlier draft of this
  page said to use it. Going through the main repo means f-droid.org builds and
  signs the app with *their* key, which would break the single-fingerprint promise
  in §3 and the custody model in `SIGNING.md`. That is the whole reason LW-M6-03
  runs our own repo. Do not restore the shorter instruction.
- **Accrescent.** Install Accrescent. Add the Accrescent repository. Search for **Redoubt**,
  install it. Accrescent handles updates; there is no in-app check to configure.
- **direct APK.** Download the APK from `redoubtbrowser.org` (when it is live). In your
  browser, allow installs from that source when Android asks. Install. There is no store
  behind this one: point Obtainium at the GitHub repository, or, once a build carries it, enable the opt-in in-app
  version check in Settings (see §6). Obtainium does not compare the signing certificate
  with ours, so the page tells the user to verify the first install themselves; Android's
  same-key rule then covers every update.

---

## 6. Update awareness, stated honestly

- **F-Droid / Accrescent:** the repository notifies you. Nothing in the app is needed.
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
- It does not tell users to point anything at `redoubtbrowser.org` before DNS serves the site;
  Obtainium is pointed at the GitHub repository, which works today.
- It does not soften the parity sentence in §1.
