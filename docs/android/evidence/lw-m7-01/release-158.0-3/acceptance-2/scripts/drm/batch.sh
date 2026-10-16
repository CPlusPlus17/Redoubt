#!/bin/bash
# 158.0-3 second acceptance: the LW-M7-39 Widevine flows on the ONE running emulator, with MOZ_LOG EME:5 so that
# license requests per EME session can be counted (count.py). From the api31-33-fix batch.sh (evidence/lw-m7-39/
# api31-33-fix/scripts), without its harness checks (they run in batch2.sh / drive-api3x.sh).
#   flow     Allowed PlayLow Play PlaySwitch Ask Blocked  (default Blocked, Allowed, pinned low 60 s / ABR 40 s /
#            switch to highest at 10 s, Ask to allow prompt, Blocked rejection)
#   first1-3 fresh profile (pm clear), Allowed, Play70 (ABR, report at 70 s; the clip is ~60 s)
# Graded on the reached currentTime and the license request count, not on play.html's ok (5 s is enough for ok).
# usage: drm/batch.sh LEVEL RUNS     eme-server.py must listen on 18766 with OUTDIR $R/eme-out.
set -u
L=$1; RUNS=$2
R=/home/mgysin/redoubt-artifacts/release-158.0-3/accept2
D=$(cd "$(dirname "$0")" && pwd)
APK=$R/apk/fenix-x86_64-158.0-3-throwaway.apk
ADB=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
PKG=org.redoubtbrowser
export EME_OUT=$R/eme-out
SERIAL=$($ADB devices | awk '/^emulator-/{print $1; exit}')
[ -n "$SERIAL" ] || { echo "no emulator-* serial; stopping"; exit 1; }
[ "$($ADB -s $SERIAL shell getprop ro.build.version.sdk | tr -d '\r')" = "$L" ] || { echo "emulator is not API $L"; exit 1; }
mkdir -p $RUNS
echo "$(date -u +%FT%TZ) serial=$SERIAL api=$L fingerprint=$($ADB -s $SERIAL shell getprop ro.build.fingerprint | tr -d '\r') apk=$(sha256sum $APK | cut -c1-64)" | tee -a $RUNS/drm-batch.log
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
  echo "$(date -u +%T) $n counts $(python3 $D/count.py $o/logcat.txt $PKG | tee $o/counts.json)" | tee -a $RUNS/drm-batch.log
  grep -v "drm screen" $o/flow.out | tee -a $RUNS/drm-batch.log
  gzip -f $o/logcat.txt
}
flow drm-api$L-flow Allowed PlayLow Play PlaySwitch Ask Blocked
for i in $(seq 1 ${FIRSTS:-3}); do flow drm-api$L-first$i Allowed Play70; done
$ADB -s $SERIAL shell rm -f /data/local/tmp/$PKG-geckoview-config.yaml; $ADB -s $SERIAL shell am clear-debug-app
$ADB -s $SERIAL reverse --remove tcp:18766
echo "DRM BATCH $L DONE" | tee -a $RUNS/drm-batch.log
