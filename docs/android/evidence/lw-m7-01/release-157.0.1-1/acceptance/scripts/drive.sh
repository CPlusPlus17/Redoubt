#!/bin/bash
# 157.0.1-1 driver. Main session on ONE emulator: API 34 google_apis x86_64, booted by the
# harness from the android-34-only SDK view $R/sdk34 (-dns-server 9.9.9.9 -tcpdump). The first check
# boots it (--emulator --keep-emulator); batches 1-3 reuse it with --serial.
R=/home/mgysin/redoubt-artifacts/release-157.0.1-1; S=$R/repo/docs/android/evidence/lw-m7-01/release-157.0.1-1/acceptance/scripts
cd $R
RUNS=$R/runs SERIAL= $S/run-check.sh check-launcher-start --check-launcher-start
# stop here if the first check did not leave an emulator (the batches pick the first emulator- serial)
/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb devices | grep -q '^emulator-' || { echo 'no emulator after check-launcher-start; stopping'; exit 1; }
bash $S/batch1.sh > runs/batch1.log 2>&1
bash $S/batch2.sh > runs/batch2.log 2>&1
bash $S/batch3.sh > runs/batch3.log 2>&1
echo DRIVE DONE
