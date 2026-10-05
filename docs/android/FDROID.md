# The Redoubt F-Droid repository (LW-M6-03)

Redoubt runs its **own** F-Droid repository. It is not in f-droid.org's main repository,
because f-droid.org builds and signs apps with its own key, which would give Redoubt a second
fingerprint (`WEBSITE.md` §5, `SIGNING.md`).

    repository URL   https://redoubtbrowser.org/fdroid/repo
    human page       https://redoubtbrowser.org/fdroid.html   (rendered by `publish`)
    index key        RSA 4096, held by the owner only; its fingerprint is published by the
                     owner after `init`, never before ("Publishing the fingerprint" below)
    APKs             the GitHub release's per-ABI APKs, byte for byte, release key
                     64:14:EB:...:28:3B:D0 (`SIGNING.md`)
    hosting          the existing GitHub Pages site (owner decision 2026-10-05)
    state            tooling, Pages assembly and throwaway-key proof done 2026-10-05;
                     the owner has not run `init` yet, so nothing is published

## Decisions (2026-10-05)

**Hosting: the existing GitHub Pages site.** The owner chose it on 2026-10-05. Hetzner
Object Storage was rejected because it has no custom domain, and Swiss hosts were
considered. An earlier draft of this tooling deployed with rsync over SSH to a separate host.
That plan is dropped, and so is its `deploy` subcommand. Only the small signed index is
committed (`site/fdroid/repo/`). `.github/workflows/pages.yaml` downloads the APKs from the
GitHub release at deploy time, verifies them against the signed index, and places them next to
it before `upload-pages-artifact`. The APKs never enter git, so git's 100 MB file limit does not
apply. The Pages limits that do apply, from
[GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
(read 2026-10-05):

| limit (quoted) | effect here |
|---|---|
| "Published GitHub Pages sites may be no larger than 1 GB." | Two releases fit (about 0.78 GB for 157.0-2 plus Beta 5), three do not (1.17 GB with Beta 4). `fdroid-pages.py` fails the deploy above 1,000,000,000 bytes. |
| "a *soft* bandwidth limit of 100 GB per month" | That is about 750 APK downloads a month. The escape hatch is the index's `mirrors` entry ("Mirrors"). |
| "deployments will timeout if they take longer than 10 minutes" | This counts the deploy job only. The download happens in the build job before it. |
| "a *soft* limit of 10 builds per hour", which "does not apply if you build and publish your site with a custom GitHub Actions workflow" | The site already uses a custom workflow. |

The page names no per-file limit. **Live test, 2026-10-05:** a single 128 MiB file was deployed
through `actions/upload-pages-artifact@v3` and `actions/deploy-pages@v4` from the scratch
repository `CPlusPlus17/redoubt-pages-size-test`. It was served with HTTP 200, full length, a
matching sha256, `content-type: application/vnd.android.package-archive` and
`accept-ranges: bytes`. Redoubt's largest per-ABI APK is 135 MB (128.7 MiB, x86_64 157.0-2).
The test is recorded with the owner decision of 2026-10-05; it was not repeated for this document.

**What the repository serves: the three per-ABI APKs of each release, not the universal one.**
F-Droid clients pick the APK whose `nativecode` matches the device, and every supported device
matches arm64-v8a, armeabi-v7a or x86_64. The universal APK (288 MB) would push one release to
0.68 GB, so the site could hold only one release. It would also carry the highest versionCode of
its build (`+7`), so clients would prefer it and download 2.2 times the bytes. It stays on the
GitHub release.

**Retention: the current release and the one before it** (`KEEP_RELEASES=2`). That is the
most that fits in 1 GB. A downgrade stays possible for one release. There is no archive
section (`archive_older: 0`, fdroidserver's default), because an archive's APKs would have to
be in the same 1 GB. `update` deletes older APKs before it signs the index, so the index never
names a file the deploy cannot fetch. A "release" is one build hour: every APK of a Redoubt build
shares `versionCode >> 3`.

**Anti-features: `Tracking`.** F-Droid defines it as "apps that track you and/or report your
activity to somewhere, either without your permission or by default"
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

**No double notification, without a second Gecko build.** The APKs are the direct-download
APKs, and they have the opt-in update check compiled in. The app hides the "Check for updates"
row, and never runs the check, when the **installer of record** is a store client: F-Droid
(`org.fdroid.fdroid`, `org.fdroid.basic`), Droid-ify, Neo Store, Accrescent or Play. That is
`UpdateCheck.isOffered` in `patches/android/update-check.patch`, and `DISTRIBUTION.md`, "F-Droid
and Accrescent do not double-notify", records the contract change. It ships from the first
build after 157.0-2. 157.0-2 itself has only the switch, which is off by default, and the
repository description tells F-Droid users to leave it off.

How Android reports the installer of record was measured on an API 34 emulator with F-Droid
2.0.1 (`evidence/lw-m6-03/logs/11-13`):

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

**Tooling: F-Droid's own container image, pinned by digest.** It is
`registry.gitlab.com/fdroid/docker-executable-fdroidserver@sha256:75f6b88e…`, the `master` tag
of 2026-10-04, fdroidserver commit `c21c177ff6d8`. A pinned pip version in a venv was the
alternative. The image also brings the exact `apksigner`, `keytool` and `python3-qrcode`
versions fdroidserver is tested with, and a digest pins all of them at once. The `latest` tag is
a 2024 build. The container that sees the repository key runs with `--network=none`.

## The pieces

| file | role |
|---|---|
| `scripts/fdroid-repo.sh` | the owner's tool: `init`, `add <tag>`, `update`, `publish <checkout>`, `verify [url]`, `fingerprint` |
| `assets/fdroid/config.yml.in` | the fdroidserver config template (no secrets; the passphrase comes from the environment of one container run) |
| `assets/fdroid/metadata/org.redoubtbrowser.yml` | name, summary, description, MPL-2.0, links, `Tracking`, `AllowedAPKSigningKeys` |
| `assets/fdroid/fdroid.html.in`, `repo-icon.png` | the human page template, the repository icon |
| `assets/fdroid/repo-fingerprint` | **written by the first `publish`**: the pinned index-key fingerprint, plain hex. It does not exist until the owner runs `init` |
| `site/fdroid/repo/` | **written by `publish`**: `entry.jar`, `entry.json`, `index-v1.jar`, `index-v1.json`, `index-v2.json`, `index.jar`, `diff/`, `icons*/`. Never an APK |
| `site/fdroid/sources.json` | **written by `publish`**: the GitHub release asset each APK in the index comes from |
| `site/fdroid.html`, `site/fdroid/repo-qr.svg` | **written by `publish`**: the human page and its QR code (`fdroidrepos://` link with the fingerprint) |
| `scripts/fdroid-pages.py` | `check` (offline) and `assemble` (download), run by `pages.yaml` |
| `scripts/tests/test-fdroid-pages.py` | 14 hermetic tests with throwaway keys |

What `fdroid-pages.py` enforces, so that the deploy publishes exactly what the repository key
signed:

- `entry.jar`, `index-v1.jar` and `index.jar` carry one signer whose certificate SHA-256 equals
  `assets/fdroid/repo-fingerprint`. The PKCS#7 signature is checked with openssl, the `.SF`
  must cover `MANIFEST.MF`, and `MANIFEST.MF` must cover the signed file. fdroidserver signs
  `entry.jar` with SHA-256 but the two legacy JARs with SHA1withRSA for old clients; Fedora's
  OpenSSL refuses SHA-1 signatures unless `OPENSSL_ENABLE_SHA1_SIGNATURES=1` is set, and the
  script sets it for verification only.
- The signed `entry.json` names `index-v2.json` by sha256 and size. `index-v1.json` and
  `index-v2.json` list the same APKs with the same sha256, and every signer is the release key.
- Every APK is downloaded from the release named in `sources.json`. Its URL must be an
  `android-*` release asset of `CPlusPlus17/Redoubt`. sha256 and size must equal the signed
  index, and `scripts/android-verify-signature.sh` must accept it (release key, v2+v3, no v1).
  It uses the runner image's `apksigner`: ubuntu-24.04 ships build-tools 34-37 under
  `ANDROID_HOME` ([runner image README](https://raw.githubusercontent.com/actions/runner-images/main/images/ubuntu/Ubuntu2404-Readme.md),
  image 20260927, read 2026-10-05).
- No `.apk` is committed under `site/`, and site plus APKs stay at or under 1,000,000,000 bytes.
  The size is checked before anything is downloaded and again after.
- Without `site/fdroid/repo/` the step only copies `site/`, which is today's state.

`scripts/site-check.py` changed deliberately. It does not lint `site/fdroid/**`, which holds
index files, not pages. It refuses any committed `.apk`. It requires `site/fdroid.html`, when
present, to carry the fingerprint pinned in `assets/fdroid/repo-fingerprint`. And it allows
links to `https://f-droid.org/` and to
`fdroidrepos://redoubtbrowser.org/fdroid/repo?fingerprint=<64 hex>` only. A page rendered for any
other repository URL, such as a local test URL, fails the site check.

## Owner runbook

No hosting setup is needed: the site and its domain already exist (`WEBSITE.md`).

### Once: create the repository key

On box A, outside any git checkout:

    ./scripts/fdroid-repo.sh init        # asks twice for a new passphrase (12+ characters)

This creates `~/redoubt-fdroid/keystore.p12` (mode 0600), `~/redoubt-fdroid/work/` and
`~/redoubt-fdroid/repo-fingerprint.txt`, and prints the fingerprint. **Back up the keystore and
its passphrase now**, with the custody of `SIGNING.md`, "The F-Droid repository key", and
restore-test the backup with `REDOUBT_FDROID_HOME=<restored copy> ./scripts/fdroid-repo.sh
fingerprint`. Run `init` exactly once. It refuses to overwrite a keystore, because a second key
orphans every client that added the first one.

### Per release

After the GitHub release is public and verified (`SIGNING.md`, "Release procedure"):

    ./scripts/fdroid-repo.sh add android-<version>      # e.g. android-157.0-2
    ./scripts/fdroid-repo.sh update                     # asks for the keystore passphrase
    ./scripts/fdroid-repo.sh publish ~/Documents/librewolf   # a clean checkout of main

- `add` refuses a draft, and refuses a prerelease unless given `--allow-prerelease`. It also
  refuses any APK whose sha256 differs from `SHA256SUMS.signed` or from GitHub's own asset
  digest, whose certificate is not the release key, or whose versionName does not match the tag.
- `update` drops releases beyond the newest two, re-verifies every APK and signs the index with
  no network. It prints the APK bytes the deploy will fetch against the 1 GB limit.
- `publish` writes the files listed above and runs `fdroid-pages.py check` and `site-check.py`
  on the checkout. It then prints `git status` for exactly those paths. Review the diff, then
  commit (signed) and push to `main`. The push starts `pages.yaml`, which fetches the APKs. If
  `publish` says REFUSED, discard what it wrote (`git -C <checkout> checkout -- site/fdroid
  site/fdroid.html; git -C <checkout> clean -fd site/fdroid`) and fix the cause.

Then, after the Pages deploy:

    ./scripts/fdroid-repo.sh verify          # https://redoubtbrowser.org/fdroid/repo

`verify` runs fdroidserver's own client-side check: the `entry.jar` signature, the fingerprint,
and `index-v2.json` against `entry.json`. It then checks that every listed APK is signed by the
release key and is served byte-exact (it downloads each one). A failure means the site and the
index disagree. Do not announce the release on F-Droid users' behalf until it passes.

### Publishing the fingerprint (first time only)

LW-M6-03 requires the fingerprint in at least two independent places. After the first
`publish`, the rendered `site/fdroid.html` is the first. Prepared edits for `site/install.html`
and `README.md` are in `~/redoubt-artifacts/channels/fdroid-site-placeholder.diff`, outside
the repository. Replace `<REPO_URL>` with `https://redoubtbrowser.org/fdroid/repo` and
`<REPO_FINGERPRINT>` with the printed fingerprint, apply the diff, run `site-check.py`, and
commit with the first publish. Also publish it in the next GitHub release notes, which is a
third place outside this repository. Never commit the placeholders: `site-check.py` does not
recognise `<REPO_FINGERPRINT>` as a missing fingerprint.

### Mirrors

If bandwidth nears the soft 100 GB a month, or Pages has to be left, add a mirror. A mirror
serves the same `repo/` tree, APKs included, for example an object-storage bucket filled by the
same `assemble` step. Uncomment `mirrors:` in `assets/fdroid/config.yml.in`, keep the Pages URL
first, then `update` and `publish`. Clients read the list from the signed index and fall back on
their own. The fingerprint does not change.

## Proof with throwaway keys (2026-10-05)

`evidence/lw-m6-03/README.md` has the logs and screenshots. In short: a throwaway index key
(fingerprint `C06A44BE…4B8F`, used only on this host) built a repository from the published
`android-157.0-2` and `android-157.0-1-beta.5` per-ABI APKs. The real `pages.yaml` step then
downloaded all six from GitHub and verified them (778,385,359 bytes). The assembled site was
served at `http://10.0.2.2:8000/fdroid/repo`, and F-Droid 2.0.1 (its certificate checked against
F-Droid's published `43238d51…c9ccab`) added it on an API 34 emulator. F-Droid listed Redoubt,
updated a hand-installed Beta 5 to 157.0-2, and installed it fresh. The installed APK's sha256 is
`c4eb178b…022522` (`fenix-x86_64-release.apk`), and its certificate is the release key.
`verify` passed against the local URL and failed with a wrong fingerprint. The step failed on a
substituted APK, on a bit-flipped APK and on a three-release index (1.17 GB).
