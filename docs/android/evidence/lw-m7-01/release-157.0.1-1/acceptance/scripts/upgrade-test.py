#!/usr/bin/env python3
"""REAL upgrade 157.0-3 (CI run 37441476096, x86_64 versionCode 2016188750) -> 157.0.1-1 (CI run
37993605790, Firefox 157.0.1) with `adb install -r`, same throwaway key. Copied from the 158.0-1 Beta 1
acceptance's upgrade-test.py with the candidate changed (157.0-3 is still the source); phase A
turns the opt-in update check ON through Settings, and phase C requires it to still be ON.

usage: upgrade-test.py SERIAL OUTDIR PHASE      PHASE = A | B | C

  A  157.0-3 fresh install (uninstall first). Launcher start, acknowledge the uBO
     sheet, then through the real UI: Settings > Search "Show search suggestions"
     ON, Settings > DNS over HTTPS "Max Protection", bookmark https://example.org/
     from the main menu. Through Marionette (GeckoView debug config, as the
     harness does): read Gecko's TRR prefs and uBO's storage, then tick
     "Dan Pollock's hosts file" in uBO's own Filter lists pane and Apply. The
     debug config is removed again before the upgrade.
  B  logcat cleared; `adb install -r` of rc2 (no -d, no uninstall); first launch
     from the launcher, observed 45 s (dumps at 10 s and 45 s, crash buffer, alive);
     force-stop; second launcher launch, same checks.
  C  Verify on the upgraded profile (no wipe): the suggestions switch, the DoH
     screen, the bookmark list, and through Marionette the TRR prefs, uBO version,
     state and filter-list selection.
Every step writes NN-name.xml/.png into OUTDIR; results go to phase-<P>.json.
"""
import html, importlib.util, json, os, re, subprocess, sys, time
R = "/home/mgysin/redoubt-artifacts/release-157.0.1-1"
S = R + "/repo/docs/android/evidence/lw-m7-01/release-157.0.1-1/acceptance/scripts"
ADBX = "/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb"
PKG = "org.redoubtbrowser"
UBO = "uBlock0@raymondhill.net"
BETA3 = R + "/apk/fenix-x86_64-157.0-3-throwaway.apk"   # name kept from the 157.0-1 script: the upgrade SOURCE, 157.0-3
RC2 = R + "/apk/fenix-x86_64-157.0.1-1-throwaway.apk"    # name kept: the candidate, 157.0.1-1
AAPT2 = R + "/x/aapt2/aapt2"
serial, out, phase = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
os.environ.setdefault("LW_SMOKE_REPO", R + "/repo")
spec = importlib.util.spec_from_file_location("drv", R + "/work/harness/driver.py")
drv = importlib.util.module_from_spec(spec); spec.loader.exec_module(drv)
adb = drv.Adb(ADBX, serial); app = drv.App(adb, PKG, R + "/work")
res = {"phase": phase, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "steps": []}
TRR = open(S + "/trr.js").read()
counter = [{"A": 0, "B": 30, "C": 60}[phase]]

def note(name, **kw):
    kw["step"] = name; kw["t"] = time.strftime("%H:%M:%S"); res["steps"].append(kw)
    print(json.dumps(kw, default=str)[:600], flush=True)

def dump(tag):
    counter[0] += 1; name = "%02d-%s" % (counter[0], tag)
    xml = drv._ui_dump(adb)
    open(os.path.join(out, name + ".xml"), "w").write(xml)
    with open(os.path.join(out, name + ".png"), "wb") as f:
        f.write(subprocess.run([ADBX, "-s", serial, "exec-out", "screencap", "-p"], capture_output=True).stdout)
    return xml

def labels(xml):
    return [html.unescape(x) for x in re.findall(r'\b(?:text|content-desc)="([^"]*)"', xml) if x.strip()]

def find(xml, pred):
    for m in re.finditer(r'<node [^>]*>', xml):
        n = m.group(0)
        t = html.unescape((re.search(r' text="([^"]*)"', n) or [None, ""])[1])
        d = html.unescape((re.search(r'content-desc="([^"]*)"', n) or [None, ""])[1])
        if pred(t, d):
            b = list(map(int, re.findall(r"\d+", re.search(r'bounds="([^"]*)"', n).group(1))))
            return ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)
    return None

def tap(pt, wait=2.0):
    adb.shell("input tap %d %d" % pt, timeout=60); time.sleep(wait)

def back():
    adb.shell("input keyevent 4", timeout=60); time.sleep(1.5)

def scroll_top():
    w, h = drv._screen_size(adb)
    for _ in range(6):
        adb.shell("input swipe %d %d %d %d 200" % (w // 2, int(h * 0.3), w // 2, int(h * 0.8)), timeout=60)
    time.sleep(1)

def dialogs(xml):
    """Anything that looks like a modal: an AlertDialog title/panel or a known startup sheet."""
    ls = labels(xml)
    hits = [l for l in ls if re.search(r"setup failed|was added|provider changed|has stopped|isn.t responding|Retry|What.s new|Welcome", l, re.I)]
    alert = bool(re.search(r'resource-id="(android|%s):id/(alertTitle|parentPanel|message)"' % re.escape(PKG), xml))
    return {"alert_panel": alert, "suspicious_labels": hits}

def crash_buffer():
    return subprocess.run([ADBX, "-s", serial, "logcat", "-d", "-b", "crash"], capture_output=True, text=True).stdout

def pkginfo(tag):
    s = adb.shell("dumpsys package %s | grep -E 'versionCode|versionName|firstInstallTime|lastUpdateTime|signatures'" % PKG, timeout=60)
    open(os.path.join(out, "pkg-%s.txt" % tag), "w").write(s)
    return s.strip()

def scheme():
    return drv.apk_deeplink_scheme(AAPT2, RC2 if phase != "A" else BETA3)

def marionette_state(m, tag):
    st = {"trr": m.script(TRR, chrome=True)}
    st["ubo"] = m.script(r"""return (async () => {
      const {AddonManager} = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
      const a = await AddonManager.getAddonByID(arguments[0]); const p = WebExtensionPolicy.getByID(arguments[0]);
      const r = a ? {version: a.version, isActive: a.isActive, userDisabled: a.userDisabled, signedState: a.signedState} : null;
      if (p) { try {
        const {ExtensionStorageIDB} = ChromeUtils.importESModule("resource://gre/modules/ExtensionStorageIDB.sys.mjs");
        const db = await ExtensionStorageIDB.open(ExtensionStorageIDB.getStoragePrincipal(p.extension));
        const all = await db.get(["selectedFilterLists", "version", "availableFilterLists"]);
        r.storageVersion = all.version; r.selectedFilterLists = all.selectedFilterLists;
        r.catalogKeys = all.availableFilterLists ? Object.keys(all.availableFilterLists).length : null;
        r.hostname = p.mozExtensionHostname;
      } catch (e) { r.storageError = String(e); } }
      r.bootstrapPref = Services.prefs.getStringPref("librewolf.uBO.assetsBootstrapLocation", "<unset>");
      return r; })();""", [UBO], chrome=True)
    st["appinfo"] = m.script("return {version: Services.appinfo.version, buildID: Services.appinfo.appBuildID};", chrome=True)
    json.dump(st, open(os.path.join(out, "state-%s.json" % tag), "w"), indent=1)
    return st

def launcher_launch(tag):
    since = time.time()
    adb.shell("am force-stop " + PKG, timeout=60); time.sleep(1.5)
    subprocess.run([ADBX, "-s", serial, "logcat", "-c"])
    lc = subprocess.Popen([ADBX, "-s", serial, "logcat", "-v", "threadtime"], stdout=open(os.path.join(out, tag + ".logcat"), "w"), stderr=subprocess.STDOUT)
    app.start_home()
    time.sleep(10); x10 = dump(tag + "-10s")
    time.sleep(35); x45 = dump(tag + "-45s")
    lc.terminate(); lc.wait()
    log = open(os.path.join(out, tag + ".logcat"), errors="replace").read()
    r = {"alive": app.alive(), "dialogs_10s": dialogs(x10), "dialogs_45s": dialogs(x45),
         "labels_45s": [l for l in labels(x45) if len(l) < 80][:30],
         "crash_buffer": crash_buffer().strip()[:2000],
         "fatal_lines": [l for l in log.splitlines() if re.search(r"FATAL EXCEPTION|AndroidRuntime: Process: " + PKG + r"|ANR in " + PKG, l)][:10],
         "ubo_lines": [l[:220] for l in log.splitlines() if re.search(r"uBlock Origin startup|uBO|DohProviderMigration|Replaced discontinued", l)][:10],
         "logcat_lines": len(log.splitlines())}
    subprocess.run(["gzip", "-f", os.path.join(out, tag + ".logcat")])
    return r

try:
    if phase == "A":
        adb.run("uninstall", PKG, timeout=300)
        p = adb.run("install", BETA3, timeout=900)
        note("install-beta3", stdout=p.stdout.strip(), stderr=p.stderr.strip(), pkg=pkginfo("A-beta3"))
        app.uid = None
        r = launcher_launch("A-first-launch")
        note("beta3-first-launch", **r)
        xml = dump("A-before-ack")
        xml, acked = drv.acknowledge_ubo_added_notice(adb, PKG, xml)
        note("ubo-sheet", acknowledged=acked)
        sch = scheme(); note("scheme", scheme=sch)
        before, after = drv.set_suggestions_switch(adb, PKG, sch, True)
        note("suggestions-on", before=before, after=after)
        # DNS over HTTPS -> Max Protection
        drv._deeplink(adb, PKG, sch, "settings"); scroll_top()
        xml, pt = drv._find_row(adb, "DNS over HTTPS", max_scrolls=8)
        note("doh-row", found=pt)
        if pt:
            tap(pt); xml = dump("A-doh-screen")
            # Tap the RadioButton level with the "Max Protection" label: tapping the label itself does
            # not select it (measured on Beta 3 in the rc2 run).
            lab = re.search(r'text="Max Protection"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)
            radios = [tuple(map(int, r)) for r in re.findall(
                r'class="android.widget.RadioButton"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)]
            if lab and radios:
                ly = (int(lab.group(2)) + int(lab.group(4))) // 2
                rb = min(radios, key=lambda r: abs((r[1] + r[3]) // 2 - ly))
                tap(((rb[0] + rb[2]) // 2, (rb[1] + rb[3]) // 2)); xml = dump("A-doh-max-selected")
                note("doh-max", radios=re.findall(r'class="android.widget.RadioButton"[^>]*checked="(true|false)"', xml),
                     labels=[l for l in labels(xml) if len(l) < 90][:30])
            back()
        back()
        # 157.0-3 acceptance: the opt-in update check ON in 157.0-2, through the real Settings row.
        drv._deeplink(adb, PKG, sch, "settings")
        xml, pt = drv._find_row(adb, "Check for updates", max_scrolls=16)
        uc_before = drv._switch_after(xml, "Check for updates") if pt else None
        if pt and uc_before is False:
            adb.shell("input tap %d %d" % drv._switch_bounds_after(xml, "Check for updates"), timeout=60); time.sleep(1.5)
            xml = drv._ui_dump(adb)
        uc_after = drv._switch_after(xml, "Check for updates") if pt else None
        dump("A-update-check-on")
        note("update-check-on", row_found=pt, before=uc_before, after=uc_after,
             store=adb.shell("su 0 sh -c 'grep -H pref_key_lw_update_check /data/data/%s/shared_prefs/*.xml'" % PKG, timeout=60).strip())
        back()
        # bookmark example.org from the main menu
        app.start_url("https://example.org/"); time.sleep(8)
        xml, pt, _ = drv.toolbar_ready(adb, PKG, timeout=40)
        mb = find(drv._ui_dump(adb), lambda t, d: re.search(r"main menu|more options", d, re.I) is not None)
        note("menu-button", found=mb)
        if mb:
            tap(mb); xml = dump("A-menu")
            bk = find(xml, lambda t, d: re.fullmatch(r"Bookmark( page| this page)?", t or d) is not None)
            note("bookmark-item", found=bk, labels=[l for l in labels(xml) if len(l) < 60][:30])
            if bk:
                tap(bk, 1.0); dump("A-after-bookmark")
            else:
                back()
        # Marionette: state + uBO pane change
        m = drv.open_session(app, "https://example.org/"); time.sleep(5)
        note("storage-controller-module-loaded-at-session", loaded=m.script(
            'return Cu.isESModuleLoaded("resource://gre/modules/GeckoViewStorageController.sys.mjs");', chrome=True))
        st = marionette_state(m, "A-before-pane")
        note("beta3-state", trr_mode=st["trr"].get("network.trr.mode"), trr_uri=st["trr"].get("network.trr.uri"),
             ubo=st["ubo"], appinfo=st["appinfo"])
        m.cmd("Marionette:SetContext", {"value": "content"})
        m.cmd("WebDriver:Navigate", {"url": "moz-extension://%s/3p-filters.html" % st["ubo"]["hostname"]}); time.sleep(6)
        clicked = m.script(r"""const e = document.querySelector('.listEntry[data-key="dpollock-0"] input[type="checkbox"]');
          if (!e) return {error: 'no dpollock-0 entry'}; const was = e.checked; e.click();
          const apply = document.querySelector('#buttonApply'); if (apply) apply.click();
          return {was, now: e.checked, apply: !!apply};""")
        time.sleep(8); dump("A-ubo-pane-after-apply")
        st2 = marionette_state(m, "A-final")
        note("ubo-pane-change", clicked=clicked, selected=st2["ubo"].get("selectedFilterLists"))
        m.close()
        app.remove_debug_config(); adb.shell("am clear-debug-app", timeout=60)
        adb.shell("rm -f /data/local/tmp/%s-geckoview-config.yaml" % PKG, timeout=60)
        drv._deeplink(adb, PKG, sch, "urls_bookmarks"); time.sleep(3)
        xml = dump("A-bookmarks-before-upgrade")
        note("bookmarks-before-upgrade", example=any("Example Domain" in l for l in labels(xml)))
        adb.shell("am force-stop " + PKG, timeout=60)
        note("debug-config-removed", ls=adb.shell("ls /data/local/tmp/", timeout=30).strip())
    elif phase == "B":
        subprocess.run([ADBX, "-s", serial, "logcat", "-b", "all", "-c"])
        before = pkginfo("B-before")
        p = adb.run("install", "-r", RC2, timeout=900)
        note("adb-install-r", cmd="adb install -r " + RC2, stdout=p.stdout.strip(), stderr=p.stderr.strip(),
             before=before, after=pkginfo("B-after"))
        note("upgrade-first-launch", **launcher_launch("B-first-launch"))
        note("upgrade-second-launch", **launcher_launch("B-second-launch"))
    elif phase == "C":
        sch = scheme(); note("scheme", scheme=sch)
        drv._deeplink(adb, PKG, sch, "settings_search_engine")
        xml, pt = drv._find_row(adb, drv.SUGGEST_SWITCH)
        note("suggestions-after-upgrade", found=pt, on=drv._switch_after(xml, drv.SUGGEST_SWITCH) if pt else None)
        dump("C-search-settings"); back()
        drv._deeplink(adb, PKG, sch, "settings"); scroll_top()
        xml, pt = drv._find_row(adb, "DNS over HTTPS", max_scrolls=8)
        row_summary = None
        if pt:
            i = xml.find('text="DNS over HTTPS"')
            m2 = re.search(r' text="([^"]+)"', xml[i + 25:]) if i >= 0 else None
            row_summary = m2.group(1) if m2 else None
            tap(pt); xml = dump("C-doh-screen")
            note("doh-after-upgrade", row_summary=row_summary,
                 labels=[l for l in labels(xml) if len(l) < 90][:30],
                 radios=re.findall(r'class="android.widget.RadioButton"[^>]*checked="(true|false)"', xml))
            back()
        back()
        # 157.0-3: the opt-in update check must be present and still ON on the upgraded profile (turned on in phase A).
        drv._deeplink(adb, PKG, sch, "settings")
        xml, pt = drv._find_row(adb, "Check for updates", max_scrolls=16)
        uc_on = drv._switch_after(xml, "Check for updates") if pt else None
        dump("C-update-check-row")
        uc_prefs = adb.shell("su 0 sh -c 'ls /data/data/%s/shared_prefs/; cat /data/data/%s/shared_prefs/lw_update_check.xml; grep -i update_check /data/data/%s/shared_prefs/*.xml'" % (PKG, PKG, PKG), timeout=60)
        note("update-check-after-upgrade", row_found=pt, switch_on=uc_on, prefs=uc_prefs.strip()[:800])
        back()
        drv._deeplink(adb, PKG, sch, "urls_bookmarks"); time.sleep(3)
        xml = dump("C-bookmarks")
        note("bookmarks-after-upgrade", labels=[l for l in labels(xml) if len(l) < 90][:30],
             example=any("Example Domain" in l or "example.org" in l for l in labels(xml)))
        back()
        m = drv.open_session(app, "https://example.org/"); time.sleep(5)
        st = marionette_state(m, "C-after-upgrade")
        note("state-after-upgrade", trr_mode=st["trr"].get("network.trr.mode"), trr_uri=st["trr"].get("network.trr.uri"),
             ubo=st["ubo"], appinfo=st["appinfo"])
        m.close()
        app.remove_debug_config(); adb.shell("am clear-debug-app", timeout=60)
except Exception:
    import traceback
    res["error"] = traceback.format_exc(); print(res["error"])
json.dump(res, open(os.path.join(out, "phase-%s.json" % phase), "w"), indent=1, default=str)
