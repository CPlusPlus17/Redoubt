#!/usr/bin/env python3
"""Scratch: submit the URL with the soft keyboard's own action key instead of `input keyevent 66`."""
import os, re, sys, subprocess, time
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
phase = sys.argv[2]
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
f = find(x, rid="ADDRESSBAR_SEARCH_BOX")
tap(f, "url-field"); time.sleep(0.8)
sh("input text", "'" + scen.URL + "'")
time.sleep(1)
open(os.path.join(OUT, "kbd.png"), "wb").write(subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True).stdout)
ime_touch("keyboard-up")
if phase == "shot":
    raise SystemExit(0)
gx, gy = phase.split(",")
sh("input tap", gx, gy); log("tapped soft-keyboard action key", gx, gy)
end = time.monotonic() + 25
while time.monotonic() < end:
    x = dump("snack")
    if find(x, text="Review", rid="snackbar_action") is not None: break
ime_touch("at-snackbar")
open(os.path.join(OUT, "at-snackbar.png"), "wb").write(subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True).stdout)
print("RESULT", item, "go-key", scen.review("go"), flush=True)
