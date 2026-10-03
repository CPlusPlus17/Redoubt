#!/usr/bin/env python3
"""Is ExtensionStorageIDB.selectBackend ever called for uBO in a normal session?
usage: select-backend-probe.py SERIAL OUTFILE [--no-wipe]
Cold start on example.org through the harness's Marionette door, wait 30 s (uBO has
started and read its storage by then), then read in the parent: the per-extension
migrated pref, the sharedData entry the child checks before calling selectBackend,
and whether selectBackend's cache holds a promise for uBO's Extension object."""
import importlib.util, json, os, sys, time
A = "/home/mgysin/redoubt-artifacts/beta5/accept"
os.environ.setdefault("LW_SMOKE_REPO", "/home/mgysin/redoubt-artifacts/beta5/repo")
spec = importlib.util.spec_from_file_location("drv", A + "/work/harness/driver.py")
drv = importlib.util.module_from_spec(spec); spec.loader.exec_module(drv)
serial, outf = sys.argv[1], sys.argv[2]
adb = drv.Adb("/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb", serial)
app = drv.App(adb, "org.redoubtbrowser", A + "/work")
m = drv.open_session(app, "https://example.org/")
drv.toolbar_ready(adb, "org.redoubtbrowser", timeout=40)
time.sleep(30)
r = m.script(r"""return (async () => {
  const id = "uBlock0@raymondhill.net";
  const {ExtensionStorageIDB} = ChromeUtils.importESModule("resource://gre/modules/ExtensionStorageIDB.sys.mjs");
  const p = WebExtensionPolicy.getByID(id);
  const ext = p && p.extension;
  return {
    buildID: Services.appinfo.appBuildID,
    policyActive: !!(p && p.active),
    startupReason: ext && ext.startupReason,
    backendEnabledPref: Services.prefs.getBoolPref("extensions.webextensions.ExtensionStorageIDB.enabled", null),
    migratedPref: Services.prefs.getBoolPref("extensions.webextensions.ExtensionStorageIDB.migrated." + id, null),
    sharedDataStorageIDBBackend: Services.ppmm.sharedData.get("extension/" + id + "/storageIDBBackend"),
    selectBackendCalledThisSession: !!(ext && ExtensionStorageIDB.selectedBackendPromises.has(ext)),
    cookieListsMigratedPref: Services.prefs.getPrefType("librewolf.uBO.cookieListsMigrated"),
  };
})();""", chrome=True)
r["serial"] = serial; r["utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
r["installed"] = adb.shell("dumpsys package org.redoubtbrowser | grep -E 'versionCode|lastUpdateTime'", timeout=60).strip()
m.close(); app.remove_debug_config(); adb.shell("am clear-debug-app", timeout=60); app.force_stop()
json.dump(r, open(outf, "w"), indent=1); print(json.dumps(r, indent=1))
