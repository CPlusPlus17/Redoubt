#!/usr/bin/env python3
"""about:config CSP probe (diagnostic, not a gate).  Run AFTER `--check-aboutconfig`,
on the same emulator, with the rc2 APK already installed by the harness.

It reuses the committed harness's own client (work/harness/driver.py, which
android-smoke.sh writes from itself on every run) and:

  1. wipes the app (fresh profile) and opens a Marionette session the harness's way;
  2. POSITIVE CONTROL A: reports a marker error through the console service, to show
     whether this release build forwards console errors to logcat at all;
  3. POSITIVE CONTROL B: provokes a real script-src-attr CSP violation in a web page
     (an inline handler under `script-src 'none'`), to show the console query and the
     logcat grep can see exactly the class of error being looked for;
  4. opens about:config, waits for a populated list, drives the page's own filter box,
     and toggles a pref it created (the handlers that 153.4's baseline CSP blocked);
  5. reads every console message, and the whole logcat stream, and counts CSP /
     script-src-attr errors whose source is about:config.

usage: aboutconfig-csp-probe.py SERIAL OUTDIR
"""
import importlib.util, json, os, subprocess, sys, time

R = "/home/mgysin/redoubt-artifacts/esr-153.4/build/rc2/final/runtime"
ADB = "/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb"
PKG = "org.redoubtbrowser"
serial, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)

spec = importlib.util.spec_from_file_location("drv", R + "/work/harness/driver.py")
drv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drv)

adb = drv.Adb(ADB, serial)
app = drv.App(adb, PKG, R + "/work")
MARK = "REDOUBT-CSP-PROBE-MARKER-%d" % int(time.time())
CONTROL_PAGE = "https://example.org/"
result = {"marker": MARK, "serial": serial}

lc_path = os.path.join(out, "probe.logcat")
lc = subprocess.Popen([ADB, "-s", serial, "logcat", "-v", "threadtime"],
                      stdout=open(lc_path, "w"), stderr=subprocess.STDOUT)
m = None
try:
    app.force_stop()
    app.wipe()
    result["installed_apk"] = adb.shell("pm path %s" % PKG, timeout=60).strip()
    m = drv.open_session(app, CONTROL_PAGE)
    for _ in range(120):
        snap = m.script('return {url: location.href, ready: document.readyState};')
        if snap and snap.get("url", "").startswith(CONTROL_PAGE) and snap.get("ready") == "complete":
            break
        time.sleep(0.5)
    result["control_page"] = snap

    # A: console -> logcat forwarding
    m.script('Cu.reportError(arguments[0]); return true;', [MARK], chrome=True)

    # B: a real script-src-attr violation in content
    m.cmd("Marionette:SetContext", {"value": "content"})
    m.script(r'''
      const f = document.createElement("iframe");
      f.srcdoc = "<meta http-equiv=\"Content-Security-Policy\" content=\"script-src 'none'\">" +
                 "<img src=\"data:,x\" onerror=\"window.cspProbeRan=1\">";
      document.body.appendChild(f); return true;''')
    time.sleep(3)

    # about:config, driven the way the harness drives it
    name = "librewolf.smoke.cspprobe.%d" % int(time.time())
    m.script('Services.prefs.setBoolPref(arguments[0], false); return true;', [name], chrome=True)
    m.cmd("Marionette:SetContext", {"value": "content"})
    m.cmd("WebDriver:SetTimeouts", {"script": 60000, "pageLoad": 45000})
    m.cmd("WebDriver:Navigate", {"url": "about:config"})
    result["page"] = drv.probe_aboutconfig_page(m)
    result["filter"] = drv.probe_aboutconfig_readonly(m, drv.JS_ABOUTCONFIG_FILTER, [name])
    result["toggle"] = m.script(r'''
      const li = document.querySelector('#prefs-container .pref-item[name="' + arguments[0] + '"]');
      li.querySelector(".pref-button.toggle").click();
      const f = document.getElementById("filter-input"); f.focus(); f.blur();
      return true;''', [name])
    time.sleep(2)
    result["pref_after_toggle"] = m.script(
        'return Services.prefs.getBoolPref(arguments[0], null);', [name], chrome=True)
    m.script('Services.prefs.clearUserPref(arguments[0]); return true;', [name], chrome=True)
    time.sleep(2)

    msgs = m.script(r'''
      return Services.console.getMessageArray().map(x => {
        let o = {message: String(x.message || "")};
        try { const e = x.QueryInterface(Ci.nsIScriptError);
              o.errorMessage = e.errorMessage; o.sourceName = e.sourceName;
              o.category = e.category; o.flags = e.flags; } catch (_) {}
        return o; });''', chrome=True)
    result["console_message_count"] = len(msgs)
    def is_csp(x):
        t = (x.get("errorMessage") or x["message"])
        return "Content-Security-Policy" in t or "script-src-attr" in t or x.get("category") == "CSP"
    csp = [x for x in msgs if is_csp(x)]
    result["console_csp_all"] = csp
    result["console_csp_about_config"] = [x for x in csp if "about:config" in
                                          ((x.get("sourceName") or "") + x["message"])]
    result["console_csp_control"] = [x for x in csp if "about:config" not in
                                     ((x.get("sourceName") or "") + x["message"])]
    result["console_marker_seen"] = any(MARK in x["message"] for x in msgs)
finally:
    if m:
        try: m.close()
        except Exception: pass
    try:
        app.remove_debug_config()
        adb.shell("am clear-debug-app", timeout=60)
        app.force_stop()
    except Exception:
        pass
    time.sleep(2)
    lc.terminate(); lc.wait()

log = open(lc_path, errors="replace").read().splitlines()
result["logcat_lines"] = len(log)
result["logcat_marker_lines"] = [l for l in log if MARK in l]
result["logcat_csp_lines"] = [l for l in log if "Content-Security-Policy" in l or "script-src-attr" in l]
result["logcat_csp_about_config_lines"] = [l for l in result["logcat_csp_lines"] if "about:config" in l]
result["verdict"] = {
    "about_config_loaded": result.get("page", {}).get("rows", 0) >= 20,
    "toggle_worked": result.get("pref_after_toggle") is True,
    "console_control_csp_seen": bool(result.get("console_csp_control")),
    "console_about_config_csp_errors": len(result.get("console_csp_about_config", [])),
    "logcat_forwards_console": bool(result["logcat_marker_lines"]),
    "logcat_control_csp_seen": bool(result["logcat_csp_lines"]) and
                               not result["logcat_csp_about_config_lines"],
    "logcat_about_config_csp_lines": len(result["logcat_csp_about_config_lines"]),
}
json.dump(result, open(os.path.join(out, "probe.json"), "w"), indent=1)
print(json.dumps(result["verdict"], indent=1))
