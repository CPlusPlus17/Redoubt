#!/bin/bash
# Second, separate session on the android-30 `default` x86_64 image (no GMS), the image the 157.0-3
# main suite ran on (and Beta 1's second session), for the checks the API 34 google_apis session cannot grade:
#  - graphics acceptance (baseline-smoke, static-no-gms-no-adjust): scripts/android-graphics-smoke.py
#    parses API 30's `dumpsys input` window list; on API 34 the format differs (inputConfig=, a
#    transform line per window) and the webgl row fails with "No org.redoubtbrowser window is in the
#    input dispatcher's window list" before any GL check runs;
#  - check-update-privacy and first-run-capture, like for like with 157.0-3's API 30 captures.
# The harness boots the AVD from the full SDK (it ranks `default` first) in its own work dir.
R=/home/mgysin/redoubt-artifacts/beta-158.0-1-b2; S=$R/repo/docs/android/evidence/lw-m7-01/release-158.0-1-beta.2/acceptance/scripts
export SDK=/home/mgysin/redoubt-artifacts/android-sdk WORK=$R/work30 RUNS=$R/runs30
mkdir -p $WORK $RUNS; cd $R
SERIAL= $S/run-check.sh baseline-smoke
export SERIAL=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb devices | awk '/^emulator-/{print $1; exit}')
[ -n "$SERIAL" ] || { echo "no emulator-* serial; stopping"; exit 1; }   # added for Beta 2
echo "serial=$SERIAL sdk=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL shell getprop ro.build.version.sdk) fp=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL shell getprop ro.build.fingerprint)"
$S/run-check.sh static-no-gms-no-adjust --check-no-gms --check-no-adjust
$S/run-check.sh check-update-privacy --check-update-privacy
$S/run-check.sh first-run-capture --first-run-capture
# New for Beta 2 (LW-M7-46): the manual WebGL page, on this API 30 image (the UI helpers' tap guard reads its dumpsys input)
python3 $S/webgl-manual.py $SERIAL $RUNS/webgl-manual $R/apk/fenix-x86_64-158.0-1-beta2-throwaway.apk > $RUNS/webgl-manual.console 2>&1; echo "$(date -u +%T) webgl-manual exit=$?"
/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL emu kill
echo DRIVE30 DONE
