#!/bin/bash
# Second, separate session on the android-30 `default` x86_64 image (no GMS), the image the 157.0-3
# main suite ran on, for the checks the API 34 google_apis session cannot grade:
#  - graphics acceptance (baseline-smoke, static-no-gms-no-adjust): scripts/android-graphics-smoke.py
#    parses API 30's `dumpsys input` window list; on API 34 the format differs (inputConfig=, a
#    transform line per window) and the webgl row fails with "No org.redoubtbrowser window is in the
#    input dispatcher's window list" before any GL check runs;
#  - check-update-privacy and first-run-capture, like for like with 157.0-3's API 30 captures.
# The harness boots the AVD from the full SDK (it ranks `default` first) in its own work dir.
R=/home/mgysin/redoubt-artifacts/beta-158.0-1-b1; S=$R/repo/docs/android/evidence/lw-m7-01/release-158.0-1-beta.1/acceptance/scripts
export SDK=/home/mgysin/redoubt-artifacts/android-sdk WORK=$R/work30 RUNS=$R/runs30
mkdir -p $WORK $RUNS; cd $R
SERIAL= $S/run-check.sh baseline-smoke
export SERIAL=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb devices | awk '/^emulator-/{print $1; exit}')
echo "serial=$SERIAL sdk=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL shell getprop ro.build.version.sdk) fp=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL shell getprop ro.build.fingerprint)"
$S/run-check.sh static-no-gms-no-adjust --check-no-gms --check-no-adjust
$S/run-check.sh check-update-privacy --check-update-privacy
$S/run-check.sh first-run-capture --first-run-capture
/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL emu kill
echo DRIVE30 DONE
