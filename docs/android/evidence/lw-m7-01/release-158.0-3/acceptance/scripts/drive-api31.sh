#!/bin/bash
# 158.0-2 (LW-M7-50): third session on API 31 (Android 12) google_apis x86_64, the lowest API level where the
# runtime gate turns isolation ON. The system image is the one installed for the LW-M7-50 work
# (~/redoubt-artifacts/iso-158-2/sdkdl/root, seen through the android-31-only SDK view iso-158-2/sdk31), reused.
# The harness boots it from that view (it holds only this image); one emulator at a time, after API 34 is shut down.
R=/home/mgysin/redoubt-artifacts/release-158.0-3; S=$R/repo/docs/android/evidence/lw-m7-01/release-158.0-3/acceptance/scripts
export SDK=/home/mgysin/redoubt-artifacts/iso-158-2/sdk31 WORK=$R/work31 RUNS=$R/runs31
mkdir -p $WORK $RUNS; cd $R
SERIAL= $S/run-check.sh check-isolation-1 --check-isolation
export SERIAL=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb devices | awk '/^emulator-/{print $1; exit}')
[ -n "$SERIAL" ] || { echo "no emulator-* serial; stopping"; exit 1; }
echo "serial=$SERIAL sdk=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL shell getprop ro.build.version.sdk) fp=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL shell getprop ro.build.fingerprint)"
$S/run-check.sh check-isolation-2 --check-isolation
$S/run-check.sh check-video-1 --check-video
$S/run-check.sh check-video-2 --check-video
# 158.0-3 (LW-M7-39): --check-eme was never measured on API 31; twice, then the Widevine playback flows
$S/run-check.sh check-eme-1 --check-eme
$S/run-check.sh check-eme-2 --check-eme
bash $S/drm/batch.sh 31 $RUNS > $RUNS/drm-batch.console 2>&1; echo "$(date -u +%T) drm batch exit=$?"
/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL install -r $R/apk/fenix-x86_64-158.0-3-throwaway.apk
python3 $S/process-labels.py $SERIAL $RUNS/process-labels 158.0-3-api31 > $RUNS/process-labels-158.0-3-api31.console 2>&1; echo "$(date -u +%T) process-labels exit=$?"
/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL emu kill
echo DRIVE31 DONE
