# Final beta Fenix verification — 2026-09-08

The final patched-tree run passes E5. It ran the complete
`./mach gradle fenix:testDebugUnitTest --no-daemon -PgleanBuildDate=2026-09-06T19:00:00`
task with `MOZ_BUILD_DATE=20260906190000`. `fenix-run.sh` records the mounts and
environment. The run started at 14:07:52 UTC and completed in 10m 31s.

The authoritative `fenix-gate.txt` output is:

```text
# 598 classes / 5426 tests from librewolf-153.0esr-1/obj-x86_64/gradle/build/mobile/android/fenix/app/test-results/testDebugUnitTest
# newest result written 2026-09-08 16:18:37 — check this against the change you are testing
# failing 93 = 90 environmental + 3 known-real + 0 unexpected

ok: no failures beyond the documented allowlist
```

The displayed result timestamp is Europe/Zurich; the XML files were written at
14:18:37 UTC. Gradle exits 1 because of the documented failures. The board gate
exits 0, including when invoked without an explicit results path
(`fenix-gate-default.txt`). XML reports 5,326 passing, 93 failing and 7 skipped
cases. The same seven cases were skipped before this patch; their exact names
are preserved in `fenix-skipped-cases.json`. No allowlist changes were made.

`fenix-junit-xml.tar.gz` contains all 598 original XML files with their timestamps.
Every archived file was compared byte for byte with the live result, and the
board gate was rerun successfully after extracting the archive into a temporary
directory (`fenix-archive-gate.txt`). `fenix-integrity.json` also verifies that
every XML file is newer than this run's start and that the only failed Gradle
task was `:fenix:testDebugUnitTest`.

The complete console logs are retained losslessly as `fenix-unit-tests.log.gz`
and `fenix-prepatch-unit-tests.log.gz`. The provenance records hash the original
uncompressed bytes; the integrity verifier checks the final decompressed log
against that recorded hash.

The 13,142-file source hash manifest in `fenix-source-sha256.json.gz` covers
Fenix, Android Components (including the Config plugin), Android Gradle tooling,
and the root Gradle build files. These files did not change during the run and
all match `librewolf-153.0esr-1-beta-20260908`, the separate release-build tree.
`fenix-final-candidate.json` links this source manifest to the four completed
unsigned APKs in `librewolf-android-apk-153.0esr-1-beta-20260908/apk`, with their
hashes, metadata and recorded build times. Those candidate hashes were checked
again after the suite. The original unsigned outdir supplied the unit run's
caches; APK hashes in `fenix-provenance-before.txt` and
`fenix-provenance-after.txt` identify those older input artifacts, while
`fenix-final-candidate.json` identifies the final candidate.

The deterministic-version-code patch was applied to the extracted source before
this final run. The newly compiled actual `Config.class` passed all five tests
in `scripts/tests/test-android-version-code.py`: fixed ABI codes and ordering,
timezone independence, malformed/missing/out-of-range dates, next-hour advance,
and same-hour stability. See `fenix-version-code-regression.txt` and its hash
record. `fenix-generated-GleanBuildInfo.kt.txt` captures the generated September
6, 19:00 UTC Glean date.

To recheck the retained evidence while the source and candidate files remain:

```sh
python3 docs/android/evidence/lw-m7-06/beta-audit-2026-09-08/fenix-verify-evidence.py
```

To replay the XML gate after a build removes the live result directory:

```sh
results=$(mktemp -d)
tar -xzf docs/android/evidence/lw-m7-06/beta-audit-2026-09-08/fenix-junit-xml.tar.gz -C "$results"
python3 docs/android/board.py --check-fenix-tests --results "$results"
```

Files prefixed `fenix-prepatch-` preserve the first run, before the deterministic
version-code patch. That run also passed with 598 classes / 5,426 cases and the
same failure and skip counts; its result timestamp is 16:06:45 Europe/Zurich.
The archived run script and provenance retain the original filenames used when
captured. They are historical records; `fenix-run.sh` is the final run recipe.
