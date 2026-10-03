#!/usr/bin/env python3
"""Is the empty "Canvas and WebGL permissions" list after a cold start the lazy-listener window?

usage: review-race-probe.py SERIAL OUTDIR VARIANT [VARIANT ...]
  VARIANT plain   cold start, trigger WebGL, tap the quiet notice's Review
  VARIANT guard   same, but first register an extra, permanent Gecko listener for
                  GeckoView:GetAllPermissions (it only records the dispatch time; the
                  real handler still answers). With it the event's listener list is
                  never empty, so Java's hasGeckoListener() cannot read false.
Per attempt: module-loaded state before the tap, list rendered or not, the app's
"No listener for GeckoView:GetAllPermissions" lines, and (guard) dispatch times.
"""
import http.server, importlib.util, json, os, re, socketserver, subprocess, sys, threading, time
R = "/home/mgysin/redoubt-artifacts/release-157/acceptance/runtime"
ADBX = "/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb"
PKG = "org.redoubtbrowser"
serial, out, variants = sys.argv[1], sys.argv[2], sys.argv[3:]
os.makedirs(out, exist_ok=True)
os.environ.setdefault("LW_SMOKE_REPO", "/home/mgysin/redoubt-artifacts/release-157/repo")
spec = importlib.util.spec_from_file_location("drv", R + "/work/harness/driver.py")
drv = importlib.util.module_from_spec(spec); spec.loader.exec_module(drv)
adb = drv.Adb(ADBX, serial); app = drv.App(adb, PKG, R + "/work")
PAGE = b"<!doctype html><meta name=viewport content='width=device-width'><title>race</title><h1>review race</h1>"
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(PAGE)
srv = socketserver.TCPServer(("127.0.0.1", 0), H); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
adb.run("reverse", "tcp:%d" % port, "tcp:%d" % port, check=True)
URL = "http://localhost:%d/race" % port

GUARD = r"""
const {EventDispatcher} = ChromeUtils.importESModule("resource://gre/modules/Messaging.sys.mjs");
const {GeckoViewUtils} = ChromeUtils.importESModule("resource://gre/modules/GeckoViewUtils.sys.mjs");
GeckoViewUtils.__lwTimes = [];
GeckoViewUtils.__lwGuard = { onEvent(ev) { GeckoViewUtils.__lwTimes.push([ev, Date.now()]); } };
EventDispatcher.instance.registerListener(GeckoViewUtils.__lwGuard, ["GeckoView:GetAllPermissions"]);
return true;"""
TIMES = r"""const {GeckoViewUtils} = ChromeUtils.importESModule("resource://gre/modules/GeckoViewUtils.sys.mjs");
return GeckoViewUtils.__lwTimes || null;"""
LOADED = 'return Cu.isESModuleLoaded("resource://gre/modules/GeckoViewStorageController.sys.mjs");'
WEBGL = "const c=document.createElement('canvas'); return !!c.getContext('webgl');"

def dump():
    return drv._ui_dump(adb)
def centre(xml, rid):
    m = re.search(r'resource-id="%s:id/%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % (PKG, rid), xml)
    return None if not m else ((int(m.group(1)) + int(m.group(3))) // 2, (int(m.group(2)) + int(m.group(4))) // 2)

results = []
for i, variant in enumerate(variants):
    r = {"attempt": i, "variant": variant}
    m = None
    try:
        app.force_stop(); time.sleep(1)
        subprocess.run([ADBX, "-s", serial, "logcat", "-c"])
        m = drv.open_session(app, URL)
        drv.wait_for_initial_document(m, URL)
        r["pid"] = adb.shell("pidof " + PKG, timeout=30).strip()
        xml, pt, acked = drv.toolbar_ready(adb, PKG, timeout=30)
        r["module_loaded_before"] = m.script(LOADED, chrome=True)
        if variant == "guard":
            r["guard"] = m.script(GUARD, chrome=True)
        m.cmd("Marionette:SetContext", {"value": "content"})
        r["webgl_context"] = m.script(WEBGL)
        snack = None; t0 = time.time()
        while time.time() - t0 < 8 and not snack:
            snack = centre(dump(), "snackbar_action")
        r["snackbar_seen_after_s"] = round(time.time() - t0, 1) if snack else None
        if snack:
            adb.shell("input tap %d %d" % snack, timeout=30)
            time.sleep(3)
            xml = dump()
            open(os.path.join(out, "attempt-%d-%s.xml" % (i, variant)), "w").write(xml)
            r["list_rendered"] = "Ask for each site" in xml
            r["pending_webgl_row"] = centre(xml, "origin_permission_pending_webgl") is not None
            r["module_loaded_after"] = m.script(LOADED, chrome=True)
            if variant == "guard":
                r["dispatch_times"] = m.script(TIMES, chrome=True)
        log = subprocess.run([ADBX, "-s", serial, "logcat", "-d", "-v", "threadtime"], capture_output=True, text=True).stdout
        r["no_listener_get_all"] = [l for l in log.splitlines() if "No listener for GeckoView:GetAllPermissions" in l]
        open(os.path.join(out, "attempt-%d-%s.logcat" % (i, variant)), "w").write(log)
    except Exception as e:
        r["error"] = repr(e)
    finally:
        if m:
            try: m.close()
            except Exception: pass
        adb.shell("input keyevent 4", timeout=30)
    results.append(r); print(json.dumps(r), flush=True)
adb.run("reverse", "--remove", "tcp:%d" % port); srv.shutdown()
json.dump(results, open(os.path.join(out, "results.json"), "w"), indent=1)
