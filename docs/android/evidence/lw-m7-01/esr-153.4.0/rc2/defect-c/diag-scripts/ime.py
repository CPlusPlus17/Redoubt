#!/usr/bin/env python3
"""Scratch: is the soft keyboard up when the quiet snackbar shows after a TYPED url?"""
import os, sys, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scen
from drv import *

def ime(label):
    s = sh("dumpsys input_method", check=False)
    open(os.path.join(OUT, label + "-ime.txt"), "w").write(s)
    keys = [l.strip() for l in s.splitlines() if any(k in l for k in ("mInputShown", "mWindowVisible", "mDecorViewVisible", "mIsInputViewShown"))]
    log(label, "IME:", keys)
    shot = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True).stdout
    open(os.path.join(OUT, label + ".png"), "wb").write(shot)

mode = sys.argv[1]
scen.fresh()
if mode == "typed-normal":
    x = dump("home")
    scen.type_url(scen.URL)
elif mode == "typed-private":
    scen.open_normal(); time.sleep(5)
    scen.open_via_menu("New private tab")
end = time.monotonic() + 25
while time.monotonic() < end:
    x = dump(mode + "-snack")
    n = find(x, text="Review", rid="snackbar_action")
    if n is not None:
        break
ime(mode + "-at-snackbar")
print("RESULT", mode, scen.review(mode))
