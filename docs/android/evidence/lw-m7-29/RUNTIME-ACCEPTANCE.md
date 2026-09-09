# LW-M7-29 target acceptance — all pending

The parent owns guest/build/device execution. No Task29 APK, Rust unit test,
Kotlin unit test, native ingestion or UI/network observation is asserted here.
Record source revision, patch/catalog/ABI artifact/APK hashes with every run.

1. Compile the native remote_settings and suggest targets with their actual
   generated UniFFI bindings; run the 16 added Rust tests. Exercise existing
   affected RS config/reset and Suggest ingestion tests too. The new integration
   tests use real retained fixtures and query `2026 fi` (Wikipedia) and `gro`
   (German AMP), require icon bytes and global configuration, and use both local
   providers with the complementary collection's baseline seed.
2. Compile Fenix and A-C and run the 13 added Kotlin tests plus affected suites.
   Run `./mach gradle fenix:testDebugUnitTest`, then the repository's
   `python3 docs/android/board.py --check-fenix-tests` against the actual results.
   New failures are not excused as JNI baseline failures without that gate.
3. Build a source-bound APK. Verify default-off/new profile and preserved upgrade
   choices from Task26: no Suggest storage/provider/downloader construction or
   new network traffic from opening settings, switching only the master/leaf,
   startup ingestion, periodic ingestion or waking already scheduled workers.
   Preserve ordinary query suggestions, history, bookmarks and custom search.
4. In regular mode, enable local web data and explicitly choose English on a
   `de-CH` device/app locale. Verify labels, available languages, displayed exact
   byte total, disclosure and the separate Download action. Capture only the
   pinned selected attachment CDN URLs. No redirect, metadata fetch, cookie,
   referrer or query text belongs in this transport. Verify real results/icons
   after ingestion and restart, with external network unavailable during query.
5. Explicitly select German sponsored phone data with a different app language.
   Verify actual sponsored results and icons; switching to an unsupported device
   context does not silently discard an already explicit selection. Tablets
   visibly lack sponsored installation while retaining web language choices.
6. Cover cancellation before factory construction, during a blocked response,
   after response and while native transaction publication is paused. Disable
   the master/leaf and perform off/on while an older reference remains active.
   Cancellation that wins must prevent commit. If publication already won, read
   and report actual cache state rather than claiming traffic or disk rollback.
   Re-enter settings while cancelled blocking cleanup remains in progress; the
   old attempt must not clear a new dialog/job or permit a second import.
7. Start with usable prior data; inject truncated, oversized, changed-hash,
   missing-icon and HTTP failures, a mid-transaction insert failure and deferred
   COMMIT failure. Preserve prior records, metadata, attachments and usable query
   results. Kill the app during partial download and during native publication;
   restart into a complete old or new transaction state, never a partial set.
   No implicit retry or resume may create traffic after restart.
8. Switch RS configuration with a pending config already consumed but not
   applied, and with two clients sharing a collection database. Pending config
   import/status must reject; delayed config applications must preserve usable
   Suggest data and other collections' reset behavior. Stage/custom/non-main
   clients cannot import or read the production dataset through the narrow API.
9. Confirm downloaded data survives a new APK with baseline timestamp0. A current
   status match requires complete pinned metadata/bytes. Older catalog data may
   remain usable without matching the new catalog; failure of the replacement
   preserves it. Verify a post-commit ingestion failure is reported as saved data
   with preparation failure, and does not claim the old data was retained.
10. Inspect final production native libraries and APK assets: small catalog,
    config-only/empty seeds, no 78.5 MiB bulk payload closure and no test fixture
    payload embedded outside native test builds. Run source-bound Android smoke
    and preference audit gates. Record actual icon decode/UI walk evidence.

Use controlled test interception/fixtures for error cases. No production network
telemetry experiment is authorized by this checklist; root determines the
bounded device test environment and retains the results.
