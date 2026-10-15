#!/bin/bash
# Stage 3 (after batch2, same emulator): the update-check probes (live, then the local
# wrongly-signed document), the pref audit, the store-installer probe, the process labels,
# the LW-M7-42 shadow-DOM autofill pages, then the upgrade 158.0-1 -> 158.0-2 (last: it uninstalls).
# 158.0-2: the local wrongly-signed document is doc-wrongkey-158 (version_code 2016199999, ABOVE this build's codes;
# the old doc-wrongkey's 2016189999 is below 158.0-1's, so it could not have offered anything even if verified).
R=/home/mgysin/redoubt-artifacts/release-158.0-3; S=$R/repo/docs/android/evidence/lw-m7-01/release-158.0-3/acceptance/scripts
ADB=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
SERIAL=$($ADB devices | awk '/^emulator-/{print $1; exit}')
[ -n "$SERIAL" ] || { echo "no emulator-* serial; stopping (never fall back to another device)"; exit 1; }   # added for Beta 2
CAND=$R/apk/fenix-x86_64-158.0-3-throwaway.apk
echo "serial=$SERIAL"
# the harness's last check may have left another build or a wiped profile: reinstall the candidate
$ADB -s $SERIAL install -r $CAND
python3 $S/update-check-probe.py $SERIAL $R/runs/update-check-live live > $R/runs/update-check-live.console 2>&1; echo "$(date -u +%T) update-check live exit=$?"
python3 $S/update-check-probe.py $SERIAL $R/runs/update-check-local local $R/x/wrongsig/doc-wrongkey-158 > $R/runs/update-check-local.console 2>&1; echo "$(date -u +%T) update-check local exit=$?"
bash $S/batch3-pref-audit.sh > $R/runs/pref-audit.console 2>&1; echo "$(date -u +%T) pref-audit exit=$?"
python3 $S/store-installer-probe.py $SERIAL $R/runs/store-installer $CAND > $R/runs/store-installer.console 2>&1; echo "$(date -u +%T) store-installer exit=$?"
$ADB -s $SERIAL install -r $CAND
python3 $S/process-labels.py $SERIAL $R/runs/process-labels 158.0-3-api34 > $R/runs/process-labels-158.0-3-api34.console 2>&1; echo "$(date -u +%T) process-labels exit=$?"
SERIAL=$SERIAL bash $S/autofill.sh > $R/runs/autofill.console 2>&1; echo "$(date -u +%T) autofill exit=$?"
SERIAL=$SERIAL bash $S/reddit-cold.sh > $R/runs/reddit-cold.console 2>&1; echo "$(date -u +%T) reddit-cold exit=$?"
for p in A B C; do UPGRADE_SOURCE=$R/apk/fenix-x86_64-158.0-2-throwaway.apk python3 $S/upgrade-test.py $SERIAL $R/runs/upgrade-from-158.0-2 $p > $R/runs/upgrade-from-158.0-2-$p.console 2>&1; echo "$(date -u +%T) upgrade from 158.0-2 $p exit=$?"; done
echo BATCH3 DONE
