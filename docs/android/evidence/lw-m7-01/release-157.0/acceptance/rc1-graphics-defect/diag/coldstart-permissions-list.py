#!/usr/bin/env python3
"""After a cold start, open Site controls > Canvas and WebGL permissions after DELAY
seconds and record whether the list rendered (header row present) and what the app
logged ("No listener for GeckoView:GetAllPermissions").

usage: coldstart-permissions-list.py SERIAL OUTDIR DELAY [DELAY ...]
Uses the existing profile (no wipe), so no first-run sheet. The page is example.org.
"""
import html, os, re, subprocess, sys, time
ADB = ["/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb", "-s", sys.argv[1]]
out = sys.argv[2]; os.makedirs(out, exist_ok=True)
PKG = "org.redoubtbrowser"
def sh(*a, **kw): return subprocess.run(ADB + ["shell"] + list(a), capture_output=True, text=True, timeout=60).stdout
def dump():
    sh("uiautomator", "dump", "/sdcard/cs.xml"); x = sh("cat", "/sdcard/cs.xml"); sh("rm", "-f", "/sdcard/cs.xml"); return x
def node(xml, rid=None, desc=None, text=None):
    for m in re.finditer(r'<node [^>]*>', xml):
        n = m.group(0)
        if rid and ('resource-id="%s"' % rid) not in n and ('resource-id="%s:id/%s"' % (PKG, rid)) not in n: continue
        if desc and ('content-desc="%s"' % desc) not in n: continue
        if text and text not in n: continue
        b = list(map(int, re.findall(r"\d+", re.search(r'bounds="([^"]*)"', n).group(1))))
        return ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)
results = []
for delay in map(float, sys.argv[3:]):
    sh("am", "force-stop", PKG); time.sleep(1.5)
    subprocess.run(ADB + ["logcat", "-c"]); t0 = time.time()
    sh("am", "start", "-a", "android.intent.action.VIEW", "-d", "https://example.org/", "-n", PKG + "/org.mozilla.fenix.IntentReceiverActivity")
    # open site controls as soon as the toolbar indicator exists, then wait until DELAY to tap the entry
    pt = None
    while time.time() - t0 < 30 and not pt:
        xml = dump()
        pt = node(xml, rid="mozac_browser_toolbar_tracking_protection_indicator") or node(xml, rid="mozac_browser_toolbar_site_info_indicator") or node(xml, desc="Site information")
    if not pt:
        results.append({"delay": delay, "error": "no site controls"}); continue
    subprocess.run(ADB + ["shell", "input", "tap", str(pt[0]), str(pt[1])])
    entry = None
    while time.time() - t0 < 40 and not entry:
        entry = node(dump(), rid="origin_permissions_entry")
    wait = delay - (time.time() - t0)
    if wait > 0: time.sleep(wait)
    tapped_at = round(time.time() - t0, 1)
    subprocess.run(ADB + ["shell", "input", "tap", str(entry[0]), str(entry[1])])
    time.sleep(3)
    xml = dump()
    header = "Ask for each site" in xml or "Requests for this page" in xml
    log = subprocess.run(ADB + ["logcat", "-d", "-v", "threadtime"], capture_output=True, text=True).stdout
    nl = [l for l in log.splitlines() if "No listener for GeckoView:" in l]
    open(os.path.join(out, "delay-%s.xml" % delay), "w").write(xml)
    open(os.path.join(out, "delay-%s.logcat" % delay), "w").write(log)
    r = {"delay": delay, "tapped_at_s": tapped_at, "list_rendered": header, "no_listener_lines": nl}
    results.append(r); print(r, flush=True)
    sh("input", "keyevent", "4"); sh("input", "keyevent", "4")
import json; json.dump(results, open(os.path.join(out, "results.json"), "w"), indent=1)
