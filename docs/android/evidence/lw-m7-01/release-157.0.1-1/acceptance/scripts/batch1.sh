#!/bin/bash
# Stage 1 (after check-launcher-start booted the API 34 AVD): about:config and the CSP probe.
R=/home/mgysin/redoubt-artifacts/release-157.0.1-1; S=$R/repo/docs/android/evidence/lw-m7-01/release-157.0.1-1/acceptance/scripts
export SERIAL=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb devices | awk '/^emulator-/{print $1; exit}') RUNS=$R/runs
echo "serial=$SERIAL"
$S/run-check.sh check-aboutconfig --check-aboutconfig
python3 $S/aboutconfig-csp-probe.py $SERIAL $R/runs/aboutconfig-csp > $R/runs/aboutconfig-csp.console 2>&1; echo "$(date -u +%T) aboutconfig-csp-probe exit=$?"
echo BATCH1 DONE
