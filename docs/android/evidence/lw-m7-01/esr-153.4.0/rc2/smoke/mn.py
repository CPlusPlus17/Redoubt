#!/usr/bin/env python3
"""Tiny Marionette helper reusing the smoke harness's own client (driver.py).
usage: mn.py [--launch URL] [--chrome] SCRIPT   -> prints JSON result
Requires GeckoView debug config at /data/local/tmp/<pkg>-geckoview-config.yaml and
am set-debug-app (release APK) -- the same door android-smoke.sh opens."""
import sys, json, subprocess, time, importlib.util, os
R="/home/mgysin/redoubt-artifacts/esr-153.4/build/rc2/runtime"
spec=importlib.util.spec_from_file_location("drv", R+"/work/harness/driver.py"); drv=importlib.util.module_from_spec(spec)
sys.argv_saved=sys.argv; spec.loader.exec_module(drv)
ADB=[os.path.expanduser("~/redoubt-artifacts/android-sdk/platform-tools/adb"),"-s","emulator-5584"]
PKG="org.redoubtbrowser"
args=sys.argv[1:]; launch=None; chrome=False; nav=None
while args and args[0].startswith("--"):
    a=args.pop(0)
    if a=="--launch": launch=args.pop(0)
    elif a=="--chrome": chrome=True
    elif a=="--navigate": nav=args.pop(0)
script=args[0]
def sh(*c): return subprocess.run(ADB+list(c),capture_output=True,text=True,timeout=120).stdout
if launch:
    sh("push",R+"/work/geckoview-config.yaml","/data/local/tmp/%s-geckoview-config.yaml"%PKG)
    sh("shell","am","set-debug-app","--persistent",PKG)
    sh("shell","am","force-stop",PKG); time.sleep(1)
    sh("shell","am start -a android.intent.action.VIEW -d '%s' -n %s/org.mozilla.fenix.IntentReceiverActivity"%(launch,PKG))
port=drv.free_port(); sh("forward","tcp:%d"%port,"tcp:2828")
deadline=time.time()+120; m=None
while time.time()<deadline:
    try:
        m=drv.Marionette(port); m.cmd("WebDriver:NewSession",{"capabilities":{"alwaysMatch":{}}}); break
    except Exception as e:
        m=None; time.sleep(3)
if not m: print(json.dumps({"error":"no marionette"})); sys.exit(2)
if nav:
    try: m.cmd("WebDriver:Navigate",{"url":nav})
    except Exception as e: print("navigate:",e)
    time.sleep(5)
if chrome: m.cmd("Marionette:SetContext",{"value":"chrome"})
r=m.cmd("WebDriver:ExecuteScript",{"script":script,"args":[]})
print(json.dumps(r,indent=1))
