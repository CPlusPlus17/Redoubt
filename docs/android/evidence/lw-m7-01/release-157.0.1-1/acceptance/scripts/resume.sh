#!/bin/bash
# Resume after the Wi-Fi capture finding: batch2 (with Wi-Fi off) and batch3 on the same emulator.
R=/home/mgysin/redoubt-artifacts/release-157.0.1-1; S=$R/repo/docs/android/evidence/lw-m7-01/release-157.0.1-1/acceptance/scripts
cd $R
bash $S/batch2.sh > runs/batch2.log 2>&1
bash $S/batch3.sh > runs/batch3.log 2>&1
echo RESUME DONE
