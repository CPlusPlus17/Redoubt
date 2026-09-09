# First full target run for the compiled165-file candidate failed

Invocation `2ea3f25605b5412ebff203aa3b363653` first passed resource checks for all
four compiled APKs, then stopped during the required target suites. No runtime
stage ran. Source manifest
`c53736e87152ba6de7ae232efd0a26197601027e4553be3f5f4bd7e6045601ae`
matched all165 files before and after the run and again during root capture.

Fenix test compilation failed on the missing `io.mockk.Called` import in
`DefaultCookieBannerDetailsControllerTest.kt:199`. No Fenix XML was produced;
the actual board gate reports that its result directory is absent. Prior Fenix
results were archived before this run and are not accepted as current evidence.

Root independently counted every retained XML result:

| Suite | Tests | Failures |
| --- | ---: | ---: |
| Support webextensions |53|0|
| Gecko engine |57|7|
| Browser state |2|0|
| Firefox accounts |19|5|
| Synced tabs |1|0|
| Suggest admission |14|0|

The accounts failures expose nullable generic Boolean matchers and cascading
Mockito state errors. Five Gecko failures expose nested mock construction during
outer stubbing; two compare exception instances across coroutine recovery. These
are fixture diagnoses, not passing target evidence. The corrected fixtures still
require a fresh full run. The checked-in failure allowance is unchanged.

The archive includes complete target logs, all seven XML archives (including
the empty Fenix archive), actual gate outputs, captured test source and driver
configuration. `root-verification.json` binds independent member/hash/XML checks.
