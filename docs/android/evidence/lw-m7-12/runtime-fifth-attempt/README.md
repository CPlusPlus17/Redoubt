# Startup cache mismatch measured

Guest service `redoubt-parity-smoke5-20260909.service`, invocation
`cf31f50b73fc47e3b30d7cac5fa2f51d`, ran the same development APK. No privacy prefs
were injected. The complete artifact/input binding and observations are in the
archive's `ubo-lifecycle.json`.

Read-only observations confirm the startup-cache boundary:

| Point | Registry active / userDisabled | Startup cache memory / disk enabled | Live blocking listeners | Actual request |
|---|---|---|---|---|
| Fresh first page | true / false | true / true | 1 | blocked; allowed control executes |
| After disable completes | false / true | false / true | 0 | both scripts execute and reach origin |
| Immediate force-stop/restart | false / true | true / true | 1 | blocked again; allowed control executes |

The harness reads `addonStartup.json.lz4` through IOUtils without flushing or
changing it. Source inspection shows XPIStates uses JSONFile's 1,500-ms save
delay, while XPIDatabase uses 20 ms. Cold startup enumerates the enabled cache
records. LW-M7-19 owns fixing durable decisions/startup coherence. The failed
restart stops this run before removal; it does not claim removal was tested.

The HTTPS-only check reached the actual Fenix resource error page with its
visible Continue to HTTP Site button and native exception method, while the
fixture marker was absent. Its document was `interactive`, so the old
complete-only assertion rejected it. That was a harness mismatch. The corrected
assertion additionally requires Fenix's exact resource URI and
`showContinueHttp=true`; actual button/HTTP/HTTPS behavior is tested separately
in the next attempt. The live pref audit again passed its curated baseline.

Overall service exit 1; the uBO restart regression remains open.
