#!/usr/bin/env python3
"""Fresh-profile Settings list (scrolling) and the DNS over HTTPS summary. usage: settings-scan.py SERIAL LABEL OUTDIR"""
import json, os, sys, time
from ui import UI
serial, label, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
u = UI(serial)
u.sh("am", "start", "-a", "android.intent.action.VIEW", "-d", "redoubt://settings", "org.redoubtbrowser")
time.sleep(3)
for _ in range(8):
    u.sh("input", "swipe", "540", "700", "540", "1600", "300"); time.sleep(0.5)
seen = []
for i in range(12):
    u.dump(save=os.path.join(out, f"{label}-settings-{i}.xml"))
    for t in u.texts():
        if t not in seen:
            seen.append(t)
    u.sh("input", "swipe", "540", "1400", "540", "900", "500"); time.sleep(1)
doh = seen[seen.index("DNS over HTTPS") + 1] if "DNS over HTTPS" in seen else None
json.dump({"label": label, "texts": seen, "dns_over_https_summary": doh}, open(os.path.join(out, f"{label}-settings.json"), "w"), indent=1)
print("DNS over HTTPS:", doh)
