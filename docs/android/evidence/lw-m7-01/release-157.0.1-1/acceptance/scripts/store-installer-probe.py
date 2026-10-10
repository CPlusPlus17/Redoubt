#!/usr/bin/env python3
"""Store-installer probe, copied unchanged from the 157.0-3 acceptance except paths (diagnostic, not a gate).

157.0-3 is the first build carrying a06577dd ("update-check: hide the check on store installs"):
UpdateCheck.isOffered asks the installer of record, and for F-Droid (and the other stores in
UpdateCheck.STORE_INSTALLERS) the Settings row is hidden and isEnabled is false whatever is stored.
That commit was tested with Robolectric only; no APK was built with it. This probe tests it on the
device, with the same parent-process request observer as update-check-probe.py.

usage: store-installer-probe.py SERIAL OUTDIR APK

  1  HAND    `adb install -r APK`, then `pm clear`. Read the installer of record. The Settings row
             must be present and OFF; tap it ON (fenix_preferences.xml must read true).
  2  STORE   `pm install -r -i org.fdroid.fdroid` of the same APK (app data kept). Installer of
             record must read org.fdroid.fdroid. The throttle file is removed. The row must be
             ABSENT; Home + launcher resume must make 0 requests to redoubtbrowser.org and must not
             create lw_update_check.xml, although the stored switch value is still true.
  3  HAND    `adb install -r APK` again (data kept). Installer of record back to the shell/package
             installer. The row must be back and ON. Observed control (as the 157.0-2 probe's): the
             switch is turned off, the app stopped, the throttle file removed, a session with the
             observer opened, the switch turned on in Settings; the next resume must GET the
             endpoint, with no Accept-Language request header.
Also records the SELinux labels of the app's processes while a tab is open (ps -A -Z).
"""
import html, importlib.util, json, os, re, subprocess, sys, time

R = "/home/mgysin/redoubt-artifacts/release-157.0.1-1"
WORK = os.environ.get("LW_ACCEPT_WORK", R + "/work")   # the API 34 session uses its own work dir
ADB = "/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb"
PKG = "org.redoubtbrowser"
STORE = "org.fdroid.fdroid"
FDROID_APK = R + "/x/fdroid/F-Droid.apk"
serial, out, apk = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
os.environ.setdefault("LW_SMOKE_REPO", R + "/repo")
spec = importlib.util.spec_from_file_location("drv", WORK + "/harness/driver.py")
drv = importlib.util.module_from_spec(spec); spec.loader.exec_module(drv)
adb = drv.Adb(ADB, serial)
app = drv.App(adb, PKG, WORK)
res = {"serial": serial, "apk": apk, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "steps": []}
n = [0]
SCH = drv.apk_deeplink_scheme(R + "/x/aapt2/aapt2", apk)
OBSERVER = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "update-check-probe.py")).read()
OBSERVER = OBSERVER.split('OBSERVER = r"""', 1)[1].split('"""', 1)[0]
READ = 'return (Cu.getGlobalForObject(Services).__redoubtUpdateProbe || {rec: null}).rec;'


def note(name, **kw):
    kw["step"] = name; kw["t"] = time.strftime("%H:%M:%S"); res["steps"].append(kw)
    print(json.dumps(kw, default=str)[:900], flush=True)


def dump(tag):
    n[0] += 1; name = "%02d-%s" % (n[0], tag)
    xml = drv._ui_dump(adb)
    open(os.path.join(out, name + ".xml"), "w").write(xml)
    with open(os.path.join(out, name + ".png"), "wb") as f:
        f.write(subprocess.run([ADB, "-s", serial, "exec-out", "screencap", "-p"], capture_output=True).stdout)
    return xml


def installer():
    s = adb.shell("dumpsys package %s | grep -iE 'installerPackageName|installInitiatingPackageName|"
                  "installOriginatingPackageName|initiatingPackageName|originatingPackageName|updateOwner|versionCode'" % PKG,
                  timeout=60)
    return s.strip()


def store_file():
    return adb.shell("su 0 sh -c 'cd /data/data/%s/shared_prefs && grep -H pref_key_lw_update_check *.xml; "
                     "echo ---; cat lw_update_check.xml 2>&1'" % PKG, timeout=60).strip()


def row():
    drv._deeplink(adb, PKG, SCH, "settings")
    xml, pt = drv._find_row(adb, "Check for updates", max_scrolls=16)
    return xml, pt, (drv._switch_after(xml, "Check for updates") if pt else None)


def labels():
    return adb.shell("ps -A -o LABEL,USER,UID,PID,NAME | grep -E 'LABEL|%s'" % re.escape(PKG), timeout=60).strip()


def resume_and_observe(tag):
    """Fresh Marionette session with the observer, then Home + launcher resume; return new records."""
    m = drv.open_session(app, "https://example.org/"); time.sleep(6)
    m.cmd("Marionette:SetContext", {"value": "chrome"})
    m.script(OBSERVER, chrome=True)
    proc = labels()
    n0 = len(m.script(READ, chrome=True))
    adb.shell("input keyevent 3", timeout=60); time.sleep(2)
    app.start_home(); time.sleep(25)
    dump(tag + "-after-resume-25s")
    recs = m.script(READ, chrome=True)[n0:]
    alive = app.alive()
    m.close()
    return recs, alive, proc


def install_hand():
    p = adb.run("install", "-r", apk, timeout=900)
    return (p.stdout + p.stderr).strip()


def install_store():
    adb.run("push", apk, "/data/local/tmp/lw-store-probe.apk", timeout=600, check=True)
    r = adb.shell("pm install -r -i %s /data/local/tmp/lw-store-probe.apk; rm -f /data/local/tmp/lw-store-probe.apk" % STORE,
                  timeout=900)
    return r.strip()


lc = None
try:
    subprocess.run([ADB, "-s", serial, "logcat", "-b", "all", "-c"])
    lc = subprocess.Popen([ADB, "-s", serial, "logcat", "-v", "threadtime"],
                          stdout=open(os.path.join(out, "probe.logcat"), "w"), stderr=subprocess.STDOUT)
    # 0 a real F-Droid client must be installed, or Android records no installer for `pm install -i`
    #   (measured on API 34: installerPackageName=null without it). F-Droid 2.0.1 from f-droid.org,
    #   the same file as the LW-M6-03 evidence (sha256 83d3fe52...3778).
    p = adb.run("install", "-r", FDROID_APK, timeout=600)
    note("0-fdroid-client", out=(p.stdout + p.stderr).strip(),
         sha256=subprocess.run(["sha256sum", FDROID_APK], capture_output=True, text=True).stdout.split()[0],
         pkg=adb.shell("dumpsys package %s | grep -E 'versionName|versionCode'" % STORE, timeout=60).strip())
    # 1 HAND
    note("1-hand-install", out=install_hand())
    app.force_stop(); app.wipe()
    note("1-installer", dumpsys=installer())
    app.start_home(); time.sleep(12)
    xml = dump("1-home"); xml, acked = drv.acknowledge_ubo_added_notice(adb, PKG, xml)
    note("1-ubo-sheet", acknowledged=acked)
    xml, pt, on = row(); dump("1-settings-row")
    note("1-row", found=bool(pt), switch_on=on)
    if not pt or on is not False:
        raise RuntimeError("hand install: row missing or not OFF by default")
    adb.shell("input tap %d %d" % drv._switch_bounds_after(xml, "Check for updates"), timeout=60); time.sleep(1.5)
    xml = dump("1-settings-row-tapped")
    res["hand_switch_on"] = drv._switch_after(xml, "Check for updates")
    note("1-switch-on", switch_on=res["hand_switch_on"], store=store_file())
    app.force_stop()
    # 2 STORE
    note("2-store-install", out=install_store())
    res["store_installer"] = installer()
    note("2-installer", dumpsys=res["store_installer"])
    adb.shell("su 0 rm -f /data/data/%s/shared_prefs/lw_update_check.xml" % PKG, timeout=60)
    note("2-store-before", store=store_file())
    xml, pt, on = row(); dump("2-settings-no-row")
    res["store_row_found"] = bool(pt)
    note("2-row", found=bool(pt), switch_on=on, rows=[l for l in re.findall(r' text="([^"]+)"', xml)][:40])
    recs, alive, proc = resume_and_observe("2")
    res["store_records"] = recs; res["store_alive"] = alive; res["process_labels_store"] = proc
    res["store_after"] = store_file()
    note("2-resume", records=len(recs), alive=alive, store=res["store_after"], process_labels=proc)
    # 3 HAND again
    app.force_stop()
    note("3-hand-reinstall", out=install_hand())
    res["hand2_installer"] = installer()
    note("3-installer", dumpsys=res["hand2_installer"])
    xml, pt, on = row(); dump("3-settings-row-back")
    res["hand2_row_found"] = bool(pt); res["hand2_switch_on"] = on
    time.sleep(8)
    # The deep link resumed HomeActivity with the switch ON and no throttle file: the check runs
    # (unobserved); lw_update_check.xml with last_run_ms is the trace.
    res["hand2_after_row"] = store_file()
    note("3-row", found=bool(pt), switch_on=on, store=res["hand2_after_row"])
    if not pt or on is not True:
        raise RuntimeError("hand reinstall: row missing or not ON")
    # Observed control, as in the 157.0-2 probe: switch OFF, stop, remove the throttle file, open a
    # session with the request observer, switch ON in Settings, then Home + launcher resume.
    adb.shell("input tap %d %d" % drv._switch_bounds_after(xml, "Check for updates"), timeout=60); time.sleep(1.5)
    note("3-switch-off-for-control", switch_on=drv._switch_after(drv._ui_dump(adb), "Check for updates"))
    app.force_stop(); time.sleep(1)
    adb.shell("su 0 rm -f /data/data/%s/shared_prefs/lw_update_check.xml" % PKG, timeout=60)
    m = drv.open_session(app, "https://example.org/"); time.sleep(6)
    m.cmd("Marionette:SetContext", {"value": "chrome"})
    m.script(OBSERVER, chrome=True)
    res["process_labels_hand2"] = labels()
    xml, pt, on = row()
    if pt and on is False:
        adb.shell("input tap %d %d" % drv._switch_bounds_after(xml, "Check for updates"), timeout=60); time.sleep(1.5)
    xml = dump("3-settings-row-on-again")
    note("3-switch-on-again", switch_on=drv._switch_after(xml, "Check for updates"), store=store_file())
    n0 = len(m.script(READ, chrome=True))
    adb.shell("input keyevent 3", timeout=60); time.sleep(2)
    app.start_home(); time.sleep(25)
    dump("3-after-resume-25s")
    recs = m.script(READ, chrome=True)[n0:]
    alive = app.alive(); m.close()
    res["hand2_records"] = recs; res["hand2_alive"] = alive
    res["hand2_after"] = store_file()
    gets = [r for r in recs if r.get("topic") == "http-on-modify-request"]
    res["hand2_request_headers"] = [r.get("requestHeaders") for r in gets]
    res["hand2_accept_language_present"] = any(k.lower() == "accept-language" for r in gets for k, _ in (r.get("requestHeaders") or []))
    note("3-resume", requests=[(r.get("method"), r.get("url")) for r in gets], alive=alive,
         accept_language=res["hand2_accept_language_present"], store=res["hand2_after"])
    res["crash_buffer"] = subprocess.run([ADB, "-s", serial, "logcat", "-d", "-b", "crash"], capture_output=True, text=True).stdout.strip()[:3000]
except Exception:
    import traceback
    res["error"] = traceback.format_exc(); print(res["error"])
finally:
    try:
        app._set_debug_app = True; app.remove_debug_config()
    except Exception as e:
        note("cleanup-error", error=str(e))
    try:
        note("cleanup-fdroid-uninstall", out=adb.run("uninstall", STORE, timeout=300).stdout.strip())
    except Exception as e:
        note("cleanup-error", error=str(e))
    if lc:
        lc.terminate(); lc.wait()
        log = open(os.path.join(out, "probe.logcat"), errors="replace").read()
        res["fatal_lines"] = [l for l in log.splitlines() if re.search(r"FATAL EXCEPTION|ANR in " + PKG, l)][:10]
        subprocess.run(["gzip", "-f", os.path.join(out, "probe.logcat")])
    json.dump(res, open(os.path.join(out, "probe.json"), "w"), indent=1, default=str)
