#!/bin/bash
# run.sh NAME FLAG : one harness run of the new dev APK on emulator-5594
F=/home/mgysin/redoubt-artifacts/iso-proto/fix; S=/home/mgysin/redoubt-artifacts/iso-proto/sdk34
cd /home/mgysin/redoubt-artifacts/iso-proto/repo
ANDROID_SDK_ROOT=$S LW_SMOKE_PACKAGE=org.redoubtbrowser.dev timeout 570 ./scripts/android-smoke.sh --serial emulator-5594 --sdk $S \
  --apk $F/apk/redoubt-dev-iso-x86_64.apk $2 --work $F/smokework --json $F/results/device-api34/$1.json > $F/results/device-api34/$1.out 2>&1
echo "rc=$?" >> $F/results/device-api34/$1.out
