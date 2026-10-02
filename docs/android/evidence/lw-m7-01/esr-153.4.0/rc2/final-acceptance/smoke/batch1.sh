#!/bin/bash
# Stage 1: boot a fresh AVD through the harness (launcher start), then about:config.
R=/home/mgysin/redoubt-artifacts/esr-153.4/build/rc2/final/runtime
SERIAL= $R/run-check.sh check-launcher-start --check-launcher-start
export SERIAL=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb devices | awk '/^emulator-/{print $1; exit}')
echo "serial=$SERIAL"
$R/run-check.sh check-aboutconfig --check-aboutconfig
echo BATCH1 DONE
