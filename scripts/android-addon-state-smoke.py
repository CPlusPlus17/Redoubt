#!/usr/bin/env python3
"""Exercise installed-release add-on choices through real Fenix controls.

Uses a dedicated profile and pre-enabled transport-only Marionette. Never
installs an APK/extension, wipes state or mutates AddonManager/preferences.
Signed update coverage and an unobservably slow immediate restart stay PENDING.
"""
from __future__ import annotations

import argparse
import hashlib
import http.server
import importlib.util
import io
import json
from pathlib import Path
import re
import secrets
import shlex
import shutil
import socket
import sys
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("lw_addon_transport", ROOT / "scripts/android-graphics-smoke.py")
g = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(g)
Pending, Failure, require = g.Pending, g.Failure, g.require
PASS, FAIL, PENDING = g.PASS, g.FAIL, g.PENDING
ADDON_ID, ADDON_NAME = "uBlock0@raymondhill.net", "uBlock Origin"
FILTER_FILE = "assets/thirdparties/easylist/easylist.txt"
FILTER_RULE = "/banner_ads/*$~xmlhttprequest,domain=~clickbd.com"
BLOCKED_PATH, ALLOWED_PATH = "/banner_ads/redoubt-probe.js", "/redoubt-allowed.js"
MAX_ACTION_TO_STOP_MS = 1000
REQUIRED = {"initial-normal", "disabled-normal", "enabled-normal", "private-denied-normal",
            "private-denied-private", "private-allowed-normal", "private-allowed-private",
            "removed-normal", "removed-private", "removed-second-restart", "signed-update"}


def bundle_evidence(apk):
    """Read the supplied exact APK, its immutable uBO pin and durability modules."""
    with zipfile.ZipFile(apk) as archive:
        pin = json.loads(archive.read("assets/extensions/ubo-extension.json"))
        xpi = archive.read("assets/extensions/ublock_origin.xpi")
        with zipfile.ZipFile(io.BytesIO(archive.read("assets/omni.ja"))) as omni:
            source = json.loads((ROOT / "docs/android/evidence/lw-m7-19/source-files.json").read_text())
            modules = {}
            for item in source["files"]:
                name = Path(item["path"]).name
                if name in ("AndroidAddonState.sys.mjs", "XPIDatabase.sys.mjs", "XPIInstall.sys.mjs", "XPIProvider.sys.mjs"):
                    digest = hashlib.sha256(omni.read("modules/addons/" + name)).hexdigest()
                    require(digest == item["after_sha256"], "APK durability module differs from reviewed source: " + name)
                    modules[name] = digest
            require(len(modules) == 4, "Missing reviewed durability-module manifest")
    require(hashlib.sha256(xpi).hexdigest() == pin.get("sha256") and len(xpi) == pin.get("size"),
            "Packaged uBO differs from its own byte pin")
    repository_pin = json.loads((ROOT / "assets/ubo-extension.json").read_text())
    require(pin == repository_pin, "Packaged uBO pin differs from the reviewed repository pin")
    with zipfile.ZipFile(io.BytesIO(xpi)) as extension:
        manifest = json.loads(extension.read("manifest.json"))
        identity = manifest.get("browser_specific_settings", manifest.get("applications", {})).get("gecko", {}).get("id")
        require(identity == ADDON_ID and manifest.get("version") == pin["version"], "Packaged add-on ID/version mismatch")
        filters = extension.read(FILTER_FILE)
        require(FILTER_RULE in filters.decode().splitlines(), "Actual packaged EasyList does not contain the probe rule")
    return {"pin": pin, "filterPath": FILTER_FILE, "filterRule": FILTER_RULE,
            "filterSha256": hashlib.sha256(filters).hexdigest(), "durabilityModules": modules}


def grade_state(data, *, installed, enabled, private_allowed, version):
    require(isinstance(data, dict) and not data.get("errors"), "Missing or unreadable add-on state")
    require(data.get("id") == ADDON_ID, "Observation is for another add-on")
    require(data.get("sameNameOtherIds") == [], "The UI name is ambiguous among installed add-ons")
    require(type(data.get("listeners")) is int and data["listeners"] >= 0, "Missing real listener count")
    addon, database, cache = data.get("addon"), data.get("database"), data.get("cache")
    require(isinstance(database, list) and isinstance(cache, list), "Missing independent disk state")
    if not installed:
        require(addon is None and database == [] and cache == [] and data.get("memory") is None,
                "Removed add-on remains in registry or startup persistence")
        require(data.get("policy") is False and data["listeners"] == 0, "Removed add-on retains a live policy/listener")
        require(data.get("privatePermission") is False, "Removed add-on retains its stored private permission")
        require(data.get("permissionBackend") in ("legacy-json", "rkv"), "Unknown extension permission backend")
        if data["permissionBackend"] == "legacy-json":
            require(data.get("privatePermissionDisk") is False, "Removed add-on retains private permission in the legacy file")
        return data
    require(isinstance(addon, dict) and addon.get("id") == ADDON_ID and addon.get("version") == version,
            "Installed add-on identity/version differs from the pinned fixture")
    require(addon.get("amoSigned") is True and addon.get("isBuiltin") is False,
            "Fixture is not an ordinary signed add-on")
    require(addon.get("active") is enabled and addon.get("userDisabled") is (not enabled) and
            addon.get("appDisabled") is False and addon.get("pendingUninstall") is False,
            "Registry state disagrees with the real UI choice")
    require(data.get("policy") is enabled and bool(data["listeners"]) is enabled,
            "Registry and live extension policy/listeners disagree")
    require(data.get("privatePermission") is private_allowed, "Stored private permission disagrees with the UI choice")
    require(data.get("permissionBackend") in ("legacy-json", "rkv"), "Unknown extension permission backend")
    if data["permissionBackend"] == "legacy-json":
        require(data.get("privatePermissionDisk") is private_allowed, "Legacy permission file disagrees with the acknowledged private choice")
    if enabled:
        require(data.get("policyPrivateAllowed") is private_allowed, "Live private permission disagrees with storage")
    require(len(database) == 1 and len(cache) == 1 and isinstance(data.get("memory"), dict),
            "Missing or duplicated independent add-on persistence records")
    require(database[0].get("active") is enabled and database[0].get("userDisabled") is (not enabled) and
            database[0].get("version") == version, "Disk database does not retain the acknowledged choice")
    require(cache[0].get("enabled") is enabled and cache[0].get("version") == version and
            data["memory"].get("enabled") is enabled, "Startup cache and acknowledged choice disagree")
    return data


def grade_navigation(page, requests, *, run, case_id, document_id, origin, blocked, before_connect=None):
    require(isinstance(page, dict), "Missing parser page evidence")
    for key, expected in {"run": run, "caseId": case_id, "documentId": document_id,
                          "origin": origin}.items():
        require(page.get(key) == expected, "Wrong/stale parser identity: " + key)
    require(page.get("loaded") is True and page.get("errors") == [], "Parser page did not finish cleanly")
    require(page.get("url") == origin + "/addon-probe?" + urllib.parse.urlencode({"run": run, "case": case_id}),
            "Parser page URL does not match its exact case")
    bound = [row for row in requests if row.get("documentId") == document_id]
    require(bound and all(row.get("run") == run and row.get("caseId") == case_id and row.get("origin") == origin
                          for row in bound), "Wrong-origin server records")
    documents = [row for row in bound if row.get("kind") == "document"]
    reports = [row for row in bound if row.get("kind") == "report"]
    require(len(documents) == 1 and len(reports) >= 1, "Missing real parser navigation or allowed report request")
    if before_connect is not None:
        require(documents[0]["at"] < before_connect and reports[0]["at"] < before_connect,
                "First navigation did not complete before Marionette attached")
    expected_counts = {"allowed": 1, "blocked": 0 if blocked else 1}
    counts = page.get("counts")
    require(isinstance(counts, dict) and counts == expected_counts and
            all(type(value) is int for value in counts.values()), "Wrong actual script-execution counts")
    for kind, count in expected_counts.items():
        hits = [row for row in bound if row.get("kind") == kind]
        require(len(hits) == count, "Independent resource requests differ from page execution: " + kind)
    executions = page.get("executions")
    require(isinstance(executions, list) and len(executions) == sum(expected_counts.values()), "Missing actual script execution provenance")
    require(all(sum(event.get("kind") == kind for event in executions) == count for kind, count in expected_counts.items()),
            "Script execution provenance does not cover each actual resource")
    for event in executions:
        path = ALLOWED_PATH if event.get("kind") == "allowed" else BLOCKED_PATH
        require(event.get("ready") == "loading" and event.get("async") is False and event.get("defer") is False and
                event.get("src") == origin + path + "?" + urllib.parse.urlencode({"run": run, "case": case_id, "doc": document_id}),
                "Script was not executed by its original parser-inserted resource")
    report_counts = reports[-1].get("counts")
    require(isinstance(report_counts, dict) and report_counts == expected_counts and
            all(type(value) is int for value in report_counts.values()), "Server report disagrees with current page")
    return {"run": run, "caseId": case_id, "documentId": document_id, "origin": origin,
            "blocked": blocked, "counts": expected_counts, "requests": bound, "executions": executions}


def ui_node(xml, rid, package, required=True):
    return g.select_node(xml, rid=rid, package=package, required=required)


def grade_ui_ack(xml, *, action, value, package):
    """The checked bit is optimistic; re-enabled controls establish callback completion."""
    if action == "remove":
        require(ui_node(xml, "enable_switch", package, False) is None and
                ui_node(xml, "add_ons_list", package, False) is not None,
                "Removal did not acknowledge by returning to the real manager")
        return {"action": action, "ack": "manager-after-success", "confirmationDialogOffered": False}
    g.select_node(xml, text=ADDON_NAME, package=package)
    target = ui_node(xml, "enable_switch" if action == "enabled" else "allow_in_private_browsing_switch", package)
    require(target.get("checkable") == "true" and target.get("checked") == str(value).lower(),
            "The UI switch has not reached the requested choice")
    require(target.get("clickable") == "true", "Optimistic switch change has not been acknowledged")
    for rid in ("remove_add_on", "report_add_on"):
        require(ui_node(xml, rid, package).get("enabled") == "true", "Add-on completion controls remain disabled")
    if action == "enabled":
        require((ui_node(xml, "allow_in_private_browsing_switch", package, False) is not None) is value,
                "Enable callback has not updated the dependent private control")
    return {"action": action, "value": value, "ack": "interactive-after-callback"}


def grade_timing(timing):
    require(timing.get("acknowledged") is True, "No actual UI completion acknowledgment")
    ordered = [timing.get(name) for name in ("actionStarted", "ackObserved", "stopIssued", "stopCompleted")]
    require(all(type(item) in (int, float) for item in ordered) and ordered == sorted(ordered), "Missing or reversed restart timing")
    upper = (ordered[-1] - ordered[0]) * 1000
    if upper > MAX_ACTION_TO_STOP_MS:
        raise Pending("UI observation/force-stop took %.0f ms; cannot establish the <=%d ms immediate restart window" %
                      (upper, MAX_ACTION_TO_STOP_MS))
    return {"actionToStoppedUpperBoundMs": upper, "maximumMs": MAX_ACTION_TO_STOP_MS}


STATE_JS = r"""
return (async()=>{
  const {AddonManager}=ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
  const {ExtensionPermissions}=ChromeUtils.importESModule('resource://gre/modules/ExtensionPermissions.sys.mjs');
  const {AppConstants}=ChromeUtils.importESModule('resource://gre/modules/AppConstants.sys.mjs');
  const {XPIInternal}=ChromeUtils.importESModule('resource://gre/modules/addons/XPIProvider.sys.mjs');
  const id=arguments[0], all=await AddonManager.getAllAddons(), a=all.find(item=>item.id===id);
  const p=WebExtensionPolicy.getByID(id), memory=XPIInternal.XPIStates.findAddon(id);
  const result={id,errors:[],sameNameOtherIds:all.filter(item=>item.name==='uBlock Origin'&&item.id!==id).map(item=>item.id),
    addon:a?{id:a.id,version:a.version,active:a.isActive,userDisabled:a.userDisabled,appDisabled:a.appDisabled,
      pendingUninstall:!!(a.pendingOperations & AddonManager.PENDING_UNINSTALL),
      amoSigned:a.signedState===AddonManager.SIGNEDSTATE_SIGNED,isBuiltin:a.isBuiltin}:null,
    policy:!!p,policyPrivateAllowed:p?.privateBrowsingAllowed??null,
    listeners:p?.extension?.redoubtBlockingResponseListeners?.size??0,
    memory:memory?{enabled:memory.enabled,version:memory.version}:null};
  try {
    result.privatePermission=(await ExtensionPermissions.get(id)).permissions.includes('internal:privateBrowsingAllowed');
    const profile=Services.dirsvc.get('ProfD',Ci.nsIFile).path;
    result.permissionBackend=AppConstants.NIGHTLY_BUILD?'rkv':'legacy-json';
    result.privatePermissionDisk=null;
    if(result.permissionBackend==='legacy-json') {
      try {
        const permissions=await IOUtils.readJSON(PathUtils.join(profile,'extension-preferences.json'));
        result.privatePermissionDisk=!!permissions[id]?.permissions?.includes('internal:privateBrowsingAllowed');
      } catch(error) {
        if(error.name==='NotFoundError')result.privatePermissionDisk=false;else throw error;
      }
    }
    const database=await IOUtils.readJSON(PathUtils.join(profile,'extensions.json'));
    result.database=database.addons.filter(item=>item.id===id).map(item=>({id:item.id,version:item.version,
      active:item.active,userDisabled:item.userDisabled,pendingUninstall:item.pendingUninstall}));
    const disk=await IOUtils.readJSON(PathUtils.join(profile,'addonStartup.json.lz4'),{decompress:true});
    result.cache=Object.entries(disk).flatMap(([location,data])=>{
      const record=data.addons?.[id];return record?[{location,enabled:record.enabled,version:record.version}]:[];
    });
  } catch(error) {result.errors.push(String(error));}
  return result;
})();
"""
PREFS_JS = g.PREFS_JS.replace("const names = [", "const names = [" + ",".join(json.dumps(name) for name in [
    "xpinstall.signatures.required", "extensions.update.enabled", "extensions.update.url",
    "extensions.allowPrivateBrowsingByDefault", "extensions.webextensions.userScripts.enabled"]) + ",")
PAGE_JS = "return JSON.parse(document.getElementById('addon-state').textContent);"
FIXTURE_JS = r"""
const config=JSON.parse(document.getElementById('fixture-state').textContent);
const state={...config,loaded:false,errors:[],counts:{blocked:0,allowed:0},executions:[]};
function render(){document.getElementById('addon-state').textContent=JSON.stringify(state);}
window.fixtureScriptRan=(kind)=>{
 const script=document.currentScript;
 state.counts[kind]++;state.executions.push({kind,ready:document.readyState,src:script?.src,
   async:script?.async,defer:script?.defer});render();
};
window.addEventListener('load',async()=>{
 state.loaded=true;render();
 try {const response=await fetch('/report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(state)});
   if(!response.ok)throw new Error('Allowed report failed '+response.status);
 } catch(error){state.errors.push(String(error));render();}
});
render();
"""


class Evidence(g.Evidence):
    def __init__(self, work, run):
        self.work = Path(work); self.work.mkdir(parents=True, exist_ok=True)
        self.path = self.work / "addon-results.json"
        self.counter, self.lock = 0, threading.RLock()
        self.data = {"schema": 1, "run": run, "status": "PENDING", "acceptanceComplete": False,
                     "functionalComplete": False, "checks": [], "events": [], "artifacts": [], "pending": []}
        self.flush()

    def pending(self, criterion, reason):
        with self.lock:
            self.data["pending"].append({"criterion": criterion, "reason": reason}); self.flush()


class Fixture:
    def __init__(self, run, evidence):
        self.run, self.evidence = run, evidence
        self.cases, self.documents, self.requests = {}, {}, []
        self.lock = threading.RLock()
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args): pass

            def reply(self, data, content_type="application/json", status=200):
                raw = data.encode() if isinstance(data, str) else json.dumps(data).encode()
                self.send_response(status); self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(raw))); self.end_headers()
                try: self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError): pass

            def do_GET(self):
                parsed = urllib.parse.urlsplit(self.path); query = urllib.parse.parse_qs(parsed.query)
                case_id = query.get("case", [None])[0]
                if query.get("run") != [owner.run] or case_id not in owner.cases:
                    return self.reply({"error": "unknown fixture identity"}, status=404)
                if parsed.path == "/addon-probe":
                    document_id = secrets.token_hex(16)
                    meta = {"run": owner.run, "caseId": case_id, "documentId": document_id,
                            "origin": owner.origin, "url": owner.url(case_id)}
                    row = dict(meta, kind="document", at=time.time())
                    with owner.lock:
                        owner.documents[document_id] = meta; owner.requests.append(row)
                    owner.evidence.event("parser-document-request", row)
                    suffix = "?" + urllib.parse.urlencode({"run": owner.run, "case": case_id, "doc": document_id})
                    html = '<!doctype html><meta charset="utf-8"><title>Add-on parser fixture</title>' + \
                        '<pre id="fixture-state">' + json.dumps(meta) + '</pre><pre id="addon-state"></pre>' + \
                        '<pre id="frame-state"></pre><pre id="fixture-error"></pre><script>' + FIXTURE_JS + '</script>' + \
                        '<script src="' + BLOCKED_PATH + suffix + '"></script><script src="' + ALLOWED_PATH + suffix + '"></script>'
                    return self.reply(html, "text/html; charset=utf-8")
                document_id = query.get("doc", [None])[0]
                meta = owner.documents.get(document_id)
                if not meta or meta["caseId"] != case_id or parsed.path not in (BLOCKED_PATH, ALLOWED_PATH):
                    return self.reply({"error": "unknown parser resource"}, status=404)
                kind = "blocked" if parsed.path == BLOCKED_PATH else "allowed"
                row = dict(meta, kind=kind, at=time.time())
                with owner.lock: owner.requests.append(row)
                owner.evidence.event("parser-resource-request", row)
                self.reply('window.fixtureScriptRan(' + json.dumps(kind) + ');', "application/javascript")

            def do_POST(self):
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if self.path != "/report" or not 0 < size < 30000: raise ValueError()
                    body = json.loads(self.rfile.read(size)); meta = owner.documents.get(body.get("documentId"))
                    if not meta or any(body.get(key) != value for key, value in meta.items()): raise ValueError()
                    row = dict(body, kind="report", at=time.time())
                    with owner.lock:
                        owner.requests.append(row); owner.documents[body["documentId"]]["registeredAt"] = time.time()
                    owner.evidence.event("parser-report-request", row)
                    self.reply({"ok": True})
                except (ValueError, TypeError, KeyError): self.reply({"error": "invalid parser report"}, status=400)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]; self.origin = f"http://127.0.0.1:{self.port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def case(self, label):
        case_id = label + "-" + secrets.token_hex(8); self.cases[case_id] = label; return case_id

    def url(self, role, child=None):
        require(child is None and role in self.cases, "Unknown parser fixture case")
        return self.origin + "/addon-probe?" + urllib.parse.urlencode({"run": self.run, "case": role})

    def close(self): self.server.shutdown(); self.server.server_close()


class AddonUI(g.UI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self.remote = self.remote.replace("graphics", "addon")

    def open_addon(self, scheme):
        self.shell("am", "start", "-a", "android.intent.action.VIEW", "-d", scheme + "://settings_addon_manager", self.package)
        self.wait(rid="add_ons_list", label="real-addon-manager")
        xml, _ = self.wait(rid="add_on_name", text=ADDON_NAME, label="exact-addon-name")
        root = g.parse_ui(xml); parents = {child: parent for parent in root.iter() for child in parent}
        name = next(node for node in root.iter("node") if node.get("text") == ADDON_NAME and
                    g.resource_matches(node.get("resource-id", ""), "add_on_name") and node.get("package") == self.package)
        row = name
        while row in parents and not g.resource_matches(row.get("resource-id", ""), "add_on_content_wrapper"):
            row = parents[row]
        require(g.resource_matches(row.get("resource-id", ""), "add_on_content_wrapper"), "Add-on name has no exact content wrapper")
        subtree = "<hierarchy>" + ET.tostring(row, encoding="unicode") + "</hierarchy>"
        self.tap(ui_node(subtree, "add_on_content_wrapper", self.package), "open-ordinary-ubo-controls")
        self.wait(rid="enable_switch", label="installed-addon-controls")
        return self.dump("before-addon-choice", screenshot=True)

    def choose_then_stop(self, action, value, scheme):
        before = self.open_addon(scheme)
        g.select_node(before, text=ADDON_NAME, package=self.package)
        rid = {"enabled": "enable_switch", "private": "allow_in_private_browsing_switch", "remove": "remove_add_on"}[action]
        target = ui_node(before, rid, self.package)
        require(target.get("clickable") == "true", "Add-on control is not interactive before the choice")
        if action != "remove":
            require(target.get("checked") == str(not value).lower(), "Add-on control did not start in the opposite state")
        timing = {"actionStarted": time.monotonic(), "acknowledged": False}
        self.tap(target, "real-addon-" + action + "-" + str(value))
        captured, ack = [], None
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            # No artifact writes, screenshots or registry reads in this interval.
            self.remote_used = True
            self.shell("uiautomator", "dump", "--compressed", self.remote, timeout=45)
            xml = self.shell("cat", self.remote)
            captured.append(xml)
            try: ack = grade_ui_ack(xml, action=action, value=value, package=self.package)
            except Failure: continue
            timing.update(ackObserved=time.monotonic(), acknowledged=True, stopIssued=time.monotonic())
            self.shell("am", "force-stop", self.package)
            timing["stopCompleted"] = time.monotonic()
            break
        # Preserve every actual response even when the UI failed to acknowledge.
        for index, xml in enumerate(captured): self.evidence.artifact("choice-" + action + "-" + str(index), xml, "xml")
        self.evidence.event("ui-choice-stop", {"action": action, "value": value, "timing": timing, "ack": ack})
        require(ack is not None, "Actual add-on UI never acknowledged the choice; state was not repaired")
        return timing


class Runner(g.Runner):
    def __init__(self, args, evidence, protocol, adb):
        super().__init__(args, evidence, protocol, adb)
        evidence.data.pop("pixelChallenge", None)
        self.ui = AddonUI(adb, args.package, evidence, evidence.data["run"], args.ui_timeout, not args.no_screenshots)
        self.case_id = None; self.connected_at = None

    def prerequisite(self):
        if not self.args.apk or not self.args.apk.is_file(): raise Pending("Supply the exact already installed release APK")
        present = self.adb.run("shell", shlex.join(["pm", "path", self.args.package]), timeout=30)
        if present.returncode or "package:" not in present.stdout: raise Pending("Installed package is absent; no installation is performed")
        super().prerequisite()
        self.bundle = bundle_evidence(self.args.apk)
        self.evidence.data["bundle"] = self.bundle; self.evidence.flush()

    def start_fixtures(self):
        self.fixture = Fixture(self.evidence.data["run"], self.evidence); self.fixtures = [self.fixture]
        self.adb.run("reverse", "--no-rebind", f"tcp:{self.fixture.port}", f"tcp:{self.fixture.port}", check=True, timeout=30)
        self.reversed_ports.append(self.fixture.port)
        self.forward_port = self.args.marionette_port
        if self.forward_port is None:
            with socket.socket() as sock: sock.bind(("127.0.0.1", 0)); self.forward_port = sock.getsockname()[1]
            self.adb.run("forward", "--no-rebind", f"tcp:{self.forward_port}", f"tcp:{self.args.device_marionette_port}", check=True, timeout=30)
            self.forward_created = True
        self.evidence.event("fixture-origin", {"origin": self.fixture.origin})

    def connect(self):
        self.connected_at = time.time()  # Upper boundary is connection attempt, not later registry observation.
        super().connect()

    def facts(self):
        prefs = self.marionette.script(PREFS_JS, chrome=True)
        self.evidence.event("effective-preferences", {"preferences": prefs})
        values = {item["name"]: item["value"] for item in prefs}
        require(values.get("xpinstall.signatures.required") is True, "Add-on signature enforcement is disabled")
        config = self.shell("cat", f"/data/local/tmp/{self.args.package}-geckoview-config.yaml")
        require(g.transport_config_facts(config)["transportOnly"], "Transport gained policy/test injection")
        return values

    def open_case(self, label, private=False, connect=False):
        self.case_id = self.fixture.case(label)
        return super().open(self.fixture, role=self.case_id, private=private, connect=connect)

    def observe(self, label, *, installed=True, enabled=True, private_allowed=False, first=False):
        current = self.snapshot(); page = self.marionette.script(PAGE_JS)
        with self.fixture.lock: requests = [row.copy() for row in self.fixture.requests]
        raw = self.marionette.script(STATE_JS, [ADDON_ID], chrome=True)
        self.evidence.artifact(label + "-observations", json.dumps({"page": page, "requests": requests, "addon": raw}, indent=2), "json")
        grade_state(raw, installed=installed, enabled=enabled, private_allowed=private_allowed, version=self.bundle["pin"]["version"])
        blocked = installed and enabled and (not self.private or private_allowed)
        navigation = grade_navigation(page, requests, run=self.evidence.data["run"], case_id=self.case_id,
            document_id=current["document"]["documentId"], origin=self.fixture.origin, blocked=blocked,
            before_connect=self.connected_at if first else None)
        require(self.snapshot()["document"]["documentId"] == current["document"]["documentId"], "Document changed during state observation")
        self.evidence.check(label, {"private": self.private, "addon": raw, "navigation": navigation})
        return raw

    def resume_first_navigation(self, label, old_pid):
        require(not self.adb.run("shell", shlex.join(["pidof", self.args.package]), timeout=10).stdout.strip(),
                "Old application process did not stop")
        if self.marionette: self.marionette.close(); self.marionette = None
        self.case_id = self.fixture.case(label)
        self.active_url, self.private = self.fixture.url(self.case_id), False
        since = time.time()
        self.shell("am", "start", "-a", "android.intent.action.VIEW", "-d", self.active_url,
                   "-n", self.args.package + "/org.mozilla.fenix.IntentReceiverActivity", timeout=45)
        self.wait_fixture_navigation(self.fixture, self.active_url, since)
        with self.fixture.lock:
            pages = [row.copy() for row in self.fixture.requests if row["kind"] == "document" and row["at"] >= since]
        require(pages and pages[0]["url"] == self.active_url, "Another fixture page loaded before the intended first navigation")
        self.connect(); self.snapshot()
        new_pid = self.shell("pidof", self.args.package).strip()
        require(bool(new_pid) and new_pid != old_pid, "A different app process was not observed")
        self.facts()
        self.evidence.check("real-process-restart", {"oldPid": old_pid, "newPid": new_pid, "firstFixtureUrl": self.active_url})

    def choice_restart(self, action, value, label):
        old_pid = self.shell("pidof", self.args.package).strip(); require(bool(old_pid), "No old app process")
        timing = self.ui.choose_then_stop(action, value, self.args.scheme)
        try: self.evidence.check("immediate-" + label, grade_timing(timing))
        except Pending as error: self.evidence.pending("immediate-" + label, str(error))
        self.resume_first_navigation(label, old_pid)

    def run(self):
        self.prerequisite(); self.start_fixtures()
        self.open_case("initial", connect=True); self.facts()
        initial = self.marionette.script(STATE_JS, [ADDON_ID], chrome=True)
        private_allowed = initial.get("privatePermission")
        require(type(private_allowed) is bool, "Initial private permission is unknown")
        self.observe("initial-normal", private_allowed=private_allowed, first=True)
        self.choice_restart("enabled", False, "disabled-normal")
        self.observe("disabled-normal", enabled=False, private_allowed=private_allowed, first=True)
        self.choice_restart("enabled", True, "enabled-normal")
        self.observe("enabled-normal", private_allowed=private_allowed, first=True)
        for allowed in (not private_allowed, private_allowed):
            label = "private-allowed" if allowed else "private-denied"
            self.choice_restart("private", allowed, label)
            self.observe(label + "-normal", private_allowed=allowed, first=True)
            require(self.marionette.script(g.PRIVATE_WINDOWS_JS, chrome=True) == 0, "Existing private tabs prevent an isolated private test")
            self.open_case(label, private=True)
            self.observe(label + "-private", private_allowed=allowed)
            self.close_private()
        # Update needs separately prepared signed versions and a real completion
        # route. A no-update result or API-only operation must never count here.
        self.evidence.pending("signed-update", "No reproducible signed older-to-newer UI update fixture has been executed; see source audit")
        self.choice_restart("remove", None, "removed-normal")
        self.observe("removed-normal", installed=False, enabled=False, first=True)
        self.open_case("removed-private", private=True)
        self.observe("removed-private", installed=False, enabled=False)
        self.close_private()
        old_pid = self.shell("pidof", self.args.package).strip()
        self.shell("am", "force-stop", self.args.package)
        self.resume_first_navigation("removed-second-restart", old_pid)
        self.observe("removed-second-restart", installed=False, enabled=False, first=True)
        for item in self.evidence.data["installed"]["apk"]:
            require(self.shell("sha256sum", item["path"]).strip().split()[0] == item["sha256"], "Installed APK changed during the run")
        completed = {item["name"] for item in self.evidence.data["checks"]}
        self.evidence.data["functionalComplete"] = not (REQUIRED - {"signed-update"} - completed)
        self.evidence.flush()
        missing = sorted(REQUIRED - completed)
        if missing or self.evidence.data["pending"]: raise Pending("Add-on acceptance incomplete: " + ", ".join(missing))
        self.evidence.finish("PASS", "All real add-on lifecycle and signed-update criteria passed", True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default=shutil.which("adb")); parser.add_argument("--serial")
    parser.add_argument("--package", default="org.redoubtbrowser"); parser.add_argument("--apk", type=Path)
    parser.add_argument("--work", type=Path, default=Path.home()/".cache/redoubt-addon-smoke")
    parser.add_argument("--dedicated-test-profile", action="store_true")
    parser.add_argument("--scheme", default="redoubt")
    parser.add_argument("--marionette-port", type=int); parser.add_argument("--device-marionette-port", type=int, default=2828)
    parser.add_argument("--connect-timeout", type=int, default=60); parser.add_argument("--ui-timeout", type=int, default=25)
    parser.add_argument("--no-screenshots", action="store_true")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.]+", args.package) or not re.fullmatch(r"[a-z][a-z0-9+.-]*", args.scheme):
        parser.error("Invalid package or app scheme")
    if min(args.connect_timeout, args.ui_timeout) <= 0 or any(port is not None and not 1 <= port <= 65535
            for port in (args.marionette_port, args.device_marionette_port)): parser.error("Invalid timeout or port")
    run = secrets.token_hex(8); evidence = Evidence(args.work/run, run)
    evidence.data["inputs"] = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
        ["scripts/android-addon-state-smoke.py", "scripts/android-graphics-smoke.py", "assets/ubo-extension.json",
         "docs/android/evidence/lw-m7-19/source-files.json"]}
    runner, status = None, PENDING
    try:
        if not args.adb or not shutil.which(args.adb): raise Pending("adb unavailable; no lifecycle was tested")
        if not args.dedicated_test_profile: raise Pending("Real add-on choices/removal require a dedicated test profile")
        protocol = g.foundation(); adb = protocol.Adb(args.adb, args.serial); devices = adb.devices()
        if args.serial and args.serial not in devices: raise Pending("Requested device is not connected and authorized")
        if not args.serial:
            if len(devices) != 1: raise Pending("Select one connected and authorized device")
            adb.serial = devices[0]
        runner = Runner(args, evidence, protocol, adb); runner.run()
        if evidence.data["status"] != "PASS" or evidence.data["acceptanceComplete"] is not True:
            raise Pending("Runner returned without complete add-on acceptance evidence")
        status = PASS
    except Pending as error: evidence.finish("PENDING", str(error))
    except Exception as error: evidence.finish("FAIL", str(error)); status = FAIL
    except KeyboardInterrupt: evidence.finish("PENDING", "Interrupted before complete add-on acceptance")
    finally:
        if runner:
            if status != PASS: runner.diagnostics()
            try: runner.close()
            except Exception as error:
                evidence.event("cleanup-error", {"error": str(error)})
                if status == PASS: evidence.finish("FAIL", "Cleanup failed"); status = FAIL
    print(json.dumps({"status": evidence.data["status"], "acceptanceComplete": evidence.data["acceptanceComplete"],
        "functionalComplete": evidence.data["functionalComplete"],
        "passedChecks": len(evidence.data["checks"]), "pending": evidence.data["pending"],
        "reason": evidence.data["reason"], "report": str(evidence.path)}))
    return status


if __name__ == "__main__": sys.exit(main())
