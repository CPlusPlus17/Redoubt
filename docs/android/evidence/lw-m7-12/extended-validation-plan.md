# Extended candidate validation drivers

Prepared on the host while native attempt 2 runs; **not executed in the guest**.

`run-extended-apk.sh` requires terminal native success and its exact copied
source manifest. It verifies source before/after packaging, records all three
native inputs, and uses only guest development signing. Its own output directory
is archived before repeat runs. It does not create a shipping version upgrade.

`run-extended-tests.sh` requires that APK build to have completed. It moves the
four previous XML result directories into a per-run archive before running the
full Fenix suite, full extension-support suite, three affected Gecko-engine
classes and browser-state permission class. Missing XML forces the Gradle test
output to be recreated and prevents a failed compilation from reusing old XML.
The existing Fenix subtraction gate remains authoritative for known failures.
The additional grader requires fresh XML, minimum full-suite counts and all
new feature classes without failures or skips. AC/extension failures are not
subtracted. Six negative controls and a positive control pass on the host.

The default smoke now dispatches to the full LW-M7-18 graphics runner when the
new WebGL permission bridge is enabled. It requires actual consent, pixel,
revocation, lifetime, private and frame checks, the installed APK hash and
untainted transport configuration. The diagnostic core-only runner's exit 3
cannot produce a baseline pass. Old prompt=false artifacts retain their existing
rendering check. The surrounding media/HTTPS checks reconnect after the graphics
runner's process restarts. All 43 host smoke tests pass after integration;
the new APK flow remains unexecuted.

The standalone graphics source's 38 host tests also pass after merging. Neither
these host tests nor the prepared drivers establish target build or runtime
success. GeckoView instrumentation, cookie behavior and actual translation
remain separate required checks.
