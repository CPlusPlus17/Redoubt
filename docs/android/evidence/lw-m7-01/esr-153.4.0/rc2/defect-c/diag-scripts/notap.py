#!/usr/bin/env python3
"""Scratch: menu flow, type into the already-focused address field WITHOUT tapping it again."""
import os, re, sys, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scen
from drv import *
from gokey_fn import ime_touch
item, retap = sys.argv[1], sys.argv[2] == "retap"
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
x = dump("url-entry")
focused = [n for n in nodes(x) if n.get("package") == PKG and n.get("class") == "android.widget.EditText" and n.get("focused") == "true"]
log("focused EditText before any tap:", len(focused))
ime_touch("after-menu")
if retap:
    f = find(x, rid="ADDRESSBAR_SEARCH_BOX"); tap(f, "url-field"); time.sleep(0.8)
sh("input text", "'" + scen.URL + "'"); sh("input keyevent 66"); log("submitted")
end = time.monotonic() + 25
while time.monotonic() < end:
    x = dump("snack")
    n = find(x, text="Review", rid="snackbar_action")
    if n is not None: break
r = ime_touch("at-snackbar")
if len(sys.argv) > 3 and sys.argv[3] == "killime":
    sh("am force-stop com.android.inputmethod.latin"); log("force-stopped IME")
    for _ in range(20):
        r2 = ime_touch("after-kill")
        if r2 is None or r2[0] != "true": break
        time.sleep(0.25)
res = scen.review("notap")
print("RESULT", item, "retap" if retap else "no-retap", "ime", r, "review", res, flush=True)
