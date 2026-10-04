# LW-M7-41: uBO cookie-list migration, Beta 5 candidate on a device (2026-10-03)

The candidate was built from **`cdeadd6cebed214a05085899930d7dd269fa5a5a`** (`git rev-parse HEAD` at
build time, also in `build/repo-head.txt`; settings gitlink `8a69936f`, unchanged since Beta 4). That
commit fixes a defect in the migration patch as first committed in
`fc846c480764dd2f2a7159d6e8461f5946a8cae5`. That version could never run on a device (see "The defect").
Every result below is for the fixed build.

**Result:** the migration works.
- Upgraded profiles get both cookie lists once, and the lists filter on that first start.
- A later opt-out holds through restarts and a reinstall.
- Fresh installs are a no-op.
- Beta 3 upgraders keep all their other uBO settings.
- The regression smoke matches Beta 4. The only red row is first-run capture, which is expected red under E12.

## The defect, found before the build (fixed in `cdeadd6c`)

The hook sits in `ExtensionStorageIDB.selectBackend`. A child context only calls `selectBackend` when it
does not already know the extension's `storage.local` backend.

At startup, upstream `Extension.sys.mjs` announces the backend through
`sharedData extension/<id>/storageIDBBackend = true` in two cases:
- every extension already migrated to IndexedDB (`extensions.webextensions.ExtensionStorageIDB.migrated.<id>`);
- every extension just installed while IDB is enabled.

Every Redoubt uBO falls into one of these cases, so `selectBackend` is never called for it and the hook can never run.

This came from reading the 157 tree: `Extension.sys.mjs` around line 4220, and the
`useStorageIDBBackend` branch in `child/ext-storage.js`. It was then measured on Beta 4 rc3
(`diag/select-backend-beta4.json`, probe `diag/select-backend-probe.py`). At 30 s into a cold
start, the probe read:
- migrated pref `true`
- sharedData `storageIDBBackend` `true`
- `ExtensionStorageIDB.selectedBackendPromises.has(uBO's Extension)` `false`

The first build of `fc846c48` was aborted 4 minutes in (`build/commands.log`). The patch now leaves
uBO's backend unannounced at startup only while `librewolf.uBO.cookieListsMigrated` is unset
(`ExtensionStorageIDB.redoubtMustSelectBackend`; an install still sets the migrated pref as upstream
does). As a result, uBO's first `storage.local` call of the session goes through `selectBackend`.

Once the pref is set, startup is upstream's again. `diag/select-backend-candidate-after-migration.json`
shows this on the candidate after the migration: sharedData `true`, and no `selectBackend` call.

The JS test and `android-cookie-banner-smoke.py` now fail without the startup branch:
- `node scripts/tests/test-ubo-cookie-lists-migration.js <fc846c48's patch>` gives `no Extension.sys.mjs hunk`.
- The smoke reports `FAIL migration` on the tree built from `fc846c48`.

## Build

| | |
| --- | --- |
| Tree | Fresh `make dir TARGETS=android` at `cdeadd6c`, moved to `beta5/work/librewolf-157.0-1`. The brand check passes (`build/brand-check-tree.out`). Diffed against the Beta 4 rc build tree, excluding build byproducts, the only source differences are `toolkit/components/extensions/Extension.sys.mjs` and `ExtensionStorageIDB.sys.mjs` (`build/tree-diff-vs-beta4-rc.txt`; the five `manifest.json` lines are Gradle outputs). |
| Why a full build | The patch changes toolkit JavaScript, which ships in GeckoView's `omni.ja`, so the app-only path was not applicable. The fat AAR was built in one run, 3 ABIs, `-j8`, image `localhost/librewolf-android-build:fx157` (`b3f9fc5d6358`), commands in `build/aar-cmd.txt` and `build/apk-cmd.txt`, log in `build/commands.log`. |
| Build date | `MOZ_BUILD_DATE=20261003200000` (Beta 4: `20261002210000`). All three objdirs' `buildid.h` agree (`build/buildid-objdirs.txt`). |
| Time | AAR 4,582 s (v7a 1,499, arm64 1,186, x86_64 1,099, fat 794). APK 2,086 s (`build/*-build-times.txt`). |
| Memory | Minimum MemAvailable 8,148,752 kB (`build/memavail-min.txt`). `memguard.sh` paused the APK container twice, for 9 s and 21 s, when it dipped below its 8.25 GB threshold, the lowest sample being 8,016,128 kB (`build/memguard.log`). Other CI load shared the host. |
| AAR | `geckoview-default-omni-157.0.20261003200000.aar` `edc21b1d…e7fb` (`build/SHA256SUMS.aar`) |
| APKs (unsigned) | x86_64 `da72cbbe5d57bc2be0d25aec2032e8282c999292e0befe48ea19d833001768b9`, arm64-v8a `fe8e3161…59d8`, armeabi-v7a `73b31d94…3de8`, universal `9220f632…7ea0` (`build/SHA256SUMS.apk`) |
| versionCode | v7a 2016188256, arm64 2016188258, x86_64 2016188262, universal 2016188263. All are above Beta 4's 2016188072/74/78/79. versionName is unchanged: `157.0-1-default` (`build/apk-badging.txt`) |
| Packaged code | In all four APKs, `omni.ja!/modules/Extension.sys.mjs` and `ExtensionStorageIDB.sys.mjs` equal the tree files byte for byte (`build/packaged-vs-tree.txt`). |
| Against Beta 4 rc3 (x86_64) | 11 of 3,273 APK entries differ. In `omni.ja`, only `AppConstants.sys.mjs` (build ID) and the two patched modules differ. The rest is build-date or version fallout: `libxul.so`, `libmozglue.so`, `AndroidManifest.xml`, `classes2.dex`, the baseline profile and five built-in extension manifests (`build/rc3-vs-candidate-x86_64.txt`). |
| Static | `android-cookie-banner-smoke.py --fetch`: 5/5 PASS on x86_64 and universal, including `migration` and `hosted` (`build/cookie-lists-apk-*.out`) |

**Device APKs, all throwaway-signed** (`CN=Redoubt throwaway test key 2026-10-02, O=NOT A RELEASE KEY`, cert
`31e9a40f…b760`, key `keep/throwaway-keys/throwaway.p12`, apksigner 36.0.0). Hashes are in `build/SHA256SUMS.test-apks`.
- **Candidate x86_64:** `f09c6f4a337d844bea23abfb229f6a44279348134478cb1f65f8b327a5e47ea2`. All 3,131 non-META-INF entries equal the unsigned APK's.
- **Beta 4 rc3 x86_64:** `a5edc9ae…62dd`, from unsigned `2a7d279f…308f`.
- **Beta 3 x86_64:** `720e3e09…508a`, from unsigned `1ac3b01d…95e8`.

These signed hashes differ from the Beta 4 acceptance's signed copies, which used the same certificate and
other tooling; the unsigned inputs are the same.

## Conditions

- **Emulator:** one emulator, emulator-5584, android-30 `default` x86_64 (no GMS). It was booted by the harness (`--dns-server 9.9.9.9`), with network to AMO and the list hosts.
- **Probe:** `scripts/migration-test.py` (sha256 `872a3b9b…0b7`) reuses the committed harness's client (`android-smoke.sh` `dba0f279…ce46`, the same as Beta 4's acceptance) and its Marionette door (GeckoView debug config plus `am set-debug-app`).
- **Starts:** every start is a cold start (force-stop, then launch on `https://example.org/`).
- **What each step reads:**
  - the full uBO `storage.local` (with a sha256 per key);
  - the pref;
  - uBO's own Filter lists pane, which renders uBO's in-memory selection;
  - the cookie probe from the Beta 4 acceptance on example.org: it inserts `#AcceptCookieContainer` and `.accept-cookies-banner` plus a control, and fetches `cdn.cookie-script.com`.
- **Logs:** every step streams logcat. No step's crash buffer has entries, and no line matches the migration or `ExtensionStorageIDB`.
- **Outputs:** `device/<scenario>/<step>.json`, `*-state-*.json`, `*.png` and `*.logcat.gz`.

## Results

| # | Scenario | Result | Evidence |
| --- | --- | --- | --- |
| 1a | Beta 4 rc3 fresh install, airplane mode ON before the first launch | Pref absent. 11 lists selected, **neither cookie list**; pane unticked. After airplane OFF and an online Beta 4 cold start: the same 11, neither list. The cookie probe shows both elements and the fetch resolves | `device/s1/s1-beta4-offline*` |
| 1b | `adb install -r` candidate (2016188078 → 2016188262, `firstInstallTime` kept), first cold start online | 15 s in: `librewolf.uBO.cookieListsMigrated = true` (user value). The selection is the previous 11 **unchanged, followed by** `fanboy-cookiemonster`, `ublock-cookies-easylist`, once each. Pane: both `checked cached recent`, so uBO's in-memory selection has them and its updater fetched them in the same session. The probe's first load hides both elements, the control stays visible, and the fetch is rejected | `device/s1/s1-upgrade*` |
| 1c | Untick both in uBO's Filter lists pane, Apply | Selection back to the 11, without the two lists. Pane unticked. The pref stays `true` | `device/s1/s1-optout*` |
| 1d | Two cold starts | Both stay OFF (storage and pane). The probe shows the elements and the fetch resolves. The pref stays `true` | `device/s1/s1-restart1*`, `s1-restart2*` |
| 1e | `adb install -r` the same candidate again, cold start | Both lists stay OFF, the same as 1d | `device/s1/s1-reinstall*` |
| 2 | Beta 3 fresh install, online first run. Through uBO's UI: tick "Dan Pollock's hosts file" + Apply; `colorBlindFriendly` ON. Then `adb install -r` candidate | 15 lists before. After the first start: the same 15 in the same order, then the two cookie lists, both ticked and active. The pref is `true`. Across uBO's 45 `storage.local` keys, 41 are byte-identical, including `colorBlindFriendly` and `dpollock-0`'s cache. The 4 that changed: `selectedFilterLists` (only the append); `cachedManagedStorage` (Beta 3's `librewolf.dev` bootstrap URL → the pinned Android URL, the 157 cfg); `assetCacheRegistry` (read times); `availableFilterLists` (+165 bytes; this value is above the probe's 20 kB inline limit, so only its size and digest were kept). The 4 keys added are the two lists' `cache/` and `cache/compiled/` entries | `device/s2/`, `device/s2/s2-settings-compare.txt` |
| 3 | Fresh online install of the candidate | 16 lists, each cookie list **once**, in the catalog's own position (not appended), so the migration wrote nothing. The pref is set during the first session (the "watch first selection" path). Pane: `checked isDefault cached recent`. The probe blocks. A second cold start shows the same | `device/s3/` |
| 5 | (extra) Fresh install of the candidate, offline first run | Offline: 11 lists, neither cookie list, and **no pref** (left for the next start). After airplane OFF, the first online cold start appends both once and sets the pref. Pane `checked cached recent`; the probe blocks | `device/s5/` |
| D | Backend path after the migration | sharedData `storageIDBBackend` `true` at startup, and no `selectBackend` call for uBO: upstream behaviour once the pref is set | `diag/select-backend-candidate-after-migration.json` |

### Regression smoke (fresh profile per check, the harness's own `--serial` runs)

All checks ran on the installed candidate `f09c6f4a…7ea2`, harness `dba0f279…ce46`, graphics harness
`ce0072ea…4612`, repo HEAD `cdeadd6c` with no uncommitted script changes (`smoke/exit-status.jsonl`).

| Check | Exit | Result |
| --- | --- | --- |
| `--check-launcher-start` | 0 | PASS. Fresh-profile and restart launcher cold starts reached uBO readiness, with no setup-failure dialog after 45 s |
| `--check-ubo-preinstall` | 0 | PASS, 2/2 |
| `--check-ubo-lifecycle` | 0 | PASS, 10/10: disable, restart, remove, APK reinstall |
| `--check-ubo` | 0 | PASS |
| baseline, including graphics | 0 | PASS, 8/8. Graphics `acceptanceComplete: true`, **161** checks passed (`smoke/baseline-smoke/graphics-acceptance/summary.stdout`) |
| `--check-no-suggest` | 0 | PASS. 60 s typing window: 8 keep-alive, 3 background flows, no typing flow. Enter produced 13,776 B to noai.duckduckgo.com |
| `--check-aboutconfig` | 0 | PASS. 30 rows; the edit survived a restart; 52 prefs locked |
| `--check-update-privacy` | 0 | PASS. The row is compiled out; no update-host traffic in 120 app events |
| `--check-https-only` | 0 | PASS, 3/3 |
| `--check-strings` | 0 | PASS. 243,650 rows, 0 unexplained, 36 screen stops |
| `--first-run-capture` | 1 | **E12, red as expected.** 124 events (Beta 4 rc3: 108) |

**First-run capture compared with Beta 4 rc3** (`smoke/first-run-host-comparison.json`, made with the Beta 4
acceptance's `compare-first-run.py`):
- **Named hosts:** `malware-filter.pages.dev` added and `curbengh.github.io` gone. These are the two alternative mirrors of uBO's URLhaus list, which uBO chooses between per run; Beta 3's capture had `malware-filter.pages.dev`.
- **Unnamed destinations:** `2606:50c0:8002::153` and `::154` are new. They are in GitHub's `2606:50c0::/32` range (inferred from the prefix, not looked up), and no SNI in the run names them.
- **Everything else** is the same set of named hosts.

The capture is a fresh install, so the migration takes the no-op path in it, and it adds no network
activity of its own.

## Not done / limits

- **Upgrade path:** the upgrade starts and the opt-out were driven through the Marionette debug door (a URL intent with the debug config present), not a bare launcher tap. The launcher path was covered only by `--check-launcher-start`, on a fresh profile.
- **uBO auto-update off:** not tested. With it off, the patch header says appended lists stay inactive until the user's next update or list change.
- **Residual not re-tested:** a profile whose user had both lists on and turned both off before this build ran gets them again once (the owner question from the patch commit).
- **Not run:** `--check-search`, `--self-test`, `--check-no-remote-settings` and the Fenix unit tests. The fix changes no Kotlin.
- **arm64 and armeabi-v7a:** these APKs were only checked statically.
- **Beta 4 diagnostic boot:** the emulator boot used for the Beta 4 diagnostic (a launcher-start run on rc3) is not archived; only its probe output is.
