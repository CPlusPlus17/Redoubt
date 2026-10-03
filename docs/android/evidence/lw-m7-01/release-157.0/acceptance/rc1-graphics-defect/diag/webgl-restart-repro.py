#!/usr/bin/env python3
"""Minimal reproduction of the graphics-acceptance failure after a process restart.

usage: webgl-restart-repro.py SERIAL OUTDIR [--no-grant]

fresh profile -> page tries WebGL (blocked, quiet notice) -> Review -> list
-> [allow WebGL for this session] -> force-stop + relaunch on the same URL ->
page tries WebGL again -> Review -> list. Every dump is kept. Afterwards the
console service is read for errors (release builds do not forward them to logcat).
"""
import html, http.server, importlib.util, json, os, re, socketserver, subprocess, sys, threading, time
R = "/home/mgysin/redoubt-artifacts/release-157/acceptance/runtime"
ADB = "/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb"
PKG = "org.redoubtbrowser"
serial, out = sys.argv[1], sys.argv[2]
grant = "--no-grant" not in sys.argv
os.makedirs(out, exist_ok=True)
os.environ.setdefault("LW_SMOKE_REPO", "/home/mgysin/redoubt-artifacts/release-157/repo")
spec = importlib.util.spec_from_file_location("drv", R + "/work/harness/driver.py")
drv = importlib.util.module_from_spec(spec); spec.loader.exec_module(drv)
adb = drv.Adb(ADB, serial); app = drv.App(adb, PKG, R + "/work")

PAGE = b"""<!doctype html><meta name=viewport content="width=device-width"><title>webgl</title>
<h1>webgl restart repro</h1><pre id=o></pre><script>
function t(){ const c=document.createElement('canvas'); const g=c.getContext('webgl');
  document.getElementById('o').textContent = 'webgl ' + (g ? 'context' : 'null') + ' ' + Date.now(); }
t();</script>"""
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(PAGE)
srv = socketserver.TCPServer(("127.0.0.1", 0), H); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
adb.run("reverse", "tcp:%d" % port, "tcp:%d" % port, check=True)
URL = "http://localhost:%d/webgl" % port
steps = []; n = [0]

def dump(tag):
    n[0] += 1; name = "%02d-%s" % (n[0], tag)
    xml = drv._ui_dump(adb)
    open(os.path.join(out, name + ".xml"), "w").write(xml)
    with open(os.path.join(out, name + ".png"), "wb") as f:
        f.write(subprocess.run([ADB, "-s", serial, "exec-out", "screencap", "-p"], capture_output=True).stdout)
    ids = re.findall(r'resource-id="%s:id/([^"]+)"' % PKG, xml)
    texts = [html.unescape(t) for t in re.findall(r' text="([^"]+)"', xml)]
    steps.append({"step": name, "ids": [i for i in ids if i.startswith("origin_") or i == "snackbar_action"], "texts": texts})
    return xml

def centre(xml, rid=None, text=None):
    for m in re.finditer(r'<node [^>]*>', xml):
        nd = m.group(0)
        if rid and ('resource-id="%s:id/%s"' % (PKG, rid)) not in nd: continue
        if text and ('text="%s"' % text) not in nd: continue
        b = list(map(int, re.findall(r"\d+", re.search(r'bounds="([^"]*)"', nd).group(1))))
        return ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)
    return None

def tap(pt): adb.shell("input tap %d %d" % pt, timeout=30); time.sleep(1.5)

def review_list(tag):
    for _ in range(20):
        xml = dump(tag + "-page")
        xml, _ = drv.acknowledge_ubo_added_notice(adb, PKG, xml)
        pt = centre(xml, rid="snackbar_action")
        if pt: break
        time.sleep(1)
    else:
        return None
    tap(pt)
    xml = None
    for i in range(8):
        time.sleep(1)
        xml = dump(tag + "-list")
        if centre(xml, rid="origin_permission_pending_webgl"): break
    return xml

CONSOLE = r"""return Services.console.getMessageArray().map(x => { let o = {m: String(x.message||"").slice(0,400)};
  try { const e = x.QueryInterface(Ci.nsIScriptError); o.src = e.sourceName; o.cat = e.category; o.flags = e.flags; o.em = e.errorMessage.slice(0,400);} catch(_){}
  return o; }).filter(o => /GeckoView|Permission|perm|Storage|Error/i.test(JSON.stringify(o)));"""
result = {"url": URL, "grant": grant}
m = None
try:
    app.force_stop(); app.wipe()
    m = drv.open_session(app, URL); time.sleep(4)
    xml = review_list("A")
    result["A_pending_webgl_listed"] = bool(xml and centre(xml, rid="origin_permission_pending_webgl"))
    if grant and result["A_pending_webgl_listed"]:
        tap(centre(xml, rid="origin_permission_pending_webgl"))
        xml = dump("A-decision")
        tap(centre(xml, rid="origin_permission_allow"))
        xml = dump("A-after-allow")
        pt = centre(xml, rid="origin_permission_reload") or centre(xml, text="Close")
        if pt: tap(pt)
        dump("A-closed")
    result["A_perms"] = m.script(open(R + "/perms-map.js").read(), chrome=True)
    result["A_console"] = m.script(CONSOLE, chrome=True)
    m.close(); m = None
    result["pid_before"] = adb.shell("pidof " + PKG, timeout=30).strip()
    m = drv.open_session(app, URL); time.sleep(4)
    result["pid_after"] = adb.shell("pidof " + PKG, timeout=30).strip()
    xml = review_list("B")
    result["B_pending_webgl_listed"] = bool(xml and centre(xml, rid="origin_permission_pending_webgl"))
    result["B_list_children"] = len(re.findall(r'origin_permission_', xml or ""))
    time.sleep(10)
    xml = dump("B-list-after-10s")
    result["B_pending_webgl_listed_after_10s"] = bool(centre(xml, rid="origin_permission_pending_webgl"))
    result["B_perms"] = m.script(open(R + "/perms-map.js").read(), chrome=True)
    result["B_console"] = m.script(CONSOLE, chrome=True)
finally:
    if m:
        try: m.close()
        except Exception: pass
    adb.run("reverse", "--remove", "tcp:%d" % port)
    srv.shutdown()
result["steps"] = steps
json.dump(result, open(os.path.join(out, "repro.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in result.items() if k not in ("steps", "A_console", "B_console", "A_perms", "B_perms")}, indent=1))
print("A_perms", result.get("A_perms", {}).get("types"), "B_perms", result.get("B_perms", {}).get("types"))
