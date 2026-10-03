#!/usr/bin/env python3
"""Generic cosmetic filtering on a real https page: insert elements after load, read display. usage: SERIAL URL..."""
import importlib.util, json, sys, time
R = "/home/mgysin/redoubt-artifacts/release-157/acceptance/rc3"
spec = importlib.util.spec_from_file_location("drv", R + "/work/harness/driver.py")
drv = importlib.util.module_from_spec(spec); spec.loader.exec_module(drv)
adb = drv.Adb("/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb", sys.argv[1]); app = drv.App(adb, "org.redoubtbrowser", R + "/work")
INS = """for (const [k, v] of [['class','a-adhesion'],['class','a-dserver'],['id','AcceptCookieContainer'],['class','accept-cookies-banner'],['class','lw-control']]) {
  const d = document.createElement('div'); d.setAttribute(k, v); d.textContent = v; d.style.height = '30px'; document.body.appendChild(d); } return true;"""
READ = """return [...document.querySelectorAll('body > div')].slice(-5).map(d => [d.className || d.id, getComputedStyle(d).display]);"""
out = {}
for url in sys.argv[2:]:
    m = drv.open_session(app, url); time.sleep(8)
    m.cmd("Marionette:SetContext", {"value": "content"})
    m.script(INS); time.sleep(5)
    out[url] = m.script(READ)
    m.close()
print(json.dumps(out))
