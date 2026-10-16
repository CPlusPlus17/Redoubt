#!/bin/bash
# api31-33-fix (LW-M7-39): regression on ONE named physical test phone with the arm64-v8a Redoubt Dev APK
# (org.redoubtbrowser.dev, dev key). Only that package is installed and removed; it must not be installed before.
#   --check-eme (harness copy with harness-loopback-origin.diff, ~/redoubt-artifacts/drm-phones/harness/repo),
#   then 3 x fresh profile (pm clear), Allowed, Widevine Play70 (report at 70 s) with MOZ_LOG EME:5.
# Records stay-awake/debug_app settings first and restores them; uninstalls at the end.
# usage: phone.sh SERIAL NAME APK RUNS     (eme-server.py on 18766, OUTDIR ~/redoubt-artifacts/drm-a12/eme-out)
set -u
SERIAL=$1; NAME=$2; APK=$3; RUNS=$4
D=$(cd "$(dirname "$0")" && pwd)
ADB=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
PKG=org.redoubtbrowser.dev
export EME_OUT=/home/mgysin/redoubt-artifacts/drm-a12/eme-out DRM_ALLOW_DEVICE=$SERIAL PKG SCHEME=redoubt-dev
a() { $ADB -s $SERIAL "$@"; }
[ -z "$(a shell pm list packages $PKG | tr -d '\r' | grep -x package:$PKG)" ] || { echo "$PKG already installed on $SERIAL: stopping"; exit 1; }
mkdir -p $RUNS
stay=$(a shell settings get global stay_on_while_plugged_in | tr -d '\r'); tmo=$(a shell settings get system screen_off_timeout | tr -d '\r'); dbg=$(a shell settings get global debug_app | tr -d '\r')
{ echo "$(date -u +%FT%TZ) serial=$SERIAL name=$NAME"; for p in ro.product.model ro.build.fingerprint ro.build.version.sdk ro.build.type; do echo "$p=$(a shell getprop $p | tr -d '\r')"; done
  echo "apk=$(sha256sum $APK | cut -c1-64)"; echo "before: stay_on_while_plugged_in=$stay screen_off_timeout=$tmo debug_app=$dbg"; } | tee -a $RUNS/device.txt
# --check-eme through the phone harness copy (it installs the APK itself)
P=/home/mgysin/redoubt-artifacts/drm-phones/harness/repo
o=$RUNS/$NAME-check-eme-1; mkdir -p $o /home/mgysin/redoubt-artifacts/drm-a12/work-$NAME
a logcat -c; $ADB -s $SERIAL logcat -v threadtime > $o/logcat.txt 2>&1 & lc=$!
(cd $P && LW_SMOKE_REPO=$P LW_SMOKE_PACKAGE=$PKG LW_SMOKE_LOOPBACK_ORIGIN=1 timeout 580 scripts/android-smoke.sh --serial $SERIAL \
  --sdk /home/mgysin/redoubt-artifacts/android-sdk --work /home/mgysin/redoubt-artifacts/drm-a12/work-$NAME --apk $APK \
  --aapt2 /home/mgysin/redoubt-artifacts/release-158.0-3/x/aapt2/aapt2 --check-eme --json $o/check-eme-1.json > $o/out.txt 2> $o/err.txt); rc=$?
sleep 2; kill $lc; wait $lc 2>/dev/null; gzip -f $o/logcat.txt
echo "$(date -u +%T) $NAME check-eme exit=$rc harness=$(sha256sum $P/scripts/android-smoke.sh | cut -c1-16) $(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(' '.join('%s=%s'%(c['check'],'PASS' if c['ok'] else 'FAIL') for c in d['checks']))" $o/check-eme-1.json 2>/dev/null)" | tee -a $RUNS/device.txt
a shell settings put global stay_on_while_plugged_in 7; a shell settings put system screen_off_timeout 1800000
a install -r $APK | tee -a $RUNS/device.txt
a shell dumpsys package $PKG | grep -E "versionCode|versionName" | tee -a $RUNS/device.txt
flow() {
  local n=$1; shift; local o=$RUNS/$n; mkdir -p $o
  a shell pm clear $PKG > /dev/null
  printf 'env:\n  MOZ_LOG: "EME:5,MediaKeys:5,RemoteCDM:5"\n' > $o/geckoview-config.yaml
  a push $o/geckoview-config.yaml /data/local/tmp/$PKG-geckoview-config.yaml > /dev/null; a shell am set-debug-app --persistent $PKG
  a reverse tcp:18766 tcp:18766
  a logcat -c; $ADB -s $SERIAL logcat -v threadtime > $o/logcat.txt 2>&1 & local lc=$!
  (cd $D && timeout 600 python3 $D/drm-flow.py $SERIAL $n $o 18766 "$@") > $o/flow.out 2>&1; echo "flow exit=$?" >> $o/flow.out
  sleep 2; kill $lc; wait $lc 2>/dev/null
  a shell am force-stop $PKG
  echo "$(date -u +%T) $n counts $(python3 $D/count.py $o/logcat.txt $PKG | tee $o/counts.json) isolated=$(a shell ps -AZ | grep -c "isolated_app.*$PKG")" | tee -a $RUNS/drm-batch.log
  grep -v "drm screen" $o/flow.out | tee -a $RUNS/drm-batch.log
  gzip -f $o/logcat.txt
}
for i in 1 2 3; do flow $NAME-first$i Allowed Play70; done
a shell rm -f /data/local/tmp/$PKG-geckoview-config.yaml
if [ "$dbg" = null ]; then a shell am clear-debug-app; else a shell settings put global debug_app "$dbg"; fi
a reverse --remove tcp:18766
a uninstall $PKG | tee -a $RUNS/device.txt
a shell settings put global stay_on_while_plugged_in $stay; a shell settings put system screen_off_timeout $tmo
echo "after: stay_on_while_plugged_in=$(a shell settings get global stay_on_while_plugged_in | tr -d '\r') screen_off_timeout=$(a shell settings get system screen_off_timeout | tr -d '\r') debug_app=$(a shell settings get global debug_app | tr -d '\r') installed=$(a shell pm list packages $PKG | tr -d '\r')" | tee -a $RUNS/device.txt
echo "PHONE $NAME DONE" | tee -a $RUNS/drm-batch.log
