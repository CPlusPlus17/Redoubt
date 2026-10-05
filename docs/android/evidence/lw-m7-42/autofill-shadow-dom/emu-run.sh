#!/bin/bash
# One emulator case: load a page in org.redoubtbrowser, tap the first field,
# then the second, and keep the probe AutofillService's log (tag PPINV_AF).
# usage: emu-run.sh <label> <url> <outdir> [x y1 y2]   (defaults: the test pages' field centres at 1080x2340)
set -u
L=$1; URL=$2; OUT=$3; X=${4:-491}; Y1=${5:-699}; Y2=${6:-950}
ADB="${ADB:-$HOME/redoubt-artifacts/android-sdk/platform-tools/adb} -s ${SERIAL:-emulator-5580}"
w(){ timeout "$1" bash -c 'until false; do sleep 1; done'; }
$ADB shell input keyevent KEYCODE_WAKEUP
$ADB logcat -c
$ADB shell am start -a android.intent.action.VIEW -d "$URL" org.redoubtbrowser > /dev/null
w ${LOAD_WAIT:-12}
$ADB exec-out screencap -p > "$OUT/$L-0-load.png"
$ADB shell input tap $X $Y1; w 5
$ADB exec-out screencap -p > "$OUT/$L-1-field1.png"
$ADB shell input keyevent KEYCODE_BACK; w 1   # hide IME / fill UI, keep page
$ADB shell input tap $X $Y2; w 5
$ADB exec-out screencap -p > "$OUT/$L-2-field2.png"
$ADB logcat -d -v time > "$OUT/logcat-$L.txt"
grep 'PPINV_AF' "$OUT/logcat-$L.txt" > "$OUT/probe-$L.txt"
echo "$L: onFillRequest=$(grep -c onFillRequest "$OUT/probe-$L.txt") webDomain-localhost-EditText=$(grep -c 'EditText.*webDomain=localhost' "$OUT/probe-$L.txt")"
