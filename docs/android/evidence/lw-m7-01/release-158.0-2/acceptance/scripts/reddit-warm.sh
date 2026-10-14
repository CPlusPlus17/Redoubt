#!/bin/bash
# Follow-up to reddit-cold.sh (whose step 2 opened the login URL 30 s after reddit.com/ and still saw a
# blank page): the documented workaround with longer waits. Fresh profile, first start on
# https://www.reddit.com/ (uBO sheet acknowledged), 60 s; then the login URL (a new tab, as every VIEW
# intent opens one), screenshots + UI dumps at 30 s and 90 s. Diagnostic for the release notes, not a gate.
set -u
R=/home/mgysin/redoubt-artifacts/release-158.0-2
ADB=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
SERIAL=${SERIAL:?}; A="$ADB -s $SERIAL"
CAND=${CAND:-$R/apk/fenix-x86_64-158.0-2-throwaway.apk}
O=${OUT:-$R/runs/reddit-warm}; mkdir -p $O
w(){ timeout "$1" bash -c 'until false; do sleep 1; done'; }
shot(){ $A exec-out screencap -p > "$O/$1.png"; $A shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; $A exec-out cat /sdcard/ui.xml > "$O/$1.xml" 2>/dev/null; }
$A uninstall org.redoubtbrowser >/dev/null 2>&1; $A install $CAND || exit 1
{ echo "host: $(sha256sum "$CAND")"; echo "versionCode: $($A shell dumpsys package org.redoubtbrowser | grep -m1 -o 'versionCode=[0-9]*')"
  echo "default network: $($A shell dumpsys connectivity 2>/dev/null | grep -m1 'Active default network' | tr -d '\r')"; echo "started: $(date -u +%FT%TZ)"; } > $O/installed-apk.txt
$A shell input keyevent KEYCODE_WAKEUP; $A shell svc power stayon true
$A logcat -c
$A shell am start -a android.intent.action.VIEW -d https://www.reddit.com/ org.redoubtbrowser >/dev/null
w 20
python3 - "$SERIAL" "$R" <<'PY'
import importlib.util, sys, os
serial, R = sys.argv[1:3]; os.environ.setdefault("LW_SMOKE_REPO", R + "/repo")
spec = importlib.util.spec_from_file_location("drv", R + "/work/harness/driver.py")
drv = importlib.util.module_from_spec(spec); spec.loader.exec_module(drv)
adb = drv.Adb("/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb", serial)
xml = drv._ui_dump(adb); xml, acked = drv.acknowledge_ubo_added_notice(adb, "org.redoubtbrowser", xml)
print("uBO sheet acknowledged:", acked)
PY
w 40; shot 1-home-60s
$A shell am start -a android.intent.action.VIEW -d https://www.reddit.com/login/ org.redoubtbrowser >/dev/null
w 30; shot 2-login-after-home-30s
w 60; shot 3-login-after-home-90s
$A logcat -d -v threadtime | gzip > $O/logcat.txt.gz
$A logcat -b crash -d > $O/crash-buffer.txt
echo "pid: $($A shell pidof org.redoubtbrowser)" >> $O/installed-apk.txt
for f in $O/*.xml; do echo "$(basename $f): $(grep -o 'text="[^"]\{3,\}"' $f | grep -iv 'redoubt\|reddit.com' | head -8 | tr '\n' ' ')"; done > $O/summary.txt
cat $O/summary.txt
echo REDDIT-WARM DONE
