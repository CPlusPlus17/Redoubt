#!/bin/bash
# 158.0-2: re-run of static-no-gms-no-adjust (the second full graphics acceptance) on a fresh android-30 `default`
# boot. In drive-api30.sh's session its graphics run passed all 162 checks but ended "Harness cleanup failed after
# checks": the host's adb server died mid-run ("daemon not running; starting now", see the README's run notes),
# so the run is not graded and is repeated here unchanged. The first run's directory is kept as
# static-no-gms-no-adjust-attempt1/.
R=/home/mgysin/redoubt-artifacts/release-158.0-2; S=$R/repo/docs/android/evidence/lw-m7-01/release-158.0-2/acceptance/scripts
export SDK=/home/mgysin/redoubt-artifacts/android-sdk WORK=$R/work30 RUNS=$R/runs30
cd $R
SERIAL= $S/run-check.sh static-no-gms-no-adjust --check-no-gms --check-no-adjust
SERIAL=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb devices | awk '/^emulator-/{print $1; exit}')
[ -n "$SERIAL" ] && /home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL emu kill
echo RERUN30 DONE
