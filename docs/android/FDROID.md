# The Redoubt F-Droid repository (LW-M6-03)

Redoubt runs its **own** F-Droid repository. It is not in f-droid.org's main repository,
because f-droid.org builds and signs apps with its own key, which would give Redoubt a second
fingerprint (`WEBSITE.md` §5, `SIGNING.md`).

    repository URL   https://redoubtbrowser.hel1.your-objectstorage.com/repo
                     (bucket and location: assets/fdroid/deploy.conf)
    archive URL      https://redoubtbrowser.hel1.your-objectstorage.com/archive
    human page       https://redoubtbrowser.org/fdroid.html   (rendered by `publish-page`)
    index key        RSA 4096, held by the owner only; its fingerprint is published by the
                     owner after `init`, never before ("Publishing the fingerprint" below)
    APKs             the GitHub release's per-ABI APKs, byte for byte, release key
                     64:14:EB:...:28:3B:D0 (`SIGNING.md`)
    hosting          the owner's Hetzner Object Storage bucket (owner decision 2026-10-05)
    retention        every release: the newest 5 in repo/, all older ones in archive/
    state            tooling and throwaway-key proof against a local S3 server done
                     2026-10-05; the owner has not created the bucket or run `init`, so
                     nothing is published

## Decisions (2026-10-05)

### Hosting: Hetzner Object Storage

The hosting decision changed three times on 2026-10-05. The record, in order:

1. **Hetzner Object Storage, rejected.** It cannot put a bucket under a custom domain, so the
   repository URL would not be `redoubtbrowser.org`.
2. **Swiss hosts, considered.** No Swiss S3 host was chosen.
3. **GitHub Pages, chosen.** The signed index was committed to `site/fdroid/repo/`, and
   `pages.yaml` downloaded the APKs from the GitHub release into the Pages artifact at deploy
   time. But GitHub Pages limits a published site to 1 GB, and one release's three per-ABI
   APKs are about 0.39 GB. Two releases fit and three did not, so the repository could keep
   only the current release and the one before it.
4. **Hetzner Object Storage, chosen** (owner, 2026-10-05, superseding item 3): "1-3 releases
   is not enough". The owner wants to keep every release, and accepts the bucket address in
   place of a `redoubtbrowser.org` URL.

The bucket address is acceptable because the address is not what identifies an F-Droid
repository. A client pins the **fingerprint** of the index key when the repository is added
and refuses any index signed by another key, whatever host serves it. The human page and its
QR code stay on `redoubtbrowser.org`, which users already trust for the APK fingerprint. The
page names the bucket host and says why it is Hetzner's. The cost of the address: it carries
the bucket name and Hetzner's domain for good. Moving the repository later is a mirror
operation ("Mirrors"), not a URL change.

The facts this rests on are from Hetzner's documentation, read 2026-10-05. The date in brackets
is each page's own "last change" date.

| fact | source |
|---|---|
| A public bucket serves objects at `https://<bucket-name>.<location>.your-objectstorage.com/<file-name>` (virtual-hosted style) | [Object Storage overview](https://docs.hetzner.com/storage/object-storage/overview/) (2024-09-23) |
| Locations and S3 endpoints: Falkenstein `fsn1.your-objectstorage.com`, Nuremberg `nbg1…`, Helsinki `hel1…`; Object Storage exists only in these three European locations | [Overview](https://docs.hetzner.com/storage/object-storage/overview/) (2024-09-23), [FAQ: General](https://docs.hetzner.com/storage/object-storage/faq/general/) (2024-09-23) |
| A bucket is created in Hetzner Console with visibility Private or Public. "Public: You don't need S3 keys for read permissions (e.g. read or download data). You still need S3 keys for write permissions" | [Creating a Bucket](https://docs.hetzner.com/storage/object-storage/getting-started/creating-a-bucket/) (2024-09-23) |
| "When you set the visibility to public during Bucket creation, we will automatically apply access policies that allow read access to all objects within the Bucket." Anyone who knows the URL and file name can download, but "file listing remains denied". Visibility can be changed later ("Reset visibility/policy"). Hetzner recommends making only empty buckets public. Own policies may limit read access to a prefix (`bucket_name/prefix/*`) | [FAQ: Buckets & objects](https://docs.hetzner.com/storage/object-storage/faq/buckets-objects/) (2024-09-23) |
| Bucket names: RFC 1123, 3-63 characters of `a-z`, `0-9` and `-`, start with a letter or digit, not end with `-`, not an IP address, unique across all Hetzner Object Storage users and locations | same FAQ |
| Custom domains are not supported: "Currently, it is not possible to assign a custom domain name to a Bucket." The documented CNAME workaround needs a host-header rewrite and has no TLS certificate for the custom name | [Supported actions](https://docs.hetzner.com/storage/object-storage/supported-actions/) (2024-09-23), [Custom domain with CNAME](https://docs.hetzner.com/storage/object-storage/howto-configurations/domain-cname/) (2025-03-17) |
| S3 credentials: Hetzner Console, Security, S3 Credentials, Generate credentials. The secret key cannot be viewed again once the window is closed. "By default, each key pair is automatically valid for every Bucket within the same project." | [Generating S3 keys](https://docs.hetzner.com/storage/object-storage/getting-started/generating-s3-keys/), [FAQ: S3 credentials](https://docs.hetzner.com/storage/object-storage/faq/s3-credentials/) (both 2024-09-23) |
| Limits: 5 GB per single PUT, 5 TB per object, 750 requests/s and 10 Gbit/s per bucket, 100 TB and 50,000,000 objects per bucket, 100 buckets and 200 S3 credentials per account | [Overview](https://docs.hetzner.com/storage/object-storage/overview/) (2024-09-23) |
| TLS: TLS 1.3 supported, TLS 1.2 "deprecated, support ending soon" | [FAQ: General](https://docs.hetzner.com/storage/object-storage/faq/general/) (2024-09-23) |
| rclone: provider S3, endpoint `fsn1.your-objectstorage.com`, `region = fsn1`, `acl = private`. s3cmd: DNS-style template `%(bucket)s.fsn1.your-objectstorage.com`. Credentials are bound to a project, endpoints to a location | [Using S3 compatible CLI tools](https://docs.hetzner.com/storage/object-storage/getting-started/using-s3-api-tools/) (2025-01-07) |
| CORS policies exist "to enable cross-origin requests" from web pages | [Applying CORS policies](https://docs.hetzner.com/storage/object-storage/howto-protect-objects/cors/) (2024-12-02) |

Consequences for this repository:

- **Public read: the console's Public visibility.** It is a dedicated bucket, so read access
  to every object is what is wanted. Listing stays denied, which costs nothing: F-Droid clients
  never list a repository, they fetch `entry.jar` and the files it names.
  `assets/fdroid/bucket-policy.json.in` is the equivalent policy (`s3:GetObject` for
  `*` on `arn:aws:s3:::<bucket>/*`, nothing else). It was applied to the local test server and
  is kept for the record. The owner does not need it on Hetzner.
- **URL form: virtual-hosted, as documented.** The repository URL is
  `https://<bucket>.<location>.your-objectstorage.com/repo`. The path-style public form
  `https://<location>.your-objectstorage.com/<bucket>/…` is not documented as a public URL, so
  it is not used. `verify` also checks the real URL and its TLS certificate (curl and Python
  both verify certificates by default) on every run.
  Bucket names with a dot are refused. Hetzner's naming rules forbid dots ("No period (.)",
  Buckets & objects FAQ, 2024-09-23), and a dot would put the name outside the single-label
  wildcard certificate.
- **Live check against the owner's bucket (2026-10-05, a probe object, deleted afterwards).**
  Bucket `redoubtbrowser` in `hel1`, visibility Public:
  - The certificate is `CN=hel1.your-objectstorage.com`, SAN `*.hel1.your-objectstorage.com`,
    valid to 2026-11-29 (Hetzner renews it).
  - Anonymous GET of an object returns 200 with `accept-ranges: bytes`. Anonymous listing,
    PUT and DELETE return 403.
  - A missing object returns **403, not 404**, so a 403 from `verify` means "missing" as
    often as "forbidden".
  - The pinned rclone 1.75.1 with the exact `rcl` settings (provider Hetzner, `acl=private`)
    uploads, and the object is still publicly readable: the bucket's Public policy overrides
    the private object ACL.
  - `rclone copy --immutable --checksum`, the command `deploy` uses for APKs, refused to replace
    an existing object with different content ("immutable file modified", exit 6). Note:
    `rclone copyto --immutable` on a single file did **not** refuse and overwrote it, which is
    why APKs must only ever go through `copy`.
  - Hetzner refuses a plain SigV4 upload that leaves the payload hash out of the signature
    (403). rclone signs it; any hand-made `curl --aws-sigv4` upload needs an
    `x-amz-content-sha256` header.
- **CORS: not needed.** CORS is enforced by browsers for scripts on other web pages. F-Droid
  clients are Android apps that fetch with their own HTTP stack, and `fdroid.html` loads
  nothing from the bucket (its QR code is a local SVG). No CORS policy is set.
- **S3 API addressing: rclone's default (path-style).** rclone 1.75.1 has a `Hetzner` provider
  (regions and endpoints `fsn1`, `nbg1`, `hel1`), and `force_path_style` defaults to true.
  Hetzner's own rclone example uses that default, so API calls go to
  `https://<location>.your-objectstorage.com/<bucket>/…`. This affects only uploads. The URL
  users add is the virtual-hosted public one.
- **Credentials are project-wide.** Create the bucket in a **Hetzner project of its own**,
  so the deploy key cannot touch any other bucket. The owner created bucket `redoubtbrowser` in
  `hel1` on 2026-10-05 (`assets/fdroid/deploy.conf`). If its project holds other buckets, the
  key in `s3.env` can reach them too.

**Costs.** The figures are the launch prices of December 2024: a base price of €4.99 a month
excluding VAT, with 1 TB of storage (744 TB-hours) and 1 TB of egress traffic included. Beyond
that, €0.0067 per TB-hour for storage (about €4.99 per TB-month) and €1.00 per TB of egress.
Ingress and S3 operations are free. [hetzner.com/storage/object-storage](https://www.hetzner.com/storage/object-storage/)
renders its prices with JavaScript and could not be read as text on 2026-10-05, so the figures
are from launch coverage ([heise](https://heise.de/-10189226),
[DataCentreNews](https://datacentrenews.uk/story/hetzner-unveils-new-scalable-s3-compatible-object-storage)).
The billing model (hourly, one base price per account, quota pooled across buckets, billed in
0.0001 TB steps, 64 kB minimum object size) is from the
[Overview](https://docs.hetzner.com/storage/object-storage/overview/). **Confirm the current
prices in the console before creating the bucket.** Estimate for this repository:

| | per release | per year (about 15 releases) | included in the base price |
|---|---|---|---|
| storage, three per-ABI APKs | 0.39 GB (0.78 GB counting the stale `repo/` copy, see "Retention") | 6-12 GB | 1,000 GB |
| egress, one APK download | 0.13 GB | - | about 7,700 downloads a month |

The index files are small: `entry.jar` is 2.8 kB, which is what a client fetches to check for
updates. So the base price covers this repository for years. Egress past 1 TB a month costs
about €1 per further 7,700 downloads.

### What the repository serves: the three per-ABI APKs of each release, not the universal one

F-Droid clients pick the APK whose `nativecode` matches the device, and every supported device
matches arm64-v8a, armeabi-v7a or x86_64. The universal APK (288 MB) carries the highest
versionCode of its build (`+7`), so clients would prefer it and download 2.2 times the bytes. It
stays on the GitHub release.

### Retention: keep every release

`update` runs fdroidserver with `archive_older` set so that the main section (`repo/`) shows
the newest **KEEP_VERSIONS** releases (default 5, `assets/fdroid/deploy.conf`). Every older APK
moves to the archive section (`archive/`), whose index fdroidserver signs with the same key.
fdroidserver's `archive_older` counts APK files per app, not releases, so the script writes
`KEEP_VERSIONS x 3`. That counts releases exactly, because `add` refuses a release that lacks
any of the three ABIs. A "release" is one build hour: every APK of a Redoubt build shares
`versionCode >> 3`.

**Nothing is ever deleted** by the tooling, locally or in the bucket. In F-Droid 2.0.1 the
archive is per repository: in *Repositories*, open Redoubt, then *Settings*, then turn on
*Show archived apps and outdated versions of apps*. The app page then offers
*Redoubt (archive)* in its repository list (`evidence/lw-m6-03/hetzner/screens/10-16`).

One storage cost follows from "never delete". When a release moves from `repo/` to `archive/`,
`deploy` uploads it to `archive/` and leaves the old `repo/` copy in the bucket, unreferenced.
`deploy` lists such copies as "orphan" after every run. They cost storage (0.39 GB per release)
but are never served by an index. The owner may delete them by hand in the console. The tooling
never does.

### Anti-features: `Tracking`

F-Droid defines it as "apps that track you and/or report your activity to somewhere, either
without your permission or by default"
([Anti-Features](https://f-droid.org/en/docs/Anti-Features/), read 2026-10-05). F-Droid's own
metadata gives that label, with the reason "Connects to various Mozilla services", to Fennec
F-Droid and to Mull, a hardened fork like Redoubt
([org.mozilla.fennec_fdroid.yml](https://gitlab.com/fdroid/fdroiddata/-/raw/master/metadata/org.mozilla.fennec_fdroid.yml),
[us.spotco.fennec_dos.yml](https://gitlab.com/fdroid/fdroiddata/-/raw/master/metadata/us.spotco.fennec_dos.yml),
read 2026-10-05). Redoubt still contacts Remote Settings and addons.mozilla.org by default
(`PARITY.md`), so the same label applies. The reason is spelled out in
`assets/fdroid/metadata/org.redoubtbrowser.yml`. An earlier draft declared no anti-features;
that was not consistent with how F-Droid labels the same behaviour. `NonFreeNet` ("depend
entirely on a proprietary network service") does not apply: the browser does not depend on
those services, and their server software is free. `NonFreeAdd` was not given to Fennec either.

### No double notification, without a second Gecko build

The APKs are the direct-download APKs, and they have the opt-in update check compiled in. The
app hides the "Check for updates" row, and never runs the check, when the **installer of
record** is a store client: F-Droid (`org.fdroid.fdroid`, `org.fdroid.basic`), Droid-ify, Neo
Store, Accrescent or Play. That is `UpdateCheck.isOffered` in `patches/android/update-check.patch`,
and `DISTRIBUTION.md`, "F-Droid and Accrescent do not double-notify", records the contract
change. It ships from the first build after 157.0-2. 157.0-2 itself has only the switch, which
is off by default, and the repository description tells F-Droid users to leave it off.

How Android reports the installer of record was measured on an API 34 emulator with F-Droid
2.0.1 (`evidence/lw-m6-03/logs/11-13`; the fresh install from the bucket repeated row 2,
`evidence/lw-m6-03/hetzner/logs/21`):

| how the app got there | `installerPackageName` | update owner |
|---|---|---|
| hand install of Beta 5, then **F-Droid updates it** to 157.0-2 | `org.fdroid.fdroid` | none (F-Droid can claim it only on an initial install) |
| fresh install from the repository by F-Droid | `org.fdroid.fdroid` | `org.fdroid.fdroid` (F-Droid sets `setRequestUpdateOwnership(true)` on API 34+, `SessionInstallManager.kt`) |
| APK installed by hand over that F-Droid install | system package installer | cleared |

So the installer of record is whoever made the **latest** install or update, which is the
behaviour the check needs. `InstallSourceInfo.getInstallingPackageName` is documented as "the
installer of record" and "may be modified via `setInstallerPackageName`"
([AOSP source](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/core/java/android/content/pm/InstallSourceInfo.java),
read 2026-10-05). Two limits: rows 1 and 3 used `pm install -i` from adb, which stands in for a
hand install but skips the Android 14 update-ownership prompt a real user would see when
overriding F-Droid's ownership. And an installer that reports nothing (adb, an uninstalled
store) counts as "not a store", so the switch stays offered, off by default.

### Tooling

**fdroidserver: F-Droid's own container image, pinned by digest.** It is
`registry.gitlab.com/fdroid/docker-executable-fdroidserver@sha256:75f6b88e…`, the `master` tag
of 2026-10-04, fdroidserver commit `c21c177ff6d8`. A pinned pip version in a venv was the
alternative. The image also brings the exact `apksigner`, `keytool` and `python3-qrcode`
versions fdroidserver is tested with, and a digest pins all of them at once. The `latest` tag is
a 2024 build. The container that sees the repository key runs with `--network=none`.

**Upload: rclone 1.75.1, pinned by the sha256 of its release zip**
(`982b5aa7…0a13ab` for linux-amd64, `03f25041…dc0dff9` for linux-arm64). The sums come from
`https://downloads.rclone.org/v1.75.1/SHA256SUMS`, whose PGP signature was verified on
2026-10-05 against rclone's release key `FBF737ECE9F8AB18604BD2AC93935E02FF3B54FA`
([rclone.org/release_signing](https://rclone.org/release_signing/), `evidence/lw-m6-03/hetzner/logs/00-rclone-pin.txt`). `deploy` downloads the zip once into
`~/redoubt-fdroid/tools/`, checks the sha256 on every run, and extracts the binary into a
private temporary directory for that run only. fdroidserver's own `fdroid deploy` was the
alternative, and it was rejected: its rclone path runs `rclone sync --delete-after`
(`fdroidserver/deploy.py`, `update_remote_storage_with_rclone`), which deletes remote files
that are missing locally. That breaks "never delete", and its upload order is not "APKs first,
index last". rclone's `Hetzner` provider covers the endpoints, and plain `copy`/`copyto` never
delete anything.

## The pieces

| file | role |
|---|---|
| `scripts/fdroid-repo.sh` | the owner's tool: `init`, `add <tag>`, `update`, `deploy`, `verify [url] [--quick]`, `publish-page <checkout>`, `fingerprint` |
| `assets/fdroid/deploy.conf` | **not secret**: bucket, location, `KEEP_VERSIONS`. The bucket is filled in by `init --bucket` and committed. Parsed, never sourced |
| `~/redoubt-fdroid/s3.env` | **secret, never in the repository**: `S3_ACCESS_KEY_ID=` and `S3_SECRET_ACCESS_KEY=`, mode 600. Created by the owner |
| `assets/fdroid/config.yml.in` | the fdroidserver config template, with `archive_older`. No secrets: the keystore passphrase comes from the environment of one container run |
| `assets/fdroid/bucket-policy.json.in` | the public-read policy equivalent to Hetzner's Public visibility, for tests and the record |
| `assets/fdroid/metadata/org.redoubtbrowser.yml` | name, summary, description, MPL-2.0, links, `Tracking`, `AllowedAPKSigningKeys` |
| `assets/fdroid/fdroid.html.in`, `repo-icon.png` | the human page template, the repository icon |
| `assets/fdroid/repo-fingerprint` | **written by the first `publish-page`**: the pinned index-key fingerprint, plain hex. It does not exist until the owner runs `init` |
| `site/fdroid.html`, `site/fdroid-qr.svg` | **written by `publish-page`**: the human page and its QR code (`fdroidrepos://` link with the fingerprint) |
| `scripts/site-check.py`, `scripts/tests/test-site-check-fdroid.py` | the site check's F-Droid rules and 14 hermetic tests, run by `pages.yaml` |

`.github/workflows/pages.yaml` no longer touches the repository. It publishes `site/` as it is
and downloads no APK. `scripts/fdroid-pages.py`, the assembler that fetched the APKs for GitHub
Pages, has been removed with its tests.

### What `deploy` and `verify` guarantee

`deploy` runs in this order, and stops at the first failure:

1. **Credentials.** `s3.env` must be a regular file owned by the user, with mode 600 or 400,
   outside the checkout, and contain only the two keys. Otherwise REFUSED, before anything else
   (`hetzner/logs/04`). The keys are handed to rclone through the environment of one subshell,
   which is never `env KEY=…` on a command line, so they are never in any process's arguments.
   rclone reads no config file (`RCLONE_CONFIG=/notfound`), and no line of the file is printed.
2. **Local check, no network.** In the pinned image: both `entry.jar` files carry the
   repository key, `index-v2.json` matches `entry.json`, and every APK and diff the indexes name
   is present locally with the signed size and sha256.
3. **APKs**, archive then repo: `rclone copy --immutable --checksum`. New APKs are uploaded. An
   APK already in the bucket is never overwritten, and if its size, or its MD5 where the bucket
   reports one, differs from the local file, the deploy stops before any index is touched
   (`hetzner/logs/13`). Every object rclone uploads below 200 MiB is a single PUT, whose ETag is
   its MD5. An object uploaded by another tool as multipart has no MD5 to compare, and then only
   the size is compared (`hetzner/logs/12`). The byte-for-byte check is `verify`'s job.
4. **Icons and index diffs**, then
5. **the indexes, last**: archive first, then repo, in the order `index-v1.json`,
   `index-v1.jar`, `index.jar`, `index-v2.json`, `entry.json`, and `entry.jar` at the very end,
   with `Cache-Control: no-cache`. A client that sees the new `entry.jar` finds every file it
   names already in place. A client that fetches during the few seconds of step 5 can see a new
   `index-v2.json` with the old `entry.jar`. It then fails the sha256 check and retries at its
   next refresh. It is never served a wrong file.
6. **Orphans**, reported, never deleted.
7. **`verify --quick`** against the public URL.

`verify [<url>]` uses fdroidserver's own client code on both sections. It checks the
`entry.jar` JAR signature, that the signer is the expected fingerprint, and `index-v2.json`
against `entry.json`. Every listed APK must name the release key as signer. Without `--quick`
it also downloads every APK in `repo/` **and** `archive/` and compares size and sha256 with the
signed index. That is about 0.39 GB of egress per release kept, so run the full check once per
release, not in a loop.

`scripts/site-check.py` changed deliberately. It refuses any committed `.apk` and any
`site/fdroid/` directory, the old Pages layout. It refuses a committed `deploy.conf` that sets
the test-only keys `S3_ENDPOINT` or `PUBLIC_BASE_URL`. It requires `site/fdroid.html`, when
present, to carry the pinned fingerprint and a bucket in `deploy.conf`. It allows, from
`fdroid.html` only, `fdroidrepos://<bucket>.<location>.your-objectstorage.com/repo?fingerprint=<64 hex>`
and `https://<bucket>.<location>.your-objectstorage.com/repo` or `/archive`. A page rendered
for any other URL, such as a local test server, fails the site check.

## Owner runbook

### Once: create the bucket and the S3 credentials

In [Hetzner Console](https://console.hetzner.com/):

1. Create a **new project** for the repository only (for example `redoubt-fdroid`). S3
   credentials are valid for every bucket of their project, so a dedicated project keeps the
   deploy key away from anything else.
2. *Object Storage*, *Create Bucket*. Choose the **location** (`fsn1` Falkenstein, `nbg1`
   Nuremberg or `hel1` Helsinki; the closest to most users is fine). The live bucket is
   **`redoubtbrowser`** in `hel1`. For a new one, pick a name (lowercase letters, digits, `-`; no dots). Set
   visibility to **Public** while it is empty. Hetzner recommends exactly that order.
3. *Security*, *S3 Credentials*, *Generate credentials* (description: `redoubt-fdroid deploy`).
   The secret is shown once. Write both values straight into the credentials file on box A,
   never into the repository or a shell command line:

       mkdir -p -m 700 ~/redoubt-fdroid
       install -m 600 /dev/null ~/redoubt-fdroid/s3.env
       ${EDITOR:-vi} ~/redoubt-fdroid/s3.env

   with exactly these two lines:

       S3_ACCESS_KEY_ID=<access key>
       S3_SECRET_ACCESS_KEY=<secret key>

   Back the credentials up with the repository key below. They can be regenerated in the
   console at any time. The repository key cannot.

### Once: create the repository key

On box A, in a clean checkout of `main`:

    ./scripts/fdroid-repo.sh init --bucket redoubtbrowser --location hel1
                                         # asks twice for a new passphrase (12+ characters)

This checks the bucket and location against `assets/fdroid/deploy.conf`, which already names
`redoubtbrowser` / `hel1` (an empty file is filled in; commit it, signed). Never run this
script under `bash -x` or `set -x`: the trace would print the S3 secret. It also creates `~/redoubt-fdroid/keystore.p12` (mode 0600),
`~/redoubt-fdroid/work/` and `~/redoubt-fdroid/repo-fingerprint.txt`, and prints the repository
URL and the fingerprint. **Back up the keystore and its passphrase now**, with the custody of
`SIGNING.md`, "The F-Droid repository key", and restore-test the backup with
`REDOUBT_FDROID_HOME=<restored copy> ./scripts/fdroid-repo.sh fingerprint`. Run `init` exactly
once. It refuses to overwrite a keystore, because a second key orphans every client that added
the first one. It also refuses to change a bucket that `deploy.conf` already names.

### Per release

After the GitHub release is public and verified (`SIGNING.md`, "Release procedure"):

    ./scripts/fdroid-repo.sh add android-<version>      # e.g. android-157.0-2
    ./scripts/fdroid-repo.sh update                     # asks for the keystore passphrase
    ./scripts/fdroid-repo.sh deploy                     # reads ~/redoubt-fdroid/s3.env
    ./scripts/fdroid-repo.sh verify                     # full: downloads every APK

- `add` refuses a draft, and refuses a prerelease unless given `--allow-prerelease`. It also
  refuses any APK whose sha256 differs from `SHA256SUMS.signed` or from GitHub's own asset
  digest, whose certificate is not the release key, or whose versionName does not match the tag.
- `update` re-verifies every APK in `repo/` and `archive/`, moves releases beyond the newest
  `KEEP_VERSIONS` to the archive, and signs both indexes with no network. It prints both
  sections and the bucket storage they need.
- `deploy` uploads as described in "What deploy and verify guarantee". If it says REFUSED,
  nothing in the public index changed. Fix the cause and run it again: it is idempotent.
  `deploy --dry-run` shows what would be uploaded.
- `verify` must pass before the release is announced to F-Droid users.

The human page changes only when the URL, the fingerprint, `KEEP_VERSIONS` or the template
changes, not per release:

    ./scripts/fdroid-repo.sh publish-page ~/Documents/librewolf   # a clean checkout of main

It writes `site/fdroid.html`, `site/fdroid-qr.svg` and, the first time,
`assets/fdroid/repo-fingerprint`. Then it runs `site-check.py` and prints `git status` for
exactly those paths. Review, commit (signed) and push to `main`. `pages.yaml` deploys the page.

### Publishing the fingerprint (first time only)

LW-M6-03 requires the fingerprint in at least two independent places. After the first
`publish-page`, the rendered `site/fdroid.html` is the first. Prepared edits for
`site/install.html`, `site/index.html` and `README.md` are in
`~/redoubt-artifacts/channels/fdroid-site-placeholder.diff`, outside the repository. Replace
`<REPO_URL>` with the URL `init` printed and `<REPO_FINGERPRINT>` with the fingerprint, apply the
diff, run `site-check.py`, and commit with the first page. Also publish it in the next GitHub
release notes, which is a third place outside this repository. Never commit the placeholders:
`site-check.py` does not recognise `<REPO_FINGERPRINT>` as a missing fingerprint.

### Mirrors

The escape hatch for an outage, bandwidth or a later move to another host. A mirror serves the
same `repo/` and `archive/` trees, APKs included: for example a second bucket in another
Hetzner location, or any static host. Uncomment `mirrors:` in `assets/fdroid/config.yml.in`,
keep the bucket URL first, then `update` and `deploy`, and fill the mirror with the same files.
`deploy` uploads only to the configured bucket; filling a mirror is a manual copy today. Clients
read the list from the signed index and fall back on their own. The fingerprint does not
change. To leave the bucket for good, add the new host as a mirror, wait until clients have
fetched that index, and only then announce the new address.

## Proof with throwaway keys and a local S3 server (2026-10-05)

`evidence/lw-m6-03/hetzner/README.md` has the logs and screenshots. In short: a pinned MinIO
server played the bucket, with the same public-read policy (anonymous GET allowed, anonymous
listing, PUT and DELETE refused) and throwaway deployer credentials. A throwaway index key
(fingerprint `F8627D00…3D32BD3F`) built a repository from the published `android-157.0-1-beta.4`,
`android-157.0-1-beta.5` and `android-157.0-2` per-ABI APKs with `KEEP_VERSIONS=1`. The first
deploy published Beta 5 in `repo/` and Beta 4 in `archive/`. The second, after adding 157.0-2,
moved Beta 5 to `archive/`; Beta 4's archived objects kept their ETag and timestamps. The log
shows the indexes uploaded last, with `entry.jar` at the end. Further results:

- `deploy` refused a credentials file of mode 644 or 640, and one with a stray line.
- No process's arguments contained the secret during a deploy.
- Full `verify` passed on all 9 APKs of both sections, and failed with a wrong fingerprint.
- A bit-flipped archived APK was caught by `verify`. Re-uploaded as one part, it was also
  refused by `deploy`, with no index touched.

F-Droid 2.0.1 on an API 34 emulator (its certificate re-checked against F-Droid's published
`43238d51…c9ccab`) added the repository by URL and fingerprint, installed 157.0-2 (installed
APK sha256 `c4eb178b…022522`, certificate the release key) and, with the archive switched on,
listed the Beta 5 and Beta 4 versions under *Redoubt (archive)*. The URLs were path-style
(`http://10.0.0.135:9000/redoubt-fdroid/repo`): a virtual-hosted name needs a DNS entry for the
bucket host, and this host has no resolver for one without root. Hetzner's TLS and its
virtual-hosted name are therefore unproven until the owner's first `deploy` and `verify`.
