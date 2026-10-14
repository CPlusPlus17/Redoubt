#!/bin/bash
# Final port/sept24-gaps state (e9ddf406: LW-M7-38 listed, LW-M7-39 held back) on a fresh API 34 emulator.
# One emulator at a time; every adb call names the emulator serial.
D=~/redoubt-artifacts/port-sept24/device
ADB=~/redoubt-artifacts/android-sdk/platform-tools/adb
export RUNS=~/redoubt-artifacts/port-sept24/runs-final WORK=~/redoubt-artifacts/port-sept24/work-final
FINAL=$(ls ~/redoubt-artifacts/port-sept24/builds/build-final/redoubt-158.0-2-port-final-x86_64-throwaway.apk)
CTL=~/redoubt-artifacts/release-158.0-2/apk/fenix-x86_64-158.0-2-throwaway.apk
mkdir -p $RUNS
APK=$FINAL SERIAL= $D/run-check.sh final-launcher-start --check-launcher-start
export SERIAL=$($ADB devices | awk '/^emulator-/{print $1; exit}')
[ -n "$SERIAL" ] || { echo "no emulator-* serial; stopping"; exit 1; }
echo "serial=$SERIAL final=$(sha256sum $FINAL | cut -c1-64)"
$ADB -s $SERIAL reverse tcp:18765 tcp:18765
python3 $D/menu-check.py $SERIAL final $RUNS/menu 18765
python3 $D/drm-flow.py $SERIAL final $RUNS/drm 18765 Allowed
python3 $D/settings-scan.py $SERIAL final $RUNS/settings
$ADB -s $SERIAL shell svc wifi disable
APK=$FINAL $D/run-check.sh final-first-run-capture-1 --first-run-capture
APK=$CTL   $D/run-check.sh ctl-first-run-capture-1 --first-run-capture
APK=$FINAL $D/run-check.sh final-first-run-capture-2 --first-run-capture
APK=$CTL   $D/run-check.sh ctl-first-run-capture-2 --first-run-capture
APK=$FINAL $D/run-check.sh final-baseline-smoke
cp $WORK/prefs.txt $RUNS/final-baseline-smoke/prefs.txt 2>/dev/null
APK=$FINAL $D/run-check.sh final-check-isolation-1 --check-isolation
APK=$FINAL $D/run-check.sh final-check-isolation-2 --check-isolation
APK=$FINAL $D/run-check.sh final-check-video-1 --check-video
APK=$FINAL $D/run-check.sh final-check-video-2 --check-video
echo FINAL BATCH DONE
