#!/bin/bash
# install.sh <apk> <outdir>: fresh install of org.redoubtbrowser, record host and on-device sha256, warm up.
set -u
APK=$1; OUT=$2; mkdir -p "$OUT"
ADB="$HOME/redoubt-artifacts/android-sdk/platform-tools/adb -s emulator-5580"
$ADB uninstall org.redoubtbrowser >/dev/null 2>&1
$ADB install "$APK" || exit 1
P=$($ADB shell pm path org.redoubtbrowser | tr -d '\r' | sed 's/^package://')
{ echo "host:   $(sha256sum "$APK")"
  echo "device: $($ADB shell sha256sum "$P" | tr -d '\r')"
  echo "versionName: $($ADB shell dumpsys package org.redoubtbrowser | grep -m1 versionName | tr -d '\r ')"
  echo "settings secure autofill_service: $($ADB shell settings get secure autofill_service | tr -d '\r')"
  echo "installed: $(date -u +%FT%TZ)"; } > "$OUT/installed-apk.txt"
cat "$OUT/installed-apk.txt"
$ADB reverse tcp:8642 tcp:8642
$ADB shell am start -a android.intent.action.VIEW -d "http://localhost:8642/" org.redoubtbrowser >/dev/null
sleep 20
$ADB exec-out screencap -p > "$OUT/warmup.png"
$ADB shell input tap 914 2229   # dismiss "uBlock Origin was added" sheet (OK)
sleep 3
$ADB exec-out screencap -p > "$OUT/warmup-dismissed.png"
