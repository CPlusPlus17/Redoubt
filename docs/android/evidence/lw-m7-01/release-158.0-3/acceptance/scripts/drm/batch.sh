#!/bin/bash
# 158.0-3: the LW-M7-39 Widevine playback flows (copied from evidence/lw-m7-39/scripts/batch.sh; only the
# flows, the --check-eme runs are in batch2.sh / drive-api31.sh / drive-api30.sh).
# usage: drm/batch.sh LEVEL RUNS  -- on the ONE running emulator (serial checked to be emulator-*), with the
# candidate APK. eme-server.py must listen on 18766 with OUTDIR $EME_OUT.
#   every level: flow  Allowed PlayLow Play PlaySwitch Ask Blocked  (default Blocked, Allowed, Widevine Shaka
#                Angel One pinned low 60 s / ABR 40 s / switch to highest 50 s, Ask to allow prompt, Blocked)
#   then N "first play on a fresh profile" flows (Allowed, Play): 3 on API 34 and 31, 1 on API 30.
set -u
L=$1; RUNS=$2
R=/home/mgysin/redoubt-artifacts/release-158.0-3
D=$(cd "$(dirname "$0")" && pwd)
APK=$R/apk/fenix-x86_64-158.0-3-throwaway.apk
ADB=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
export EME_OUT=$R/eme-out
SERIAL=$($ADB devices | awk '/^emulator-/{print $1; exit}')
[ -n "$SERIAL" ] || { echo "no emulator-* serial; stopping"; exit 1; }
[ "$($ADB -s $SERIAL shell getprop ro.build.version.sdk | tr -d '\r')" = "$L" ] || { echo "emulator is not API $L"; exit 1; }
mkdir -p $RUNS
echo "serial=$SERIAL api=$L apk=$(sha256sum $APK | cut -c1-64)" | tee -a $RUNS/drm-batch.log
flow() {  # flow NAME choices...
  local n=$1; shift; local o=$RUNS/$n; mkdir -p $o
  $ADB -s $SERIAL install -r "$APK" > /dev/null && $ADB -s $SERIAL shell pm clear org.redoubtbrowser > /dev/null
  $ADB -s $SERIAL reverse tcp:18766 tcp:18766
  $ADB -s $SERIAL logcat -c; $ADB -s $SERIAL logcat -v threadtime > $o/logcat.txt 2>&1 & local lc=$!
  timeout 590 python3 $D/drm-flow.py $SERIAL $n $o 18766 "$@" > $o/flow.out 2>&1; echo "flow exit=$?" >> $o/flow.out
  sleep 2; kill $lc; wait $lc 2>/dev/null
  echo "$(date -u +%T) $n crypto-exceptions=$(grep -c 'Failed to query crypto scheme support' $o/logcat.txt) tab-deaths=$(grep -cE 'Process org.redoubtbrowser:[^ ]*[Tt]ab[^ ]* \(pid [0-9]+\) has died' $o/logcat.txt) parent-line=$(grep -c 'Redoubt isolation-eme: parent found' $o/logcat.txt) fatal=$(grep -cE 'FATAL EXCEPTION|Fatal signal|ANR in org.redoubtbrowser' $o/logcat.txt)" | tee -a $RUNS/drm-batch.log
  grep -v "drm screen" $o/flow.out | tee -a $RUNS/drm-batch.log
  gzip -f $o/logcat.txt
}
flow drm-api$L-flow Allowed PlayLow Play PlaySwitch Ask Blocked
for i in $(seq 1 $([ "$L" = 30 ] && echo 1 || echo 3)); do flow drm-api$L-first$i Allowed Play; done
echo "DRM BATCH $L DONE" | tee -a $RUNS/drm-batch.log
