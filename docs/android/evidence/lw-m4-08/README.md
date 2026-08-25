# LW-M4-08: Stop the Remote Settings traffic on Android

## What was delivered

1. **`patches/android/rs-blocker-android.patch`** — the fix. Three hunks in the
   Rust crate `third_party/application-services/components/remote_settings/`:
   - `service.rs` `fetch_changes()`: returns `Ok(Changes { changes: Vec::new() })`
     instead of making a network request.
   - `client.rs` `sync()`: no-op with a trace log, instead of calling
     `perform_sync_operation()` + `verify_signature()` + retry.
   - `client.rs` `make_request()`: returns `Err(Error::ResponseError { ... })`
     immediately, blocking the single choke point for all remaining egress
     (`fetch_changeset`, `fetch_attachment`, `fetch_cert`).

   The server stays `Prod` so `is_prod_server()` remains true and the packaged
   data path (`get_records` Case 1, `get_attachment` step 2, `reset_storage`
   re-seed) keeps working.

2. **`scripts/android-smoke.sh --check-no-remote-settings`** — the runtime gate.
   After a first-run capture window, asserts that none of the three Remote
   Settings hosts appear in outbound traffic. **Fails closed on a dead capture**:
   if the pcap produced zero events, the check reports FAIL (not pass), because
   an aborted capture also prints no hostnames. This is the inverted-gate bug
   the user's brief specifically called out.

3. **Registration** in `assets/patches/android.txt` and
   `docs/android/PATCH-SCOPE.md` (counts updated to 22 android / 82 total).

## Verification (all run 2026-08-25)

| Check | Command | Result |
|-------|---------|--------|
| Patch applies | `patch -p1 --dry-run` on pristine tree | EXIT 0 |
| Scope | `python3 docs/android/board.py --check-scope` | EXIT 0: "82 listed patch files — 24 common, 36 desktop, 22 android, 0 straddlers parked; PATCH-SCOPE.md agrees" |
| Order | `python3 scripts/check-patch-order.py` | EXIT 0: "patch order ok: 11/11 declared constraint(s) enforced across 2 target sequence(s); 60 shared-file pair(s) derived and classified" |
| Patchfail (desktop) | `bash scripts/check-patchfail.sh` | EXIT 0: "success: All patches where applied successfully." |
| Patchfail (android) | `bash scripts/check-patchfail.sh --targets=android` | EXIT 0: "success: All patches where applied successfully." (includes `rs-blocker-android.patch` applying to both `service.rs` and `client.rs`) |

## NOT verified

- **`--check-no-remote-settings` against a live device/emulator.** No AVD or
  physical device is available in this environment. The gate is written and
  dispatchable but has NOT been run against a fresh debug APK. To verify:
  `scripts/android-smoke.sh --emulator --apk <debug.apk> --check-no-remote-settings`
  on a host with the Android emulator + a tcpdump-capable image.

- **`board.py --check-fenix-tests`** — not run because no Kotlin files were
  touched. The patch is pure Rust.

- **The BuildFusService fault (LW-M3-13 territory)** remains unresolved and
  blocks building a fresh 3-ABI AAR / phone-runnable APK from this tree.
  This is independent of LW-M4-08 and does not change the correctness of the
  patch (which applies cleanly and is logically complete).

## Design notes

### Why three hunks and not one

- `fetch_changes()` in `service.rs` is a direct `Request::get(url)` that never
  goes through `client.rs::make_request`. Patching only `make_request` would
  leave the changes-monitor poll live.
- `sync()` in `client.rs` calls `perform_sync_operation()` which calls
  `make_request`. Patching `make_request` blocks that path, but `sync()` also
  calls `verify_signature()` and `reset_storage()` which have their own logic.
  Making `sync()` a no-op is the cleanest "never sync" semantics.
- `make_request()` is the single choke point for `fetch_changeset`,
  `fetch_attachment`, and `fetch_cert` in `client.rs`. Blocking it here ensures
  no code path can reach the network even if a future caller invokes
  `get_records(true)`.

### Why NOT a Custom server URL

`is_prod_server()` (client.rs:715-721) gates ALL packaged-dump fallbacks.
A Custom URL would make `is_prod_server()` return false, silently disabling
the seven packaged collections. That is strictly worse than the network
traffic we are removing.

### Why `search-config-overrides-v2` is safe to leave un-packaged

Fenix passes `applyEngineOverrides=false`
(`SearchEngineSelectorRepository.kt:60-62`), so no `RemoteSettingsClient`
is ever created for that collection. Nothing reads it.
