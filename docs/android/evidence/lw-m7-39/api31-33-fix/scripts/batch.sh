#!/bin/bash
# api31-33-fix (LW-M7-39, Android 12-13 DRM stall). batch.sh LEVEL SERIAL APK RUNS
# On ONE emulator (serial emulator-*, its API level checked): --check-eme, --check-isolation, --check-video,
# then the Widevine flows with MOZ_LOG EME:5 (GeckoView debug config + am set-debug-app, removed at the end):
#   flow    Allowed PlayLow Play PlaySwitch Ask Blocked   (pinned low 60 s / ABR 40 s / switch to highest at 10 s,
#           Ask to allow prompt, Blocked rejection)
#   first1-5  fresh profile (pm clear), Allowed, Play70 (ABR, report at 70 s; the clip is ~60 s)
# Per flow: count.py on the logcat (license requests per EME session, NDK dropped events, fix lines, deaths).
# eme-server.py must listen on 18766 (EME_OUT = its OUTDIR).
set -u
L=$1; export SERIAL=$2; export APK=$3; export RUNS=$4
D=$(cd "$(dirname "$0")" && pwd)
ADB=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
PKG=org.redoubtbrowser
case $SERIAL in emulator-*) ;; *) echo "not an emulator serial; stopping"; exit 1;; esac
[ "$($ADB -s $SERIAL shell getprop ro.build.version.sdk | tr -d '\r')" = "$L" ] || { echo "emulator is not API $L"; exit 1; }
export SDK=/home/mgysin/redoubt-artifacts/drm-a12/sdk/api$L WORK=/home/mgysin/redoubt-artifacts/drm-a12/work$L
export EME_OUT=/home/mgysin/redoubt-artifacts/drm-a12/eme-out
mkdir -p $RUNS $WORK
echo "$(date -u +%FT%TZ) serial=$SERIAL api=$L fingerprint=$($ADB -s $SERIAL shell getprop ro.build.fingerprint | tr -d '\r') apk=$(sha256sum $APK | cut -c1-64)" | tee -a $RUNS/batch.log
R=$D/run-check.sh
[ -z "${SKIP_CHECKS:-}" ] && for c in eme isolation video; do $R check-$c-1 --check-$c | tee -a $RUNS/batch.log; done
flow() {  # flow NAME choices...
  local n=$1; shift; local o=$RUNS/$n; mkdir -p $o
  $ADB -s $SERIAL install -r "$APK" > /dev/null && $ADB -s $SERIAL shell pm clear $PKG > /dev/null
  printf 'env:\n  MOZ_LOG: "EME:5,MediaKeys:5,RemoteCDM:5"\n' > $o/geckoview-config.yaml
  $ADB -s $SERIAL push $o/geckoview-config.yaml /data/local/tmp/$PKG-geckoview-config.yaml > /dev/null
  $ADB -s $SERIAL shell am set-debug-app --persistent $PKG
  $ADB -s $SERIAL reverse tcp:18766 tcp:18766
  $ADB -s $SERIAL logcat -c; $ADB -s $SERIAL logcat -v threadtime > $o/logcat.txt 2>&1 & local lc=$!
  (cd $D && timeout 900 python3 $D/drm-flow.py $SERIAL $n $o 18766 "$@") > $o/flow.out 2>&1; echo "flow exit=$?" >> $o/flow.out
  sleep 2; kill $lc; wait $lc 2>/dev/null
  $ADB -s $SERIAL shell am force-stop $PKG
  echo "$(date -u +%T) $n counts $(python3 $D/count.py $o/logcat.txt $PKG | tee $o/counts.json)" | tee -a $RUNS/batch.log
  grep -v "drm screen" $o/flow.out | tee -a $RUNS/batch.log
  gzip -f $o/logcat.txt
}
flow drm-api$L-flow Allowed PlayLow Play PlaySwitch Ask Blocked
for i in $(seq 1 ${FIRSTS:-5}); do flow drm-api$L-first$i Allowed Play70; done
$ADB -s $SERIAL shell rm -f /data/local/tmp/$PKG-geckoview-config.yaml; $ADB -s $SERIAL shell am clear-debug-app
$ADB -s $SERIAL reverse --remove tcp:18766
echo "BATCH $L DONE" | tee -a $RUNS/batch.log
