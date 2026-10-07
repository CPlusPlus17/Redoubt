#!/bin/bash
# LW-M7-42 shadow-DOM autofill on the candidate, with the investigation's probe AutofillService
# (com.ppinv.af/.ProbeAutofill, ~/redoubt-artifacts/pp-investigate/emu/afsvc/out/ppinv-probe.apk; it logs
# every onFillRequest under tag PPINV_AF). Pages: docs/android/evidence/lw-m7-42/autofill-shadow-dom/www/,
# served on the host and reached through `adb reverse tcp:8642`. Case driver: that directory's emu-run.sh,
# unchanged (SERIAL from the environment). Like the LW-M7-42 narrowed runs: fresh install, force-stop
# before each case (fresh activity = fresh autofill session), negative cases first.
set -u
R=/home/mgysin/redoubt-artifacts/beta-158.0-1-b1; S=$R/repo/docs/android/evidence/lw-m7-01/release-158.0-1-beta.1/acceptance/scripts
W=$R/repo/docs/android/evidence/lw-m7-42/autofill-shadow-dom
ADB=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
PROBE=/home/mgysin/redoubt-artifacts/pp-investigate/emu/afsvc/out/ppinv-probe.apk
CAND=${CAND:-$R/apk/fenix-x86_64-158.0-1-beta1-throwaway.apk}
O=${OUT:-$R/runs/autofill}; mkdir -p $O
A="$ADB -s $SERIAL"
$A install -r $PROBE
$A shell settings put secure autofill_service com.ppinv.af/.ProbeAutofill
$A uninstall org.redoubtbrowser >/dev/null 2>&1; $A install $CAND || exit 1
P=$($A shell pm path org.redoubtbrowser | tr -d '\r' | sed 's/^package://')
{ echo "host:   $(sha256sum "$CAND")"; echo "device: $($A shell sha256sum "$P" | tr -d '\r')"
  echo "probe:  $(sha256sum "$PROBE")"
  echo "versionName: $($A shell dumpsys package org.redoubtbrowser | grep -m1 versionName | tr -d '\r ')"
  echo "settings secure autofill_service: $($A shell settings get secure autofill_service | tr -d '\r')"
  echo "screen: $($A shell wm size | tr -d '\r')"
  echo "installed: $(date -u +%FT%TZ)"; } > $O/installed-apk.txt
cat $O/installed-apk.txt
(cd $W/www && exec python3 -m http.server 8642 --bind 127.0.0.1) > $O/http.log 2>&1 & HS=$!
$A reverse tcp:8642 tcp:8642
# first start: acknowledge the uBO sheet through the harness's own helper
python3 - "$SERIAL" "$R" <<'PY'
import importlib.util, sys, time, os
serial, R = sys.argv[1:3]; os.environ.setdefault("LW_SMOKE_REPO", R + "/repo")
spec = importlib.util.spec_from_file_location("drv", R + "/work/harness/driver.py")
drv = importlib.util.module_from_spec(spec); spec.loader.exec_module(drv)
adb = drv.Adb("/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb", serial)
adb.shell("am start -a android.intent.action.VIEW -d http://localhost:8642/plain.html org.redoubtbrowser", timeout=60)
time.sleep(20)
xml = drv._ui_dump(adb); xml, acked = drv.acknowledge_ubo_added_notice(adb, "org.redoubtbrowser", xml)
print("uBO sheet acknowledged:", acked)
PY
$A exec-out screencap -p > $O/warmup.png
for c in shadow-email-only shadow-nonlogin shadow-closed shadow-open plain shadow-email-only; do
  $A shell am force-stop org.redoubtbrowser; sleep 2
  L=$c; [ -e $O/probe-$c.txt ] && L=$c-again
  SERIAL=$SERIAL LOAD_WAIT=15 bash $W/emu-run.sh $L http://localhost:8642/$c.html $O ${AF_X:-491} ${AF_Y1:-699} ${AF_Y2:-950}
done | tee $O/summary.txt
kill $HS 2>/dev/null
$A reverse --remove tcp:8642
$A shell settings delete secure autofill_service
echo AUTOFILL DONE
