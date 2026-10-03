#!/usr/bin/env python3
"""uBO cookie-notice lists and add-on re-enable, on a running device (diagnostic probe).

Run AFTER the harness has installed the APK under test; it reuses the committed
harness's own client (work/harness/driver.py, which android-smoke.sh writes from
itself on every run). Every mode starts from a fresh profile (pm clear).

usage: ubo-cookie-probe.py SERIAL OUTDIR MODE
  online   network up. On https://example.org/ (a real origin; uBO applies no
           cosmetic filtering on loopback hosts, measured) the probe inserts
             #AcceptCookieContainer and .accept-cookies-banner  (generic rules
               ###AcceptCookieContainer / ##.accept-cookies-banner, which are in
               EasyList Cookie Notices and in no other list uBO enables by default),
             .lw-control (matches nothing: must stay visible),
           and fetches https://cdn.cookie-script.com/ from the page (no-cors):
             ||cookie-script.com^$third-party is in EasyList Cookie Notices only.
           It reloads until both elements are hidden and the fetch is blocked
           (or 300 s), then reads uBO's storage.local (selectedFilterLists, cache
           keys) and uBO's own "Filter lists" pane (ticked/cached, screenshot).
           Then LW-M7-19 re-enable: disable uBO through AddonManager -> the same
           page shows the elements and the fetch goes through (negative control);
           enable it, no restart -> uBO active again and hiding/blocking resumes.
  offline  airplane mode ON before the first launch: storage + pane after 90 s;
           then airplane OFF, relaunch, and the same checks as online.
  control  like online's first part, read-only: the Beta 3 negative control.
"""
import http.server, importlib.util, json, os, socketserver, subprocess, sys, threading, time

R = "/home/mgysin/redoubt-artifacts/release-157/acceptance/rc3"
ADB = "/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb"
PKG = "org.redoubtbrowser"
UBO = "uBlock0@raymondhill.net"
SITE = "https://example.org/"
COOKIE_KEYS = ("fanboy-cookiemonster", "ublock-cookies-easylist", "ublock-cookies-adguard", "adguard-cookies")
serial, out, mode = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
os.environ.setdefault("LW_SMOKE_REPO", "/home/mgysin/redoubt-artifacts/release-157/repo")

spec = importlib.util.spec_from_file_location("drv", R + "/work/harness/driver.py")
drv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drv)
adb = drv.Adb(ADB, serial)
app = drv.App(adb, PKG, R + "/work")

# A loopback page, used only as somewhere to sit while offline.
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
        self.wfile.write(b"<!doctype html><title>offline parking</title><h1>offline parking</h1>")
srv = socketserver.TCPServer(("127.0.0.1", 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
adb.run("reverse", "tcp:%d" % port, "tcp:%d" % port, check=True)
PARK = "http://127.0.0.1:%d/park" % port

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
            return True, round(time.time() - t0, 1), n, s
        time.sleep(4)
    return False, round(time.time() - t0, 1), n, s

JS_STORAGE = r"""
return (async () => {
  const policy = WebExtensionPolicy.getByID(arguments[0]);
  if (!policy) return {error: "no policy"};
  const res = {hostname: policy.mozExtensionHostname, active: policy.active};
  try {
    const {ExtensionStorageIDB} = ChromeUtils.importESModule("resource://gre/modules/ExtensionStorageIDB.sys.mjs");
    const db = await ExtensionStorageIDB.open(ExtensionStorageIDB.getStoragePrincipal(policy.extension));
    const all = await db.get(null);
    res.keys = Object.keys(all || {}).sort();
    res.selectedFilterLists = all.selectedFilterLists ?? null;
    res.userSettings = all.userSettings ?? null;
    res.hiddenSettings = all.hiddenSettings ?? null;
  } catch (e) { res.idbError = String(e); }
  res.bootstrapPref = Services.prefs.getStringPref("librewolf.uBO.assetsBootstrapLocation", "<unset>");
  return res;
})();
"""

JS_ADDON = r"""
return (async () => {
  const {AddonManager} = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
  const a = await AddonManager.getAddonByID(arguments[0]);
  const p = WebExtensionPolicy.getByID(arguments[0]);
  return a && {version: a.version, isActive: a.isActive, userDisabled: a.userDisabled, policyActive: !!(p && p.active)};
})();
"""

JS_TOGGLE = r"""
return (async () => {
  const {AddonManager} = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
  const a = await AddonManager.getAddonByID(arguments[0]);
  if (arguments[1]) await a.enable(); else await a.disable();
  return {isActive: a.isActive, userDisabled: a.userDisabled};
})();
"""

JS_PANE = r"""
const keys = arguments[0];
const entry = k => { const e = document.querySelector('.listEntry[data-key="' + k + '"]'); if (!e) return null;
  const cb = e.querySelector('input[type="checkbox"]');
  return {checked: cb ? cb.checked : null, classes: e.className, name: (e.querySelector('.listname') || e).textContent.trim()}; };
const label = [...document.querySelectorAll('label')].find(l => /Ignore generic cosmetic filters/i.test(l.textContent));
const ig = label ? label.querySelector('input[type="checkbox"]') : null;
const all = [...document.querySelectorAll('.listEntry[data-key]')];
return {entries: all.length,
        ticked: all.filter(e => { const c = e.querySelector('input[type="checkbox"]'); return c && c.checked; }).map(e => e.dataset.key),
        cookie: Object.fromEntries(keys.map(k => [k, entry(k)])),
        ignoreGenericCosmeticFilters: ig ? ig.checked : null};
"""

def shot(name):
    with open(os.path.join(out, name + ".png"), "wb") as f:
        f.write(subprocess.run([ADB, "-s", serial, "exec-out", "screencap", "-p"], capture_output=True).stdout)

def pane(m, host, tag):
    m.cmd("Marionette:SetContext", {"value": "content"})
    m.cmd("WebDriver:Navigate", {"url": "moz-extension://%s/3p-filters.html" % host})
    d = None
    for _ in range(30):
        time.sleep(1.5)
        try:
            d = m.script(JS_PANE, [list(COOKIE_KEYS)])
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
    shot("pane-3p-filters-" + tag)
    return d

def airplane(on):
    adb.shell("cmd connectivity airplane-mode %s" % ("enable" if on else "disable"), timeout=60)

def selected(storage):
    sel = (storage or {}).get("selectedFilterLists") or []
    return {k: (k in sel) for k in COOKIE_KEYS}

result = {"mode": mode, "serial": serial, "site": SITE, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
lc_path = os.path.join(out, "probe-%s.logcat" % mode)
lc = subprocess.Popen([ADB, "-s", serial, "logcat", "-v", "threadtime"], stdout=open(lc_path, "w"), stderr=subprocess.STDOUT)
m = None
try:
    result["installed"] = adb.shell("dumpsys package %s | grep -E 'versionName|versionCode'" % PKG, timeout=60).strip()
    app.force_stop()
    app.wipe()
    if mode == "offline":
        airplane(True); time.sleep(5)
        result["airplane_on"] = adb.shell("settings get global airplane_mode_on", timeout=30).strip()
        m = drv.open_session(app, PARK)
        drv.toolbar_ready(adb, PKG, timeout=40)
        time.sleep(90)
        result["offline_storage"] = m.script(JS_STORAGE, [UBO], chrome=True)
        result["offline_selected"] = selected(result["offline_storage"])
        result["offline_addon"] = m.script(JS_ADDON, [UBO], chrome=True)
        result["offline_pane"] = pane(m, result["offline_storage"].get("hostname"), "offline")
        m.close(); m = None
        airplane(False); time.sleep(20)
        result["airplane_after"] = adb.shell("settings get global airplane_mode_on", timeout=30).strip()
        m = drv.open_session(app, SITE)
        ok, t, n, s = poll(m, blocked, 300)
        result["after_network"] = {"blocked": ok, "seconds": t, "loads": n, "state": s}
        st = m.script(JS_STORAGE, [UBO], chrome=True)
        result["after_network_storage"] = st
        result["after_network_selected"] = selected(st)
        result["after_network_pane"] = pane(m, st.get("hostname"), "offline-then-online")
    else:
        m = drv.open_session(app, SITE)
        drv.toolbar_ready(adb, PKG, timeout=40)
        ok, t, n, s = poll(m, blocked, 300 if mode == "online" else 150)
        result["cookie_rules"] = {"blocked": ok, "seconds_from_session": t, "loads": n, "state": s}
        shot("site-" + mode)
        st = m.script(JS_STORAGE, [UBO], chrome=True)
        result["storage"] = st
        result["selected"] = selected(st)
        result["addon"] = m.script(JS_ADDON, [UBO], chrome=True)
        result["pane"] = pane(m, st.get("hostname"), mode)
        if mode == "online":
            m.cmd("Marionette:SetContext", {"value": "content"})
            m.cmd("WebDriver:Navigate", {"url": SITE})  # leave the moz-extension page: disabling unloads it
            time.sleep(2)
            pid0 = adb.shell("pidof %s" % PKG, timeout=30).strip()
            dis = m.script(JS_TOGGLE, [UBO, False], chrome=True)
            time.sleep(3)
            s_dis = probe_site(m)
            a_dis = m.script(JS_ADDON, [UBO], chrome=True)
            en = m.script(JS_TOGGLE, [UBO, True], chrome=True)
            ok2, t2, n2, s_en = poll(m, blocked, 90)
            a_en = m.script(JS_ADDON, [UBO], chrome=True)
            pid1 = adb.shell("pidof %s" % PKG, timeout=30).strip()
            result["reenable"] = {"disable_call": dis, "after_disable_addon": a_dis, "after_disable_site": s_dis,
                                  "rules_inactive_while_disabled": unblocked(s_dis),
                                  "enable_call": en, "after_enable_addon": a_en,
                                  "rules_active_after_enable_without_restart": ok2, "seconds": t2, "loads": n2,
                                  "after_enable_site": s_en, "pid_before": pid0, "pid_after": pid1,
                                  "same_process": bool(pid0) and pid0 == pid1}
except Exception:
    import traceback
    result["error"] = traceback.format_exc()
finally:
    if mode == "offline":
        try: airplane(False)
        except Exception: pass
    if m:
        try: m.close()
        except Exception: pass
    try:
        app.remove_debug_config(); adb.shell("am clear-debug-app", timeout=60); app.force_stop()
        adb.run("reverse", "--remove", "tcp:%d" % port)
    except Exception:
        pass
    time.sleep(2)
    lc.terminate(); lc.wait()
    subprocess.run(["gzip", "-f", lc_path])
    srv.shutdown()

json.dump(result, open(os.path.join(out, "probe-%s.json" % mode), "w"), indent=1)
keep = ("cookie_rules", "selected", "addon", "reenable", "offline_selected", "offline_addon", "after_network",
        "after_network_selected", "error")
summary = {k: result[k] for k in keep if k in result}
for k in ("pane", "offline_pane", "after_network_pane"):
    if isinstance(result.get(k), dict):
        summary[k] = {x: result[k].get(x) for x in ("entries", "cookie", "ignoreGenericCosmeticFilters")}
print(json.dumps(summary, indent=1, default=str))
