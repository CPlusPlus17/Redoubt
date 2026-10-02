#!/usr/bin/env python3
"""Scratch: does the stale IME touch region need the mode-switch relaunch, and does it persist?"""
import os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scen
from drv import *

def ime_touch(label):
    s = sh("dumpsys input", check=False)
    m = re.search(r"name='Window\{\w+ u0 InputMethod\}'.*?visible=(\w+).*?touchableRegion=([^,]*(?:,[^,]*)?)", s)
    r = (m.group(1), m.group(2)) if m else None
    log(label, "IME input window:", r)
    return r

item = sys.argv[1]
scen.fresh(); scen.open_normal(); time.sleep(5)
scen.open_via_menu(item)
end = time.monotonic() + 25
while time.monotonic() < end:
    x = dump("snack")
    if find(x, text="Review", rid="snackbar_action") is not None:
        break
ime_touch("at-snackbar")
r = scen.review(item.replace(" ", "-"))
time.sleep(15)
ime_touch("15s-later")
print("RESULT", item, r, flush=True)
