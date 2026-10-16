#!/usr/bin/env python3
"""(copied from evidence/lw-m7-51/scripts/device/menu-check.py; 158.0-3: also on a named phone, page eme-probe.html) LW-M7-38 device check: open a web page, open the main menu, expand "More",
and record whether "Report broken site" is offered. usage: menu-check.py SERIAL LABEL OUTDIR PORT"""
import json, os, subprocess, sys, time
from ui import UI, ADB
serial, label, out, port = sys.argv[1:5]
assert serial.startswith("emulator-") or serial == os.environ.get("DRM_ALLOW_DEVICE")   # 158.0-3: a named phone only
os.makedirs(out, exist_ok=True)
u = UI(serial)
u.sh("input", "keyevent", "KEYCODE_WAKEUP")
u.sh("am", "start", "-a", "android.intent.action.VIEW", "-d", f"http://127.0.0.1:{port}/eme-probe.html?tag={label}-menu", "org.redoubtbrowser")
time.sleep(6)
res = {"label": label, "page": f"http://127.0.0.1:{port}/eme-probe.html"}
u.dump()
if u.find(r"^uBlock Origin was added$"):   # 158.0-3: a fresh install shows the uBO sheet first; acknowledge it
    u.tap(r"^OK$", dump=False); time.sleep(2)
u.tap(r"^More options$")
u.dump(save=os.path.join(out, f"{label}-menu.xml"))
res["menu"] = u.texts()
u.tap(r"^More( Collapsed)?$")
x = u.dump(save=os.path.join(out, f"{label}-menu-more.xml"))
res["more"] = u.texts()
with open(os.path.join(out, f"{label}-menu-more.png"), "wb") as f:
    f.write(subprocess.run([ADB, "-s", serial, "exec-out", "screencap", "-p"], capture_output=True).stdout)
res["report_broken_site_offered"] = any("Report broken site" in t for t in res["menu"] + res["more"])
res["raw_xml_mentions"] = x.count("Report broken site")
u.sh("input", "keyevent", "KEYCODE_BACK")
json.dump(res, open(os.path.join(out, f"{label}-menu.json"), "w"), indent=1)
print(json.dumps({k: res[k] for k in ("label", "report_broken_site_offered", "raw_xml_mentions")}), res["more"])
