#!/usr/bin/env python3
"""Scratch: capture the full view hierarchy while the quiet snackbar is up (typed vs intent)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scen
from drv import *
mode = sys.argv[1]
scen.fresh()
if mode == "typed":
    dump("home"); scen.type_url(scen.URL)
else:
    scen.open_normal()
end = time.monotonic() + 25
while time.monotonic() < end:
    x = dump(mode + "-snack")
    if find(x, text="Review", rid="snackbar_action") is not None:
        break
open(os.path.join(OUT, mode + "-top.txt"), "w").write(sh("dumpsys activity top", check=False))
log("captured")
