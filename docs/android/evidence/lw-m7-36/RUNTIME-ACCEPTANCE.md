# Pending target acceptance

All items below are **pending**. Source replay and Node output do not close them.
Root owns builds, VM/device execution and retained source-bound receipts.

1. Integrate the final Task35 current-profile primitive before Task36; update
   predecessor hashes if its patch changes. Apply the complete Android sequence
   and classify the seven Task36 shared pairs. Compile native, GeckoView Java,
   Android Components and Fenix; generate/check the GeckoView API signature file.
   Execute JS/native lint and applicable Kotlin formatting/static checks.
2. Run the 13 `GlobalPrivacySettingsModelTest` tests (including two actual
   Fragment/Preference listener cases), five
   `GeckoGlobalPrivacyControllerTest` tests, and three GV
   `GlobalPrivacySettingsTest` instrumented tests. Run the full required Fenix
   unit suite and retain `board.py --check-fenix-tests` output with results path
   and timestamp. Run the five xpcshell native-service cases; their injected
   save boundary remains distinct from Task35's real current-profile tests.
3. Run Task35's real profile I/O tests, including missing profile/shutdown,
   immutable snapshots, actual failed write and serial save behavior. Exercise
   Task36 public API through a real GeckoRuntime profile. A save rejected before
   mutation must retain the original native value. A failed final write must
   return actual memory, retain uncertainty and never claim confirmed disk or
   rollback. Test same-value retry and a lock/external writer during I/O.
4. Use the packaged settings UI on a fresh profile and an upgraded profile with
   prior explicit native choices. Record all five effective/default/user/lock
   states through the actual API. Toggle each control, wait for acknowledged
   save, immediately force-stop, relaunch and reread. Repeat reset and middle
   referrer choice1. Confirm a set equal to a non-sticky default reports saved
   with native user state absent. Do not use debug-pref injection as the release
   control path. Retain APK hash, exact source/patch lineage and profile identity.
5. Verify native locks prevent actual UI changes, raw hidden user values are
   shown as unavailable, popup control is disabled only while global WebGL
   bypass is on, and error/retry text remains usable. Rotate/background/navigate
   away during an active save; no detached view is touched. Reopen/read after
   failure must not hide uncertainty, and ordinary refresh must not label later
   external state with an older saved status.
6. RFP: compare fresh normal/private documents and workers after actual UI
   changes and reload, including parent/opener inheritance where applicable.
   Record private-only RFP, separate FPP, exemptions and override context. Check
   reset/restart. A changed pref alone does not establish document behavior or
   prove all fingerprinting defenses are off.
7. WebGL: use a fresh context to prove Always allow bypasses approval without
   deleting/granting site permissions. Restore approval-required mode and prove
   preexisting exact-principal grants and blocks still apply (including distinct
   ports/private attributes). Toggle popup visibility and prove quiet review
   versus automatic prompt while permission enforcement persists. Check normal,
   private and worker/offscreen paths where supported; do not infer destruction
   of preexisting contexts. Keep `webgl.disabled` unchanged.
8. IPv6: use uncached controlled dual-stack names, actual DNS/connection receipts,
   and an IPv4 positive control before/after UI change and restart. Record TRR
   configuration rather than changing it to force a result. The setting is a DNS
   address-family boundary; test IPv6 literals and existing connections as
   separate observations, without claiming OS-wide network shutdown.
9. Referrers: capture server-observed Referer for same host with different port
   and scheme, sibling subdomains, and different base domains for0/1/2. Include
   scheme-policy positive/negative controls so another restrictive policy is not
   mistaken for host matching. Verify cross-origin trimming and other native
   referrer rules remain intact; repeat reset/restart.
10. Run source-bound Android smoke and curated native preference audit after the
    actual target build. Retain all outputs and limitations; do not promote
    broad startup success to any fresh-document or network behavior gate.
