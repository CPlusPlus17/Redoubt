#!/usr/bin/env python3
"""Scratch: IME/window state at the private snackbar (menu-driven flow)."""
import os, sys, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scen
from drv import *
scen.fresh(); scen.open_normal(); time.sleep(5)
item = sys.argv[1] if len(sys.argv) > 1 else "New private tab"
scen.open_via_menu(item)
end = time.monotonic() + 25
while time.monotonic() < end:
    x = dump("snack")
    if find(x, text="Review", rid="snackbar_action") is not None:
        break
for name, cmd in (("ime", "dumpsys input_method"), ("windows", "dumpsys window windows"), ("input", "dumpsys input")):
    open(os.path.join(OUT, name + ".txt"), "w").write(sh(cmd, check=False))
open(os.path.join(OUT, "shot.png"), "wb").write(subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True).stdout)
log("captured")
