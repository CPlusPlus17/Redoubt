#!/bin/bash
# Stage 3 (after batch2, same emulator): the update-check probes (live, then the local
# wrongly-signed document), the pref audit, the store-installer probe, the process labels,
# the LW-M7-42 shadow-DOM autofill pages, then the 157.0-3 -> 158.0-1 Beta 1 upgrade (last: it uninstalls).
R=/home/mgysin/redoubt-artifacts/beta-158.0-1-b1; S=$R/repo/docs/android/evidence/lw-m7-01/release-158.0-1-beta.1/acceptance/scripts
ADB=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
SERIAL=$($ADB devices | awk '/^emulator-/{print $1; exit}')
CAND=$R/apk/fenix-x86_64-158.0-1-beta1-throwaway.apk
echo "serial=$SERIAL"
# the harness's last check may have left another build or a wiped profile: reinstall the candidate
$ADB -s $SERIAL install -r $CAND
python3 $S/update-check-probe.py $SERIAL $R/runs/update-check-live live > $R/runs/update-check-live.console 2>&1; echo "$(date -u +%T) update-check live exit=$?"
python3 $S/update-check-probe.py $SERIAL $R/runs/update-check-local local $R/x/wrongsig/doc-wrongkey > $R/runs/update-check-local.console 2>&1; echo "$(date -u +%T) update-check local exit=$?"
bash $S/batch3-pref-audit.sh > $R/runs/pref-audit.console 2>&1; echo "$(date -u +%T) pref-audit exit=$?"
python3 $S/store-installer-probe.py $SERIAL $R/runs/store-installer $CAND > $R/runs/store-installer.console 2>&1; echo "$(date -u +%T) store-installer exit=$?"
$ADB -s $SERIAL install -r $CAND
python3 $S/process-labels.py $SERIAL $R/runs/process-labels 158.0-1-beta.1 > $R/runs/process-labels-158.0-1-beta.1.console 2>&1; echo "$(date -u +%T) process-labels exit=$?"
SERIAL=$SERIAL bash $S/autofill.sh > $R/runs/autofill.console 2>&1; echo "$(date -u +%T) autofill exit=$?"
for p in A B C; do python3 $S/upgrade-test.py $SERIAL $R/runs/upgrade $p > $R/runs/upgrade-$p.console 2>&1; echo "$(date -u +%T) upgrade $p exit=$?"; done
echo BATCH3 DONE
