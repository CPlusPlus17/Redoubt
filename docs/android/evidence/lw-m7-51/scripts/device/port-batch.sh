#!/bin/bash
# port APK on the running API 34 emulator (one at a time; serial checked to be an emulator)
D=~/redoubt-artifacts/port-sept24/device
export APK=~/redoubt-artifacts/port-sept24/builds/build-apk/redoubt-158.0-2-port-x86_64-throwaway.apk
export SERIAL=$(~/redoubt-artifacts/android-sdk/platform-tools/adb devices | awk '/^emulator-/{print $1; exit}')
[ -n "$SERIAL" ] || { echo "no emulator-* serial; stopping"; exit 1; }
echo "serial=$SERIAL apk=$(sha256sum $APK | cut -c1-64)"
$D/run-check.sh port-first-run-capture-1 --first-run-capture
$D/run-check.sh port-first-run-capture-2 --first-run-capture
$D/run-check.sh port-baseline-smoke
$D/run-check.sh port-check-isolation-1 --check-isolation
$D/run-check.sh port-check-isolation-2 --check-isolation
$D/run-check.sh port-check-video-1 --check-video
$D/run-check.sh port-check-video-2 --check-video
echo PORT BATCH DONE
