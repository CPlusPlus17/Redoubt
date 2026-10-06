#!/bin/bash
# Phase 2 driver (API 34 google_apis x86_64, the image LW-M7-43 and LW-M6-03 measured on).
# The emulator was booted by the harness from an SDK view that holds only android-34
# ($R/sdk34: symlinks to the real emulator, platform-tools and system-images/android-34),
# work dir $R/work34. --check-video, the store-installer probe, then process labels
# (157.0-3, then 157.0-2 as the contrast).
R=/home/mgysin/redoubt-artifacts/release-157.0-3; S=$R/repo/docs/android/evidence/lw-m7-01/release-157.0-3/acceptance/scripts
ADB=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
SERIAL=${SERIAL:-emulator-5584}; O=$R/runs34; mkdir -p $O
APK=$R/apk/fenix-x86_64-157.0-3-throwaway.apk
echo "serial=$SERIAL sdk=$($ADB -s $SERIAL shell getprop ro.build.version.sdk) fp=$($ADB -s $SERIAL shell getprop ro.build.fingerprint)"
cd $R/repo
for i in 1 2; do
  LW_SMOKE_REPO=$R/repo scripts/android-smoke.sh --serial $SERIAL --sdk $R/sdk34 --work $R/work34 --apk $APK --aapt2 $R/x/aapt2/aapt2 --check-video --json $O/check-video-$i.json > $O/check-video-$i.out 2> $O/check-video-$i.err
  echo "$(date -u +%T) check-video run $i exit=$? apk=$(sha256sum $APK | cut -c1-64) harness=$(sha256sum scripts/android-smoke.sh | cut -c1-64)"
done
LW_ACCEPT_WORK=$R/work34 python3 $S/store-installer-probe.py $SERIAL $O/store-installer $APK > $O/store-installer.console 2>&1; echo "$(date -u +%T) store-installer exit=$?"
$ADB -s $SERIAL install -r $APK >/dev/null
python3 $S/process-labels.py $SERIAL $O/process-labels 157.0-3 > $O/process-labels-157.0-3.console 2>&1; echo "$(date -u +%T) process-labels 157.0-3 exit=$?"
$ADB -s $SERIAL uninstall org.redoubtbrowser >/dev/null; $ADB -s $SERIAL install $R/apk/fenix-x86_64-157.0-2-throwaway.apk >/dev/null
python3 $S/process-labels.py $SERIAL $O/process-labels 157.0-2 > $O/process-labels-157.0-2.console 2>&1; echo "$(date -u +%T) process-labels 157.0-2 exit=$?"
echo DRIVE34 DONE
