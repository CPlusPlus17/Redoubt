#!/usr/bin/env python3
"""LW-M7-41 on a device: the one-time uBO cookie-list migration (diagnostic probe, not a gate).

usage: migration-test.py SERIAL OUTDIR STEP

Reuses the committed harness's own client (work/harness/driver.py, written by
scripts/android-smoke.sh) and its Marionette door (GeckoView debug config +
`am set-debug-app`, exactly as the harness opens it). Every app start in this
script is a cold start: open_session() force-stops the app and starts it on a URL.

Steps (run in this order; each writes OUTDIR/<step>.json, NN-*.png and a logcat):
  s1-beta4-offline   uninstall; install Beta 4 rc3 (throwaway); airplane ON before the
                     first launch; state after 90 s; airplane OFF; Beta 4 online cold
                     start; state again (both lists still unselected).
  s1-upgrade         `adb install -r` the candidate (no -d, no uninstall); first cold
                     start online; state at ~15 s; uBO's own Filter lists pane (uBO's
                     in-memory selection); cookie probe on example.org until both
                     rules apply and the fetch is blocked (<= 300 s); state again.
  s1-optout          untick both lists in uBO's Filter lists pane + Apply; state.
  s1-restart1/2      cold start; state + pane + cookie probe (must stay OFF).
  s1-reinstall       `adb install -r` of the same candidate again; cold start; same.
  s2-beta3           uninstall; install Beta 3 (throwaway); online first run; tick
                     "Dan Pollock's hosts file" + Apply; colorBlindFriendly ON in
                     settings.html; full uBO storage dump.
  s2-upgrade         `adb install -r` candidate; cold start; full dump; cookie probe.
  s3-fresh           uninstall; install candidate; online first run; state when uBO
                     has written its first selection; then a second cold start.
  s5-fresh-offline   (extra) uninstall; install candidate; airplane ON first run;
                     state; airplane OFF; cold start; state + cookie probe.
"""
import hashlib, http.server, importlib.util, json, os, re, socketserver, subprocess, sys, threading, time

A = "/home/mgysin/redoubt-artifacts/beta5/accept"
ADB = "/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb"
PKG = "org.redoubtbrowser"
UBO = "uBlock0@raymondhill.net"
PREF = "librewolf.uBO.cookieListsMigrated"
SITE = "https://example.org/"
COOKIE = ("fanboy-cookiemonster", "ublock-cookies-easylist")
APK = {
    "beta3": A + "/apk/beta3/fenix-x86_64-release-throwaway.apk",
    "beta4": A + "/apk/beta4-rc3/fenix-x86_64-release-throwaway.apk",
    "cand": A + "/apk/candidate/fenix-x86_64-release-throwaway.apk",
}
serial, out, step = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
os.environ.setdefault("LW_SMOKE_REPO", "/home/mgysin/redoubt-artifacts/beta5/repo")
spec = importlib.util.spec_from_file_location("drv", A + "/work/harness/driver.py")
drv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drv)
adb = drv.Adb(ADB, serial)
app = drv.App(adb, PKG, A + "/work")

res = {"step": step, "serial": serial, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
       "events": []}
shotn = [0]


def note(name, **kw):
    kw["event"] = name
    kw["t_utc"] = time.strftime("%H:%M:%S", time.gmtime())
    res["events"].append(kw)
    print(json.dumps(kw, default=str)[:900], flush=True)


def shot(tag):
    shotn[0] += 1
    p = os.path.join(out, "%s-%02d-%s.png" % (step, shotn[0], tag))
    with open(p, "wb") as f:
        f.write(subprocess.run([ADB, "-s", serial, "exec-out", "screencap", "-p"], capture_output=True).stdout)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def pkginfo():
    return adb.shell("dumpsys package %s | grep -E 'versionCode|versionName|firstInstallTime|lastUpdateTime'" % PKG,
                     timeout=60).strip()


def install(which, replace):
    apk = APK[which]
    if not replace:
        adb.run("uninstall", PKG, timeout=300)
        p = adb.run("install", apk, timeout=900)
        cmd = "adb install " + apk
    else:
        p = adb.run("install", "-r", apk, timeout=900)
        cmd = "adb install -r " + apk
    note("install", which=which, cmd=cmd, apk_sha256=sha(apk), stdout=p.stdout.strip(), stderr=p.stderr.strip(),
         pkg=pkginfo())
    if "Success" not in p.stdout:
        raise RuntimeError("install failed")
    app.uid = None
    adb.run("logcat", "-b", "crash", "-c", timeout=60)


def airplane(on):
    adb.shell("cmd connectivity airplane-mode %s" % ("enable" if on else "disable"), timeout=60)
    time.sleep(5 if on else 20)
    return adb.shell("settings get global airplane_mode_on", timeout=30).strip()


# A loopback page to sit on while offline (uBO applies no filtering there; it is only a window).
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<!doctype html><title>parking</title><h1>parking</h1>")


srv = socketserver.TCPServer(("127.0.0.1", 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
adb.run("reverse", "tcp:%d" % port, "tcp:%d" % port, check=True)
PARK = "http://127.0.0.1:%d/park" % port

JS_STATE = r"""
return (async () => {
  const id = arguments[0], prefName = arguments[1];
  const r = {};
  const pt = Services.prefs.getPrefType(prefName);
  r.pref = {type: pt, hasUserValue: Services.prefs.prefHasUserValue(prefName),
            value: pt === Services.prefs.PREF_BOOL ? Services.prefs.getBoolPref(prefName) : null,
            locked: Services.prefs.prefIsLocked(prefName)};
  r.appinfo = {version: Services.appinfo.version, buildID: Services.appinfo.appBuildID};
  r.idbBackendPref = Services.prefs.getBoolPref("extensions.webextensions.ExtensionStorageIDB.enabled", null);
  r.bootstrapPref = Services.prefs.getStringPref("librewolf.uBO.assetsBootstrapLocation", "<unset>");
  const {AddonManager} = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
  const a = await AddonManager.getAddonByID(id);
  r.addon = a ? {version: a.version, isActive: a.isActive, userDisabled: a.userDisabled, signedState: a.signedState} : null;
  const p = WebExtensionPolicy.getByID(id);
  r.policyActive = !!(p && p.active);
  if (p) {
    r.hostname = p.mozExtensionHostname;
    try {
      const {ExtensionStorageIDB} = ChromeUtils.importESModule("resource://gre/modules/ExtensionStorageIDB.sys.mjs");
      const db = await ExtensionStorageIDB.open(ExtensionStorageIDB.getStoragePrincipal(p.extension));
      const all = await db.get(null);
      db.close();
      r.selectedFilterLists = all.selectedFilterLists ?? null;
      r.keys = {};
      r.small = {};
      for (const k of Object.keys(all).sort()) {
        const s = JSON.stringify(all[k]);
        r.keys[k] = {bytes: s ? s.length : 0};
        if (s && s.length <= 20000) r.small[k] = all[k];
        else r.keys[k].head = s ? s.slice(0, 200) : s;
      }
      r.keyDigests = {};
      for (const k of Object.keys(all).sort()) {
        const s = JSON.stringify(all[k]) || "";
        const h = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
        r.keyDigests[k] = Array.from(new Uint8Array(h)).map(b => b.toString(16).padStart(2, "0")).join("");
      }
    } catch (e) { r.idbError = String(e); }
  }
  return r;
})();
"""

JS_PANE = r"""
const keys = arguments[0];
const entry = k => { const e = document.querySelector('.listEntry[data-key="' + k + '"]'); if (!e) return null;
  const cb = e.querySelector('input[type="checkbox"]');
  return {checked: cb ? cb.checked : null, classes: e.className}; };
const all = [...document.querySelectorAll('.listEntry[data-key]')];
return {entries: all.length,
        ticked: all.filter(e => { const c = e.querySelector(':scope > .detailbar input[type="checkbox"], input[type="checkbox"]'); return c && c.checked; }).map(e => e.dataset.key),
        cookie: Object.fromEntries(keys.map(k => [k, entry(k)])),
        applyDisabled: (document.querySelector('#buttonApply') || {}).className};
"""

JS_UNTICK = r"""
const keys = arguments[0]; const r = {};
for (const k of keys) {
  const e = document.querySelector('.listEntry[data-key="' + k + '"] input[type="checkbox"]');
  if (!e) { r[k] = 'missing'; continue; }
  const was = e.checked; if (was) e.click(); r[k] = {was, now: e.checked};
}
const apply = document.querySelector('#buttonApply');
r.applyClassBefore = apply ? apply.className : null;
if (apply) apply.click();
return r;
"""

JS_PROBE = r"""
const done = arguments[arguments.length - 1];
for (const [k, v] of [['id', 'AcceptCookieContainer'], ['class', 'accept-cookies-banner'], ['class', 'lw-control']]) {
  const d = document.createElement('div'); d.setAttribute(k, v); d.textContent = 'redoubt probe ' + v;
  d.style.height = '30px'; d.dataset.lwProbe = '1'; document.body.appendChild(d);
}
const t0 = Date.now();
fetch('https://cdn.cookie-script.com/redoubt-probe-' + t0 + '.js', {mode: 'no-cors', cache: 'no-store'})
  .then(() => 'resolved', e => 'rejected: ' + e)
  .then(fetchResult => setTimeout(() => {
    const st = s => { const e = document.querySelector('[data-lw-probe]' + s); return e ? getComputedStyle(e).display : null; };
    done({url: location.href, fetch: fetchResult, fetchMs: Date.now() - t0,
          id_rule: st('#AcceptCookieContainer'), class_rule: st('.accept-cookies-banner'), control: st('.lw-control')});
  }, 2500));
"""


def blocked(s):
    return bool(s) and s.get("id_rule") == "none" and s.get("class_rule") == "none" \
        and s.get("control") not in (None, "none") and str(s.get("fetch", "")).startswith("rejected")


def unblocked(s):
    return bool(s) and s.get("id_rule") not in (None, "none") and s.get("class_rule") not in (None, "none") \
        and s.get("fetch") == "resolved"


def probe_site(m):
    m.cmd("Marionette:SetContext", {"value": "content"})
    try:
        m.cmd("WebDriver:Navigate", {"url": SITE})
        time.sleep(2)
        return m.async_script(JS_PROBE)
    except Exception as e:
        return {"error": str(e)}


def poll(m, want, timeout):
    t0 = time.time(); s = None; n = 0
    while time.time() - t0 < timeout:
        s = probe_site(m); n += 1
        if want(s):
            return {"reached": True, "seconds": round(time.time() - t0, 1), "loads": n, "state": s}
        time.sleep(4)
    return {"reached": False, "seconds": round(time.time() - t0, 1), "loads": n, "state": s}


def state(m, tag):
    st = m.script(JS_STATE, [UBO, PREF], chrome=True)
    json.dump(st, open(os.path.join(out, "%s-state-%s.json" % (step, tag)), "w"), indent=1, default=str)
    sel = st.get("selectedFilterLists")
    summary = {"pref": st.get("pref"), "selected_count": len(sel) if isinstance(sel, list) else sel,
               "cookie_selected": {k: (sel.count(k) if isinstance(sel, list) else None) for k in COOKIE},
               "tail": sel[-4:] if isinstance(sel, list) else None, "addon": st.get("addon"),
               "policyActive": st.get("policyActive"), "buildID": (st.get("appinfo") or {}).get("buildID"),
               "idbError": st.get("idbError")}
    note("state-" + tag, **summary)
    return st


def pane(m, host, tag):
    m.cmd("Marionette:SetContext", {"value": "content"})
    m.cmd("WebDriver:Navigate", {"url": "moz-extension://%s/3p-filters.html" % host})
    d = None
    for _ in range(30):
        time.sleep(1.5)
        try:
            d = m.script(JS_PANE, [list(COOKIE)])
        except Exception as e:
            d = {"error": str(e)}
        if d and d.get("entries", 0) > 10:
            break
    try:
        m.script(r"""for (const g of document.querySelectorAll('.listEntry[data-role="node"]')) g.classList.add('expanded');
          const e = document.querySelector('.listEntry[data-key="fanboy-cookiemonster"]');
          if (e) e.scrollIntoView({block: 'center'}); return true;""")
        time.sleep(1.5)
    except Exception:
        pass
    shot("pane-" + tag)
    note("pane-" + tag, cookie=(d or {}).get("cookie"), entries=(d or {}).get("entries"), error=(d or {}).get("error"))
    return d


def session(url):
    return drv.open_session(app, url)


def logcat_start(tag):
    subprocess.run([ADB, "-s", serial, "logcat", "-b", "all", "-c"])
    p = os.path.join(out, "%s-%s.logcat" % (step, tag))
    return p, subprocess.Popen([ADB, "-s", serial, "logcat", "-v", "threadtime"], stdout=open(p, "w"),
                               stderr=subprocess.STDOUT)


def logcat_stop(lc):
    p, proc = lc
    proc.terminate(); proc.wait()
    txt = open(p, errors="replace").read()
    hits = [l[:300] for l in txt.splitlines()
            if re.search(r"LW-M7-41|cookieListsMigrated|ExtensionStorageIDB|redoubtUbo|FATAL EXCEPTION|ANR in " + PKG, l)]
    crash = subprocess.run([ADB, "-s", serial, "logcat", "-d", "-b", "crash"], capture_output=True, text=True).stdout
    subprocess.run(["gzip", "-f", p])
    note("logcat", lines=len(txt.splitlines()), relevant=hits[:40], crash_buffer=crash.strip()[:1500])


def finish_session(m):
    try:
        m.close()
    except Exception:
        pass
    app.force_stop()


def cold_start_check(tag, expect_on, probe=True):
    """Cold start online on example.org, read state, pane, cookie probe."""
    lc = logcat_start(tag)
    m = session(SITE)
    drv.toolbar_ready(adb, PKG, timeout=40)
    time.sleep(15)
    st = state(m, tag + "-15s")
    pn = pane(m, st.get("hostname"), tag)
    pr = None
    if probe:
        if expect_on:
            pr = poll(m, blocked, 300)
        else:
            time.sleep(20)  # give uBO's updater its post-launch window first
            pr = {"state": probe_site(m)}
            pr["unblocked"] = unblocked(pr["state"])
        note("cookie-probe-" + tag, **pr)
    st2 = state(m, tag + "-end")
    finish_session(m)
    logcat_stop(lc)
    return st, pn, pr, st2


try:
    res["device"] = {"serial": serial, "release": adb.shell("getprop ro.build.version.release", timeout=30).strip(),
                     "abi": adb.shell("getprop ro.product.cpu.abi", timeout=30).strip()}
    if step == "s1-beta4-offline":
        install("beta4", replace=False)
        note("airplane-on", airplane_mode_on=airplane(True))
        lc = logcat_start("offline")
        m = session(PARK)
        drv.toolbar_ready(adb, PKG, timeout=40)
        time.sleep(90)
        st = state(m, "offline-90s")
        pane(m, st.get("hostname"), "offline")
        finish_session(m)
        logcat_stop(lc)
        note("airplane-off", airplane_mode_on=airplane(False))
        st, pn, pr, st2 = cold_start_check("beta4-online", expect_on=False)
    elif step == "s1-upgrade":
        before = None
        install("cand", replace=True)
        st, pn, pr, st2 = cold_start_check("first-start", expect_on=True)
    elif step == "s1-optout":
        lc = logcat_start("optout")
        m = session(SITE)
        drv.toolbar_ready(adb, PKG, timeout=40)
        time.sleep(10)
        st = state(m, "before")
        pane(m, st.get("hostname"), "before-untick")
        r = m.script(JS_UNTICK, [list(COOKIE)])
        note("untick-apply", result=r)
        time.sleep(10)
        shot("after-apply")
        pane(m, st.get("hostname"), "after-apply")
        state(m, "after")
        finish_session(m)
        logcat_stop(lc)
    elif step in ("s1-restart1", "s1-restart2"):
        cold_start_check(step.split("-")[1], expect_on=False)
    elif step == "s1-reinstall":
        install("cand", replace=True)
        cold_start_check("after-reinstall", expect_on=False)
    elif step == "s2-beta3":
        install("beta3", replace=False)
        lc = logcat_start("beta3")
        m = session(SITE)
        xml, pt, acked = drv.toolbar_ready(adb, PKG, timeout=40)
        note("ubo-sheet", acknowledged=acked)
        time.sleep(60)
        st = state(m, "fresh")
        m.cmd("Marionette:SetContext", {"value": "content"})
        m.cmd("WebDriver:Navigate", {"url": "moz-extension://%s/3p-filters.html" % st["hostname"]})
        time.sleep(6)
        clicked = m.script(r"""const e = document.querySelector('.listEntry[data-key="dpollock-0"] input[type="checkbox"]');
          if (!e) return {error: 'no dpollock-0 entry'}; const was = e.checked; e.click();
          const apply = document.querySelector('#buttonApply'); if (apply) apply.click();
          return {was, now: e.checked, apply: !!apply};""")
        time.sleep(8)
        shot("pane-after-dpollock")
        note("tick-dpollock", result=clicked)
        m.cmd("WebDriver:Navigate", {"url": "moz-extension://%s/settings.html" % st["hostname"]})
        time.sleep(5)
        cb = m.script(r"""const e = document.querySelector('input[data-setting-name="colorBlindFriendly"]');
          if (!e) return {error: 'no colorBlindFriendly'}; const was = e.checked; if (!was) e.click();
          return {was, now: e.checked};""")
        time.sleep(4)
        shot("settings-colorblind")
        note("colorBlindFriendly", result=cb)
        m.cmd("WebDriver:Navigate", {"url": SITE})
        time.sleep(3)
        st = state(m, "before-upgrade")
        finish_session(m)
        logcat_stop(lc)
    elif step == "s2-upgrade":
        install("cand", replace=True)
        cold_start_check("first-start", expect_on=True)
    elif step == "s3-fresh":
        install("cand", replace=False)
        lc = logcat_start("first-run")
        m = session(SITE)
        xml, pt, acked = drv.toolbar_ready(adb, PKG, timeout=40)
        note("ubo-sheet", acknowledged=acked)
        t0 = time.time(); st = None
        while time.time() - t0 < 120:
            st = state(m, "poll")
            if isinstance(st.get("selectedFilterLists"), list) and st["pref"].get("hasUserValue"):
                break
            time.sleep(5)
        note("first-selection", seconds=round(time.time() - t0, 1))
        time.sleep(30)
        st = state(m, "first-run-end")
        pane(m, st.get("hostname"), "first-run")
        pr = poll(m, blocked, 300)
        note("cookie-probe-first-run", **pr)
        finish_session(m)
        logcat_stop(lc)
        cold_start_check("second-start", expect_on=True)
    elif step == "s5-fresh-offline":
        install("cand", replace=False)
        note("airplane-on", airplane_mode_on=airplane(True))
        lc = logcat_start("offline")
        m = session(PARK)
        drv.toolbar_ready(adb, PKG, timeout=40)
        time.sleep(90)
        st = state(m, "offline-90s")
        pane(m, st.get("hostname"), "offline")
        finish_session(m)
        logcat_stop(lc)
        note("airplane-off", airplane_mode_on=airplane(False))
        cold_start_check("online", expect_on=True)
    else:
        raise SystemExit("unknown step " + step)
except Exception:
    import traceback
    res["error"] = traceback.format_exc()
    print(res["error"], flush=True)
finally:
    try:
        if step in ("s1-beta4-offline", "s5-fresh-offline"):
            adb.shell("cmd connectivity airplane-mode disable", timeout=60)
    except Exception:
        pass
    try:
        app.remove_debug_config()
        adb.shell("am clear-debug-app", timeout=60)
        app.force_stop()
        adb.run("reverse", "--remove", "tcp:%d" % port)
    except Exception:
        pass
    srv.shutdown()
res["completed_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
json.dump(res, open(os.path.join(out, "%s.json" % step), "w"), indent=1, default=str)
sys.exit(1 if res.get("error") else 0)
