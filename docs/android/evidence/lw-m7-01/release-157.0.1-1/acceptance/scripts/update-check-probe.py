#!/usr/bin/env python3
"""Update-check probe for the 157.0.1-1 acceptance (diagnostic, not a gate). Copied from the 158.0-1 Beta 1
acceptance with paths changed; the live endpoint serves the owner-signed 157.0-3 document, which is
OLDER than 157.0.1-1, so the expected outcome is "up to date": no offer, no dialog.

Run 2 (CI run 37248744119) changes, against the copy committed with the rejected run:
paths; the local endpoint's host port (8443 was taken on this host, so the first local run
reached no server: see the README) and a check that the server is up; the switch's stored value is read from EVERY shared_prefs file (the fix stores it
in fenix_preferences.xml only); and, in live mode, an OFF half after the ON half: the
switch is turned off in Settings, the app is stopped, the 24 h throttle file is removed,
and a relaunch plus resume must leave no request and no new lw_update_check.xml; then a
control turns the switch back on and the next resume must request again.

Run on the acceptance emulator with the candidate already installed. It reuses the
committed harness's own client (work/harness/driver.py, written by android-smoke.sh)
and Marionette door, and it complements `--check-update-privacy`, which sees only
host names in the packet capture. Here an observer inside Gecko's parent process
records the update check's requests themselves: the full URL, the method, every
request header, the load flags and the response status. TLS hides all of that from
the capture.

usage: update-check-probe.py SERIAL OUTDIR MODE [DOCDIR]

MODE
  live      the real endpoint (https://redoubtbrowser.org/update/android/latest.json),
            which answers 404 until the document is published. Expected: one GET of
            exactly that URL, no identifier, 404, no .sig request, no dialog, no crash.
  local     a LOCAL copy served from DOCDIR by update-endpoint-server.py (throwaway CA,
            certificate for redoubtbrowser.org), reached through `adb reverse tcp:443`
            and Gecko's network.dns.localDomains. DOCDIR holds a document that WOULD offer
            an update (version_code above the candidate's) with a signature that is not
            the owner's. Expected: both files fetched, no dialog, and the update check's
            SharedPreferences gain last_run_ms but never last_offered_version (written
            only for a verified UpdateAvailable).

Every run starts from a fresh profile (pm clear). The switch is turned on through
the real Settings UI; the check then runs on the next HomeActivity.onResume (Home
key, then the launcher intent), exactly as for a user.
"""
import html, importlib.util, json, os, re, subprocess, sys, time

R = "/home/mgysin/redoubt-artifacts/release-157.0.1-1"
ADB = "/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb"
PKG = "org.redoubtbrowser"
ENDPOINT = "https://redoubtbrowser.org/update/android/latest.json"
TLS = R + "/x/tls"
SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "update-endpoint-server.py")
LOCAL_PORT = int(os.environ.get("LW_UPDATE_PROBE_PORT", "28443"))   # run 1 used 8443, which is taken on this host
serial, out, mode = sys.argv[1], sys.argv[2], sys.argv[3]
docdir = sys.argv[4] if len(sys.argv) > 4 else None
os.makedirs(out, exist_ok=True)
os.environ.setdefault("LW_SMOKE_REPO", R + "/repo")

spec = importlib.util.spec_from_file_location("drv", R + "/work/harness/driver.py")
drv = importlib.util.module_from_spec(spec); spec.loader.exec_module(drv)
adb = drv.Adb(ADB, serial)
app = drv.App(adb, PKG, R + "/work")
res = {"mode": mode, "serial": serial, "endpoint_compiled_in": ENDPOINT,
       "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "steps": []}
n = [0]


def note(name, **kw):
    kw["step"] = name; kw["t"] = time.strftime("%H:%M:%S"); res["steps"].append(kw)
    print(json.dumps(kw, default=str)[:700], flush=True)


def dump(tag):
    n[0] += 1; name = "%02d-%s" % (n[0], tag)
    xml = drv._ui_dump(adb)
    open(os.path.join(out, name + ".xml"), "w").write(xml)
    with open(os.path.join(out, name + ".png"), "wb") as f:
        f.write(subprocess.run([ADB, "-s", serial, "exec-out", "screencap", "-p"], capture_output=True).stdout)
    return xml


def labels(xml):
    return [html.unescape(x) for x in re.findall(r'\b(?:text|content-desc)="([^"]*)"', xml) if x.strip()]


def update_dialog(xml):
    ls = labels(xml)
    return {"alert_panel": bool(re.search(r'resource-id="android:id/(alertTitle|parentPanel)"', xml)),
            "update_labels": [l for l in ls if re.search(r"is available|Open download page|newer version", l, re.I)]}


def uc_prefs():
    return adb.shell("su 0 sh -c 'cat /data/data/%s/shared_prefs/lw_update_check.xml 2>&1'" % PKG, timeout=60).strip()


def switch_store():
    """Where the switch value is stored: every shared_prefs file that names the key."""
    return adb.shell("su 0 sh -c 'cd /data/data/%s/shared_prefs && ls && grep -H pref_key_lw_update_check *.xml'" % PKG,
                     timeout=60).strip()


def tap_switch(want):
    sch = drv.apk_deeplink_scheme(R + "/x/aapt2/aapt2", R + "/apk/fenix-x86_64-157.0.1-1-throwaway.apk")
    drv._deeplink(adb, PKG, sch, "settings")
    xml, pt = drv._find_row(adb, "Check for updates", max_scrolls=16)
    before = drv._switch_after(xml, "Check for updates") if pt else None
    if pt and before != want:
        adb.shell("input tap %d %d" % drv._switch_bounds_after(xml, "Check for updates"), timeout=60); time.sleep(1.5)
        xml = drv._ui_dump(adb)
    return before, drv._switch_after(xml, "Check for updates") if pt else None


OBSERVER = r"""
const KEY = "__redoubtUpdateProbe";
const G = Cu.getGlobalForObject(Services);   // a module global that outlives one script call
if (!G[KEY]) {
  const rec = [];
  const want = ch => /redoubtbrowser\.org/i.test(ch.URI.spec);
  const obs = {
    observe(subject, topic) {
      try {
        const ch = subject.QueryInterface(Ci.nsIHttpChannel);
        if (!want(ch)) return;
        const e = {topic, t: Date.now(), url: ch.URI.spec, method: ch.requestMethod};
        if (topic === "http-on-modify-request" || topic === "http-on-before-connect") {
          const h = []; ch.visitRequestHeaders({visitHeader(k, v) { h.push([k, v]); }});
          e.requestHeaders = h;
          e.loadFlags = ch.loadFlags;
          e.LOAD_ANONYMOUS = !!(ch.loadFlags & Ci.nsIRequest.LOAD_ANONYMOUS);
          e.LOAD_BYPASS_CACHE = !!(ch.loadFlags & Ci.nsIRequest.LOAD_BYPASS_CACHE);
          e.INHIBIT_CACHING = !!(ch.loadFlags & Ci.nsIRequest.INHIBIT_CACHING);
          try { e.privateBrowsingId = ch.loadInfo.originAttributes.privateBrowsingId; } catch (x) {}
          try { e.redirectionLimit = ch.redirectionLimit; } catch (x) {}
          try { e.referrer = ch.referrerInfo ? String(ch.referrerInfo.originalReferrer && ch.referrerInfo.originalReferrer.spec) : null; } catch (x) {}
        } else {
          try { e.status = ch.responseStatus; } catch (x) { e.status = "n/a"; }
          const h = []; try { ch.visitResponseHeaders({visitHeader(k, v) { h.push([k, v]); }}); } catch (x) {}
          e.responseHeaders = h;
        }
        rec.push(e);
      } catch (err) { rec.push({topic, error: String(err)}); }
    }
  };
  for (const t of ["http-on-modify-request", "http-on-before-connect", "http-on-examine-response",
                   "http-on-examine-cached-response", "http-on-failed-opening-request"]) {
    Services.obs.addObserver(obs, t);
  }
  G[KEY] = {rec, obs};
}
return true;
"""

READ = 'return (Cu.getGlobalForObject(Services).__redoubtUpdateProbe || {rec: null}).rec;'

server = None
lc = None
m = None
try:
    if mode == "local":
        open(os.path.join(out, "server-requests.jsonl"), "w").close()
        server = subprocess.Popen([sys.executable, SERVER, str(LOCAL_PORT), TLS + "/leaf.pem", TLS + "/leaf.key", docdir,
                                   os.path.join(out, "server-requests.jsonl")],
                                  stdout=open(os.path.join(out, "server.out"), "w"), stderr=subprocess.STDOUT)
        time.sleep(1.5)
        if server.poll() is not None:
            raise RuntimeError("local endpoint server exited: " + open(os.path.join(out, "server.out")).read()[-400:])
        r = subprocess.run([ADB, "-s", serial, "root"], capture_output=True, text=True, timeout=120)
        note("adb-root", out=(r.stdout + r.stderr).strip())
        time.sleep(4)
        subprocess.run([ADB, "-s", serial, "wait-for-device"], timeout=120)
        r = subprocess.run([ADB, "-s", serial, "reverse", "tcp:443", "tcp:%d" % LOCAL_PORT], capture_output=True, text=True, timeout=60)
        note("adb-reverse", rc=r.returncode, out=(r.stdout + r.stderr).strip(),
             list=subprocess.run([ADB, "-s", serial, "reverse", "--list"], capture_output=True, text=True).stdout.strip())
        note("served-documents", files={f: open(os.path.join(docdir, f), "rb").read().decode("utf-8", "replace")
                                        for f in sorted(os.listdir(docdir))})

    subprocess.run([ADB, "-s", serial, "logcat", "-b", "all", "-c"])
    lc = subprocess.Popen([ADB, "-s", serial, "logcat", "-v", "threadtime"],
                          stdout=open(os.path.join(out, "probe.logcat"), "w"), stderr=subprocess.STDOUT)
    app.force_stop(); app.wipe()
    note("fresh-profile", installed=adb.shell("pm path %s" % PKG, timeout=60).strip(),
         version=adb.shell("dumpsys package %s | grep -E 'versionCode|versionName'" % PKG, timeout=60).strip())

    m = drv.open_session(app, "https://example.org/"); time.sleep(6)
    m.cmd("Marionette:SetContext", {"value": "chrome"})
    note("observer", installed=m.script(OBSERVER, chrome=True))
    if mode == "local":
        ca = open(TLS + "/ca.der.b64").read().strip()
        r = m.script(r"""
          const db = Cc["@mozilla.org/security/x509certdb;1"].getService(Ci.nsIX509CertDB);
          const c = db.addCertFromBase64(arguments[0], "C,,");
          Services.prefs.setCharPref("network.dns.localDomains", "redoubtbrowser.org");
          Services.dns.clearCache(true);
          return {ca: c.subjectName, sha256: c.sha256Fingerprint,
                  localDomains: Services.prefs.getCharPref("network.dns.localDomains")};""", [ca], chrome=True)
        note("local-endpoint-wiring", **r)
    note("prefs-before-switch", lw_update_check_xml=uc_prefs())

    # The switch, through the UI, like a user.
    xml0 = dump("home-or-tab")
    xml, acked = drv.acknowledge_ubo_added_notice(adb, PKG, xml0)
    sch = drv.apk_deeplink_scheme(R + "/x/aapt2/aapt2", R + "/apk/fenix-x86_64-157.0.1-1-throwaway.apk")
    drv._deeplink(adb, PKG, sch, "settings")
    xml, pt = drv._find_row(adb, "Check for updates", max_scrolls=16)
    before = drv._switch_after(xml, "Check for updates") if pt else None
    dump("settings-row-before")
    i = xml.find('text="Check for updates"')
    summary = re.search(r' text="([^"]+)"', xml[i + 30:]).group(1) if i >= 0 else None
    note("row", found=pt, switch_on=before, summary=html.unescape(summary) if summary else None)
    if not pt or before is not False:
        raise RuntimeError("row missing or not OFF by default")
    adb.shell("input tap %d %d" % drv._switch_bounds_after(xml, "Check for updates"), timeout=60); time.sleep(1.5)
    xml = dump("settings-row-after-tap")
    after = drv._switch_after(xml, "Check for updates")
    note("switch-tapped", switch_on=after, prefs_now=uc_prefs(), switch_store=switch_store())
    if not after:
        raise RuntimeError("switch did not turn on")
    note("observer-before-resume", records=m.script(READ, chrome=True))

    # Next HomeActivity.onResume runs the check: Home key, then the launcher intent.
    adb.shell("input keyevent 3", timeout=60); time.sleep(2)
    t0 = time.time()
    app.start_home()
    time.sleep(25)
    xml = dump("after-resume-25s")
    note("after-resume", alive=app.alive(), dialog=update_dialog(xml), labels=[l for l in labels(xml) if len(l) < 90][:25])
    recs = m.script(READ, chrome=True)
    note("observer-records", records=recs)
    time.sleep(20)
    xml = dump("after-resume-45s")
    res["dialog_45s"] = update_dialog(xml)
    res["alive_45s"] = app.alive()
    res["records"] = m.script(READ, chrome=True)
    res["lw_update_check_xml"] = uc_prefs()
    res["switch_store_after_on"] = switch_store()
    if mode == "local":
        res["server_requests"] = [json.loads(l) for l in open(os.path.join(out, "server-requests.jsonl")) if l.strip()]
    note("final", alive=res["alive_45s"], dialog=res["dialog_45s"], prefs=res["lw_update_check_xml"])
    # Second resume inside the 24 h window: must not fetch again.
    adb.shell("input keyevent 3", timeout=60); time.sleep(2)
    n_before = len(res["records"])
    app.start_home(); time.sleep(12)
    rec2 = m.script(READ, chrome=True)
    res["second_resume_new_records"] = rec2[n_before:]
    note("second-resume", new_records=len(rec2) - n_before)
    if mode == "live":
        # OFF half: switch off in Settings, stop the app, remove the throttle file, relaunch, resume.
        b, a = tap_switch(False)
        xml = dump("settings-row-switched-off")
        res["off_switch"] = {"before": b, "after": a, "switch_store": switch_store()}
        note("switch-off", **res["off_switch"])
        if a is not False:
            raise RuntimeError("switch did not turn off")
        m.close(); m = None
        app.force_stop(); time.sleep(1)
        adb.shell("su 0 rm -f /data/data/%s/shared_prefs/lw_update_check.xml" % PKG, timeout=60)
        note("throttle-file-removed", lw_update_check_xml=uc_prefs())
        m = drv.open_session(app, "https://example.org/"); time.sleep(6)
        m.cmd("Marionette:SetContext", {"value": "chrome"})
        note("observer-off", installed=m.script(OBSERVER, chrome=True))
        adb.shell("input keyevent 3", timeout=60); time.sleep(2)
        app.start_home(); time.sleep(25)
        dump("off-after-resume-25s")
        res["off_records"] = m.script(READ, chrome=True)
        res["off_lw_update_check_xml"] = uc_prefs()
        res["off_alive"] = app.alive()
        note("off-result", records=len(res["off_records"]), lw_update_check_xml=res["off_lw_update_check_xml"], alive=res["off_alive"])
        # Control: switch back on; the throttle file is gone, so the next resume must request again.
        b, a = tap_switch(True)
        res["control_switch"] = {"before": b, "after": a, "switch_store": switch_store()}
        note("control-switch-on", **res["control_switch"])
        n0 = len(m.script(READ, chrome=True))
        adb.shell("input keyevent 3", timeout=60); time.sleep(2)
        app.start_home(); time.sleep(25)
        dump("control-after-resume-25s")
        rc = m.script(READ, chrome=True)
        res["control_new_records"] = rc[n0:]
        res["control_lw_update_check_xml"] = uc_prefs()
        res["control_alive"] = app.alive()
        note("control-result", new_records=len(rc) - n0, lw_update_check_xml=res["control_lw_update_check_xml"])
    res["crash_buffer"] = subprocess.run([ADB, "-s", serial, "logcat", "-d", "-b", "crash"], capture_output=True, text=True).stdout.strip()[:3000]
finally:
    try:
        if m:
            m.close()
    except Exception:
        pass
    try:
        app.remove_debug_config(); adb.shell("am clear-debug-app", timeout=60)
    except Exception as e:
        note("cleanup-error", error=str(e))
    if lc:
        lc.terminate(); lc.wait()
        log = open(os.path.join(out, "probe.logcat"), errors="replace").read()
        res["fatal_lines"] = [l for l in log.splitlines() if re.search(r"FATAL EXCEPTION|ANR in " + PKG, l)][:10]
        res["update_log_lines"] = [l[:300] for l in log.splitlines() if re.search(r"UpdateCheck|update check", l, re.I)][:40]
        subprocess.run(["gzip", "-f", os.path.join(out, "probe.logcat")])
    if mode == "local":
        subprocess.run([ADB, "-s", serial, "reverse", "--remove", "tcp:443"], capture_output=True)
        r = subprocess.run([ADB, "-s", serial, "unroot"], capture_output=True, text=True, timeout=120)
        time.sleep(4); subprocess.run([ADB, "-s", serial, "wait-for-device"], timeout=120)
        res["adb_unroot"] = (r.stdout + r.stderr).strip()
        if server:
            server.terminate(); server.wait()
    json.dump(res, open(os.path.join(out, "probe.json"), "w"), indent=1, default=str)
