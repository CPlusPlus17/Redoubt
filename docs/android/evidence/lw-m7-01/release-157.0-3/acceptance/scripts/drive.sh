#!/bin/bash
# Phase 1 driver (android-30 default x86_64, the harness's own choice, as in the 157.0-2 acceptance):
# the harness boots the emulator in the first check, then batches 1-3 reuse it with --serial.
R=/home/mgysin/redoubt-artifacts/release-157.0-3; S=$R/repo/docs/android/evidence/lw-m7-01/release-157.0-3/acceptance/scripts
cd $R
RUNS=$R/runs SERIAL= $S/run-check.sh check-launcher-start --check-launcher-start
bash $S/batch1.sh > runs/batch1.log 2>&1
bash $S/batch2.sh > runs/batch2.log 2>&1
bash $S/batch3.sh > runs/batch3.log 2>&1
echo DRIVE DONE
