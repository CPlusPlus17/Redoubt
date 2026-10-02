#!/usr/bin/env python3
"""Scratch: does the ghost keyboard appear without any quiet snackbar (plain page)?"""
import os, re, sys, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scen
from drv import *
from gokey_fn import ime_touch
item, url, submit = sys.argv[1], sys.argv[2], sys.argv[3]
scen.fresh(); scen.open_normal(); time.sleep(5)
x = dump("before-counter"); c = scen.counter(x)
sh("input swipe", c.get("cx"), c.get("cy"), c.get("cx"), c.get("cy"), "750")
end = time.monotonic() + 15
while True:
    x = dump("tab-menu")
    cands = [m for m in nodes(x) if m.get("package") == PKG and item in (m.get("content-desc"), m.get("text")) and scen.width(m) > 300]
    if cands: tap(cands[0], "menu"); break
    if time.monotonic() > end: raise SystemExit("no menu")
time.sleep(1.5)
x = dump("url-entry"); f = find(x, rid="ADDRESSBAR_SEARCH_BOX"); tap(f, "url-field"); time.sleep(0.8)
sh("input text", "'" + url + "'"); time.sleep(1)
if submit == "go":
    sh("input tap 998 1825")
else:
    sh("input keyevent 66")
log("submitted via", submit)
time.sleep(6)
r = ime_touch("6s-after-submit")
open(os.path.join(OUT, "ghost-%s-%s.png" % (submit, os.path.basename(url).split("?")[0])), "wb").write(
    subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True).stdout)
print("RESULT", item, url, submit, "ime-touchable" if r and r[0] == "true" else "clear", r, flush=True)
