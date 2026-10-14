#!/bin/bash
# 158.0-2: copied from the 158.0-1 acceptance, paths changed, isolation-OFF rows added at the end.
# Second, separate session on the android-30 `default` x86_64 image (no GMS), the image the 157.0-3
# main suite ran on (and Beta 1's second session), for the checks the API 34 google_apis session cannot grade:
#  - graphics acceptance (baseline-smoke, static-no-gms-no-adjust): scripts/android-graphics-smoke.py
#    parses API 30's `dumpsys input` window list; on API 34 the format differs (inputConfig=, a
#    transform line per window) and the webgl row fails with "No org.redoubtbrowser window is in the
#    input dispatcher's window list" before any GL check runs;
#  - check-update-privacy and first-run-capture, like for like with 157.0-3's API 30 captures.
# The harness boots the AVD from the full SDK (it ranks `default` first) in its own work dir.
R=/home/mgysin/redoubt-artifacts/release-158.0-2; S=$R/repo/docs/android/evidence/lw-m7-01/release-158.0-2/acceptance/scripts
export SDK=/home/mgysin/redoubt-artifacts/android-sdk WORK=$R/work30 RUNS=$R/runs30
mkdir -p $WORK $RUNS; cd $R
SERIAL= $S/run-check.sh baseline-smoke
export SERIAL=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb devices | awk '/^emulator-/{print $1; exit}')
[ -n "$SERIAL" ] || { echo "no emulator-* serial; stopping"; exit 1; }   # added for Beta 2
echo "serial=$SERIAL sdk=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL shell getprop ro.build.version.sdk) fp=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL shell getprop ro.build.fingerprint)"
$S/run-check.sh static-no-gms-no-adjust --check-no-gms --check-no-adjust
$S/run-check.sh check-update-privacy --check-update-privacy
# as in the 157.0.1-1 acceptance: --check-no-suggest on the no-GMS image (the API 34 google_apis image adds OS traffic in the typing window)
$S/run-check.sh check-no-suggest --check-no-suggest
$S/run-check.sh first-run-capture --first-run-capture
# From Beta 2 (LW-M7-46): the manual WebGL page, on this API 30 image (the UI helpers' tap guard reads its dumpsys input)
python3 $S/webgl-manual.py $SERIAL $RUNS/webgl-manual $R/apk/fenix-x86_64-158.0-2-throwaway.apk > $RUNS/webgl-manual.console 2>&1; echo "$(date -u +%T) webgl-manual exit=$?"
# New for 158.0-2 (LW-M7-50): below API 31 the runtime gate is OFF, so --check-isolation must report isolation OFF
# with 158.0-1's media path; then --check-video, the process labels, and the upgrade 158.0-1 -> 158.0-2 on this image.
$S/run-check.sh check-isolation-1 --check-isolation
$S/run-check.sh check-video --check-video
/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL install -r $R/apk/fenix-x86_64-158.0-2-throwaway.apk
python3 $S/process-labels.py $SERIAL $RUNS/process-labels 158.0-2-api30 > $RUNS/process-labels-158.0-2-api30.console 2>&1; echo "$(date -u +%T) process-labels exit=$?"
for p in A B C; do UPGRADE_SOURCE=$R/apk/fenix-x86_64-158.0-1-throwaway.apk python3 $S/upgrade-test.py $SERIAL $RUNS/upgrade-from-158.0-1 $p > $RUNS/upgrade-from-158.0-1-$p.console 2>&1; echo "$(date -u +%T) upgrade from 158.0-1 $p exit=$?"; done
/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SERIAL emu kill
echo DRIVE30 DONE
