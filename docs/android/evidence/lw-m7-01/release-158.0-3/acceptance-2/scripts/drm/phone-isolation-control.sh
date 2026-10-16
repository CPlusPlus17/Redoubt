#!/bin/bash
# Control for the phone --check-isolation H.264 row: the same harness run (phone harness copy, loopback origin) with
# another build, here 158.0-2 (arm64-v8a, throwaway-signed). org.redoubtbrowser must not be installed before; it is
# uninstalled after, and the stay-awake settings are restored. usage: phone-isolation-control.sh SERIAL NAME APK OUT
set -u
SERIAL=$1; NAME=$2; APK=$3; O=$4
R=/home/mgysin/redoubt-artifacts/release-158.0-3/accept2; P=$R/phone-harness
ADB=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
a() { $ADB -s $SERIAL "$@"; }
[ -z "$(a shell pm list packages org.redoubtbrowser | tr -d '\r' | grep -x package:org.redoubtbrowser)" ] || { echo "already installed; stopping"; exit 1; }
mkdir -p $O $R/work-$NAME
stay=$(a shell settings get global stay_on_while_plugged_in | tr -d '\r'); tmo=$(a shell settings get system screen_off_timeout | tr -d '\r')
echo "$(date -u +%FT%TZ) serial=$SERIAL apk=$(sha256sum $APK | cut -c1-64) before: stay_on_while_plugged_in=$stay screen_off_timeout=$tmo" | tee -a $O/device.txt
a logcat -c; $ADB -s $SERIAL logcat -v threadtime > $O/logcat.txt 2>&1 & lc=$!
(cd $P && LW_SMOKE_REPO=$P LW_SMOKE_PACKAGE=org.redoubtbrowser LW_SMOKE_LOOPBACK_ORIGIN=1 timeout 580 scripts/android-smoke.sh --serial $SERIAL \
  --sdk /home/mgysin/redoubt-artifacts/android-sdk --work $R/work-$NAME --apk $APK \
  --aapt2 $R/x/aapt2/aapt2 --check-isolation --json $O/check-isolation.json > $O/out.txt 2> $O/err.txt); rc=$?
sleep 2; kill $lc; wait $lc 2>/dev/null; gzip -f $O/logcat.txt
echo "$(date -u +%T) check-isolation exit=$rc $(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(' '.join('%s=%s'%(c['check'],'PASS' if c['ok'] else 'FAIL') for c in d['checks']))" $O/check-isolation.json 2>/dev/null)" | tee -a $O/device.txt
a uninstall org.redoubtbrowser | tee -a $O/device.txt
a shell settings put global stay_on_while_plugged_in $stay; a shell settings put system screen_off_timeout $tmo
echo "after: stay_on_while_plugged_in=$(a shell settings get global stay_on_while_plugged_in | tr -d '\r') screen_off_timeout=$(a shell settings get system screen_off_timeout | tr -d '\r') installed=$(a shell pm list packages org.redoubtbrowser | tr -d '\r')" | tee -a $O/device.txt
