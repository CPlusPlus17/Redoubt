#!/usr/bin/env python3
"""Scratch: what does one system Back do while the stuck keyboard covers the page?"""
import os, re, sys, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scen
from drv import *
from gokey_fn import ime_touch
item = sys.argv[1]
scen.fresh(); scen.open_normal(); time.sleep(5)
scen.open_via_menu(item)            # same as harness: types URL + KEYCODE_ENTER
end = time.monotonic() + 25
while time.monotonic() < end:
    x = dump("snack")
    if find(x, text="Review", rid="snackbar_action") is not None: break
before = ime_touch("before-back")
sh("input keyevent 4"); log("BACK")
time.sleep(1.5)
after = ime_touch("after-back")
x = dump("after-back")
url = [n.get("content-desc") for n in nodes(x) if "localhost:8765" in (n.get("content-desc") or "")]
log("url after back:", url, "counter:", [n.get("content-desc") for n in nodes(x) if "Tabs Open" in (n.get("content-desc") or "")])
print("RESULT", item, "before", before, "after", after, "snackbar-still", find(x, text="Review", rid="snackbar_action") is not None, flush=True)
