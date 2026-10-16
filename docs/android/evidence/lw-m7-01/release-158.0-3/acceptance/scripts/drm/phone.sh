#!/bin/bash
# 158.0-3: the Widevine flows on ONE named physical phone (the owner's test phones; org.redoubtbrowser not installed
# on them before). Installs the throwaway-signed arm64-v8a candidate, runs the DRM flow and three fresh-profile first
# plays, records the phone's stay-awake settings first and restores them, and uninstalls the app at the end.
# usage: drm/phone.sh SERIAL NAME RUNS     (eme-server.py on 18766, OUTDIR $R/eme-out)
set -u
SERIAL=$1; NAME=$2; RUNS=$3
R=/home/mgysin/redoubt-artifacts/release-158.0-3
D=$(cd "$(dirname "$0")" && pwd)
APK=$R/apk/fenix-arm64-v8a-158.0-3-throwaway.apk
ADB=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
export EME_OUT=$R/eme-out DRM_ALLOW_DEVICE=$SERIAL
mkdir -p $RUNS
a() { $ADB -s $SERIAL "$@"; }
[ -z "$(a shell pm list packages org.redoubtbrowser | tr -d '\r' | grep -x package:org.redoubtbrowser)" ] || { echo "org.redoubtbrowser already installed on $SERIAL: stopping (never replace the owner's install)"; exit 1; }
stay=$(a shell settings get global stay_on_while_plugged_in | tr -d '\r'); tmo=$(a shell settings get system screen_off_timeout | tr -d '\r')
{ echo "serial=$SERIAL name=$NAME"; for p in ro.product.model ro.build.fingerprint ro.build.version.sdk ro.build.type ro.debuggable; do echo "$p=$(a shell getprop $p | tr -d '\r')"; done
  echo "apk=$(sha256sum $APK | cut -c1-64)"; echo "before: stay_on_while_plugged_in=$stay screen_off_timeout=$tmo"; } | tee $RUNS/device.txt
a shell settings put global stay_on_while_plugged_in 7; a shell settings put system screen_off_timeout 1800000
a install $APK | tee -a $RUNS/device.txt
a shell dumpsys package org.redoubtbrowser | grep -E "versionCode|versionName" | tee -a $RUNS/device.txt
flow() {
  local n=$1; shift; local o=$RUNS/$n; mkdir -p $o
  a shell pm clear org.redoubtbrowser > /dev/null
  a reverse tcp:18766 tcp:18766
  a logcat -c; $ADB -s $SERIAL logcat -v threadtime > $o/logcat.txt 2>&1 & local lc=$!   # adb itself, not the function: kill $lc must stop adb
  timeout 590 python3 $D/drm-flow.py $SERIAL $n $o 18766 "$@" > $o/flow.out 2>&1; echo "flow exit=$?" >> $o/flow.out
  sleep 2; kill $lc; wait $lc 2>/dev/null
  echo "$(date -u +%T) $n crypto-exceptions=$(grep -c 'Failed to query crypto scheme support' $o/logcat.txt) tab-deaths=$(grep -cE 'Process org.redoubtbrowser:[^ ]*[Tt]ab[^ ]* \(pid [0-9]+\) has died' $o/logcat.txt) parent-line=$(grep -c 'Redoubt isolation-eme: parent found' $o/logcat.txt) fatal=$(grep -cE 'FATAL EXCEPTION|Fatal signal|ANR in org.redoubtbrowser' $o/logcat.txt) isolated=$(a shell ps -AZ | grep -c 'isolated_app.*org.redoubtbrowser')" | tee -a $RUNS/drm-batch.log
  grep -v "drm screen" $o/flow.out | tee -a $RUNS/drm-batch.log
  a shell ps -AZ | grep org.redoubtbrowser > $o/processes.txt
  gzip -f $o/logcat.txt
}
flow $NAME-flow Allowed PlayLow Play PlaySwitch Ask Blocked
for i in 1 2 3; do flow $NAME-first$i Allowed Play; done
a reverse --remove tcp:18766
a uninstall org.redoubtbrowser | tee -a $RUNS/device.txt
a shell settings put global stay_on_while_plugged_in $stay; a shell settings put system screen_off_timeout $tmo
echo "after: stay_on_while_plugged_in=$(a shell settings get global stay_on_while_plugged_in | tr -d '\r') screen_off_timeout=$(a shell settings get system screen_off_timeout | tr -d '\r')" | tee -a $RUNS/device.txt
echo "PHONE $NAME DONE" | tee -a $RUNS/drm-batch.log
