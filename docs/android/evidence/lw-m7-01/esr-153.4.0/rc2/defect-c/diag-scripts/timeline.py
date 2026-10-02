#!/usr/bin/env python3
"""Scratch: keyboard state timeline after submitting a URL from the tab-counter menu flow."""
import os, re, sys, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scen
from drv import *
from gokey_fn import ime_touch
item, url, submit = sys.argv[1], sys.argv[2], sys.argv[3]
scen.fresh()
if item != "home-field":
    scen.open_normal(); time.sleep(5)
    x = dump("before-counter"); c = scen.counter(x)
    sh("input swipe", c.get("cx"), c.get("cy"), c.get("cx"), c.get("cy"), "750")
    end = time.monotonic() + 15
    while True:
        x = dump("tab-menu")
        cands = [m for m in nodes(x) if m.get("package") == PKG and item in (m.get("content-desc"), m.get("text")) and scen.width(m) > 300]
        if cands: tap(cands[0], "menu"); break
        if time.monotonic() > end: raise SystemExit("no menu")
time.sleep(1.5)
x = dump("url-entry"); f = find(x, rid="ADDRESSBAR_SEARCH_BOX"); f = f if f is not None else find(x, rid="ADDRESSBAR_URL_BOX"); tap(f, "url-field"); time.sleep(0.8)
sh("input text", "'" + url + "'"); time.sleep(1)
t0 = time.monotonic()
sh("input tap 998 1825") if submit == "go" else sh("input keyevent 66")
tag = "%s-%s" % (item.replace(" ", "_"), submit)
for t in (1, 3, 6, 12, 25):
    while time.monotonic() - t0 < t: time.sleep(0.1)
    s = sh("dumpsys input_method", check=False)
    shown = re.search(r"mInputShown=(\w+)", s).group(1)
    r = ime_touch("t+%ds mInputShown=%s" % (t, shown))
    open(os.path.join(OUT, "%s-t%02d.png" % (tag, t)), "wb").write(subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True).stdout)
