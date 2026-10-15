#!/bin/bash
# batch.sh LEVEL APK : the LW-M7-39 device runs on the ONE running emulator (serial checked to be emulator-*).
#   LEVEL 34: --check-eme x2, DRM UI flow + Widevine playback (pinned low, ABR, forced switch), five
#             "first play on a fresh profile" flows, --check-isolation x2, --check-video x2, default suite,
#             first-run capture.   LEVEL 30: --check-eme, flow + playback, two first-play flows, isolation, video.
# Run names are prefixed with $TAG (default v3).
# eme-server.py must listen on 18766 (EME_OUT = its OUTDIR).
set -u
L=$1; export APK=$2
D=$(cd "$(dirname "$0")" && pwd)
ADB=~/redoubt-artifacts/android-sdk/platform-tools/adb
export SERIAL=$($ADB devices | awk '/^emulator-/{print $1; exit}')
[ -n "$SERIAL" ] || { echo "no emulator-* serial; stopping"; exit 1; }
[ "$($ADB -s $SERIAL shell getprop ro.build.version.sdk | tr -d '\r')" = "$L" ] || { echo "emulator is not API $L"; exit 1; }
export RUNS=~/redoubt-artifacts/drm-iso/runs$L EME_OUT=~/redoubt-artifacts/drm-iso/eme-out
[ "$L" = 30 ] && export SDK=~/redoubt-artifacts/android-sdk WORK=~/redoubt-artifacts/drm-iso/work-emu30
mkdir -p $RUNS
echo "serial=$SERIAL api=$L apk=$(sha256sum $APK | cut -c1-64)" | tee -a $RUNS/batch.log
flow() {  # flow NAME choices...
  local n=$1; shift; local o=$RUNS/$n; mkdir -p $o
  $ADB -s $SERIAL install -r "$APK" > /dev/null && $ADB -s $SERIAL shell pm clear org.redoubtbrowser > /dev/null
  $ADB -s $SERIAL reverse tcp:18766 tcp:18766
  $ADB -s $SERIAL logcat -c; $ADB -s $SERIAL logcat -v threadtime > $o/logcat.txt 2>&1 & local lc=$!
  timeout 590 python3 $D/drm-flow.py $SERIAL $n $o 18766 "$@" > $o/flow.out 2>&1; echo "flow exit=$?" >> $o/flow.out
  sleep 2; kill $lc; wait $lc 2>/dev/null
  echo "$(date -u +%T) $n crypto-exceptions=$(grep -c 'Failed to query crypto scheme support' $o/logcat.txt) tab-deaths=$(grep -cE 'Process org.redoubtbrowser:[^ ]*[Tt]ab[^ ]* \(pid [0-9]+\) has died' $o/logcat.txt) parent-line=$(grep -c 'Redoubt isolation-eme: parent found' $o/logcat.txt)" | tee -a $RUNS/batch.log
  grep -v "drm screen" $o/flow.out | tee -a $RUNS/batch.log
  gzip -f $o/logcat.txt
}
R=$D/run-check.sh
T=${TAG:-v3}
$R $T-check-eme-1 --check-eme | tee -a $RUNS/batch.log
[ "$L" = 34 ] && $R $T-check-eme-2 --check-eme | tee -a $RUNS/batch.log
flow $T-api$L-flow Allowed PlayLow Play PlaySwitch Ask Blocked
for i in $(seq 1 $([ "$L" = 34 ] && echo 5 || echo 2)); do flow $T-api$L-first$i Allowed Play; done
$R $T-check-isolation-1 --check-isolation | tee -a $RUNS/batch.log
$R $T-check-video-1 --check-video | tee -a $RUNS/batch.log
if [ "$L" = 34 ]; then
  $R $T-check-isolation-2 --check-isolation | tee -a $RUNS/batch.log
  $R $T-check-video-2 --check-video | tee -a $RUNS/batch.log
  $R $T-baseline-smoke | tee -a $RUNS/batch.log
  $R $T-first-run-capture --first-run-capture | tee -a $RUNS/batch.log
fi
echo "BATCH $L DONE" | tee -a $RUNS/batch.log
