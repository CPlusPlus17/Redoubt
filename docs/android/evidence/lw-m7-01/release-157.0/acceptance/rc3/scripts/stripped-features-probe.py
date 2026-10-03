#!/usr/bin/env python3
"""The four stripped features are absent from the running UI (diagnostic probe).

usage: stripped-features-probe.py SERIAL OUTDIR

Fresh profile (pm clear), the APK the harness installed. Every screen visited is
dumped with uiautomator (XML + PNG kept in OUTDIR) and every text and
content-desc on it is matched against the labels the APK itself carries for the
features (read from resources.arsc before the run, see README):

  Summarize   browser_menu_summarize_page "Summarize page", the shake CFR
  IP Protect. ip_protection_* ("VPN", "Built-in VPN", "Get Redoubt VPN", ...)
  Lens        context_menu_open_image_with_google_lens "Search with Google Lens"

Screens: the browser's main menu (scrolled), the long-press context menu of an
image, the address bar in edit mode, the Settings root (scrolled to the end),
and Settings > Privacy and security (scrolled). Positive controls: each screen
must show an item it is known to have (otherwise the dump proves nothing).
"""
import html, http.server, importlib.util, json, os, re, socketserver, subprocess, sys, threading, time

R = "/home/mgysin/redoubt-artifacts/release-157/acceptance/rc3"
ADB = "/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb"
PKG = "org.redoubtbrowser"
serial, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
os.environ.setdefault("LW_SMOKE_REPO", "/home/mgysin/redoubt-artifacts/release-157/repo")
spec = importlib.util.spec_from_file_location("drv", R + "/work/harness/driver.py")
drv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drv)
adb = drv.Adb(ADB, serial)
app = drv.App(adb, PKG, R + "/work")

BANNED = {"summarize": re.compile(r"summari[sz]", re.I),
          "ip-protection": re.compile(r"\bVPN\b|IP protection", re.I),
          "lens": re.compile(r"\bLens\b")}

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
       b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82")
PAGE = b"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>stripped features fixture</title></head><body style="margin:0">
<p>Redoubt stripped-features fixture. A paragraph of ordinary text, long enough to be a page.</p>
<img id="img" src="/pixel.png" style="position:fixed;left:10%;top:35%;width:80%;height:30%;background:#888">
</body></html>"""

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        body, ct = (PNG, "image/png") if self.path.startswith("/pixel.png") else (PAGE, "text/html")
        self.send_response(200); self.send_header("Content-Type", ct); self.end_headers(); self.wfile.write(body)

srv = socketserver.TCPServer(("127.0.0.1", 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
adb.run("reverse", "tcp:%d" % port, "tcp:%d" % port, check=True)
URL = "http://127.0.0.1:%d/page.html" % port

screens = []

def labels(xml):
    t = [html.unescape(x) for x in re.findall(r'\b(?:text|content-desc)="([^"]*)"', xml) if x]
    return t

def dump(tag):
    xml = drv._ui_dump(adb)
    open(os.path.join(out, tag + ".xml"), "w").write(xml)
    with open(os.path.join(out, tag + ".png"), "wb") as f:
        f.write(subprocess.run([ADB, "-s", serial, "exec-out", "screencap", "-p"], capture_output=True).stdout)
    ls = labels(xml)
    hits = {k: sorted({l for l in ls if r.search(l)}) for k, r in BANNED.items()}
    screens.append({"screen": tag, "labels": ls, "banned_hits": {k: v for k, v in hits.items() if v}})
    return xml

def bounds_of(xml, pred):
    for m in re.finditer(r'<node [^>]*>', xml):
        n = m.group(0)
        t = html.unescape((re.search(r'text="([^"]*)"', n) or [None, ""])[1])
        d = html.unescape((re.search(r'content-desc="([^"]*)"', n) or [None, ""])[1])
        if pred(t, d):
            b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', n)
            if b:
                x1, y1, x2, y2 = map(int, b.groups())
                return ((x1 + x2) // 2, (y1 + y2) // 2)
    return None

def tap(pt):
    adb.shell("input tap %d %d" % pt, timeout=60); time.sleep(2)

def back():
    adb.shell("input keyevent 4", timeout=60); time.sleep(1.5)

def scroll_all(prefix, max_pages=12):
    w, h = drv._screen_size(adb)
    prev = None
    for i in range(max_pages):
        xml = dump("%s-%02d" % (prefix, i))
        sig = tuple(labels(xml))
        if sig == prev:
            break
        prev = sig
        adb.shell("input swipe %d %d %d %d 400" % (w // 2, int(h * 0.75), w // 2, int(h * 0.3)), timeout=60)
        time.sleep(1.5)

result = {"serial": serial, "url": URL}
try:
    app.force_stop(); app.wipe()
    adb.shell("am start -a android.intent.action.VIEW -d '%s' -n %s/org.mozilla.fenix.IntentReceiverActivity"
              % (URL, PKG), timeout=90)
    time.sleep(8)
    xml, pt, acked = drv.toolbar_ready(adb, PKG, timeout=60)
    result["ubo_sheet_acknowledged"] = acked
    time.sleep(3)
    dump("00-page")

    # 1. main menu
    xml = drv._ui_dump(adb)
    mpt = bounds_of(xml, lambda t, d: re.search(r"main menu|^menu$|more options", d, re.I) is not None)
    result["menu_button"] = mpt
    if mpt:
        tap(mpt)
        scroll_all("01-main-menu", 4)
        xml = drv._ui_dump(adb)
        more = bounds_of(xml, lambda t, d: t == "More" or d.startswith("More "))
        result["more_button"] = more
        if more:
            tap(more)
            scroll_all("01b-main-menu-more", 4)
        back()

    # 2. image long-press context menu
    w, h = drv._screen_size(adb)
    adb.shell("input swipe %d %d %d %d 1500" % (w // 2, h // 2, w // 2, h // 2), timeout=60)
    time.sleep(2.5)
    dump("02-image-context-menu")
    back()

    # 3. address bar edit mode
    xml, pt, _ = drv.toolbar_ready(adb, PKG, timeout=30)
    if pt:
        tap(pt)
        time.sleep(1.5)
        dump("03-toolbar-edit")
        back(); back()

    # 4. settings root and privacy
    APK = R + "/apk/rc3/fenix-x86_64-release-throwaway.apk"
    AAPT2 = ("/home/mgysin/redoubt-artifacts/release-157/rc/librewolf-android-aar-157.0-1/gradle-home/caches/9.7.1/"
             "transforms/b6b06824b556dd67e1fb37a085c3296a/transformed/aapt2-9.4.0-15978811-linux/aapt2")
    scheme = drv.apk_deeplink_scheme(AAPT2, APK)
    result["scheme"] = scheme
    drv._deeplink(adb, PKG, scheme, "settings")
    scroll_all("04-settings")
    for i, row in enumerate(("AI controls", "Redoubt Labs")):
        drv._deeplink(adb, PKG, scheme, "settings")
        w, h = drv._screen_size(adb)
        for _ in range(6):  # the screen can come back scrolled to the end; _find_row only scrolls down
            adb.shell("input swipe %d %d %d %d 200" % (w // 2, int(h * 0.3), w // 2, int(h * 0.8)), timeout=60)
        time.sleep(1)
        xml, pt = drv._find_row(adb, row, max_scrolls=8)
        result.setdefault("rows", {})[row] = pt
        if pt:
            tap(pt)
            scroll_all("%02d-settings-%s" % (5 + i, row.lower().replace(" ", "-")))
            back()
finally:
    try:
        app.force_stop(); adb.run("reverse", "--remove", "tcp:%d" % port)
    except Exception:
        pass
    srv.shutdown()

allhits = {}
for s in screens:
    for k, v in s["banned_hits"].items():
        allhits.setdefault(k, []).append({"screen": s["screen"], "labels": v})
def seen(prefix, rx):
    return any(s["screen"].startswith(prefix) and any(re.search(rx, l) for l in s["labels"]) for s in screens)
result["positive_controls"] = {
    "main-menu shows Settings": seen("01-main-menu", r"^Settings$"),
    "context menu shows an image item": seen("02-image-context-menu", r"(?i)image"),
    "toolbar edit shows a search/URL field": seen("03-toolbar-edit", r"(?i)search|enter address|url"),
    "settings shows Search": seen("04-settings", r"^Search$"),
    "settings shows Privacy and security with HTTPS-Only": seen("04-settings", r"^HTTPS-Only Mode$"),
    "main menu More expanded": any(s["screen"].startswith("01b-main-menu-more") for s in screens),
    "AI controls screen opened": seen("05-settings-ai-controls", r"^AI controls$"),
    "Redoubt Labs screen opened": seen("06-settings-redoubt-labs", r"Labs"),
}
result["banned_hits"] = allhits
result["screens"] = screens
result["verdict"] = {"absent": not allhits, "controls_ok": all(result["positive_controls"].values())}
json.dump(result, open(os.path.join(out, "probe.json"), "w"), indent=1)
print(json.dumps({k: result[k] for k in ("positive_controls", "banned_hits", "verdict", "menu_button",
                                         "ubo_sheet_acknowledged")}, indent=1))
