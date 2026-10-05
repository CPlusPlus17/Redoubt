# LW-M6-03 evidence: the F-Droid repository in an S3 bucket, proved with throwaway keys (2026-10-05)

This proves the Hetzner Object Storage design of `docs/android/FDROID.md` (owner decision
2026-10-05). It replaces the GitHub Pages proof in `../README.md`, sections 1 and 2. Everything
here is **throwaway**:

- the repository key, fingerprint `F8627D0018AF4F2826FFFD3BDDF3832A3299CD5BC8D093D15A5909AE3D32BD3F`;
- a second key used only to render the sample page,
  `3157CF0B33109CDEC3988E8689D78101FD711E0DCC11E3C944CCB609EC2DB49A`;
- the MinIO admin and deployer credentials.

All of them were generated under `~/redoubt-artifacts/channels/throwaway/hetzner/` and are
never to be published. The real key, bucket and credentials do not exist yet. The APKs are the
**real, published** release APKs, checked again against GitHub's digests, `SHA256SUMS.signed`
and the release key. Nothing was uploaded to Hetzner, and Hetzner was not contacted.

Host: box A (Fedora 44). Tools:

- fdroidserver image `registry.gitlab.com/fdroid/docker-executable-fdroidserver@sha256:75f6b88e…`;
- rclone v1.75.1, pinned by zip sha256 (`logs/00-rclone-pin.txt`);
- emulator: API 34 `google_apis` x86_64.

**The stand-in for the Hetzner bucket.** MinIO `RELEASE.2025-09-07T16-13-09Z`, image
`docker.io/minio/minio@sha256:a1a8bd4ac40ad7881a245bab97323e18f971e4d4cba2c2007ec1bedd21cbaba2`.
quay.io and Docker Hub now refuse anonymous pulls of MinIO images, so it ran from the copy
already on the host, pinned by that digest. Region `fsn1`, bucket `redoubt-fdroid`, bound to
`10.0.0.135:9000`, the host's LAN address, which both the host and the emulator can reach.
The bucket policy is `assets/fdroid/bucket-policy.json.in` with the bucket filled in:
`s3:GetObject` for everyone on `redoubt-fdroid/*`. That is what Hetzner's Public visibility
applies. A deployer user with read-write access stood in for the Hetzner S3 credentials.

**URL style: path-style**, `http://10.0.0.135:9000/redoubt-fdroid/repo`. Hetzner documents the
virtual-hosted form `https://<bucket>.<location>.your-objectstorage.com/…`. Testing it locally
needs a DNS name for the bucket host, and `*.localhost` does not resolve through glibc on this
host (`getent hosts redoubt-fdroid.s3.localhost` returns nothing) without editing `/etc/hosts`
as root. So the virtual-hosted name and Hetzner's TLS certificate are not proven here. The
owner's first `deploy` ends with `verify --quick` against the real URL, which proves both. The
throwaway `deploy.conf` set `S3_ENDPOINT=http://10.0.0.135:9000` and
`PUBLIC_BASE_URL=http://10.0.0.135:9000/redoubt-fdroid`, with `KEEP_VERSIONS=1` so that one
release moves to the archive. The rclone provider was `Hetzner`, exactly as in production.

Every command ran from this branch's working tree with `REDOUBT_FDROID_HOME` and
`FDROID_DEPLOY_CONF` pointing at the throwaway directory. In the logs `<throwaway>` is that
directory.

## 1. Bucket, key, repository (`logs/00-03`)

| log | what | result |
|---|---|---|
| `00-rclone-pin.txt` | rclone's `SHA256SUMS` for v1.75.1, its PGP signature, the zip `deploy` fetched | signature good (key `FBF737EC…FF3B54FA`, as listed on rclone.org/release_signing); the fetched zip's sha256 equals the pin |
| `00-minio-setup.txt` | bucket, public-read policy, deployer user | anonymous listing of the bucket: HTTP 403, as on Hetzner ("file listing remains denied") |
| `01-init.txt` | `fdroid-repo.sh init` with the throwaway `deploy.conf` | RSA 4096 key; repo and archive URLs printed; plain-http warning (local test only) |
| `02-add-*.txt` | `add --allow-prerelease android-157.0-1-beta.4`, `…beta.5` | sha256 equal to `SHA256SUMS.signed` and GitHub's digest; certificate is the release key, v2+v3, no v1 |
| `03-update-1.txt` | `update` with `KEEP_VERSIONS=1` (`archive_older: 3`) | fdroidserver moved Beta 4's three APKs to `archive/` and signed both indexes with no network |

## 2. Deploy (`logs/04-13`)

| log | what | result |
|---|---|---|
| `04-deploy-refused-env-mode.txt` | `deploy` with `s3.env` at mode 644, then 640, then with a stray line | REFUSED each time, exit 1, before any network access (the bucket was still empty afterwards); the stray line is not printed |
| `05-deploy-1.txt` | the first `deploy` | local index check; rclone fetched and verified; **APKs first** (archive, then repo), icons, then **the indexes last**: archive `index-v1.json`, `index-v1.jar`, `index.jar`, `index-v2.json`, `entry.json`, `entry.jar`, then the same six for repo, `entry.jar` last; `verify --quick` passed. The last line is a scan of every process's arguments, every 0.3 s during the deploy: the S3 secret was never in any of them |
| `06-public-headers.txt` | anonymous HEAD on an APK, `entry.jar`, `index-v2.json`; anonymous PUT and DELETE | APKs `application/vnd.android.package-archive`, `Cache-Control: public, max-age=31536000, immutable`; indexes `no-cache`; PUT and DELETE 403 |
| `07-add-android-157.0-2.txt`, `08-update-2.txt` | a new release | Beta 5 moved from `repo/` to `archive/`; `repo/` 157.0-2, `archive/` Beta 5 and Beta 4 (2 releases, 778,178,062 bytes) |
| `09-deploy-2.txt` | the re-deploy with the new release | new APKs only (`Copied (new)`), index diffs, then the indexes, replaced, `entry.jar` last. Beta 5's old `repo/` copies are reported as **orphans and kept**: deploy never deletes |
| `10-archive-untouched.txt` | Beta 4's archived objects before and after the re-deploy (`mc stat`: ETag, last modified, size) | identical. Admin listing: 12 APK objects, nothing deleted |
| `11-verify-full.txt` | `verify` (full), then `verify --quick` with a wrong fingerprint | all 9 APKs of both sections downloaded, size and sha256 equal to the signed indexes (1 min 37 s); wrong fingerprint: `VerificationException`, REFUSED, exit 1 |
| `12-tamper.txt` | one bit flipped in archived `org.redoubtbrowser_2016188072.apk`, put into the bucket by the admin as a **multipart** upload | `verify` REFUSED it (sha256 differs). `deploy` did **not** notice: a multipart object has no MD5 to compare, and the size is equal. It overwrote nothing, but it went on to upload the indexes. That is the stated limit (`FDROID.md`, "What deploy and verify guarantee"). The object was then restored and `verify` passed |
| `13-tamper-single-part.txt` | the same bit flip, uploaded as **one part** (ETag = MD5, as for every object rclone itself uploads under 200 MiB) | `deploy` REFUSED with "immutable file modified" in step 1; the repo's `entry.jar` ETag and timestamp are unchanged. Restored; `verify` passed |

## 3. The human page and the placeholder diff (`logs/14-15`, `sample-page/`)

| log | what | result |
|---|---|---|
| `14-publish-page-test-url-refused.txt` | `publish-page` into a scratch copy of this branch, using the MinIO repository | page, QR code and pin written; `site-check` FAILS (no bucket in the committed `deploy.conf`, `fdroidrepos://10.0.0.135:9000/…` not allowed), so `publish-page` says REFUSED: a test page can never pass |
| `15-publish-page-and-placeholder-pass.txt` | in another scratch copy: `init --bucket redoubt-fdroid-test --location fsn1` (production URL form, second throwaway key), `publish-page .`, then `~/redoubt-artifacts/channels/fdroid-site-placeholder.diff` filled with that URL and fingerprint and applied | `init` filled `deploy.conf` (`S3_BUCKET=redoubt-fdroid-test`); `site-check` PASS; the diff applied cleanly to README.md, `site/index.html`, `site/install.html`; `site-check` PASS again |

`sample-page/` is the `fdroid.html` and `fdroid-qr.svg` of log 15, rendered from the
committed template. The scratch copies were plain copies of the working tree with a throwaway
`git init`, not the repository.

## 4. A real F-Droid client (`screens/`, `logs/20-22`)

`logs/20-fdroid-client-cert.txt`: `F-Droid.apk` 2.0.1, sha256 `83d3fe52…bb53778`, certificate
SHA-256 `43238d512c1e5eb2d6569f4a3afbf5523418b82e0a3ed1552770abb9a9c9ccab`. That equals the one
F-Droid publishes ([Release Channels and Signing Keys](https://f-droid.org/en/docs/Release_Channels_and_Signing_Keys/),
read 2026-10-05). It was installed on a freshly wiped emulator.

| screen | |
|---|---|
| `01` | F-Droid first launch |
| `02`, `03` | *Repositories*, *+*, URL entered by hand with `?fingerprint=F862…BD3F`; the preview shows the Redoubt repository, its description, 1 app |
| `04`, `05` | added; the repository lists Redoubt; the app page offers **Install** |
| `06`, `07` | after Android's "install unknown apps" grant for F-Droid: Android's "Do you want to install this app?", then installed |
| `08`-`10` | the repository list; Redoubt's repository details; *Settings* says "This repository does not appear to have an archive." until *Check for archive* is pressed |
| `11`, `12` | after *Check for archive*: the switch *Show archived apps and outdated versions of apps*, turned on; F-Droid fetched `archive/entry.jar` and `archive/index-v2.json` (`logs/22`) |
| `13` | the app page, main section: 157.0-2's three APKs |
| `14`-`16` | the app page's repository list now offers **Redoubt (archive)**; there, six `157.0-1` versions (Beta 5 and Beta 4); expanded: versionCode 2016188262 (Beta 5, x86_64), signer `6414eb334681cf6e` |

| log | |
|---|---|
| `21-installed-from-bucket.txt` | the installed app: versionCode 2016188486, `157.0-2-default`, x86_64; `installerPackageName=org.fdroid.fdroid`, `updateOwnerPackageName=org.fdroid.fdroid`. The pulled `base.apk` has sha256 `c4eb178b98c99138504e6dc3e8f4cd672f30df2da1d06bc95ddc436a57022522`, equal to the bucket's `repo/org.redoubtbrowser_2016188486.apk` and to `fenix-x86_64-release.apk` in android-157.0-2's `SHA256SUMS.signed`. Its certificate is `6414eb33…1283bd0`, the release key |
| `22-client-http-log.txt` | F-Droid's own HTTP log: `repo/entry.jar`, `repo/index-v2.json`, icons, the APK, then `archive/entry.jar` and `archive/index-v2.json` |

## Gates on this branch

- `docs/android/board.py --check`: ok (125 tasks, 0 warnings); `--check-scope`: ok.
- `scripts/lint-patch-scope.py`: OK (110 files); `scripts/check-patch-order.py`: 36/36.
- `scripts/site-check.py site`: PASS; `scripts/tests/test-site-check-fdroid.py`: 14/14.
- `bash -n` and shellcheck 0.11.0 `-S warning` on `scripts/fdroid-repo.sh`: clean.
- `patches/android/update-check.patch` is unchanged.

## Not proven here

- Hetzner itself: the virtual-hosted bucket URL, its TLS certificate, and how Public
  visibility and Hetzner's handling of `x-amz-acl: private` interact with the uploads. All
  three are checked by the owner's first `deploy` (`verify --quick`) and `verify`.
- An update from an older version through the bucket. The Pages proof showed Beta 5 to
  157.0-2 (`../README.md`, section 3). Here the client did a fresh install, and there is no
  release newer than 157.0-2 yet.
