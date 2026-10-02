#!/bin/bash
# fresh profile -> acknowledge the first-run "uBlock Origin was added" sheet -> idle so uBO's
# first-run filter-list refresh finishes -> check-no-suggest with --keep-state (retry once on exit 2)
R=/home/mgysin/redoubt-artifacts/esr-153.4/build/rc2/runtime
A="$HOME/redoubt-artifacts/android-sdk/platform-tools/adb -s emulator-5584"
$A shell am force-stop org.redoubtbrowser; $A shell pm clear org.redoubtbrowser
$A shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n org.redoubtbrowser/org.mozilla.fenix.HomeActivity
timeout 10 bash -c 'while :; do sleep 1; done'
$A shell uiautomator dump /sdcard/u.xml >/dev/null; $A shell cat /sdcard/u.xml > $R/diag/fresh-home/settled-notice.xml
grep -q 'uBlock Origin was added' $R/diag/fresh-home/settled-notice.xml && echo "notice present, tapping OK" && $A shell input tap 922 1815
echo "idle start $(date -u +%T)"; timeout ${IDLE:-600} bash -c 'while :; do sleep 1; done'; echo "idle end $(date -u +%T)"
export SERIAL=emulator-5584
$R/run-check.sh check-no-suggest-settled --check-no-suggest --keep-state
if tail -1 $R/runs/exit-status.jsonl | grep -q '"exit": 2'; then $R/run-check.sh check-no-suggest-settled-retry --check-no-suggest --keep-state; fi
echo NOSUGGEST DONE
