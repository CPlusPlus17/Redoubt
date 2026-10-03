#!/bin/bash
# Probes on the rc3 APK the harness installed last (each wipes the profile itself).
R=/home/mgysin/redoubt-artifacts/release-157/acceptance/rc3; S=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb devices | awk '/^emulator-/{print $1; exit}')
A=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
echo "installed: $($A -s $S shell pm path org.redoubtbrowser) $($A -s $S shell dumpsys package org.redoubtbrowser | grep -m1 versionCode)"
python3 $R/ubo-cookie-probe.py $S $R/runs/ubo-cookie-online online > $R/runs/ubo-cookie-online.console 2>&1; echo "$(date -u +%T) ubo-cookie online exit=$?"
python3 $R/ubo-cookie-probe.py $S $R/runs/ubo-cookie-offline offline > $R/runs/ubo-cookie-offline.console 2>&1; echo "$(date -u +%T) ubo-cookie offline exit=$?"
python3 $R/stripped-features-probe.py $S $R/runs/stripped-features > $R/runs/stripped-features.console 2>&1; echo "$(date -u +%T) stripped-features exit=$?"
python3 $R/review-race-probe.py $S $R/runs/review-race-rc2 plain plain plain > $R/runs/review-race-rc2.console 2>&1; echo "$(date -u +%T) review-race-rc2 exit=$?"
python3 $R/default-browser-prompt-repro.py $S $R/runs/default-browser-prompt-rc3 7 > $R/runs/default-browser-prompt-rc3.console 2>&1; echo "$(date -u +%T) default-browser-prompt-rc3 exit=$?"
echo BATCH4 DONE
