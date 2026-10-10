#!/usr/bin/env python3
"""File-picker smoke for the 157.0.1-1 acceptance (new; Firefox 157.0.1 fixes MFSA 2026-104 /
CVE-2026-106016 in the File Handling component, and its diff touches dom/ipc/FilePickerParent.cpp).

This is a functional smoke test of the picker path, not a test of the vulnerability.
Expected: a real tap on an <input type=file> opens the Android system picker (DocumentsUI), after the
runtime-permission prompts and the chooser Fenix shows in front of it, without a crash.
  case 1 (deny): every permission prompt is answered "Don't allow". Fenix (Android Components'
         FilePicker) then dismisses the request without a picker; the page must get `cancel` and the
         app must stay alive. (Attempt 1 graded this case as "picker expected", which was wrong.)
  case 2 (pick): the prompts are allowed, the chooser's document entry is tapped, and the pushed file
         is picked; the page must read back its name, size and content.
  case 3 (back): with the permissions now granted, the picker opens again and Back cancels it; the
         page must get `cancel` and the app must stay alive. Picking a file pushed to Downloads hands the page
a File with that name, size and content. A second case uses Back to cancel the picker, and the app
must stay alive with the page usable.

usage: filepicker-probe.py SERIAL OUTDIR APK

The page is served by a local http.server on the host and reached through `adb reverse`
(http://127.0.0.1:PORT/, a loopback origin, which HTTPS-only mode does not upgrade). The page is read
back through the harness's own Marionette door (GeckoView debug config + am set-debug-app), as in the
other probes. The tap itself is a real `input tap` (WebDriver refuses Element Click on file inputs,
and a synthetic click would not be a user activation).
"""
import http.server, importlib.util, json, os, re, socketserver, subprocess, sys, threading, time

R = "/home/mgysin/redoubt-artifacts/release-157.0.1-1"
ADB = "/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb"
PKG = "org.redoubtbrowser"
serial, out, apk = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
os.environ.setdefault("LW_SMOKE_REPO", R + "/repo")
spec = importlib.util.spec_from_file_location("drv", R + "/work/harness/driver.py")
drv = importlib.util.module_from_spec(spec); spec.loader.exec_module(drv)
adb = drv.Adb(ADB, serial)
app = drv.App(adb, PKG, R + "/work")
res = {"serial": serial, "apk_sha256": subprocess.run(["sha256sum", apk], capture_output=True, text=True).stdout[:64],
       "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "steps": [], "verdict": {}}
n = [0]

def note(step, **kw):
    kw["step"] = step; kw["t"] = time.strftime("%H:%M:%S"); res["steps"].append(kw)
    print(json.dumps(kw, default=str)[:700], flush=True)

def snap(name):
    n[0] += 1; base = os.path.join(out, "%02d-%s" % (n[0], name))
    adb.shell("uiautomator dump /sdcard/fp.xml", timeout=60)
    xml = adb.shell("cat /sdcard/fp.xml", timeout=60)
    open(base + ".xml", "w").write(xml)
    png = subprocess.run([ADB, "-s", serial, "exec-out", "screencap", "-p"], capture_output=True, timeout=60).stdout
    open(base + ".png", "wb").write(png)
    return xml

def top_activity():
    o = adb.shell("dumpsys activity activities | grep -E 'topResumedActivity|mResumedActivity|ResumedActivity:' | head -3", timeout=60)
    return o.strip()

PAGE = b"""<!doctype html><html><head><meta name=viewport content="width=device-width,initial-scale=1">
<title>file picker smoke</title><style>
html,body{margin:0;height:100%}
#pick{position:fixed;left:0;top:0;width:100vw;height:100vh;opacity:0.02;font-size:40px}
#out{position:fixed;left:0;bottom:0;font:20px monospace;background:#ff0;z-index:-1}
</style></head><body>
<input type=file id=pick>
<pre id=out data-state="idle">idle</pre>
<script>
var o=document.getElementById('out'), p=document.getElementById('pick');
p.addEventListener('click',function(){o.dataset.clicks=String(+(o.dataset.clicks||0)+1);});
p.addEventListener('cancel',function(){o.dataset.state='cancel';o.textContent='cancel';});
p.addEventListener('change',function(){
  var f=p.files[0]; if(!f){o.dataset.state='change-empty';o.textContent='change, no file';return;}
  o.dataset.state='change'; o.dataset.name=f.name; o.dataset.size=String(f.size); o.dataset.type=f.type;
  var r=new FileReader(); r.onload=function(){o.dataset.content=String(r.result);o.dataset.state='read';o.textContent='read '+f.name;};
  r.onerror=function(){o.dataset.state='read-error';o.textContent='read error';};
  r.readAsText(f);
});
</script></body></html>"""

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(PAGE))); self.end_headers(); self.wfile.write(PAGE)
    def log_message(self, *a):
        with open(os.path.join(out, "server.log"), "a") as f: f.write("%s %s\n" % (time.strftime("%H:%M:%S"), a[0] % a[1:]))

srv = socketserver.TCPServer(("127.0.0.1", 0), H); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:%d/picker.html" % port
FNAME = "redoubt-pick-%d.txt" % int(time.time())
CONTENT = "Redoubt 157.0.1-1 file picker smoke\n"

PICKER_PKGS = ("com.android.documentsui", "com.google.android.documentsui")
STATE_JS = "var o=document.getElementById('out'); return o ? Object.assign({text:o.textContent}, o.dataset) : null;"

def page_state(m):
    try:
        return m.script(STATE_JS)
    except Exception as e:
        return {"error": str(e)}

PERM = {"deny": ("Don\u2019t allow", "Don't allow", "Deny"), "allow": ("While using the app", "Allow")}
CHOOSER_PKGS = ("com.android.intentresolver", "android/com.android.internal.app.ChooserActivity")

def open_picker(m, label, perms):
    """Tap the input, then walk what Android shows until DocumentsUI is in front:
    runtime-permission prompts are answered with `perms` ("deny" or "allow"), and the
    share-sheet chooser Fenix puts in front of the file request (camera, camcorder,
    sound recorder, files) gets a tap on its document entry. Every screen is saved."""
    w, h = drv._screen_size(adb)
    snap(label + "-page")
    adb.shell("input tap %d %d" % (w // 2, int(h * 0.55)), timeout=30)
    seen = []
    for i in range(30):
        time.sleep(1.5)
        ta = top_activity()
        if any(p in ta for p in PICKER_PKGS):
            note(label + "-picker-open", after_steps=i + 1, path=seen, top=ta); return True, snap(label + "-picker"), seen
        if "permissioncontroller" in ta:
            xml = snap(label + "-permission")
            q = next((t for t in drv._ui_texts(xml) if t.endswith("?")), "")
            btn = next(((t, drv._text_bounds(xml, t)) for t in PERM[perms] if drv._text_bounds(xml, t)), None)
            if btn:
                adb.shell("input tap %d %d" % btn[1], timeout=30); seen.append(("permission", q, btn[0])); note(label + "-permission", question=q, answer=btn[0])
            continue
        if any(c in ta for c in CHOOSER_PKGS):
            xml = snap(label + "-chooser")
            texts = drv._ui_texts(xml)
            target = next((t for t in ("Files", "Media", "Documents") if t in texts), None)
            seen.append(("chooser", texts, target)); note(label + "-chooser", entries=texts, tapped=target)
            if target:
                adb.shell("input tap %d %d" % drv._text_bounds(xml, target), timeout=30)
            continue
    note(label + "-picker-not-seen", path=seen, top=top_activity(), page=page_state(m)); return False, snap(label + "-no-picker"), seen

try:
    adb.run("reverse", "tcp:%d" % port, "tcp:%d" % port, timeout=30, check=True)
    adb.shell("rm -f /sdcard/Download/redoubt-pick-*.txt", timeout=30)
    p = subprocess.run([ADB, "-s", serial, "shell", "printf '%s' > /sdcard/Download/%s" % (CONTENT.replace("\n", "\\n"), FNAME)],
                       capture_output=True, text=True, timeout=30)
    adb.shell("am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Download/%s" % FNAME, timeout=30)
    note("fixture", url=URL, file=FNAME, ls=adb.shell("ls -l /sdcard/Download/%s" % FNAME, timeout=30).strip(),
         sdk=adb.shell("getprop ro.build.version.sdk", timeout=30).strip())
    adb.run("logcat", "-b", "crash", "-c", timeout=30)
    app.install(apk); app.wipe()
    m = drv.open_session(app, URL)
    time.sleep(4)
    xml, bar, acked = drv.toolbar_ready(adb, PKG, timeout=40)
    note("loaded", url=m.cmd("WebDriver:GetCurrentURL").get("value"), ubo_notice_acknowledged=acked, page=page_state(m))

    # Case 1: deny every permission prompt; no picker, the request is dismissed.
    ok1, x1, path1 = open_picker(m, "cancel", "deny")
    if ok1:
        adb.shell("input keyevent KEYCODE_BACK", timeout=30); time.sleep(3)
    for _ in range(3):   # Back out of a chooser or prompt the walk may have left
        if PKG in top_activity(): break
        adb.shell("input keyevent KEYCODE_BACK", timeout=30); time.sleep(2)
    st1 = page_state(m); top1 = top_activity()
    note("cancel-after-back", page=st1, top=top1, alive=app.alive(), crashed=app.crashed())
    snap("cancel-after")

    # Case 2: open the picker, pick the pushed file.
    picked = False
    ok2, x2, path2 = open_picker(m, "pick", "allow")
    if ok2:
        pt = drv._text_bounds(x2, FNAME)
        if not pt:
            # Not in Recent: open the roots drawer and go to Downloads.
            for ident in ('content-desc="Show roots"', 'content-desc="Open navigation drawer"'):
                mm = re.search(ident + r'[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', x2)
                if mm:
                    adb.shell("input tap %d %d" % ((int(mm.group(1)) + int(mm.group(3))) // 2, (int(mm.group(2)) + int(mm.group(4))) // 2), timeout=30); time.sleep(2); break
            xd = snap("pick-drawer")
            for t in ("Downloads", "Download"):
                q = drv._text_bounds(xd, t)
                if q:
                    adb.shell("input tap %d %d" % q, timeout=30); time.sleep(3); break
            x2 = snap("pick-downloads")
            pt = drv._text_bounds(x2, FNAME)
        if pt:
            adb.shell("input tap %d %d" % pt, timeout=30); picked = True
            note("pick-tapped", file=FNAME, at=pt)
        else:
            note("pick-file-not-found", texts=drv._ui_texts(x2)[:40])
            adb.shell("input keyevent KEYCODE_BACK", timeout=30)
        st2 = None
        for i in range(15):
            time.sleep(1); st2 = page_state(m)
            if st2 and st2.get("state") in ("read", "read-error", "change-empty"):
                break
        note("pick-result", page=st2, top=top_activity())
    else:
        st2 = page_state(m)
    snap("pick-after")
    # Case 3: permissions granted now; open the picker and cancel it with Back.
    m.script("var o=document.getElementById('out'); o.dataset.state='idle'; o.textContent='idle'; return 1;")
    ok3, x3, path3 = open_picker(m, "back", "allow")
    if ok3:
        adb.shell("input keyevent KEYCODE_BACK", timeout=30); time.sleep(3)
    for _ in range(3):
        if PKG in top_activity(): break
        adb.shell("input keyevent KEYCODE_BACK", timeout=30); time.sleep(2)
    st3 = page_state(m)
    note("back-after", page=st3, top=top_activity(), alive=app.alive())
    snap("back-after")
    alive = app.alive(); crashed = app.crashed()
    crash = adb.out("logcat", "-d", "-b", "crash", timeout=30)
    open(os.path.join(out, "crash-buffer.txt"), "w").write(crash)
    note("final", alive=alive, crashed=crashed, crash_buffer_bytes=len(crash))
    v = res["verdict"]
    v["deny_case_path"] = path1; v["pick_case_path"] = path2; v["back_case_path"] = path3
    v["deny_dismissed_request_no_picker"] = bool((not ok1) and isinstance(st1, dict) and st1.get("state") == "cancel")
    v["back_opened_picker"] = ok3
    v["back_cancelled_request"] = bool(ok3 and isinstance(st3, dict) and st3.get("state") == "cancel")
    v["picker_opened_pick_case"] = ok2
    v["picked_file_reached_page"] = bool(picked and st2 and st2.get("state") == "read" and st2.get("name") == FNAME
                                        and st2.get("content") == CONTENT and st2.get("size") == str(len(CONTENT)))
    v["no_crash"] = bool(alive and not crashed)
    v["PASS"] = bool(v["deny_dismissed_request_no_picker"] and ok2 and v["picked_file_reached_page"]
                     and v["back_cancelled_request"] and v["no_crash"])
    try: m.close()
    except Exception: pass
finally:
    try: app.remove_debug_config()
    except Exception: pass
    adb.run("reverse", "--remove", "tcp:%d" % port, timeout=30)
    adb.shell("rm -f /sdcard/Download/%s" % FNAME, timeout=30)
    srv.shutdown()
    res["completed_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(res, open(os.path.join(out, "probe.json"), "w"), indent=1, default=str)
    print("VERDICT", json.dumps(res["verdict"]))
sys.exit(0 if res["verdict"].get("PASS") else 1)
