#!/bin/bash
# af-run.sh PKG LABEL URL OUT : open URL in PKG, tap the first two EditText nodes, keep PPINV_AF log
set -u
PKG=$1; L=$2; URL=$3; OUT=$4; mkdir -p $OUT
ADB="$HOME/redoubt-artifacts/android-sdk/platform-tools/adb -s ${SERIAL:-emulator-5594}"
$ADB shell input keyevent KEYCODE_WAKEUP
$ADB logcat -c
$ADB shell am start -a android.intent.action.VIEW -d "$URL" $PKG > /dev/null
sleep 10
$ADB shell uiautomator dump /sdcard/af.xml >/dev/null; $ADB shell cat /sdcard/af.xml > $OUT/$L-ui.xml
mapfile -t C < <(python3 - $OUT/$L-ui.xml <<'PY'
import re,sys
x=open(sys.argv[1]).read()
for m in re.finditer(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',x):
    a,b,c,d=map(int,m.groups())
    if d-b<300: print((a+c)//2,(b+d)//2)
PY
)
echo "$L fields: ${C[*]:0:3}"
i=0
for c in "${C[@]:1:2}"; do i=$((i+1)); $ADB shell input tap $c; sleep 5; $ADB exec-out screencap -p > $OUT/$L-$i.png; $ADB shell input keyevent KEYCODE_BACK; sleep 1; done
$ADB logcat -d -v time > $OUT/logcat-$L.txt
grep 'PPINV_AF' $OUT/logcat-$L.txt > $OUT/probe-$L.txt
echo "$L: onFillRequest=$(grep -c onFillRequest $OUT/probe-$L.txt) webDomain-localhost-EditText=$(grep -c 'EditText.*webDomain=localhost' $OUT/probe-$L.txt)"
