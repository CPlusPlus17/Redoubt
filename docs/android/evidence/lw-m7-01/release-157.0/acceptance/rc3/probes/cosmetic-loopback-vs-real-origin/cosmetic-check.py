#!/usr/bin/env python3
"""Does uBO apply ANY cosmetic filter on a loopback page? (diagnostic)  usage: cosmetic-check.py SERIAL"""
import http.server, importlib.util, json, socketserver, sys, threading, time
R = "/home/mgysin/redoubt-artifacts/release-157/acceptance/rc3"
spec = importlib.util.spec_from_file_location("drv", R + "/work/harness/driver.py")
drv = importlib.util.module_from_spec(spec); spec.loader.exec_module(drv)
adb = drv.Adb("/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb", sys.argv[1]); app = drv.App(adb, "org.redoubtbrowser", R + "/work")
PAGE = b"""<!doctype html><title>cosmetic</title><h1>cosmetic</h1>
<div class="a-adhesion" style="height:30px">easylist a-adhesion</div><div class="a-dserver" style="height:30px">easylist a-dserver</div>
<div id="AcceptCookieContainer" style="height:30px">cookie id</div><div class="accept-cookies-banner" style="height:30px">cookie class</div>
<div class="lw-control" style="height:30px">control</div>"""
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(PAGE)
srv = socketserver.TCPServer(("127.0.0.1", 0), H); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
adb.run("reverse", "tcp:%d" % port, "tcp:%d" % port, check=True)
JS = """return [...document.querySelectorAll('div')].map(d => [d.className || d.id, getComputedStyle(d).display]);"""
out = {}
for host in ("127.0.0.1", "localhost"):
    url = "http://%s:%d/c" % (host, port)
    m = drv.open_session(app, url); time.sleep(6)
    m.cmd("Marionette:SetContext", {"value": "content"})
    out[host] = m.script(JS)
    out[host + "-ubo-content-script"] = m.script("return typeof window.wrappedJSObject !== 'undefined';")
    m.close()
print(json.dumps(out, indent=1))
adb.run("reverse", "--remove", "tcp:%d" % port); srv.shutdown()
