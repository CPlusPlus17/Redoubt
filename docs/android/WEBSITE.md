# The Android download page — content spec (`redoubtbrowser.org`)

Owner: **LW-M7-02** ("Publish the Android pages on redoubtbrowser.org"). This file is the
**content** of the download page, not a published site. `redoubtbrowser.org` is the decided
domain (see `docs/android/IDENTITY.md`) but is **not registered**; nothing on this page is a
live URL or a real address, and the page must not imply it is. The page is written to one
rule above all: **it must not overclaim.** The whole point of putting the parity statement
on the download page is that a user reads the honest version *before* they install.

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
| **F-Droid** | **Redoubt's own F-Droid repository**, not f-droid.org's main repo (LW-M6-03) | F-Droid's own updater, once our repo is added | **no** (compiled out) |
| **Accrescent** | the Accrescent repository | Accrescent's own updater | **no** (compiled out) |
| **direct APK** | the download on `redoubtbrowser.org` | the opt-in in-app version check (`DISTRIBUTION.md`) or the user's own tool (e.g. Obtainium) | **yes** (opt-in, off by default) |

The direct-APK row is the one with no store, which is exactly why it has the opt-in version
check and why the page must tell the user that, and how to get update awareness otherwise.

---

## 3. Fingerprint

- The APK signing key is generated in **LW-M6-01** (`docs/android/SECURITY.md`), a
  human-only (`agent_safe: false`) task. Its **fingerprint is published here and on every
  channel page once it exists.** It is the same key for all three channels, so there is one
  fingerprint, not three.
- Until LW-M6-01 runs, this slot is a **placeholder — it is intentionally empty.** Do not
  invent a fingerprint, and do not print a placeholder value that looks like one. The page
  states that the fingerprint will be published with the first signed release.
- A user who installs from any of the three channels should see the **same** fingerprint on
  the device; a different one is a signal the artifact is not what we published
  (`SECURITY.md` §1 treats the key as a one-way trust root).

---

## 4. How to verify what you downloaded

Every published APK ships with its **sha256** (`SECURITY.md`: "Pinned, checksummed
artifacts — every published APK ships with its sha256"). The download page lists the sha256
next to each link. After downloading:

    sha256sum redoubt-<version>-<abi>.apk

compare the printed digest to the one published next to the download link (and on the
channel page). **If it differs, do not install** and open an issue with the sha256 of what
you have, per `SECURITY.md`'s incident procedure.

- The digest is the binding check for a direct download. It is the same value `DISTRIBUTION.md`
  carries in the update-check document, so there is one source of truth, not two.
- GPG/signature verification, if and when a key and certificate are published from LW-M6-01,
  adds a `gpg --verify` step here. Until then, the sha256 is the verification, and the page
  says so plainly rather than implying a signature check that does not yet exist.

---

## 5. Install guide, per channel

- **F-Droid.** Install F-Droid. Then **add Redoubt's own repository** — its URL and
  fingerprint go in §3 when LW-M6-03 stands it up — and install **Redoubt** from it.
  F-Droid tells you when a new build lands; there is no in-app check to configure.

  Redoubt is **not** in f-droid.org's main repository and an earlier draft of this
  page said to use it. Going through the main repo means f-droid.org builds and
  signs the app with *their* key, which would break the single-fingerprint promise
  in §3 and the custody model in `SIGNING.md`. That is the whole reason LW-M6-03
  runs our own repo. Do not restore the shorter instruction.
- **Accrescent.** Install Accrescent. Add the Accrescent repository. Search for **Redoubt**,
  install it. Accrescent handles updates; there is no in-app check to configure.
- **direct APK.** Download the APK from `redoubtbrowser.org` (when it is live). In your
  browser, allow installs from that source when Android asks. Install. There is no store
  behind this one: either enable the opt-in in-app version check in Settings (see §6), or
  point a tool such as Obtainium at the `redoubtbrowser.org` update endpoint and let it do
  the checking.

---

## 6. Update awareness, stated honestly

- **F-Droid / Accrescent:** the repository notifies you. Nothing in the app is needed.
- **direct APK:** there is no store. The app has an **opt-in** version check — **off by
  default**, foreground-only, at most once a day, and it sends **only the current version
  string**, nothing that identifies the device (`docs/android/DISTRIBUTION.md`, the full
  contract). The page says: this APK has no store; here is how to turn the check on if you
  want a nudge, or how to use Obtainium instead. It does **not** say the app phones home,
  and it does **not** say the check is on by default.

---

## 7. What this page deliberately does not say

- It does not claim a Gecko content sandbox on Android (there is none — `PARITY.md` §1, §3.1).
- It does not present any `PARITY.md` PENDING row as verified (no device yet).
- It does not print a signing fingerprint or a signature-verification command before LW-M6-01
  publishes one.
- It does not treat `redoubtbrowser.org` as a live, resolving host (it is the decided, not-yet-
  registered domain).
- It does not soften the parity sentence in §1.
