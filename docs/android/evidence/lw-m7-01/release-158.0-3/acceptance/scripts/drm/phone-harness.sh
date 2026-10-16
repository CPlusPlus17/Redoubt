#!/bin/bash
# 158.0-3: --check-eme and --check-isolation on ONE named userdebug phone (Marionette needs ro.debuggable=1), with
# the arm64-v8a candidate. Records and restores the stay-awake settings the harness changes; uninstalls at the end.
# usage: phone-harness.sh SERIAL NAME RUNS
set -u
SERIAL=$1; NAME=$2; RUNS=$3
R=/home/mgysin/redoubt-artifacts/release-158.0-3; S=$R/repo/docs/android/evidence/lw-m7-01/release-158.0-3/acceptance/scripts
ADB=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
[ "$($ADB -s $SERIAL shell getprop ro.debuggable | tr -d '\r')" = 1 ] || { echo "not a debuggable build; stopping"; exit 1; }
[ -z "$($ADB -s $SERIAL shell pm list packages org.redoubtbrowser | tr -d '\r' | grep -x package:org.redoubtbrowser)" ] || { echo "already installed; stopping"; exit 1; }
stay=$($ADB -s $SERIAL shell settings get global stay_on_while_plugged_in | tr -d '\r'); tmo=$($ADB -s $SERIAL shell settings get system screen_off_timeout | tr -d '\r')
mkdir -p $RUNS; echo "before: stay_on_while_plugged_in=$stay screen_off_timeout=$tmo" | tee -a $RUNS/settings.txt
export SERIAL RUNS SDK=/home/mgysin/redoubt-artifacts/android-sdk WORK=$R/work-$NAME APK=$R/apk/fenix-arm64-v8a-158.0-3-throwaway.apk
mkdir -p $WORK; cp $R/apk/output-metadata.json $R/apk/ 2>/dev/null
$S/run-check.sh $NAME-check-eme-1 --check-eme
$S/run-check.sh $NAME-check-eme-2 --check-eme
$S/run-check.sh $NAME-check-isolation-1 --check-isolation
$ADB -s $SERIAL uninstall org.redoubtbrowser
$ADB -s $SERIAL shell settings put global stay_on_while_plugged_in $stay; $ADB -s $SERIAL shell settings put system screen_off_timeout $tmo
$ADB -s $SERIAL shell svc power stayon false 2>/dev/null; $ADB -s $SERIAL shell settings put global stay_on_while_plugged_in $stay
echo "after: stay_on_while_plugged_in=$($ADB -s $SERIAL shell settings get global stay_on_while_plugged_in | tr -d '\r') screen_off_timeout=$($ADB -s $SERIAL shell settings get system screen_off_timeout | tr -d '\r')" | tee -a $RUNS/settings.txt
echo "PHONE HARNESS $NAME DONE"
