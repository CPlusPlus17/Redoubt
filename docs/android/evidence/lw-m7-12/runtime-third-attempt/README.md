# First booted feature-candidate runtime attempt

Guest user service `redoubt-parity-smoke3-20260909.service`, invocation
`f1861043700a46f786eb7091b3f1d13e`, ran the APK whose x86_64 SHA-256 is
`423cf7ad1b8bf713a64ef1362d57a63458b8d07ee3b9ede9ea6bee5613925451`.
The installed SDK's swangle renderer booted API 30; both preceding renderer
failures are preserved under LW-M7-11.

The actual log reports first-navigation request blocking, an allowed-resource
control, ordinary AMO signature and active add-on passes. Disabling uBO allowed
both requests and its disabled state survived restart. However, the restarted
page's request/DOM check failed; removal then timed out opening a Marionette
session. The harness returned 2. Its original implementation wrote JSON only
at normal completion, so that later error lost the detailed per-probe objects.
These log-level observations are not a completed lifecycle verdict. The next
harness version checkpoints results after each probe and captures the app UI
and logcat on connection timeout.

The baseline suite timed out in `WebDriver:Navigate` to the HTTP fixture before
its HTTPS-only interstitial probe. It returned 1 from an uncaught socket timeout;
this was an automation failure, not a measured HTTPS-only behavior failure.
The separate pref audit successfully dumped the running app. It returned 1
because exactly three baseline rows still described the old defaults:
HTTPS-only false, TRR mode 0 and empty TRR URI. The new values are true, 5 and
`https://dns10.quad9.net/dns-query`, matching the committed privacy-defaults
implementation and unit tests. The integration changes only those three expected
rows; it does not copy the entire dump or change the lock audit. No settings UI
traversal occurred. All three GPC prefs still read true; their Fenix control and
actual page/header behavior remain to be tested.

`guest-evidence.tar.gz` preserves the original receipts, logs, packet capture,
full/curated pref dumps and pref-dump result. `ubo-live-logcat.txt.gz` was copied
while the lifecycle run was still active, before the next suite cleared app data.
The service ultimately failed; the candidate is not smoke-green.
