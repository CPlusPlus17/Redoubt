# Google Play — Redoubt (Android)

Owner: **LW-M6-12** (`tasks.yaml`). Status 2026-10-05: **prepared, not live.** No Play
developer account exists yet, nothing has been uploaded, and the public site and README
do not mention Play. The edit that adds Play to them is held back until the listing is
live (see "When Play goes live").

This page is the owner's runbook for putting Redoubt on Google Play, and the record of
why the project now does what LW-M6-04 said it would not.

## 1. The owner decision (2026-10-05)

    DECIDED       2026-10-05
    DECIDED BY    Manuel Gysin (owner)
    CHOICE        publish Redoubt on Google Play, YES, with the EXISTING release key
                  uploaded to Play App Signing, so that the certificate fingerprint
                  is the same on every channel; Google holds a copy of that key
    REVERSES      LW-M6-04's "the Play Store is out of scope -- its signing model
                  conflicts with LW-M6-01"

The conflict LW-M6-04 named is real and is not resolved, only accepted. Play requires
Play App Signing for new apps: Google keeps the app signing key and signs every APK it
serves. Redoubt's choice is therefore between a **second key** for Play (a Play install
and a GitHub/F-Droid install would then be different apps to Android, with no way to
move between them without losing the profile) and **giving Google a copy of the one
key**. The owner chose the copy. What that costs is written in `SIGNING.md`, "Google
holds a copy of the app signing key", and `SECURITY.md` §1: in short, **Google can sign
an update for `org.redoubtbrowser` that every install accepts, including the ones that
never came from Play.**

## 2. Requirements checked (2026-10-05)

Every fact below was read on the official page on 2026-10-05. Where a page did not say
something, this file says so instead of filling it in.

| requirement | what applies to Redoubt | source |
|---|---|---|
| App Bundle for new apps | "From August 2021, new apps are required to publish with the Android App Bundle." Compressed download (base + config APKs) <= 4 GB. Redoubt's per-ABI download is about 120 MB. | developer.android.com/guide/app-bundle |
| Play App Signing, existing key | Play Console: choose to upload your own key, "download and run the PEPK tool, and upload the generated file with your encrypted key". Must be chosen **before the first release is rolled out**; the default is a Google-generated key. | developer.android.com/studio/publish/app-signing; support.google.com/googleplay/android-developer/answer/9842756 |
| Upload key | Separate upload key recommended ("For maximum security, your upload key and app signing key should be different"); a lost upload key is **reset** by Play support from a new certificate (`keytool -export -rfc ...`, then a reset request in Play Console). If no upload key is registered, the app signing key itself stays the upload key. | answer/9842756; studio/publish/app-signing |
| Key validity | "the key you use to sign your app must have a validity period ending after 22 October 2033". The release certificate is valid until 2054-01-08 (read from the 157.0-2 APK). | studio/publish/app-signing |
| Quantum-ready hybrid signing | New apps with a **Google-generated** key are enrolled automatically in "quantum-ready, hybrid signing" (RSA 4096 + ML-DSA-65, verified on Android 17+ with signature scheme v3.2, using **Google-generated keys** that differ from the classical key). For an app that uploads its own key, Google's Android 17 post says existing apps **opt in**. Not confirmed: whether a hybrid upgrade links the new keys to ours by a proof-of-rotation lineage. Redoubt must **not** opt in (see §4). | answer/9842756; blog.google/security/security-for-the-quantum-era-implementing-post-quantum-cryptography-in-android/ |
| Target API level | From 2026-08-31, "New apps and app updates must target Android 16 (API level 36) or higher" (extension to 2026-11-01 on request). Redoubt 157.0-2 targets **API 37** (`aapt2 dump badging`, `targetSdkVersion:'37'`), minSdk 26. | developer.android.com/google/play/requirements/target-sdk |
| New personal accounts: testing | Personal accounts created after 2023-11-13 "must run a closed test for their app with a minimum of 12 testers who have been opted in continuously for at least 14 days" before production access. Organization accounts are not named by this rule. | answer/14151465 |
| Account types | Personal: legal name, address, contact email and phone, verified before publishing. Organization: additionally a D-U-N-S number (free from Dun & Bradstreet), organization website and phone. One-time registration fee US$25. | answer/13628312; answer/6112435 |
| Developer verification (sideloading) | Applies on and off Play. Timeline on the page: August 2026 developer APIs, limited-distribution accounts and a power-user "advanced flow"; **2026-09-30** protections begin for installs in Brazil, Indonesia, Singapore and Thailand on certified devices (Android 7+); **2027** global. ADB installs are exempt. A Play Console account can register apps distributed outside Play too, and registration is per package name + signing key with proof of key ownership. | developer.android.com/developer-verification; .../developer-verification/guides/faq |
| No self-update | "An app distributed via Google Play may not modify, replace, or update itself using any method other than Google Play's update mechanism", nor download executable code (dex, JAR, .so) from elsewhere; JavaScript in a browser is exempt. | answer/9888379 (Device and Network Abuse) |
| Data safety | Required even for apps that collect nothing, with a privacy-policy link. "Collection" = transmitting user data off the device, **including by libraries/SDKs**; not declared: webview/open-web navigation, end-to-end-encrypted data, user-initiated sharing. | answer/10787469 |
| Account deletion | Required when the app lets users create an **app account**, "a unique user identity that developers provide". | answer/13327111 |
| Listing assets | Icon 512x512 32-bit PNG; feature graphic 1024x500 no alpha; >= 2 screenshots; short description <= 80 characters; title <= 30. | answer/9866151; answer/9898842 |

### What the developer-verification program means for the direct APK

Confirmed (developer.android.com/developer-verification and its FAQ, read
2026-10-05): the program covers apps outside Play. Enforcement began 2026-09-30, but
only for installs from **participating stores** in Brazil, Indonesia, Singapore and
Thailand on certified devices; the FAQ says that for "other stores, or if users
sideload your app directly, these new verification requirements won't apply to your
app yet", and recommends verifying before the global rollout in 2027. ADB installs
are exempt ("you are free to install apps without verification with ADB"). A user who
wants an unverified app goes through the one-time "advanced flow": developer mode, a
restart and re-authentication, a 24-hour wait, biometric confirmation.

Registration needs the package name, the signing certificate and the developer's
identity. The FAQ also says that "developers with a Play Console account can use it as
the single place to manage all their verification requirements, including for their
apps distributed outside of Play", and that "if you use Play App Signing, ... your
eligible apps will be part of the automatic registration process". Because the Play
app is signed with the **same** key as the GitHub and F-Droid APKs, **the Play account
is also the verification path for the direct and F-Droid APKs** before 2027. Not
confirmed: what "eligible" excludes, and whether our own F-Droid repository's client
will ever count as a participating store. Re-read the FAQ before 2027.

## 3. The Play build

`scripts/android-apk.sh --bundle` (CI: dispatch `android-release.yaml` with
`mode=full bundle=true`) adds a third Gradle pass, `fenix:bundleRelease`, after the
APKs are built and verified. It uses the same tree, the same fat GeckoView AAR and the
same `MOZ_BUILD_DATE` as the APKs. Its output is `<outdir>/aab/fenix-release-unsigned.aab`
with `bundle-metadata.json` and `SHA256SUMS.aab`, and CI publishes them as the separate
artifact `redoubt-android-aab-unsigned`. CI never signs it and never talks to Google.

- **Update check: compiled out, always.** The bundle pass passes
  `-PlwUpdateCheckPubkey=` (empty) whatever `--update-check` says for the APKs. So
  `BuildConfig.LW_UPDATE_CHECK_PUBKEY` is "", the Settings row is hidden and the check
  has no code path (`patches/android/update-check.patch`). `scripts/android-aab.py
  inspect --forbid-key-file` fails the build if any dex in the bundle carries the
  committed key or the key the APKs were built with. This is Play's no-self-update rule
  ("Device and Network Abuse"). It is also DISTRIBUTION.md's "store builds do not
  double-notify".
- **A separate Gradle invocation.** Fenix's `build.gradle` turns
  `jniLibs.useLegacyPackaging` off when any requested task name contains "bundle".
  Running `bundleRelease` in the same invocation as `assembleRelease` would therefore
  change how the direct APKs package `libxul.so`.
- **Native libraries are checked.** Each `base/lib/<abi>/libxul.so` in the bundle must be
  byte-identical to the fat-AAR input (`--maven-zip`). The bundle must carry exactly the
  APKs' ABIs.

### versionCode, and moving between channels

Fenix computes the versionCode from `MOZ_BUILD_DATE` (hours since 2014-12-28, shifted
left by 3) and three low bits: x86 family, 64-bit, universal
(`ConfigPlugin.generateFennecVersionCode`; `android-aab.py versioncode` is the same
arithmetic). A bundle has no ABI filter, so Fenix's per-output code sees it as
**universal**, and every APK Play generates from it carries one code: the build's
**universal** code. For 157.0-2 (`MOZ_BUILD_DATE 20261005000000`) the codes are:

    armeabi-v7a  2016188480     arm64-v8a  2016188482
    x86_64       2016188486     universal  2016188487   <- the AAB's code

The AAB's code is above every per-ABI APK of the same build and equal to the universal
APK's. `android-aab.py inspect --build-date --apk-metadata` enforces both. It cannot be
strictly above the universal APK without changing Fenix's scheme for every channel,
which is not worth it: the universal APK is the "prefer a per-ABI APK" fallback.

Android installs an update only if it is signed by the same key and the versionCode is
not lower. Play offers an update only when its code is higher than the installed one.
With one key everywhere, that gives:

| from | to | result |
|---|---|---|
| GitHub/F-Droid per-ABI APK, build N | Play, build N | Play may offer it as an update (a higher code); same app, same data. The installer of record becomes Play. |
| GitHub/F-Droid APK, build N | Play, build N+1 | ordinary update. |
| Play, build N | GitHub per-ABI APK, build N | **refused** (`INSTALL_FAILED_VERSION_DOWNGRADE`): 480/482/486 < 487. Harmless: it is the same build. |
| Play, build N | GitHub APK, build N+1 | ordinary update. Every later build date is at least one hour later, so +8 or more, which beats any low bits. Play stops updating the app until its own code is higher again. |
| any channel | any channel, **different key** | never happens while the key is shared. This is the whole point of uploading the existing key. |

Build N+1 must have a later `MOZ_BUILD_DATE` than build N, which is already the release
rule (`android-release.yaml` input `build_date`). Measured on the emulator with a
throwaway key, in both directions: `docs/android/evidence/lw-m6-12/README.md`.

### Testing what Play will serve

`scripts/bundletool.sh` runs Google's bundletool 1.18.3, pinned by version and
sha256 `a099cfa1543f55593bc2ed16a70a7c67fe54b1747bb7301f37fdfd6d91028e29`. That is
GitHub's own asset digest for the release (checked with `gh api` on 2026-10-05) and was
re-measured on the downloaded jar. It is used only to turn a signed bundle into
installable APKs with a **throwaway** key:

    scripts/bundletool.sh build-apks --bundle=fenix-release.aab --output=play.apks \
        --mode=universal --ks=<throwaway.p12> --ks-key-alias=<alias> --ks-pass=pass:<pw>
    scripts/bundletool.sh build-apks --bundle=fenix-release.aab --output=device.apks \
        --connected-device --ks=... ; scripts/bundletool.sh install-apks --apks=device.apks

The whole path (build, owner signing with `sign-aab.sh`, bundletool, emulator install,
and moving between channels in both directions) was rehearsed with throwaway keys on
2026-10-05: `evidence/lw-m6-12/README.md`. The rehearsal found that `jarsigner -verify
-strict` rejects every self-signed upload key, and that was fixed in `sign-aab.sh`
before any owner run. `sign-aab.sh` needs a JDK's `jarsigner` on box A
(Fedora: `java-21-openjdk-devel`).

Two things a Play install has that the rehearsal could not show: the installer of
record is `com.android.vending`, and Settings keeps Fenix's "Rate on Google Play"
row, which on the Play build finally points at a real listing.

## 4. One-time setup (owner)

The agent never creates the account, never holds a key and never uploads. Every step
here is the owner's. Run steps 3-5 **in this order**, before any bundle is uploaded.
The first upload of a bundle without a configured key makes Google generate one, and
that cannot be undone once a release rolls out.

### Step 1 — account

1. **Personal or organization.**
   - **Organization** needs a legal entity and its free **D-U-N-S number** (Dun &
     Bradstreet; it can take days to weeks to be issued). It avoids the "12 testers
     for 14 days" gate, because that rule names personal accounts only, and the
     listing shows the organization's name.
   - **Personal** works without a company. It has to pass the closed-test gate (step 8)
     before production access.
   - **Recommendation:** if a registered entity (for example a Swiss sole
     proprietorship listed in the commercial register) exists or is wanted anyway, use
     an **organization** account with its D-U-N-S. Otherwise use a **personal** account
     and plan for the 14-day closed test. Before submitting, check on the sign-up form
     what Play will show publicly (name, address, email, phone) for the type you pick.
     This page could not confirm the 2026 public-display rules.
2. Pay the one-time US$25 fee. Complete identity verification (legal name and address,
   phone and email by one-time code; organizations also the D-U-N-S data).
3. Turn on 2-step verification for the Google account that owns the developer account.

### Step 2 — create the app

Play Console → **Create app**: app name `Redoubt Browser`, default language English
(United States), **App**, **Free**. Accept the declarations. The package name is fixed by
the first bundle upload: it must be **`org.redoubtbrowser`**, and every bundle from
`--bundle` carries it (`android-aab.py inspect --expect-package`).

### Step 3 — Play App Signing with the EXISTING key (PEPK)

Play Console → the app → **Test and release → Setup → App signing** (or, at the first
"Create release", **Change app signing key**). Choose the option to **use your own
existing key from a Java keystore** ("Export and upload a key from Java keystore").
The Console then offers two downloads, `pepk.jar` and Google's
`encryption_public_key.pem`, and prints the exact command with your app's values. Run
it on **box A**, in your own terminal, from a directory that is not inside the git
checkout:

    keytool -list -keystore ~/redoubt-release.p12 -storetype PKCS12   # read the alias
    java -jar pepk.jar \
        --keystore=$HOME/redoubt-release.p12 \
        --alias=<alias printed above> \
        --output=redoubt-release-encrypted.zip \
        --include-cert \
        --rsa-aes-encryption \
        --encryption-key-path=encryption_public_key.pem

PEPK asks for the keystore and key passphrases. If the Console prints a different
command (a newer PEPK), **use the Console's command**; the flags above are the
long-standing form and only the Console's copy is authoritative for your app. Upload
`redoubt-release-encrypted.zip` in the same dialog. That file is the private key,
encrypted to Google. Delete it afterwards (`shred -u`). Google cannot use it before you
upload it, and nobody else can decrypt it, but there is no reason to keep it.

Then check, on **App signing**, that **App signing key certificate → SHA-256** reads
exactly

    64:14:EB:33:46:81:CF:6E:92:90:34:B5:6A:06:2D:2B:8D:A0:90:82:21:72:F7:A3:95:2C:85:FD:D1:28:3B:D0

If it does not, stop: do not roll out any release, and remove the key while that is
still possible.

**Do not opt in to the quantum-ready hybrid key upgrade** (or any "key upgrade") for this
app. Google generates the keys for it. On Android 17 and later, a Play install would
then be verified against a Google key that the GitHub and F-Droid APKs do not carry,
and this page cannot confirm that cross-channel updates survive that. Revisit it only
when the same upgrade can be applied to every channel.

### Step 4 — the upload key (separate, owner-held)

The release key is used **once**, for the PEPK export. Every upload after that is signed
with a separate **upload key**. Google resets a lost upload key on request; the app
signing key cannot be replaced at all.

    keytool -genkeypair -keystore ~/redoubt-play-upload.p12 -storetype PKCS12 \
        -alias upload -keyalg RSA -keysize 4096 -sigalg SHA256withRSA \
        -validity 10950 -dname "CN=Redoubt Play upload, O=Redoubt, C=CH"
    keytool -export -rfc -keystore ~/redoubt-play-upload.p12 -alias upload \
        -file redoubt-play-upload-cert.pem
    keytool -printcert -file redoubt-play-upload-cert.pem | grep SHA256

(10950 days is about 30 years, past Google's 2033 floor.) Register it on **App signing →
Upload key certificate**. If the Console asks for it at step 3, give it there. Commit
the **certificate's SHA-256 only**, as `assets/play-upload-cert.sha256`, one line, 64 hex
characters with or without colons. `sign-aab.sh` refuses any other signer, and it
refuses the release key outright.

Custody: on box A, like the release key, but **a different file and a different
passphrase**. Keep an offline backup the same way. Losing it means a reset request,
with uploads paused for a few days. Losing it does not end the app. If it leaks,
request a reset at once: a leaked upload key lets someone upload a bundle **for Google
to sign**, but only into this Play Console account.

### Step 5 — App content (Policy → App content)

| item | answer |
|---|---|
| Privacy policy | `https://redoubtbrowser.org/privacy-policy.html` (`site/privacy-policy.html`): who publishes, what the developer collects (nothing), each connection the app makes on its own and on request, on-device data, permissions, children, changes and contact. |
| Ads | **No**, the app contains no ads. |
| App access | **All functionality is available without special access** (no login; Sync is optional). |
| Content rating | IARC questionnaire, see §6. |
| Target audience | **18 and over** only. This is a general-purpose web browser that is not designed for children, and picking an under-18 group brings the Families policy into play. |
| News app | No. |
| Data safety | See §7. |
| Advertising ID | **No.** The manifest has no `com.google.android.gms.permission.AD_ID` (checked on the 157.0-2 APK and the bundle). |
| Government / financial / health apps | No / No / No. |
| Account deletion | Redoubt has **no app account**. The optional Mozilla account belongs to Mozilla (a third party) and is not "a unique user identity that developers provide" (answer/13327111). If the Console insists anyway, give Mozilla's own account-deletion page and say so in the note. |
| Permissions declarations | See below. |
| Foreground service declarations | See below. |

**Sensitive permissions in the manifest.** These were read from the 157.0-2 arm64 APK
with `aapt2 dump badging`. The bundle carries the same set (evidence README). Three
need a declaration:

| permission | why Redoubt has it | Play declaration |
|---|---|---|
| `QUERY_ALL_PACKAGES` | opening links in, and sharing to, other apps; "open in app" for sites that have one | **Permissions Declaration Form.** Browsers are a named permitted use ("device search, antivirus apps, file managers, and browsers", answer/10158779). Core functionality: "Web browser". |
| `REQUEST_INSTALL_PACKAGES` | the user taps a downloaded `.apk` and the browser hands it to the system installer | **Permissions Declaration Form.** "Web browsing or search" is a permitted use (answer/12085295). |
| `FOREGROUND_SERVICE_DATA_SYNC`, `_MEDIA_PLAYBACK`, `_SPECIAL_USE` | downloads (`DownloadService`, dataSync); media sessions and listen-to-page (mediaPlayback); the private-browsing notification, crash handler and profiler services (specialUse) | **Foreground service declaration** for each type: a description, the user impact if deferred or interrupted, and a **video link** for each (answer/13392821). Record the videos on the emulator: a download, media playback with the screen off, and a private tab's notification. |

No declaration is needed for the rest. Camera, microphone and location (foreground only;
there is no `ACCESS_BACKGROUND_LOCATION`) are runtime permissions that a website asks for
through the browser's prompt. The others are `POST_NOTIFICATIONS`, `USE_BIOMETRIC`,
`READ_MEDIA_AUDIO`, `READ_MEDIA_VISUAL_USER_SELECTED`, `CREDENTIAL_MANAGER_*`,
`RECEIVE_BOOT_COMPLETED`, `REQUEST_DELETE_PACKAGES`, `ACCESS_LOCAL_NETWORK` and the
app-private permissions. `CREDENTIAL_MANAGER_SET_ORIGIN` lets a browser pass the website's
origin to Credential Manager; whether a password manager trusts that is the manager's
own allowlist (`site/passkeys.html`), and Play lists no declaration form for it.

### Step 6 — store listing

Paste from `docs/android/play/listing-en-US.md`: title `Redoubt Browser`, the short and
full descriptions, category, contact, website and privacy URL. Upload
`docs/android/play/graphics/icon-512.png`, `feature-graphic-1024x500.png` and the phone
screenshots in `docs/android/play/screenshots/`. `python3
docs/android/play/check-listing.py` checks the lengths and the trademark rule.

### Step 7 — first upload, internal testing

Build, sign and upload as in §5 "Every release", into **Internal testing**. Internal
testing has no review delay. Add yourself as a tester, install from the opt-in link on
a real phone, and check:

- **Settings → About** shows the expected version, and Settings has **no** "Check for
  updates" row;
- `adb shell dumpsys package org.redoubtbrowser | grep -A1 signatures`, or an app like
  AppVerifier, shows the fingerprint `64:14:EB:33:...:3B:D0`;
- on a phone that already has the GitHub APK of an **older** build: Play offers the
  update and the profile survives it. This is the cross-channel check, done once for
  real.

### Step 8 — closed test, 12 testers, 14 days (personal accounts)

Create a **Closed testing** track and add at least **12** testers (a Google Group or an
email list). They must stay opted in **continuously for 14 days**. Recruit them from the
early adopters who installed the betas: a GitHub Discussions post and the release notes
of the next GitHub release ("help Redoubt reach Google Play: opt in for two weeks").
Ask for real use, not just an install: Google asks about tester engagement when you
apply. Keep 15 or more testers on the list: only testers "opted in continuously for
at least 14 days" count (answer/14151465), so one who opts out partway no longer counts
and can drop you below 12. After 14 days, **Apply for production** (Dashboard). Expect
that review to take days, not hours; this page did not confirm Google's current
estimate.

## 5. Every release

Same day as the GitHub release, from the same CI run:

1. Dispatch `android-release.yaml` with `mode=full`, the release's `build_date`, its
   `update_check` setting for the APKs, and **`bundle=true`**. The run uploads
   `redoubt-android-unsigned-apks` (unchanged) and **`redoubt-android-aab-unsigned`**
   (`fenix-release-unsigned.aab`, `bundle-metadata.json`, `SHA256SUMS.aab`).
2. On box A, put the AAB artifact into the signing bundle as `play/`, next to `apk/`:

        mkdir -p play && cd play
        unzip ../redoubt-android-aab-unsigned.zip   # the three files above
        cp <repo>/scripts/android-aab.py <repo>/docs/android/SIGNING.md \
           <repo>/docs/android/evidence/lw-m6-01/sign-aab.sh \
           <repo>/assets/play-upload-cert.sha256 .
        ./sign-aab.sh ~/redoubt-play-upload.p12

   `sign-aab.sh` checks the sha256 against `SHA256SUMS.aab` and that the bundle is
   unsigned and is `org.redoubtbrowser`. It signs with `jarsigner`. An AAB is a JAR-signed
   zip, and apksigner cannot sign one. It then verifies that the signer is the
   registered upload certificate and is **not** the app signing key, and that the payload
   is byte-identical to CI's. Its output is `fenix-release.aab` plus `SHA256SUMS.aab.signed`.
3. Play Console → **Production** (or the testing track) → **Create new release** →
   upload `fenix-release.aab`. Release name: the release's version, e.g. `157.0-2`. Release notes
   are the GitHub release's summary. **Staged rollout** at 100% unless the release is
   risky. For a security release, turn **Managed publishing** off so that it goes out
   as soon as review passes.
4. When Play shows the release as live, download **App bundle explorer → the version →
   Downloads → Signed, universal APK** and run `scripts/android-verify-signature.sh`
   on it. It must print the published fingerprint. This is the one check that Google
   signed with **our** key.

Play review can delay a release by hours to days. The GitHub release does not wait for
Play: the GitHub and F-Droid builds go out as usual. A Play user is a day behind at
worst. A **security** release goes to Play the same hour as GitHub, as above.

## 6. Content rating (IARC questionnaire)

Category: **All other app types** (not a game). Expected answers, phrased the way the
questionnaire asks. The live questionnaire could not be read without an account, so
re-read each question as it appears:

- Violence, fear, sexuality, language, controlled substances, gambling, crude humour in
  the **app's own content**: **No** to all. The browser ships no such content.
- Does the app allow users to interact or exchange content: **No** for the app itself.
  The browser has no chat, accounts or user-generated content of its own.
- Does the app share the user's location with other users: **No**.
- Does the app allow purchases of digital goods: **No**.
- **Unrestricted internet access** (a web browser): **Yes.** This is the honest answer,
  and it shows as the interactive element "Unrestricted Internet" next to the rating.

## 7. Data safety answers

Derived from `site/privacy-policy.html`, `PARITY.md` and the build configuration
(telemetry and Glean upload compiled out, `--disable-crashreporter`, no GMS, no
advertising ID; update check compiled out of the Play build).

- **Does your app collect or share any of the required user data types?** **Yes**,
  because of one optional feature: Sync. Signing in to a Mozilla account sends the
  account **email address** to Mozilla's account servers through the app's Mozilla
  account library. Google counts data sent by an in-app library as collected,
  whoever receives it (answer/10787469). Everything else is not declared, each
  for a stated reason:
  - web pages, form data and anything else sent to the sites the user visits:
    open-web navigation, which Play says not to declare;
  - synced bookmarks, history, passwords and tabs: **end-to-end encrypted**, which is
    exempt;
  - search queries: sent by the user to the engine the user picked, a user-initiated
    transfer;
  - Remote Settings, add-on update checks and uBlock Origin filter-list downloads:
    they fetch data to the device and carry no user identifier. The add-on update
    check sends the add-on ids, the app version and the locale, which is app
    information, not a Data safety user data type;
  - crash reports, analytics and diagnostics: **none**, compiled out.
- **Email address** (Personal info): **collected**, **not shared**. **Optional** (only
  with Sync). Purpose: **App functionality** and **Account management**. **Not
  processed ephemerally.**
- **Is all of the user data collected by your app encrypted in transit?** **Yes**
  (HTTPS).
- **Do you provide a way for users to request that their data is deleted?** **Yes**:
  sign out of Sync in Settings, and delete the Mozilla account in Mozilla's account
  settings. The developer holds no user data to delete.
- **Independent security review:** No. **Committed to Play Families Policy:** not
  applicable (18+).

If a reviewer disputes the Sync line, the strict alternative is to declare **User IDs**
too (the Mozilla account id). Adding it costs nothing and is still true.

## 8. If Play rejects or removes the app

1. Read the email's **policy name** and the quoted evidence. Most rejections for
   browsers are declarations (QUERY_ALL_PACKAGES, REQUEST_INSTALL_PACKAGES, foreground
   services) or metadata (trademark or "keyword stuffing" in the listing). Fix the form
   or the text, and resubmit.
2. If the rejection is wrong, **appeal** through the Policy status page, quoting the
   policy text. For example, the Device and Network Abuse exemption for JavaScript run
   by a browser covers add-ons and uBlock Origin.
3. **Never** make the Play build less private to pass review: no GMS, no telemetry, no
   advertising ID, no in-app update check. If Play requires one of those, Play is not
   a channel for Redoubt. Record that here and in `tasks.yaml`, and unpublish.
4. Unpublishing Play does **not** take the key back. Google keeps the copy. A Play
   rejection does not affect the GitHub or F-Droid channels.
5. Account termination is the worst case: Play installs keep working, and those users
   can switch to the GitHub or F-Droid APK of a later build without reinstalling,
   because the key is the same.

## 9. When Play goes live

Prepared but **not applied**, because claiming a channel that does not exist yet would
be wrong:

- The README/site edit that adds the Play channel and corrects "one person holds the
  signing key". It is kept outside the repository as `play-site-pending.diff` (applies
  to the commit named in its header) and goes in only after step 3 has happened and the
  listing is public.
- `WEBSITE.md` §2/§5 and `DISTRIBUTION.md` already carry the Play row as **pending**.
  Change it to live then.
- `SIGNING.md` "Google holds a copy": fill in the date of the PEPK upload.
