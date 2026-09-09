# LW-M7-35 native pref-save independent source review

Reviewed exact `before`/`source` candidate Preferences.cpp and nsIPrefService.idl from task35. Archive/hash receipt pins the snapshot, because the owner is still refining it. Read-only review; no native compilation, xpcshell, APK or device execution claimed.

The candidate addresses the confirmed source defects:

- Existing PWRunnable used one shared sPendingWriteData across destinations, so a queued request could consume another request's snapshot. Candidate gives each runnable its own PrefSaveData and file while retaining the serial mAsyncTarget.
- Existing holder resolved true after PreferencesWriter::Write failed. Candidate resolves/rejects the holder with its own actual write result; DOM promise settlement is independent of delayed main-thread dirty bookkeeping.
- SyncRunnable ignores wrapped Run() return. Candidate retains the writer and reads its Result after SyncRunnable's monitor has completed; this supplies the necessary cross-thread synchronization.
- Dispatch failure can leak/retain the event, so relying solely on a destructor could leave pending count nonzero. Candidate calls Cancel explicitly on failed dispatch, with atomic exchange ensuring exactly-once count balancing; destructor supplies the non-run fallback. No normal ownership race was found between Run and Cancel under the event-target contract (Cancel is for failed dispatch/final destruction).
- Existing !dirty blocking save only waited for pending count, which can reach zero before failure's main-thread HandleDirty runs. Candidate always queues a current snapshot in the same serial target, returns its actual result, and only marks profile shutdown complete after success. An earlier failed snapshot cannot thereby establish current-state persistence.
- New savePrefFileAsync requires current profile and live pref table, rejects shutdown, forces a current snapshot even if !dirty, and maps the exact MozPromise outcome. It does not rewrite arbitrary profile files or infer success from scheduling. Later saves may supersede an acknowledged snapshot, correctly documented in IDL.
- OMT-disabled direct path retains its existing actual-result resolution/rejection. BackupPrefFile's existing rejection of current-file destination remains.

Followups sent to owner:

1. Run copies mFile into a local and callback while retaining mFile. A callback can execute before Run/destructor completes, so its claim to keep the final nsIFile release on main is not strictly guaranteed. Prefer direct move capture, and preserve intended release policy on non-run cancellation. Actual Unix nsLocalFile uses NS_DECL_THREADSAFE_ISUPPORTS and a default destructor, so this is not an established Android crash.
2. SavePrefFileBlocking's new !mCurrentFile early return skips the previous Flush of outstanding pre-profile backup writes. Keep a pending flush in that branch to retain prior behavior. The ordinary initialized-profile path already orders previous backup/current writes before its latest current snapshot.
3. Tests should cover actual current-file write failure/retry, queued distinct backup destinations/snapshots, failed dispatch/cancel count, failure followed by blocking suspend/shutdown, !dirty barriers, OMT-disabled write result, and later-current writes. A host production-source test is useful but must remain distinct from real native xpcshell/ABI execution and callback-to-force-stop acceptance.

No further concrete defect was found in the reviewed native ownership/result subset. These findings are not approval of the still-unreviewed higher-level extension update admission/UI logic, nor a claim that target checks passed. The owner is preparing tests and refining the two followups.
