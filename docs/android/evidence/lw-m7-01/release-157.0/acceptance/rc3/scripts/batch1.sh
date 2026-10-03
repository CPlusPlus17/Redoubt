#!/bin/bash
# Stage 1: boot a fresh AVD through the harness (launcher start), then about:config and the CSP probe.
R=/home/mgysin/redoubt-artifacts/release-157/acceptance/rc3
SERIAL= $R/run-check.sh check-launcher-start --check-launcher-start
export SERIAL=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb devices | awk '/^emulator-/{print $1; exit}')
echo "serial=$SERIAL"
$R/run-check.sh check-aboutconfig --check-aboutconfig
python3 $R/aboutconfig-csp-probe.py $SERIAL $R/runs/aboutconfig-csp > $R/runs/aboutconfig-csp.console 2>&1; echo "$(date -u +%T) aboutconfig-csp-probe exit=$?"
echo BATCH1 DONE
