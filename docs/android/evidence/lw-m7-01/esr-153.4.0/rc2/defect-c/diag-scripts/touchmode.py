#!/usr/bin/env python3
"""Scratch: is defect C the window leaving touch mode after a hardware key event?"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scen
from drv import *
mode = sys.argv[1]
scen.fresh()
if mode in ("E1", "E0"):
    scen.open_normal()
elif mode in ("E2", "E3", "E4"):
    dump("home"); scen.type_url(scen.URL)
end = time.monotonic() + 25
while time.monotonic() < end:
    x = dump(mode + "-snack")
    n = find(x, text="Review", rid="snackbar_action")
    if n is not None:
        break
if mode == "E1":
    sh("input keyevent 66"); log("sent KEYCODE_ENTER")
if mode == "E2":
    sh("input tap 540 1000"); log("neutral tap on page")
if mode != "E4":
    open(os.path.join(OUT, mode + "-top.txt"), "w").write(sh("dumpsys activity top", check=False))
tap(n, "review")
x, d = wait(6, label=mode + "-after", rid="origin_permissions_dialog_list")
print("RESULT", mode, "open" if d is not None else "none", flush=True)
