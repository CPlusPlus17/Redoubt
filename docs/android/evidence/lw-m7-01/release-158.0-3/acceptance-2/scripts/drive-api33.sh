#!/bin/bash
# 158.0-3 second acceptance: API 33 (Android 13) google_apis x86_64, new for this acceptance (the fix covers SDK 31-33).
# Image TE1A.240213.009 from the api31-33-fix work (SDK view ~/redoubt-artifacts/drm-a12/sdk/api33); note it already has
# the AOSP NDK fix, so here the fix's "event arrives, skip it" path runs. --check-eme x2, then the Widevine flows.
R=/home/mgysin/redoubt-artifacts/release-158.0-3/accept2; S=$R/repo/docs/android/evidence/lw-m7-01/release-158.0-3/acceptance-2/scripts
export SDK=/home/mgysin/redoubt-artifacts/drm-a12/sdk/api33 WORK=$R/work33 RUNS=$R/runs33
mkdir -p $WORK $RUNS; cd $R
SERIAL= $S/run-check.sh check-eme-1 --check-eme
export SERIAL=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb devices | awk '/^emulator-/{print $1; exit}')
[ -n "$SERIAL" ] || { echo "no emulator-* serial; stopping"; exit 1; }
echo "serial=$SERIAL sdk=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL shell getprop ro.build.version.sdk) fp=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL shell getprop ro.build.fingerprint)"
$S/run-check.sh check-eme-2 --check-eme
bash $S/drm/batch.sh 33 $RUNS > $RUNS/drm-batch.console 2>&1; echo "$(date -u +%T) drm batch exit=$?"
/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL emu kill
echo DRIVE33 DONE
