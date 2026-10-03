#!/bin/bash
# Run the committed graphics runner directly (same argv as the harness) so the app stays alive after a failure.
R=/home/mgysin/redoubt-artifacts/release-157/acceptance/runtime
A=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
REPO=/home/mgysin/redoubt-artifacts/release-157/repo
out=$1; mkdir -p $out
$A -s emulator-5584 shell am force-stop org.redoubtbrowser
$A -s emulator-5584 shell pm clear org.redoubtbrowser
cd $R && python3 mn.py --launch "https://example.org/" "return location.href" > $out/bootstrap.json 2>&1
python3 $REPO/scripts/android-graphics-smoke.py --adb $A --serial emulator-5584 --package org.redoubtbrowser \
  --apk $R/apk/rc/fenix-x86_64-release-throwaway.apk --dedicated-test-profile --work $out/graphics \
  > $out/summary.stdout 2> $out/runner.log
echo "runner exit=$?"
$A -s emulator-5584 shell pidof org.redoubtbrowser
