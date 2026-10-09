#!/usr/bin/env python3
"""Manual WebGL page on the Beta 2 candidate (LW-M7-46: no "Canvas or WebGL was protected" snackbar).

New for Beta 2. It repeats LW-M7-46's device steps (evidence/lw-m7-46/device/api34/, same two pages
webgl.html and canvas.html, served on the host and reached through `adb reverse tcp:8466`) on the
release candidate, using the graphics harness's own UI helpers (scripts/android-graphics-smoke.py:
UI.dump with forbid_quiet_notice=True fails on any dump that shows the snackbar text or its Review
action; UI.choose opens the site controls -> "Canvas and WebGL permissions" -> the pending WebGL row
-> Allow). The tap guard of those helpers reads API 30's `dumpsys input`, so run it on the android-30
`default` image.

usage: webgl-manual.py SERIAL OUTDIR APK
Steps (fresh install, so a fresh profile):
  1  open http://127.0.0.1:8466/webgl.html, acknowledge the uBO sheet, reload; dumps at 1-6 s:
     page text must read webgl=NULL webgl2=NULL, no notice in any dump;
  2  site controls -> permissions list lists the blocked WebGL request; Allow (session);
  3  after the reload the page must read webgl=CONTEXT webgl2=CONTEXT, no notice;
  4  http://localhost:8466/canvas.html (another origin, nothing allowed): dumps at 1-6 s, no notice.
Results: OUTDIR/webgl-manual.json (+ the numbered dumps and screenshots). Exit 0 = PASS.
"""
import html, importlib.util, json, os, re, subprocess, sys, time
from pathlib import Path

R = "/home/mgysin/redoubt-artifacts/beta-158.0-1-b2"
REPO = R + "/repo"
ADB = "/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb"
PKG = "org.redoubtbrowser"
PAGES = REPO + "/docs/android/evidence/lw-m7-46/device/api34"
serial, out, apk = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
out.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("gs", REPO + "/scripts/android-graphics-smoke.py")
gs = importlib.util.module_from_spec(spec); spec.loader.exec_module(gs)
protocol = gs.foundation(Path(REPO + "/scripts/android-smoke.sh"))
adb = protocol.Adb(ADB, serial)
ev = gs.Evidence(out, "webgl-manual", "manual")
ui = gs.UI(adb, PKG, ev, "webglmanual", 25, True)
ui.forbid_quiet_notice = True
res = {"apk": apk, "steps": []}

def a(*args, timeout=120):
    return subprocess.run([ADB, "-s", serial, *args], capture_output=True, text=True, timeout=timeout)

def note(step, **kw):
    kw["step"] = step; kw["t"] = time.strftime("%H:%M:%S"); res["steps"].append(kw)
    print(json.dumps(kw)[:400], flush=True)

def page_text(xml):
    return [html.unescape(t) for t in re.findall(r'text="((?:webgl|readback)[^"]*)"', xml)]

def watch(label, want):
    seen = []
    for i in range(1, 7):
        time.sleep(1)
        xml = ui.dump("%s-%ds" % (label, i), screenshot=(i in (1, 6)))   # raises on a notice
        seen.append(page_text(xml))
    last = [t for t in seen[-1] if "=" in t]
    gs.require(any(want in t for t in last), "%s: page text %r, wanted %r" % (label, last, want))
    note(label, page=last, dumps_without_notice=6)

server = subprocess.Popen([sys.executable, "-m", "http.server", "8466", "--bind", "127.0.0.1"], cwd=PAGES,
                          stdout=open(out / "http.log", "w"), stderr=subprocess.STDOUT)
status = "FAIL"
try:
    a("uninstall", PKG)
    p = a("install", apk, timeout=900); note("install", rc=p.returncode, out=p.stdout.strip()[-200:])
    gs.require(p.returncode == 0, "install failed")
    note("installed", versionName=a("shell", "dumpsys package %s | grep -m1 versionName" % PKG).stdout.strip(),
         sha256=subprocess.run(["sha256sum", apk], capture_output=True, text=True).stdout.split()[0])
    a("reverse", "tcp:8466", "tcp:8466")
    url = "http://127.0.0.1:8466/webgl.html"
    a("shell", "am start -a android.intent.action.VIEW -d %s %s" % (url, PKG))
    time.sleep(20)
    xml = ui.dump("first-start", screenshot=True)
    xml = ui.acknowledge_ubo_added_notice(xml)
    # reload, so that the watched window starts with the request
    a("shell", "am start -a android.intent.action.VIEW -d %s %s" % (url, PKG)); time.sleep(1)
    watch("webgl-blocked", "webgl=NULL webgl2=NULL")
    ui.choose(origin="http://127.0.0.1:8466", kind="webgl", saved=False, decision="allow",
              permanent=False, private=False)
    time.sleep(4)
    xml = ui.dump("after-allow", screenshot=True)
    note("after-allow", list_texts=[html.unescape(t) for t in re.findall(r'text="([^"]*(?:WebGL|Allowed)[^"]*)"', xml)])
    ui.close_permissions()
    watch("webgl-allowed", "webgl=CONTEXT webgl2=CONTEXT")
    a("shell", "am start -a android.intent.action.VIEW -d http://localhost:8466/canvas.html %s" % PKG)
    time.sleep(1)
    watch("canvas-blocked", "readback=")
    status = "PASS"
except Exception as e:
    res["error"] = "%s: %s" % (type(e).__name__, e); print("FAIL", res["error"], flush=True)
finally:
    server.terminate(); a("reverse", "--remove", "tcp:8466")
    res["status"] = status; res["notice_checks"] = ui.notice_checks
    (out / "webgl-manual.json").write_text(json.dumps(res, indent=2) + "\n")
    ev.finish(status, res.get("error", ""), complete=(status == "PASS"))
print("WEBGL-MANUAL", status)
sys.exit(0 if status == "PASS" else 1)
