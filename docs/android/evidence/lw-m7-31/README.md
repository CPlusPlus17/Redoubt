# LW-M7-31 — Android extension-permission completion durability

Status: **source candidate; target compilation, Android xpcshell and real immediate-restart acceptance pending**. No APK, guest, emulator or real device was changed or exercised by this task. The source establishes a completion gap; it does not establish that a real device has lost a private permission.

The patch changes two production modules. On Android, the legacy JSON permission store serializes whole-file snapshots, writes with `IOUtils.writeJSON(..., {tmpPath, flush:true})`, and publishes its in-memory value only after success. Failed grants/revocations/removals reject their real caller and leave a retry possible. Independent extension IDs retain their public queues and share a file-level write queue. Android reads reconcile the separate delayed StartupCache from the authoritative JSON or KV store. Modern KV write calls and desktop scheduled-write/cache behavior stay as before. GeckoView uninstall awaits the original exact-ID permission cleanup task started by the existing uninstall observer, including its failure.

`source-audit.md` records the observed call chain, separate cache and uninstall layers, limits and source binding. `source-files.json` pins the changed files plus two read-only production test inputs. The baseline is the frozen beta source with the already committed `ubo-readiness.patch` GeckoViewWebExtension hunks applied. `source-baseline.tar.gz` lets tests replay this exact baseline without changing the frozen source. The new patch applies with zero fuzz and no offsets.

Host checks:

- `python3 scripts/tests/test-extension-permission-durability.py`: 24 tests execute production source methods with controlled platform services and the real per-ID scheduler; 13 tests cover the runtime driver and negative graders. The same completion test rejects the original source. These mocks do not establish native I/O durability.
- `python3 docs/android/evidence/lw-m7-28/test-addon-state-smoke.py`: all 32 existing UI/observer tests remain green. The real UI runner now rejects uninstall if a stored private grant, a legacy disk private grant, or an unknown permission backend remains.
- `python3 docs/android/board.py --check`: 111 tasks, 26 waves, zero warnings in this isolated branch. Metadata depends on 19, 28 and 12 before overlapping changes; root must retain those dependencies when integrating with newer main tasks.

The Android-only native definition is `toolkit/components/extensions/test/xpcshell/test_ext_permissions_android_durability.js`, registered in `xpcshell.toml`. It uses the real JSON file, public add/remove/removeAll, controlled write failure, same-choice retries, both native store backends, stale cache directions and the original GeckoView uninstall cleanup result. The uninstall bridge test controls the event/promise; only the installed release regression below exercises a real ordinary add-on uninstall. Root must run the target xpcshell definition and existing `test_ext_permissions.js` / `test_ext_permissions_uninstall.js` in the real Android test environment, build/package the changed JavaScript, and run the required smoke/pref checks. Node syntax checks are not target compilation.

Installed-release regression (root-owned device execution):

```sh
python3 scripts/android-addon-private-durability-check.py \
  --adb <adb> --serial <serial> --package org.redoubtbrowser \
  --apk <exact-already-installed-release.apk> --dedicated-test-profile \
  --work <evidence-directory>
```

Use an initialized English dedicated profile, enabled pinned ordinary signed uBO, no existing private tabs, and pre-enabled transport-only Marionette. No APK/add-on installation, wipe, preferences, permission-file write, manual flush or signature bypass occurs. An absent APK/device stays pending. The exact installed APK, pinned XPI, four LW-M7-19 modules and both LW-M7-31 modules are checked. Extra transport config taints acceptance. Each genuine production `GeckoViewWebExtension.setPrivateBrowsingAllowed` completion (grant, revoke, grant before removal) and final `uninstallWebExtension` completion is followed by one timestamped `am force-stop` shell command. The command records device-clock timestamps immediately around force-stop; it performs no state probe or UI dump. Raw callbacks and timings are written after stop to avoid delaying it. Missing/reversed timestamps fail; either a device callback-to-stop or host observed-callback-to-stop interval over 1000 ms keeps that checkpoint pending while functional observations continue.

Each restart requires a new process and the first normal fixture parser document/report before Marionette connects. Then a new real private tab is opened through Fenix and its first fixture document is tested. This proves first normal navigation plus a fresh private context; it does **not** claim that private browsing was the very first navigation of the restarted process. Page script callbacks, exact document/run/origin bindings and independent server resource requests must agree with registry, actual listeners, live private policy and persistent permission observations. Revocation must allow the known blocked path in private mode, while the independent allowed script still runs. Removal is tested while a grant previously existed and is always last. Failure is preserved; the driver never repairs it.

`--baseline-source` runs the exact pinned predecessor module hashes for a before/after comparison. It can record the old behavior, but even a successful baseline measurement remains pending for candidate acceptance. The new runtime driver checks the actual public API completion boundary; the real Fenix UI lifecycle and signed-update acceptance remain separate LW-M7-28 requirements. No full add-on acceptance is claimed from this API regression alone.

Useful packaged source check, before device execution:

```sh
python3 scripts/tests/test-extension-permission-durability.py --apk <candidate.apk>
```

The normal `--apk` source checker binds candidate modules. The installed runner uses the full normal release fixture prerequisites inherited from 28/18. Root owns patch order/count registry updates and guest integration; this task adds only its own Android patch-list line. The recorded `board.py --check-scope` result is currently blocked only by that central count update: this branch adds Android 35→36 and total 95→96. These counts are branch-local; root must apply a +1 change to its current registry. Scope acceptance is not claimed while that check fails.
