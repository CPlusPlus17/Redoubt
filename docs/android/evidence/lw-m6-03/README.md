# LW-M6-03 evidence: the F-Droid repository, proved with throwaway keys (2026-10-05)

> **Superseded hosting, same day.** Sections 1 and 2 below prove the GitHub Pages design
> (`publish`, `site/fdroid/repo/`, `scripts/fdroid-pages.py`), which the owner replaced on
> 2026-10-05 with Hetzner Object Storage so that every release can be kept. Those scripts are
> gone. The current design is proved in [`hetzner/README.md`](hetzner/README.md). Sections 3
> (installer of record) and 4 (`update-check.patch`) are unaffected and still current.

Everything here used a **throwaway** repository key, generated for this run under
`~/redoubt-artifacts/channels/throwaway/fdroid-e2e/`. It has fingerprint
`C06A44BE77F6D540B68C0069CB2FC7BA6C25E8E1D613A8B87721DFFC75454B8F` and is never to be
published. The real key does not exist yet; the owner creates it with `fdroid-repo.sh init`.
The APKs are the **real, published** release APKs, downloaded from GitHub and checked against
the release key. Design and runbook: `docs/android/FDROID.md`.

Host: box A (Fedora 44). fdroidserver image
`registry.gitlab.com/fdroid/docker-executable-fdroidserver@sha256:75f6b88e…` (commit
`c21c177ff6d8`). Emulator: API 34 `google_apis` x86_64 (Android 14), SDK
`~/redoubt-artifacts/android-sdk`.

## 1. Building the repository (`logs/01-05`, `logs/09-10`)

| log | what | result |
|---|---|---|
| `01-init.txt` | `fdroid-repo.sh init --repo-url http://10.0.2.2:8000/fdroid/repo` | RSA 4096 key, fingerprint printed; plain-http warning (local test only) |
| `02-add-157.0-2.txt` | `add android-157.0-2` | sha256 matches `SHA256SUMS.signed` and GitHub's asset digest; certificate is the release key, v2+v3, no v1; versionCodes 2016188480/82/86, versionName `157.0-2-default` |
| `03-add-beta.5.txt` | `add --allow-prerelease android-157.0-1-beta.5` (without the flag: refused, the release is a prerelease) | same checks; 2016188256/58/62 |
| `04-update.txt` | `update` | index signed with no network; 6 APKs, 778,194,446 bytes, 0.778 GB of the 1 GB limit |
| `05-publish.txt` | `publish <scratch checkout>` | index files (no APKs), `sources.json`, pin, `fdroid.html`, QR code written; `fdroid-pages.py check` PASSED; **site-check then refuses**, correctly: the page links `fdroidrepos://10.0.2.2:8000/...`, not the production URL, so a test page can never be deployed |
| `09-budget-over-1GB.txt` | Beta 4 added and `KEEP_RELEASES=3 update`, then `publish` and the exact `pages.yaml` step | 1,167,536,505 bytes: `publish` and `assemble` both REFUSED **before downloading anything**; no output directory |
| `10-update-prunes-to-2.txt` | `update` with the default `KEEP_RELEASES=2` | Beta 4's three APKs and provenance pruned before signing; back to 0.778 GB |

The scratch checkout was a copy of this branch's working tree (with a throwaway `git init`),
not the repository.

## 2. The Pages deploy step (`logs/06-08`)

| log | what | result |
|---|---|---|
| `06-pages-assemble.txt` | `python3 scripts/fdroid-pages.py assemble --site site --out <dir>`: the exact `pages.yaml` command, run on the scratch checkout | index JARs verified against the pinned fingerprint (`entry.jar` SHA-256; `index-v1.jar` and `index.jar` SHA1withRSA, as fdroidserver signs them); **all six APKs downloaded from github.com releases** (9 min 20 s on this line); sha256 and size equal to the signed index; release certificate; 778,385,359 bytes; PASSED |
| `07-pages-assemble-tampered.txt` | `sources.json` re-points the x86_64 157.0-2 APK at the arm64-v8a asset of the same release (a substituted release asset) | downloaded, then REFUSED: sha256/size differ from the signed index; exit 1 |
| `08-pages-assemble-bitflip.txt` | the x86_64 APK in the cache with one bit flipped, `--offline` | REFUSED; exit 1 |

`scripts/tests/test-fdroid-pages.py` covers the same rules hermetically, plus a foreign index
key, an index or entry edited after signing, an index signer other than the release key,
index-v1 and index-v2 disagreeing, a missing APK, a committed APK, a source outside the
release and a missing pin: 14/14 OK (run in `pages.yaml` too).

## 3. A real F-Droid client (`screens/`, `logs/11-14`)

The client is `F-Droid.apk` from f-droid.org, version 2.0.1 (versionCode 2000051). Its sha256 is
`83d3fe522281c3cb89fce3bc05038f81b3c3b32c108536941f184c5f9bb53778`, and its certificate SHA-256
`43238d512c1e5eb2d6569f4a3afbf5523418b82e0a3ed1552770abb9a9c9ccab` equals the one F-Droid
publishes ([Release Channels and Signing Keys](https://f-droid.org/en/docs/Release_Channels_and_Signing_Keys/),
read 2026-10-05). The assembled directory from `06` was served with
`python3 -m http.server 8000` and reached from the emulator as `10.0.2.2`.

| screen | |
|---|---|
| `01` | F-Droid 2.0.1 first launch |
| `02`, `03` | repository added by URL with `?fingerprint=C06A…4B8F`; the preview shows the Redoubt repository, its description and 1 app |
| `04`, `05` | added; the repository lists Redoubt |
| `06` | Redoubt's page offers **Update**: a Beta 5 (2016188262) hand-installed beforehand |
| `07`, `08` | Android's "install unknown apps" grant for F-Droid, then Android's own "Do you want to update this app?", because F-Droid was not the installer |
| `09`, `10` | updated to 157.0-2; versions list (both releases, all ABIs) |
| `11`, `12` | after uninstalling: a fresh **Install** from the repository, with no system prompt |
| `13` | the description, after one line per paragraph (F-Droid 2.x showed the YAML's hard line breaks as they were; fixed in the metadata, index rebuilt and re-served offline from the same verified APKs) |
| `14` | repository details: the index-key fingerprint F-Droid pinned |

| log | |
|---|---|
| `11-installer-after-fdroid-update.txt` | Scenario A. Before: `installerPackageName=com.google.android.packageinstaller`, `packageSource=1`. After F-Droid's update: `installerPackageName=org.fdroid.fdroid`, `packageSource=2`, no update owner. The installed `base.apk` has sha256 `c4eb178b…022522`, which is `fenix-x86_64-release.apk` of android-157.0-2, and its certificate is `6414eb33…283bd0`, the release key. |
| `12-installer-fresh-fdroid-install.txt` | Scenario B. `installerPackageName=org.fdroid.fdroid`, `updateOwnerPackageName=org.fdroid.fdroid` |
| `13-installer-hand-install-over-fdroid.txt` | Scenario C. The same APK installed over it with `pm install -r -i com.google.android.packageinstaller`: the installer is the package installer again, and the update owner is cleared |
| `14-verify-local.txt` | `fdroid-repo.sh verify http://127.0.0.1:8000/fdroid/repo` passed: signature, fingerprint, release signer, and all six APKs served byte-exact. With a wrong fingerprint it was REFUSED, exit 1 |

Limits. The "hand installs" in A and C used `pm install -i` over adb, not a browser download
through the system installer UI. In C that skips the Android 14 update-ownership confirmation
a real user would see. The repository was served over plain http from the host, not from GitHub
Pages over https. Anti-features are in the index (`Tracking` on every version) but F-Droid 2.0.1
did not show them on the app page in these screens.

## 4. The installer-of-record check in `update-check.patch` (`patch/`)

| file | what | result |
|---|---|---|
| `check-patchfail-android-157.txt` | `./scripts/check-patchfail.sh --targets=android` against `firefox-157.0.source.tar.xz` | exit 0, "All patches where applied successfully" |
| `jvm-harness-157-tree.txt` | `scripts/tests/test-update-check-jvm.sh` in the fx157 image, pristine 157 tree, android-37.1 `android.jar`, Kotlin 2.4.0 | `UpdateCheck.kt` compiles with `-Werror` (the new `Build`/`InstallSourceInfo` calls included); 13/13 `UpdateCheckerTest` (including the store-installer list); 14/14 cross-checks |
| `robolectric-158-tree.txt`, `run-robolectric-158.sh` | `./mach gradle fenix:testDebugUnitTest --tests 'org.mozilla.fenix.lw.*' --tests org.mozilla.fenix.settings.SettingsFragmentTest` in the fx158 image, on the Firefox 158 working tree and build directory mounted as overlays (nothing in them modified), with the three changed files copied in | `:fenix:compileDebugKotlin` and `:fenix:compileDebugUnitTestKotlin` pass with `-Werror`; `UpdateCheckSwitchTest` 7/7 (three new: a store install hides the row and keeps the check off for all six store packages, a hand install keeps it, a direct install later updated by F-Droid loses it), `UpdateCheckerTest` 13/13, `DohProviderMigrationTest` 9/9, `SettingsFragmentTest` 25/25; 0 failures |
| `robolectric-158-negative-control.txt` | `UpdateCheckSwitchTest` only, with `isOffered` ignoring the installer | 7 tests, 2 failed (the store-install and the later-updated-by-F-Droid tests, `AssertionError`), so the tests detect a missing installer check; the hand-install test passes either way, as it should |

Gates on this branch: `check-patch-order.py` 36/36, `lint-patch-scope.py` OK (110 files),
`board.py --check` OK (124 tasks, 0 warnings), `board.py --check-scope` OK.

**Not done:** no APK was built with the change. There is no Firefox 157 GeckoView AAR on this
host, and the Firefox 158 tree is the only one Fenix's unit tests can run in. A device check of
the hidden row needs the next CI build: install it through F-Droid from a repository and confirm
that Settings has no "Check for updates" row, then install it by hand and confirm that the row is
back.
