#!/bin/bash
# Stage 3 (after batch2, same emulator): the update-check probes (live, then the local
# wrongly-signed document), the pref audit, the store-installer probe and the process labels
# (157.0-3, then the 157.0-2 contrast), then the 157.0-2 -> 157.0-3 upgrade (last: it uninstalls).
R=/home/mgysin/redoubt-artifacts/release-157.0-3; S=$R/repo/docs/android/evidence/lw-m7-01/release-157.0-3/acceptance/scripts
ADB=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
SERIAL=$($ADB devices | awk '/^emulator-/{print $1; exit}')
echo "serial=$SERIAL"
# the harness's last check may have left another build or a wiped profile: reinstall the candidate
$ADB -s $SERIAL install -r $R/apk/fenix-x86_64-157.0-3-throwaway.apk
python3 $S/update-check-probe.py $SERIAL $R/runs/update-check-live live > $R/runs/update-check-live.console 2>&1; echo "$(date -u +%T) update-check live exit=$?"
python3 $S/update-check-probe.py $SERIAL $R/runs/update-check-local local $R/x/wrongsig/doc-wrongkey > $R/runs/update-check-local.console 2>&1; echo "$(date -u +%T) update-check local exit=$?"
bash $S/batch3-pref-audit.sh > $R/runs/pref-audit.console 2>&1; echo "$(date -u +%T) pref-audit exit=$?"
python3 $S/store-installer-probe.py $SERIAL $R/runs/store-installer $R/apk/fenix-x86_64-157.0-3-throwaway.apk > $R/runs/store-installer.console 2>&1; echo "$(date -u +%T) store-installer exit=$?"
$ADB -s $SERIAL install -r $R/apk/fenix-x86_64-157.0-3-throwaway.apk
python3 $S/process-labels.py $SERIAL $R/runs/process-labels 157.0-3 > $R/runs/process-labels-157.0-3.console 2>&1; echo "$(date -u +%T) process-labels 157.0-3 exit=$?"
$ADB -s $SERIAL uninstall org.redoubtbrowser; $ADB -s $SERIAL install $R/apk/fenix-x86_64-157.0-2-throwaway.apk
python3 $S/process-labels.py $SERIAL $R/runs/process-labels 157.0-2 > $R/runs/process-labels-157.0-2.console 2>&1; echo "$(date -u +%T) process-labels 157.0-2 exit=$?"
for p in A B C; do python3 $S/upgrade-test.py $SERIAL $R/runs/upgrade $p > $R/runs/upgrade-$p.console 2>&1; echo "$(date -u +%T) upgrade $p exit=$?"; done
echo BATCH3 DONE
