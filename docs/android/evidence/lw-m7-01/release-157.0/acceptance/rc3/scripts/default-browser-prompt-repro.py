#!/usr/bin/env python3
"""Does the default-browser SYSTEM prompt appear on ordinary launcher cold starts? (no upgrade involved)
usage: default-browser-prompt-repro.py SERIAL OUTDIR [STARTS]
Fresh profile (pm clear); open https://example.org/ once (a tab to come back to); then STARTS launcher
cold starts (force-stop + HomeActivity), each checked after 8 s for the RoleManager RequestRoleActivity
and its text. If it shows, it is cancelled with Back and the start number recorded."""
import importlib.util, json, os, re, subprocess, sys, time
R = "/home/mgysin/redoubt-artifacts/release-157/acceptance/rc3"
ADBX = "/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb"; PKG = "org.redoubtbrowser"
serial, out = sys.argv[1], sys.argv[2]; starts = int(sys.argv[3]) if len(sys.argv) > 3 else 7
os.makedirs(out, exist_ok=True)
os.environ.setdefault("LW_SMOKE_REPO", "/home/mgysin/redoubt-artifacts/release-157/repo")
spec = importlib.util.spec_from_file_location("drv", R + "/work/harness/driver.py")
drv = importlib.util.module_from_spec(spec); spec.loader.exec_module(drv)
adb = drv.Adb(ADBX, serial); app = drv.App(adb, PKG, R + "/work")
res = {"apk": adb.shell("dumpsys package %s | grep -m2 -E 'versionCode|versionName'" % PKG).strip(), "starts": []}
app.force_stop(); app.wipe()
app.start_url("https://example.org/"); time.sleep(10)
xml = drv._ui_dump(adb); drv.acknowledge_ubo_added_notice(adb, PKG, xml)
for i in range(1, starts + 1):
    app.force_stop(); time.sleep(1.5)
    subprocess.run([ADBX, "-s", serial, "logcat", "-c"])
    app.start_home(); time.sleep(8)
    xml = drv._ui_dump(adb)
    top = adb.shell("dumpsys activity activities | grep -m1 -E 'mResumedActivity|ResumedActivity'").strip()
    log = subprocess.run([ADBX, "-s", serial, "logcat", "-d"], capture_output=True, text=True).stdout
    shown = "RequestRoleActivity" in top or "default browser app" in xml
    r = {"start": i, "prompt": shown, "resumed": top[-120:],
         "role_request_logged": any("REQUEST_ROLE" in l for l in log.splitlines()),
         "UpdateWasNativeDefaultBrowserPromptShown": "UpdateWasNativeDefaultBrowserPromptShown" in log}
    if shown:
        open(os.path.join(out, "prompt-start-%d.xml" % i), "w").write(xml)
        with open(os.path.join(out, "prompt-start-%d.png" % i), "wb") as f:
            f.write(subprocess.run([ADBX, "-s", serial, "exec-out", "screencap", "-p"], capture_output=True).stdout)
        adb.shell("input keyevent 4"); time.sleep(1.5)
    res["starts"].append(r); print(json.dumps(r), flush=True)
app.force_stop()
json.dump(res, open(os.path.join(out, "repro.json"), "w"), indent=1)
