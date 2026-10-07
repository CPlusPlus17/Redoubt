#!/usr/bin/env python3
"""SELinux labels and uids of the app's processes with web content loaded (copied from the 157.0-3 acceptance).

157.0-3 pins GeckoView's isolated content processes off (LW-M7-43). Expected for 157.0-3: the
content processes are `org.redoubtbrowser:tab<N>` in `u:r:untrusted_app:...` under the app's own
uid, and no process of the app runs as `isolated_app`. For 157.0-2 (the contrast) the content
processes were `isolatedTab`/`zygoteTab` services in `isolated_app` under isolated uids.

usage: process-labels.py SERIAL OUTDIR TAG      (the APK to judge must already be installed)
Fresh profile; opens https://example.org/ and then https://example.com/ in a second tab through
the launcher intent, waits, and reads `ps -A -o LABEL,...` (the SELinux label, as `ps -A -Z`). Writes OUTDIR/TAG.json and TAG.txt.
"""
import json, os, re, subprocess, sys, time
ADB = "/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb"
PKG = "org.redoubtbrowser"
serial, out, tag = sys.argv[1:4]
os.makedirs(out, exist_ok=True)


def sh(cmd, t=120):
    return subprocess.run([ADB, "-s", serial, "shell", cmd], capture_output=True, text=True, timeout=t).stdout


sh("am force-stop %s; pm clear %s" % (PKG, PKG))
sh("am start -n %s/org.mozilla.fenix.HomeActivity" % PKG); time.sleep(12)
for url in ("https://example.org/", "https://example.com/"):
    sh("am start -a android.intent.action.VIEW -d '%s' -n %s/org.mozilla.fenix.IntentReceiverActivity" % (url, PKG))
    time.sleep(12)
ps = sh("ps -A -o LABEL,USER,UID,PID,PPID,NAME")
app_uid = sh("su 0 stat -c %%u /data/data/%s" % PKG).strip()
rows = []
for line in ps.splitlines()[1:]:
    f = line.split()
    if len(f) >= 6 and (PKG in f[5] or "isolated" in f[5].lower() and "redoubt" in line):
        rows.append({"label": f[0], "user": f[1], "uid": f[2], "pid": f[3], "ppid": f[4], "name": f[5]})
# isolated processes are named after the service class; catch them by the app's zygote parent too
zyg = [r["pid"] for r in rows if r["name"].endswith("_zygote")]
for line in ps.splitlines()[1:]:
    f = line.split()
    if len(f) >= 6 and f[4] in zyg and not any(r["pid"] == f[3] for r in rows):
        rows.append({"label": f[0], "user": f[1], "uid": f[2], "pid": f[3], "ppid": f[4], "name": f[5]})
content = [r for r in rows if re.search(r":(tab|isolatedTab|zygoteTab)\d*", r["name"]) or "isolated_app" in r["label"]]
res = {"tag": tag, "serial": serial, "app_uid": app_uid,
       "sdk": sh("getprop ro.build.version.sdk").strip(), "fingerprint": sh("getprop ro.build.fingerprint").strip(),
       "version": sh("dumpsys package %s | grep -E 'versionCode|versionName'" % PKG).strip(),
       "processes": rows, "content_processes": content,
       "content_untrusted_app_same_uid": bool(content) and all("untrusted_app" in r["label"] and r["uid"] == app_uid for r in content),
       "any_isolated_app": any("isolated_app" in r["label"] for r in rows + content)}
open(os.path.join(out, tag + ".txt"), "w").write(ps)
json.dump(res, open(os.path.join(out, tag + ".json"), "w"), indent=1)
print(json.dumps({k: res[k] for k in ("tag", "sdk", "app_uid", "content_untrusted_app_same_uid", "any_isolated_app")}))
print("\n".join("%s %s %s %s" % (r["label"], r["uid"], r["pid"], r["name"]) for r in rows))
