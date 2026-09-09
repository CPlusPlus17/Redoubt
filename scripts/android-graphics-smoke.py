#!/usr/bin/env python3
"""Installed-release graphics acceptance through real Fenix permission controls.

Consumes an already enabled Marionette transport. Never installs/wipes an app,
writes debug configuration, changes preferences, or writes engine permissions.
Run only on a dedicated test profile: full coverage restarts the app and opens /
closes private tabs. Device/runtime absence is PENDING (3), never PASS (0).
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
import types
import urllib.parse
import xml.etree.ElementTree as ET

PASS, FAIL, PENDING = 0, 1, 3
SIZE = 32
MODES = ("dom", "offscreen", "worker", "nested-worker", "transferred-worker")
OPERATIONS = ("webgl", "webgl2", "canvas")
KINDS = ("webgl", "canvas")
ROOT = Path(__file__).resolve().parents[1]


class Pending(RuntimeError):
    """An explicit prerequisite or requested coverage is missing."""


class Failure(RuntimeError):
    """An exercised acceptance condition failed."""


def require(condition, message):
    if not condition:
        raise Failure(message)


def foundation(path=None):
    """Reuse only the embedded protocol classes, not the old runner/app lifecycle.

    AST selection prevents an old/new harness main, debug-config setup or other
    top-level expressions from executing. The hash binds the protocol input.
    """
    path = Path(path or ROOT / "scripts/android-smoke.sh")
    raw = path.read_text()
    begin, end = "<<'PYDRIVEREOF'\n", "\nPYDRIVEREOF"
    if raw.count(begin) != 1:
        raise Pending("Cannot identify the existing embedded smoke protocol")
    embedded = raw.split(begin, 1)[1].split(end, 1)[0]
    names = {"HarnessError", "Adb", "Marionette", "MarionetteError"}
    parsed = ast.parse(embedded, str(path))
    definitions = [node for node in parsed.body
                   if isinstance(node, ast.ClassDef) and node.name in names]
    if {node.name for node in definitions} != names:
        raise Pending("Embedded smoke protocol classes changed; integration is required")
    imports = [node for node in parsed.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    module = types.ModuleType("lw_graphics_transport")
    exec(compile(ast.Module(body=imports + definitions, type_ignores=[]), str(path), "exec"),
         module.__dict__)
    module.input_sha256 = hashlib.sha256(embedded.encode()).hexdigest()
    return module


def window_handles(marionette):
    # GetWindowHandles is explicitly a no-value-wrapper command in Marionette's
    # server. ExecuteScript uses a value wrapper; do not change the shared codec.
    handles = marionette.cmd("WebDriver:GetWindowHandles")
    require(isinstance(handles, list)
            and all(isinstance(handle, str) and handle for handle in handles)
            and len(set(handles)) == len(handles),
            "Marionette returned invalid window handles: " + repr(handles))
    return handles


def canonical_origin(value):
    try:
        uri = urllib.parse.urlsplit(value)
        if uri.scheme not in ("http", "https") or not uri.hostname or uri.username or uri.password:
            raise ValueError()
        port = uri.port
        host = uri.hostname.lower()
        if ":" in host:
            host = "[" + host + "]"
        if port and port != (80 if uri.scheme == "http" else 443):
            host += ":" + str(port)
        return uri.scheme + "://" + host
    except (TypeError, ValueError):
        raise Failure("Invalid website origin in evidence") from None


def text_origins(text):
    # Match whole address tokens. A prefix match confuses :8000 with :80001,
    # or example.test with example.test.evil, and must never pick a consent row.
    values = set()
    for item in re.findall(r"https?://[^\s<>\"']+", text or ""):
        try:
            values.add(canonical_origin(item.rstrip(",;)")))
        except Failure:
            pass
    return values


def resource_matches(actual, wanted):
    return actual == wanted or actual.endswith(":id/" + wanted)


def parse_ui(xml):
    start = xml.find("<?xml")
    if start < 0:
        start = xml.find("<hierarchy")
    if start < 0:
        raise Failure("uiautomator did not return an XML hierarchy")
    try:
        return ET.fromstring(xml[start:])
    except ET.ParseError as error:
        raise Failure("Malformed uiautomator hierarchy: " + str(error)) from error


def select_node(xml, *, rid=None, text=None, origin=None, description=None, package=None, class_name=None, focused=None, required=True):
    tree = parse_ui(xml)
    selected = []
    for node in tree.iter("node"):
        if package and node.get("package") != package:
            continue
        if class_name and node.get("class") != class_name:
            continue
        if focused is not None and (node.get("focused") == "true") != focused:
            continue
        if node.get("enabled", "true") != "true" or node.get("visible-to-user", "true") != "true":
            continue
        if rid and not resource_matches(node.get("resource-id", ""), rid):
            continue
        if text is not None and node.get("text", "") != text:
            continue
        if description is not None and node.get("content-desc", "") != description:
            continue
        if origin is not None and canonical_origin(origin) not in text_origins(node.get("text", "")):
            continue
        bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
        if not bounds:
            continue
        left, top, right, bottom = map(int, bounds.groups())
        if right <= left or bottom <= top:
            continue
        selected.append(dict(node.attrib, centre=((left + right) // 2, (top + bottom) // 2)))
    if len(selected) > 1:
        raise Failure(f"Ambiguous UI selection: {len(selected)} matches for {rid or text or description}, origin={origin}")
    if selected:
        return selected[0]
    if required:
        raise Failure(f"Missing visible UI control {rid or text or description}, origin={origin}")
    return None



# Exact English post-installation notice captured from the release APK. Its
# native OK callback only consumes the completed prompt and dismisses it.
# An extension permission/data-choice dialog is deliberately not recognized.
UBO_ADDED_TITLE = "uBlock Origin was added"
UBO_ADDED_DESCRIPTION = "Update permissions and data preferences any time in the extension settings."


def ubo_added_notice(xml, package):
    """Return only the unique native installed-notice OK, never a generic OK."""
    expected = {
        "icon": ("android.widget.ImageView", "", "false"),
        "title": ("android.widget.TextView", UBO_ADDED_TITLE, "false"),
        "description": ("android.widget.TextView", UBO_ADDED_DESCRIPTION, "false"),
        "confirm_button": ("android.widget.Button", "OK", "true"),
    }
    matches = []
    for container in parse_ui(xml).iter("node"):
        if container.get("package") != package or container.get("class") != "android.widget.RelativeLayout":
            continue
        children = list(container)
        if len(children) != len(expected) or any(list(child) for child in children):
            continue
        by_id = {child.get("resource-id"): child for child in children}
        if set(by_id) != {package + ":id/" + name for name in expected}:
            continue
        if any(child.get("package") != package or child.get("class") != class_name or
               child.get("text", "") != text or child.get("clickable") != clickable or
               child.get("checkable") != "false" or child.get("enabled") != "true" or
               child.get("visible-to-user", "true") != "true"
               for name, (class_name, text, clickable) in expected.items()
               for child in [by_id[package + ":id/" + name]]):
            continue
        if container.get("enabled", "true") != "true" or container.get("visible-to-user", "true") != "true":
            continue
        button = select_node("<hierarchy>" + ET.tostring(container, encoding="unicode") + "</hierarchy>",
                             package=package,
                             rid=package + ":id/confirm_button", class_name="android.widget.Button",
                             text="OK", required=False)
        if button:
            matches.append(button)
    require(len(matches) <= 1, "Ambiguous uBlock Origin installed notice")
    return matches[0] if matches else None


def transport_config_facts(body):
    """Accept only the established transport-only config; report no secret values."""
    lines = [line.strip() for line in body.splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    expected = ['args:', '- "-remote-allow-system-access"', 'env:', 'MOZ_MARIONETTE: "1"',
                'prefs:', 'remote.prefs.recommended: false']
    valid = len(lines) == 7 and lines[:6] == expected and bool(
        re.fullmatch(r"marionette\.port: [1-9][0-9]{0,4}", lines[6]))
    port = int(lines[6].split(":", 1)[1]) if valid else None
    valid = bool(valid and 1 <= port <= 65535)
    return {"sha256": hashlib.sha256(body.encode()).hexdigest(), "marionettePort": port,
            "transportOnly": valid, "nonemptyLines": len(lines),
            "reason": "exact transport-only allowlist" if valid else
            "missing/extra/changed config entries; acceptance is tainted"}


def expected_pixels(colors):
    require(len(colors) == 4 and all(len(color) == 4 for color in colors), "Bad pixel challenge")
    return bytes(channel for y in range(SIZE) for x in range(SIZE)
                 for channel in colors[(2 if y >= SIZE // 2 else 0) + (1 if x >= SIZE // 2 else 0)])


def grade_probe(result, *, operation, mode, origin, document_id, command_id, colors,
                context_allowed, readback_allowed):
    """Grade actual returned bytes against an independently computed challenge."""
    require(isinstance(result, dict), "Missing graphics result")
    require(result.get("commandId") == command_id, "Wrong/stale command result")
    require(result.get("documentId") == document_id, "Result belongs to another document")
    require(result.get("origin") == canonical_origin(origin), "Result belongs to another origin")
    require(result.get("operation") == operation and result.get("mode") == mode,
            "Wrong operation or worker mode")
    require(not result.get("error"), "Graphics operation error: " + str(result.get("error")))
    require(type(result.get("context")) is bool, "No actual context result")
    if operation != "canvas" and not context_allowed:
        require(result["context"] is False, "Unconsented WebGL context was created")
        require(result.get("pixels") is None, "Blocked context returned fabricated pixel evidence")
        return {"context": False, "protected": True, "actualPixels": False}
    require(result["context"] is True, "Expected drawable context was not created")
    pixels = result.get("pixels")
    require(isinstance(pixels, list) and len(pixels) == SIZE * SIZE * 4,
            "Missing/full-size readback is not evidence of protection")
    require(all(type(value) is int and 0 <= value <= 255 for value in pixels), "Invalid RGBA bytes")
    actual, expected = bytes(pixels), expected_pixels(colors)
    matches = actual == expected
    require(matches == readback_allowed,
            "Actual pixels leaked before consent" if matches else "Matching consent did not restore actual pixels")
    return {"context": True, "actualPixels": matches, "protected": not matches,
            "bytes": len(actual), "actualSha256": hashlib.sha256(actual).hexdigest(),
            "expectedSha256": hashlib.sha256(expected).hexdigest()}


# This script is parser-inserted by the fixture. Graphics operations never run
# inside a privileged Marionette sandbox, which could trigger native exemptions.
FIXTURE_JS = r"""
const config = JSON.parse(document.getElementById('fixture-config').textContent);
const documentId = Array.from(crypto.getRandomValues(new Uint8Array(16)), n => n.toString(16).padStart(2,'0')).join('');
const metadata = {run:config.run, documentId, origin:location.origin, url:location.href, role:config.role};
document.getElementById('fixture-state').textContent = JSON.stringify(metadata);
function paint(canvas, operation, colors) {
  canvas.width = canvas.height = 32;
  const context = operation === 'canvas' ? canvas.getContext('2d') : canvas.getContext(operation, {preserveDrawingBuffer:true});
  if (!context) return {context:false, pixels:null};
  if (operation === 'canvas') {
    for (let index=0; index<4; index++) {
      const color=colors[index]; context.fillStyle=`rgba(${color[0]},${color[1]},${color[2]},1)`;
      context.fillRect((index%2)*16,Math.floor(index/2)*16,16,16);
    }
    return {context:true, pixels:Array.from(context.getImageData(0,0,32,32).data)};
  }
  context.enable(context.SCISSOR_TEST);
  for (let index=0; index<4; index++) {
    const color=colors[index]; context.scissor((index%2)*16,Math.floor(index/2)*16,16,16);
    context.clearColor(color[0]/255,color[1]/255,color[2]/255,1); context.clear(context.COLOR_BUFFER_BIT);
  }
  context.disable(context.SCISSOR_TEST);
  const pixels=new Uint8Array(32*32*4);
  context.readPixels(0,0,32,32,context.RGBA,context.UNSIGNED_BYTE,pixels);
  return {context:true,pixels:Array.from(pixels)};
}
function workerProbe(operation, colors, nested, transfer) {
  return new Promise((resolve,reject) => {
    const source = `${paint.toString()}\n${workerProbe.toString()}\nonmessage = async e => {try {
      const r = e.data.nested ? await workerProbe(e.data.operation,e.data.colors,false,false) :
        paint(e.data.canvas || new OffscreenCanvas(32,32),e.data.operation,e.data.colors);
      postMessage(r);
    } catch(error) {postMessage({error:String(error)});}};`;
    const url=URL.createObjectURL(new Blob([source],{type:'text/javascript'}));
    const worker=new Worker(url);
    const timer=setTimeout(() => {worker.terminate();URL.revokeObjectURL(url);reject(new Error('worker timeout'));},15000);
    worker.onmessage=e => {clearTimeout(timer);worker.terminate();URL.revokeObjectURL(url);resolve(e.data);};
    worker.onerror=e => {clearTimeout(timer);worker.terminate();URL.revokeObjectURL(url);reject(new Error(e.message));};
    if (transfer) {
      const canvas=document.createElement('canvas').transferControlToOffscreen();
      worker.postMessage({operation,colors,nested,canvas},[canvas]);
    } else worker.postMessage({operation,colors,nested});
  });
}
async function probe(command) {
  let result;
  try {
    if (command.mode.includes('worker')) result = await workerProbe(command.operation,command.colors,
      command.mode === 'nested-worker', command.mode === 'transferred-worker');
    else result = paint(command.mode === 'dom' ? document.createElement('canvas') : new OffscreenCanvas(32,32),
      command.operation, command.colors);
  } catch(error) { result={error:String(error)}; }
  return {...metadata,...result,commandId:command.commandId,operation:command.operation,mode:command.mode};
}
async function poll() {
  try {
    const response=await fetch(`/next?run=${config.run}&document=${documentId}`,{cache:'no-store'});
    const command=await response.json();
    if (command) {
      const result=await probe(command);
      await fetch('/result',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(result)});
    }
  } catch(error) { document.getElementById('fixture-error').textContent=String(error); }
  setTimeout(poll,100);
}
fetch('/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(metadata)}).then(poll);
if (config.child) {
  const frame=document.createElement('iframe'); frame.id='fixture-frame'; frame.src=config.child;
  window.addEventListener('message', event => {
    if (event.source===frame.contentWindow && event.origin===new URL(config.child).origin &&
        event.data?.run===config.run) document.getElementById('frame-state').textContent=JSON.stringify(event.data);
  });
  document.body.appendChild(frame);
}
if (parent !== window) parent.postMessage(metadata,'*');
"""


class Fixture:
    def __init__(self, run, evidence, host="localhost"):
        self.run, self.evidence, self.host = run, evidence, host
        self.documents, self.commands, self.results = {}, {}, {}
        self.lock = threading.Lock()
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def reply(self, value, status=200, content_type="application/json"):
                body = value if isinstance(value, bytes) else json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                parsed = urllib.parse.urlsplit(self.path)
                args = urllib.parse.parse_qs(parsed.query)
                if args.get("run") != [owner.run]:
                    return self.reply({"error": "wrong run"}, 404)
                if parsed.path == "/next":
                    with owner.lock:
                        pending = owner.commands.get(args.get("document", [None])[0], [])
                        command = pending.pop(0) if pending else None
                    return self.reply(command)
                if parsed.path != "/graphics":
                    return self.reply({"error": "unknown fixture"}, 404)
                config = {"run": owner.run, "role": args.get("role", ["top"])[0],
                          "child": args.get("child", [None])[0]}
                content = ("<!doctype html><meta charset=utf-8><title>Redoubt graphics " + owner.run +
                           "</title><h1>Graphics acceptance fixture</h1><pre id=fixture-state></pre>"
                           "<pre id=frame-state></pre><pre id=fixture-error></pre>"
                           "<script id=fixture-config type=application/json>" +
                           json.dumps(config).replace("<", "\\u003c") + "</script><script>" +
                           FIXTURE_JS + "</script>").encode()
                owner.evidence.event("fixture-document", {"port": owner.port, "path": self.path})
                self.reply(content, content_type="text/html; charset=utf-8")

            def do_POST(self):
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 100000:
                        return self.reply({"error": "invalid size"}, 400)
                    data = json.loads(self.rfile.read(length))
                    if data.get("run") != owner.run:
                        return self.reply({"error": "wrong run"}, 404)
                    if data.get("origin") != owner.origin:
                        return self.reply({"error": "wrong origin"}, 400)
                    with owner.lock:
                        if self.path == "/register":
                            owner.documents[data["documentId"]] = dict(data, registeredAt=time.time())
                        elif self.path == "/result":
                            key = data["commandId"]
                            if key in owner.results:
                                return self.reply({"error": "duplicate result"}, 409)
                            owner.results[key] = data
                        else:
                            return self.reply({"error": "unknown route"}, 404)
                    self.reply({"ok": True})
                except (KeyError, TypeError, ValueError):
                    self.reply({"error": "invalid fixture response"}, 400)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.origin = f"http://{host}:{self.port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def url(self, role="top", child=None):
        query = {"run": self.run, "role": role}
        if child:
            query["child"] = child
        return self.origin + "/graphics?" + urllib.parse.urlencode(query)

    def issue(self, document_id, operation, mode, colors, timeout=25):
        command_id = secrets.token_hex(12)
        command = {"commandId": command_id, "operation": operation, "mode": mode, "colors": colors}
        with self.lock:
            require(document_id in self.documents, "The actual fixture did not register this document")
            self.commands.setdefault(document_id, []).append(command)
        self.evidence.event("fixture-command", {"documentId": document_id, **command})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self.lock:
                result = self.results.pop(command_id, None)
            if result is not None:
                return command_id, result
            time.sleep(0.1)
        raise Failure(f"No real fixture result for {operation}/{mode}; cannot call missing readback protected")

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class Evidence:
    def __init__(self, work, run, suite):
        self.work = Path(work)
        self.work.mkdir(parents=True, exist_ok=True)
        self.path = self.work / "graphics-results.json"
        self.counter = 0
        self.lock = threading.RLock()
        self.data = {"schema": 1, "run": run, "suite": suite, "status": "PENDING",
                     "acceptanceComplete": False, "checks": [], "events": [], "artifacts": []}
        self.flush()

    def flush(self):
        with self.lock:
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.data, indent=2) + "\n")
            os.replace(temporary, self.path)

    def event(self, name, detail):
        with self.lock:
            self.data["events"].append({"event": name, "at": time.time(), **detail})
            self.flush()

    def check(self, name, detail):
        with self.lock:
            self.data["checks"].append({"name": name, "status": "PASS", "evidence": detail})
            self.flush()
        print("[graphics] PASS " + name, file=sys.stderr, flush=True)

    def artifact(self, label, content, suffix):
        with self.lock:
            self.counter += 1
            safe = re.sub(r"[^a-zA-Z0-9_.-]", "-", label)[:100]
            path = self.work / f"{self.counter:04d}-{safe}.{suffix}"
            if isinstance(content, str):
                content = content.encode()
            path.write_bytes(content)
            item = {"path": path.name, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
            self.data["artifacts"].append(item)
            self.flush()
            return item

    def finish(self, status, reason, complete=False):
        self.data.update(status=status, reason=reason, acceptanceComplete=complete)
        self.flush()


PREFS_JS = r"""
const names = ['librewolf.webgl.prompt','librewolf.webgl.prompt.hide','webgl.disabled',
 'privacy.resistFingerprinting','privacy.fingerprintingProtection','privacy.fingerprintingProtection.pbmode',
 'privacy.fingerprintingProtection.overrides','permissions.isolateBy.privateBrowsing',
 'permissions.isolateBy.userContext','dom.security.https_only_mode','network.trr.mode'];
const read=(branch,n)=>{const type=branch.getPrefType(n);return type===128?branch.getBoolPref(n):
 type===64?branch.getIntPref(n):type===32?branch.getStringPref(n):null;};
return names.map(name=>({name,value:read(Services.prefs,name),
 defaultValue:read(Services.prefs.getDefaultBranch(''),name),
 locked:Services.prefs.prefIsLocked(name),hasUserValue:Services.prefs.prefHasUserValue(name)}));
"""
PERMISSIONS_JS = r"""
const origins=arguments[0];
return Services.perms.all.filter(p=>['canvas','webgl'].includes(p.type) && origins.includes(p.principal.originNoSuffix))
 .map(p=>({origin:p.principal.originNoSuffix,principalOrigin:p.principal.origin,
 kind:p.type,value:p.capability,expireType:p.expireType,modificationTime:p.modificationTime,
 private:p.principal.privateBrowsingId!==0,contextId:p.principal.originAttributes.geckoViewSessionContextId||null}));
"""
WINDOW_JS = r"""
const p=window.browser?.browsingContext.currentWindowGlobal?.documentPrincipal;
return p?{origin:p.originNoSuffix,principalOrigin:p.origin,private:p.privateBrowsingId!==0,
 contextId:p.originAttributes.geckoViewSessionContextId||null,active:!!window.browser.docShellIsActive}:null;
"""
PRIVATE_WINDOWS_JS = r"""
return Array.from(Services.wm.getEnumerator('navigator:geckoview')).filter(w=>
 w.browser?.browsingContext.currentWindowGlobal?.documentPrincipal.privateBrowsingId>0).length;
"""
DOCUMENT_JS = r"""
const state=document.getElementById('fixture-state')?.textContent;
return state ? {document:JSON.parse(state),frame:document.getElementById('frame-state')?.textContent||null,
 error:document.getElementById('fixture-error')?.textContent||null,ready:document.readyState}:null;
"""


class UI:
    def __init__(self, adb, package, evidence, run, timeout=25, screenshots=True):
        self.adb, self.package, self.evidence = adb, package, evidence
        self.remote = "/sdcard/lw-graphics-" + run + ".xml"
        self.remote_used = False
        self.timeout, self.screenshots = timeout, screenshots

    def node(self, xml, **selector):
        return select_node(xml, package=self.package, **selector)

    def shell(self, *args, timeout=30):
        return self.adb.run("shell", shlex.join(map(str, args)), timeout=timeout, check=True).stdout

    def dump(self, label="ui", screenshot=False):
        self.remote_used = True
        self.shell("uiautomator", "dump", self.remote, timeout=45)
        xml = self.shell("cat", self.remote)
        parse_ui(xml)
        self.evidence.artifact(label, xml, "xml")
        if screenshot and self.screenshots:
            shot = subprocess.run(self.adb._argv(["exec-out", "screencap", "-p"]), capture_output=True, timeout=30)
            if shot.returncode == 0 and shot.stdout.startswith(b"\x89PNG"):
                self.evidence.artifact(label, shot.stdout, "png")
        return xml

    def wait(self, *, label="wait-control", timeout=None, **selector):
        deadline = time.monotonic() + (timeout or self.timeout)
        while True:
            xml = self.dump(label)
            node = self.node(xml, required=False, **selector)
            if node:
                return xml, node
            if time.monotonic() >= deadline:
                raise Failure(f"Visible Fenix control did not appear: {selector}")
            time.sleep(0.25)

    def tap(self, node, label, long=False):
        x, y = node["centre"]
        self.evidence.event("ui-action", {"action": "long-press" if long else "tap", "label": label,
            "resourceId": node.get("resource-id"), "text": node.get("text"), "centre": [x, y]})
        if long:
            self.shell("input", "swipe", x, y, x, y, 750)
        else:
            self.shell("input", "tap", x, y)

    def click(self, *, label="click-control", **selector):
        _xml, node = self.wait(label=label, **selector)
        self.tap(node, label)
        return node

    def back(self):
        self.shell("input", "keyevent", "4")

    def acknowledge_ubo_added_notice(self, xml):
        button = ubo_added_notice(xml, self.package)
        if button is None:
            return xml
        self.tap(button, "acknowledge-ubo-installed-notice")
        # Tap once. Only the read-only disappearance wait may retry; the fresh
        # hierarchy is returned to the unchanged permission/quiet assertions.
        deadline = time.monotonic() + self.timeout
        while True:
            xml = self.dump("after-ubo-installed-notice", screenshot=True)
            title_present = any(node.get("package") == self.package and
                                node.get("resource-id") == self.package + ":id/title" and
                                node.get("text") == UBO_ADDED_TITLE
                                for node in parse_ui(xml).iter("node"))
            if not title_present:
                return xml
            if time.monotonic() >= deadline:
                raise Failure("uBlock Origin installed notice did not close after its OK action")
            time.sleep(0.25)

    def close_permissions(self):
        # Close only known permission/trust panels, never send blind Back to a page.
        for _ in range(4):
            xml = self.dump("close-permissions")
            if self.node(xml, rid="origin_permission_allow", required=False) or \
               self.node(xml, rid="origin_permission_reload", required=False):
                raise Failure("A permission decision/reload dialog was unexpectedly still open")
            if self.node(xml, rid="origin_permissions_dialog_list", required=False):
                self.click(text="Close", label="close-permission-list")
            elif self.node(xml, rid="origin_permissions_entry", required=False):
                self.back()
            else:
                return
        raise Failure("Permission controls did not close")

    def open_permissions(self):
        xml = self.dump("before-open-permissions", screenshot=True)
        xml = self.acknowledge_ubo_added_notice(xml)
        if self.node(xml, rid="origin_permissions_dialog_list", required=False):
            return
        entry = self.node(xml, rid="origin_permissions_entry", required=False)
        if not entry:
            notice = self.node(xml, text="Review", required=False)
            if notice:
                self.tap(notice, "quiet-review")
                self.wait(rid="origin_permissions_dialog_list", label="quiet-review-list")
                return
            for rid in ("mozac_browser_toolbar_tracking_protection_indicator",
                        "mozac_browser_toolbar_site_info_indicator"):
                indicator = self.node(xml, rid=rid, required=False)
                if indicator:
                    self.tap(indicator, "open-site-controls")
                    break
            else:
                indicator = self.node(xml, description="Site information", required=False)
                if not indicator:
                    raise Failure("No quiet Review action or real Fenix site-info control was visible")
                self.tap(indicator, "open-site-information")
        self.click(rid="origin_permissions_entry", label="open-graphics-permissions")
        self.wait(rid="origin_permissions_dialog_list", label="graphics-permissions-list")

    def choose(self, *, origin, kind, saved, decision, permanent, private, top_origin=None):
        self.open_permissions()
        row = f"origin_permission_{'saved' if saved else 'pending'}_{kind}"
        self.click(rid=row, origin=origin, label=f"select-{kind}-{'saved' if saved else 'pending'}")
        xml, node = self.wait(rid="origin_permission_request_origin", label="permission-origin")
        displayed = text_origins(node.get("text", ""))
        require(canonical_origin(origin) in displayed, "Consent dialog does not name the requesting origin")
        if top_origin and canonical_origin(top_origin) != canonical_origin(origin):
            require(canonical_origin(top_origin) in displayed, "Frame consent omits the top-level origin")
        remember = self.node(xml, rid="origin_permission_remember", required=False)
        if private:
            require(remember is None, "Private consent offers persistent Remember")
            require(not permanent, "A test tried to request permanent private permission")
        else:
            require(remember is not None and remember.get("checkable") == "true", "Remember checkbox missing")
            if not saved:
                require(remember.get("checked") == "false", "New origin consent defaults to persistent")
            if (remember.get("checked") == "true") != permanent:
                self.tap(remember, "set-explicit-lifetime")
                _xml, checked = self.wait(rid="origin_permission_remember", label="verify-lifetime")
                require((checked.get("checked") == "true") == permanent, "Remember did not change")
        self.dump("consent-" + kind + "-" + decision, screenshot=True)
        target = "origin_permission_" + ("reset" if saved and decision == "ask" else decision)
        self.click(rid=target, label=f"consent-{kind}-{decision}")
        self.evidence.check(f"ui-{kind}-{decision}-{'private' if private else 'remembered' if permanent else 'session'}",
                            {"origin": canonical_origin(origin), "saved": saved, "topOrigin": top_origin})

    def saved_reload(self):
        self.click(rid="origin_permission_reload", label="explicit-saved-record-reload")

    def tab_menu(self, item):
        self.close_permissions()
        xml = self.dump("before-tab-menu")
        counter = self.node(xml, rid="ADDRESSBAR_TABS_COUNTER", required=False)
        if not counter:
            matches = [node for node in parse_ui(xml).iter("node")
                       if re.fullmatch(r"(?:Private )?Tabs Open: .+\. Tap to switch tabs\.", node.get("content-desc", ""))]
            require(len(matches) == 1, "Cannot identify the real Fenix tab counter uniquely")
            counter = self.node(xml, description=matches[0].get("content-desc"))
        self.tap(counter, "open-tab-counter-menu", long=True)
        self.click(text=item, label="tab-menu-" + item)

    def type_url(self, url):
        xml = self.dump("private-url-entry")
        field = self.node(xml, rid="ADDRESSBAR_SEARCH_BOX", required=False)
        if not field:
            for rid in ("ADDRESSBAR_URL_BOX", "mozac_browser_toolbar_url_view", "mozac_browser_toolbar_edit_url_view"):
                field = self.node(xml, rid=rid, required=False)
                if field:
                    break
        if not field:
            field = self.node(xml, class_name="android.widget.EditText", focused=True, required=False)
        require(field is not None, "Fenix URL input has no usable selector")
        self.tap(field, "focus-private-url")
        xml = self.dump("focused-private-url-input")
        fields = [node for node in parse_ui(xml).iter("node")
                  if node.get("package") == self.package and node.get("class") == "android.widget.EditText"
                  and node.get("focused") == "true"]
        require(len(fields) == 1, "No unique focused native address field after New private tab")
        # Android accessibility can expose a hint as text; accept that only when
        # the same node identifies the hint. Never append to an existing URL.
        value, hint = fields[0].get("text", ""), fields[0].get("hint", "")
        require(value == "" or (hint and value == hint), "New private address field is not empty")
        self.shell("input", "text", url)
        self.shell("input", "keyevent", "66")


class Runner:
    def __init__(self, args, evidence, protocol, adb):
        self.args, self.evidence, self.protocol, self.adb = args, evidence, protocol, adb
        self.ui = UI(adb, args.package, evidence, evidence.data["run"], args.ui_timeout, not args.no_screenshots)
        self.fixtures, self.marionette, self.forward_port = [], None, None
        self.forward_created = False
        self.reversed_ports = []
        self.active_url, self.private = None, False
        self.colors = [[secrets.randbelow(224) + 16 for _ in range(3)] + [255] for _ in range(4)]
        self.evidence.data["pixelChallenge"] = {"size": SIZE, "colors": self.colors,
            "expectedSha256": hashlib.sha256(expected_pixels(self.colors)).hexdigest()}

    def shell(self, *args, **kwargs):
        return self.ui.shell(*args, **kwargs)

    def prerequisite(self):
        packages = self.shell("pm", "path", self.args.package).strip().splitlines()
        paths = [line[len("package:"):] for line in packages if line.startswith("package:")]
        if not paths:
            raise Pending("Requested installed package is absent; this runner never installs an APK")
        dump = self.shell("dumpsys", "package", self.args.package)
        flags = [line.strip() for line in dump.splitlines()
                 if re.match(r"\s*(pkgFlags|flags|privateFlags)=", line)]
        if not flags:
            raise Pending("Cannot establish installed package build flags")
        if any("DEBUGGABLE" in line for line in flags):
            raise Pending("Installed package is debuggable; this is not release acceptance")
        hashes = []
        for path in paths:
            answer = self.shell("sha256sum", path).strip().split()
            if not answer or not re.fullmatch(r"[0-9a-f]{64}", answer[0]):
                raise Pending("Cannot bind evidence to the installed APK hash")
            hashes.append({"path": path, "sha256": answer[0]})
        if self.args.apk:
            expected = hashlib.sha256(Path(self.args.apk).read_bytes()).hexdigest()
            require(any(item["sha256"] == expected for item in hashes), "Installed APK differs from --apk")
        config_path = f"/data/local/tmp/{self.args.package}-geckoview-config.yaml"
        config = self.adb.run("shell", shlex.join(["cat", config_path]), timeout=30)
        facts = transport_config_facts(config.stdout)
        self.evidence.data["transportConfig"] = facts
        if config.returncode or not facts["transportOnly"] or facts["marionettePort"] != self.args.device_marionette_port:
            self.evidence.flush()
            raise Pending("Pre-enable the standard transport-only Marionette config; extra/missing config taints acceptance")
        self.evidence.data["installed"] = {"package": self.args.package, "apk": hashes, "flags": flags,
            "serial": self.adb.serial, "abi": self.shell("getprop", "ro.product.cpu.abi").strip(),
            "android": self.shell("getprop", "ro.build.version.release").strip(),
            "fingerprint": self.shell("getprop", "ro.build.fingerprint").strip(),
            "protocolSha256": self.protocol.input_sha256}
        self.evidence.flush()

    def start_fixtures(self):
        for _ in range(2):
            fixture = Fixture(self.evidence.data["run"], self.evidence)
            self.fixtures.append(fixture)
            self.adb.run("reverse", "--no-rebind", f"tcp:{fixture.port}", f"tcp:{fixture.port}", check=True, timeout=30)
            self.reversed_ports.append(fixture.port)
        self.evidence.data["origins"] = [fixture.origin for fixture in self.fixtures]
        if self.args.marionette_port:
            self.forward_port = self.args.marionette_port
        else:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                self.forward_port = sock.getsockname()[1]
            self.adb.run("forward", "--no-rebind", f"tcp:{self.forward_port}", f"tcp:{self.args.device_marionette_port}",
                         check=True, timeout=30)
            self.forward_created = True
        self.evidence.flush()

    def connect(self):
        if self.marionette:
            self.marionette.close()
            self.marionette = None
        deadline = time.monotonic() + self.args.connect_timeout
        last = None
        while time.monotonic() < deadline:
            client = None
            try:
                self.evidence.event("marionette-connect", {"hostPort": self.forward_port})
                client = self.protocol.Marionette(self.forward_port, timeout=15)
                client.cmd("WebDriver:NewSession", {"capabilities": {"alwaysMatch": {}}})
                client.cmd("WebDriver:SetTimeouts", {"script": 15000, "pageLoad": 60000})
                self.marionette = client
                return
            except Exception as error:
                last = str(error)
                if client:
                    client.close()
                time.sleep(0.5)
        raise Pending("Marionette transport unavailable after real fixture navigation: " + str(last))

    def browser_document(self, url, private, timeout=30):
        deadline, last = time.monotonic() + timeout, None
        while time.monotonic() < deadline:
            try:
                handles = window_handles(self.marionette)
                found = []
                for handle in handles:
                    self.marionette.cmd("WebDriver:SwitchToWindow", {"handle": handle, "focus": False})
                    principal = self.marionette.script(WINDOW_JS, chrome=True)
                    if not principal or principal.get("private") is not private or principal.get("active") is not True:
                        continue
                    self.marionette.cmd("Marionette:SetContext", {"value": "content"})
                    snapshot = self.marionette.script(DOCUMENT_JS)
                    last = snapshot
                    if snapshot and snapshot.get("ready") == "complete" and snapshot["document"].get("url") == url:
                        require(snapshot["document"].get("run") == self.evidence.data["run"], "Wrong fixture run")
                        found.append((handle, snapshot, principal))
                require(len(found) <= 1, "Two Gecko windows match the exact fixture URL and mode")
                if found:
                    handle, snapshot, principal = found[0]
                    self.marionette.cmd("WebDriver:SwitchToWindow", {"handle": handle, "focus": False})
                    snapshot["principal"] = principal
                    snapshot["frame"] = json.loads(snapshot["frame"]) if snapshot.get("frame") else None
                    return snapshot
            except Failure:
                raise
            except (self.protocol.MarionetteError, OSError, ValueError) as error:
                last = str(error)
            time.sleep(0.25)
        raise Failure("No current Gecko document for the exact URL/private mode: " + str(last))

    def snapshot(self):
        return self.browser_document(self.active_url, self.private)

    def wait_fixture_navigation(self, fixture, url, since, timeout=75):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with fixture.lock:
                registered = [row for row in fixture.documents.values()
                              if row["url"] == url and row.get("registeredAt", 0) >= since]
            if registered:
                return
            time.sleep(0.2)
        raise Failure("The parser-loaded fixture did not register after real Fenix navigation")

    def open(self, fixture, role="top", child=None, private=False, connect=False):
        url = fixture.url(role, child)
        since = time.time()
        self.evidence.event("navigate", {"url": url, "private": private})
        if private:
            self.ui.tab_menu("New private tab")
            self.ui.type_url(url)
        else:
            self.ui.close_permissions() if self.marionette else None
            self.shell("am", "start", "-a", "android.intent.action.VIEW", "-d", url,
                       "-n", self.args.package + "/org.mozilla.fenix.IntentReceiverActivity", timeout=45)
        self.wait_fixture_navigation(fixture, url, since)
        if connect:
            self.connect()
        self.active_url, self.private = url, private
        result = self.snapshot()
        self.evidence.check("current-fixture-document", result)
        return result

    def facts(self):
        prefs = self.marionette.script(PREFS_JS, chrome=True)
        self.evidence.event("effective-preferences", {"preferences": prefs})
        values = {item["name"]: item["value"] for item in prefs}
        require(values.get("librewolf.webgl.prompt") is True, "The installed default graphics gate is disabled")
        require(values.get("librewolf.webgl.prompt.hide") is True, "The shipped quiet WebGL policy is disabled")
        require(values.get("webgl.disabled") is False, "WebGL is globally disabled instead of usable with consent")
        require(values.get("permissions.isolateBy.privateBrowsing") is True, "Private permission isolation is disabled")
        return values

    def records(self):
        rows = self.marionette.script(PERMISSIONS_JS, [[item.origin for item in self.fixtures]], chrome=True)
        require(isinstance(rows, list), "Engine permission observation failed")
        self.evidence.event("engine-permission-observation", {"records": rows})
        return rows

    def matching_record(self, origin, kind, private):
        rows = [row for row in self.records() if row["origin"] == canonical_origin(origin)
                and row["kind"] == kind and row["private"] is private and row["contextId"] is None]
        require(len(rows) <= 1, "Multiple records match the tested principal/type")
        return rows[0] if rows else None

    def wait_record(self, origin, kind, value, permanent=False, private=False):
        deadline, last = time.monotonic() + 20, None
        while time.monotonic() < deadline:
            last = self.matching_record(origin, kind, private)
            if value is None and last is None:
                return None
            if last and last["value"] == value and last["expireType"] == (0 if permanent and not private else 2):
                return last
            time.sleep(0.2)
        raise Failure("Actual UI choice did not produce the exact expected engine value/lifetime: " + str(last))

    def wait_reload(self, before, frame=False):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            current = self.snapshot()
            if frame:
                require(current["document"]["documentId"] == before["document"]["documentId"],
                        "A requesting-frame choice incorrectly reloaded the top document")
                if current.get("frame") and before.get("frame") and \
                   current["frame"]["documentId"] != before["frame"]["documentId"]:
                    return current
            elif current["document"]["documentId"] != before["document"]["documentId"]:
                return current
            time.sleep(0.2)
        raise Failure("The actual consent/reload control did not replace its requesting document")

    def probe(self, fixture, operation, mode="dom", *, context_allowed, readback_allowed, frame=False):
        snapshot = self.snapshot()
        metadata = snapshot.get("frame") if frame else snapshot["document"]
        require(metadata is not None and metadata["origin"] == fixture.origin, "No matching live fixture frame")
        command, result = fixture.issue(metadata["documentId"], operation, mode, self.colors)
        raw = self.evidence.artifact(operation + "-" + mode + "-response", json.dumps(result) + "\n", "json")
        after = self.snapshot()
        current_metadata = after.get("frame") if frame else after["document"]
        require(current_metadata == metadata, "Current document changed during graphics operation")
        verdict = grade_probe(result, operation=operation, mode=mode, origin=fixture.origin,
            document_id=metadata["documentId"], command_id=command, colors=self.colors,
            context_allowed=context_allowed, readback_allowed=readback_allowed)
        if result.get("pixels") is not None:
            verdict["pixelArtifact"] = self.evidence.artifact(operation + "-" + mode, bytes(result["pixels"]), "rgba")
        verdict.update(origin=fixture.origin, documentId=metadata["documentId"], commandId=command,
                       private=self.private, mode=mode, operation=operation, responseArtifact=raw)
        self.evidence.check(f"{'frame-' if frame else ''}{operation}-{mode}-{'allowed' if readback_allowed else 'protected'}", verdict)
        return verdict

    def matrix(self, fixture, *, webgl, canvas, frame=False, full=True):
        for mode in MODES if full else ("dom",):
            for operation in OPERATIONS:
                self.probe(fixture, operation, mode, context_allowed=webgl,
                           readback_allowed=canvas, frame=frame)

    def choose(self, fixture, kind, decision, *, saved=False, permanent=False, frame=False):
        before = self.snapshot()
        self.ui.choose(origin=fixture.origin, kind=kind, saved=saved, decision=decision,
            permanent=permanent, private=self.private,
            top_origin=before["document"]["origin"] if frame and not saved else None)
        expected = {"allow": 1, "block": 2, "ask": None}[decision]
        record = self.wait_record(fixture.origin, kind, expected, permanent, self.private)
        if saved:
            self.ui.saved_reload()
        if saved or decision != "ask":
            self.wait_reload(before, frame=frame and not saved)
        self.ui.close_permissions()
        self.evidence.check("acknowledged-ui-choice", {"kind": kind, "decision": decision,
            "origin": fixture.origin, "record": record, "frameOnlyReload": frame and not saved})

    def grant_both(self, fixture, permanent=False, frame=False):
        self.probe(fixture, "webgl", context_allowed=False, readback_allowed=False, frame=frame)
        self.choose(fixture, "webgl", "allow", permanent=permanent, frame=frame)
        # The WebGL reload cancels any old canvas request. Produce a new actual
        # readback attempt in the new document before choosing its canvas row.
        self.probe(fixture, "canvas", context_allowed=True, readback_allowed=False, frame=frame)
        self.choose(fixture, "canvas", "allow", permanent=permanent, frame=frame)

    def core(self):
        fixture = self.fixtures[0]
        xml = self.ui.dump("before-quiet-probes", screenshot=True)
        self.ui.acknowledge_ubo_added_notice(xml)
        self.matrix(fixture, webgl=False, canvas=False)
        xml = self.ui.dump("quiet-protection", screenshot=True)
        xml = self.ui.acknowledge_ubo_added_notice(xml)
        require(self.ui.node(xml, rid="origin_permission_allow", required=False) is None,
                "A pre-gesture quiet attempt opened the consent dialog automatically")
        require(self.ui.node(xml, rid="origin_permissions_dialog_list", required=False) is None,
                "A pre-gesture quiet attempt opened the permission list automatically")
        self.evidence.check("quiet-no-automatic-dialog", {"origin": fixture.origin})
        self.choose(fixture, "webgl", "allow")
        self.probe(fixture, "canvas", context_allowed=True, readback_allowed=False)
        self.choose(fixture, "canvas", "allow")
        self.matrix(fixture, webgl=True, canvas=True)
        self.choose(fixture, "canvas", "ask", saved=True)
        self.matrix(fixture, webgl=True, canvas=False)
        self.choose(fixture, "webgl", "block", saved=True)
        self.matrix(fixture, webgl=False, canvas=False, full=False)
        self.choose(fixture, "webgl", "ask", saved=True)
        self.matrix(fixture, webgl=False, canvas=False)
        self.evidence.check("core-real-ui-consent-and-revoke", {"origin": fixture.origin,
            "operations": list(OPERATIONS), "modes": list(MODES)})

    def restart(self, fixture):
        before_pid = self.shell("pidof", self.args.package).strip()
        require(bool(before_pid), "No running app process before lifetime restart")
        before = self.snapshot()
        self.evidence.event("process-restart-start", {"pid": before_pid, "document": before["document"]})
        self.marionette.close()
        self.marionette = None
        self.shell("am", "force-stop", self.args.package)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if not self.adb.run("shell", shlex.join(["pidof", self.args.package]), timeout=10).stdout.strip():
                break
            time.sleep(0.2)
        else:
            raise Failure("Force-stop did not end the old process")
        since = time.time()
        self.shell("am", "start", "-a", "android.intent.action.VIEW", "-d", self.active_url,
                   "-n", self.args.package + "/org.mozilla.fenix.IntentReceiverActivity", timeout=45)
        self.wait_fixture_navigation(fixture, self.active_url, since)
        self.connect()
        current = self.snapshot()
        after_pid = self.shell("pidof", self.args.package).strip()
        require(bool(after_pid) and after_pid != before_pid, "A different app process was not observed")
        require(current["document"]["documentId"] != before["document"]["documentId"], "Old document survived process restart")
        self.facts()
        config = self.shell("cat", f"/data/local/tmp/{self.args.package}-geckoview-config.yaml")
        require(transport_config_facts(config)["transportOnly"], "Transport config changed during lifetime test")
        self.evidence.check("actual-process-restart", {"oldPid": before_pid, "newPid": after_pid,
            "oldDocument": before["document"]["documentId"], "newDocument": current["document"]["documentId"]})

    def lifetimes(self):
        fixture = self.fixtures[0]
        # The final default matrix left quiet requests pending in this document.
        self.choose(fixture, "webgl", "allow")
        self.probe(fixture, "canvas", context_allowed=True, readback_allowed=False)
        self.choose(fixture, "canvas", "allow")
        self.matrix(fixture, webgl=True, canvas=True, full=False)
        self.restart(fixture)
        for kind in KINDS:
            self.wait_record(fixture.origin, kind, None)
        self.matrix(fixture, webgl=False, canvas=False, full=False)
        self.evidence.check("session-exceptions-expire-on-process-restart", {"origin": fixture.origin})
        self.choose(fixture, "webgl", "allow", permanent=True)
        self.probe(fixture, "canvas", context_allowed=True, readback_allowed=False)
        self.choose(fixture, "canvas", "allow", permanent=True)
        self.restart(fixture)
        for kind in KINDS:
            self.wait_record(fixture.origin, kind, 1, permanent=True)
        self.matrix(fixture, webgl=True, canvas=True, full=False)
        self.evidence.check("remembered-exceptions-survive-process-restart", {"origin": fixture.origin})

    def private_lifetime(self):
        fixture = self.fixtures[0]
        normal = {row["kind"]: row for row in self.records() if row["origin"] == fixture.origin and not row["private"]}
        count = self.marionette.script(PRIVATE_WINDOWS_JS, chrome=True)
        require(count == 0, "Private lifetime test requires no pre-existing private Gecko windows")
        self.open(fixture, role="private-first", private=True)
        self.matrix(fixture, webgl=False, canvas=False, full=False)
        self.choose(fixture, "webgl", "allow")
        self.probe(fixture, "canvas", context_allowed=True, readback_allowed=False)
        self.choose(fixture, "canvas", "allow")
        self.matrix(fixture, webgl=True, canvas=True, full=False)
        for kind in KINDS:
            private = self.wait_record(fixture.origin, kind, 1, private=True)
            require(private["principalOrigin"] != normal[kind]["principalOrigin"], "Private and normal permissions share a principal")
            require(self.matching_record(fixture.origin, kind, False) == normal[kind], "Private consent modified a normal exception")
        self.close_private()
        for kind in KINDS:
            self.wait_record(fixture.origin, kind, None, private=True)
        self.open(fixture, role="private-second", private=True)
        self.matrix(fixture, webgl=False, canvas=False, full=False)
        self.close_private()
        self.open(fixture, role="after-private")
        self.matrix(fixture, webgl=True, canvas=True, full=False)
        self.evidence.check("private-choices-isolated-and-cleared-on-last-private-close", {"origin": fixture.origin})

    def close_private(self):
        require(self.private, "Refusing to close a non-private tab as private cleanup")
        self.ui.tab_menu("Close tab")
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            try:
                # The old current window was closed. Attach to a remaining normal
                # window before reading global private-window/permission state.
                handles = window_handles(self.marionette)
                if handles:
                    self.marionette.cmd("WebDriver:SwitchToWindow", {"handle": handles[0], "focus": False})
                    if self.marionette.script(PRIVATE_WINDOWS_JS, chrome=True) == 0:
                        self.private = False
                        return
            except (self.protocol.MarionetteError, OSError):
                pass
            time.sleep(0.25)
        raise Failure("Closing the private tab did not end the last private Gecko context")

    def frames(self):
        parent, child = self.fixtures
        child_url = child.url("child")
        parent_state = {row["kind"]: row for row in self.records() if row["origin"] == parent.origin and not row["private"]}
        self.open(parent, role="frame-parent", child=child_url)
        deadline = time.monotonic() + 30
        while not self.snapshot().get("frame"):
            if time.monotonic() >= deadline:
                raise Failure("The actual cross-origin frame did not become ready")
            time.sleep(0.25)
        for kind in KINDS:
            require(self.matching_record(child.origin, kind, False) is None, "Frame origin already has an exception")
        self.matrix(child, webgl=False, canvas=False, frame=True, full=False)
        self.choose(child, "webgl", "allow", frame=True)
        self.probe(child, "canvas", context_allowed=True, readback_allowed=False, frame=True)
        self.choose(child, "canvas", "allow", frame=True)
        self.matrix(child, webgl=True, canvas=True, frame=True)
        for kind in KINDS:
            require(self.matching_record(parent.origin, kind, False) == parent_state[kind],
                    "Frame consent modified the top-level principal")
        self.choose(child, "canvas", "ask", saved=True, frame=True)
        self.choose(child, "webgl", "ask", saved=True, frame=True)
        self.matrix(child, webgl=False, canvas=False, frame=True, full=False)
        self.matrix(parent, webgl=True, canvas=True, full=False)
        self.evidence.check("frame-origin-port-and-revoke-isolation", {"parent": parent.origin, "frame": child.origin})
        # Leave no normal remembered exceptions for our ephemeral test origin.
        self.choose(parent, "canvas", "ask", saved=True)
        self.choose(parent, "webgl", "ask", saved=True)
        for fixture in self.fixtures:
            for kind in KINDS:
                self.wait_record(fixture.origin, kind, None)

    def run(self):
        self.prerequisite()
        self.start_fixtures()
        self.open(self.fixtures[0], connect=True)
        self.facts()
        if self.records():
            raise Pending("Fixture origins already have graphics exceptions; use a clean dedicated profile")
        self.core()
        if self.args.stop_after_core:
            raise Pending("Core consent/revoke checks passed; lifetime and frame acceptance deliberately not run")
        self.lifetimes()
        self.private_lifetime()
        self.frames()
        for installed in self.evidence.data["installed"]["apk"]:
            final_hash = self.shell("sha256sum", installed["path"]).strip().split()[0]
            require(final_hash == installed["sha256"], "Installed APK changed during acceptance")
        required = {"core-real-ui-consent-and-revoke", "session-exceptions-expire-on-process-restart",
                    "remembered-exceptions-survive-process-restart",
                    "private-choices-isolated-and-cleared-on-last-private-close", "frame-origin-port-and-revoke-isolation"}
        require(required <= {check["name"] for check in self.evidence.data["checks"]}, "Acceptance stages are incomplete")
        self.evidence.finish("PASS", "Real release UI consent, pixels, revoke, lifetimes and frame isolation passed", True)

    def diagnostics(self):
        if "installed" not in self.evidence.data:
            return
        try:
            self.ui.dump("failure-ui", screenshot=True)
        except Exception as error:
            self.evidence.event("diagnostics-unavailable", {"error": str(error)})
        try:
            crash = self.adb.run("logcat", "-d", "-b", "crash", "-t", "200", timeout=20).stdout
            if self.args.package in crash:
                self.evidence.artifact("app-crash-buffer", crash, "txt")
        except Exception:
            pass

    def close(self):
        errors = []
        def cleanup(action):
            try:
                action()
            except Exception as error:
                errors.append(str(error))
        if self.marionette:
            cleanup(self.marionette.close)
        for port in self.reversed_ports:
            cleanup(lambda port=port: self.adb.run("reverse", "--remove", f"tcp:{port}", timeout=15, check=True))
        for fixture in self.fixtures:
            cleanup(fixture.close)
        if self.forward_created:
            cleanup(lambda: self.adb.run("forward", "--remove", f"tcp:{self.forward_port}", timeout=15, check=True))
        if self.ui.remote_used:
            cleanup(lambda: self.adb.run("shell", shlex.join(["rm", "-f", self.ui.remote]), timeout=15, check=True))
        require(not errors, "Cleanup errors: " + "; ".join(errors))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default=shutil.which("adb"))
    parser.add_argument("--serial", help="already running, dedicated test device")
    parser.add_argument("--package", default="org.redoubtbrowser")
    parser.add_argument("--apk", type=Path, help="optional expected installed base APK, checked by SHA256")
    parser.add_argument("--work", type=Path, default=Path.home() / ".cache/redoubt-graphics-smoke")
    parser.add_argument("--dedicated-test-profile", action="store_true", help="required: authorizes process restart and private test tabs")
    parser.add_argument("--marionette-port", type=int, help="existing host forwarded transport port; otherwise add one")
    parser.add_argument("--device-marionette-port", type=int, default=2828)
    parser.add_argument("--connect-timeout", type=int, default=60)
    parser.add_argument("--ui-timeout", type=int, default=25)
    parser.add_argument("--stop-after-core", action="store_true", help="diagnostic subset; full acceptance remains PENDING")
    parser.add_argument("--no-screenshots", action="store_true", help="retain XML/bytes but omit PNG diagnostics")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.]+", args.package):
        parser.error("Invalid package")
    if any(port is not None and not 1 <= port <= 65535 for port in (args.marionette_port, args.device_marionette_port)):
        parser.error("Transport ports must be between 1 and 65535")
    if args.connect_timeout <= 0 or args.ui_timeout <= 0:
        parser.error("Timeouts must be positive")
    run = secrets.token_hex(8)
    evidence = Evidence(args.work / run, run, "core-only" if args.stop_after_core else "full")
    runner, status = None, PENDING
    try:
        if not args.adb or not shutil.which(args.adb):
            raise Pending("adb is unavailable; no graphics behavior was tested")
        protocol = foundation()
        adb = protocol.Adb(args.adb, args.serial)
        devices = adb.devices()
        if args.serial and args.serial not in devices:
            raise Pending("Requested device is not connected and authorized")
        if not args.serial:
            if len(devices) != 1:
                raise Pending("Select one connected device with --serial; no behavior was tested")
            adb.serial = devices[0]
        if not args.dedicated_test_profile:
            raise Pending("A dedicated test profile is required for consent/revoke and private lifecycle actions")
        runner = Runner(args, evidence, protocol, adb)
        runner.run()
        if evidence.data["status"] != "PASS" or evidence.data["acceptanceComplete"] is not True:
            raise Pending("Runner returned without complete release acceptance evidence")
        status = PASS
    except Pending as error:
        evidence.finish("PENDING", str(error))
    except Exception as error:
        # Unexpected transport failures during exercised acceptance are failures,
        # never converted into a successful blocked/readback observation.
        evidence.finish("FAIL", str(error))
        status = FAIL
    except KeyboardInterrupt:
        evidence.finish("PENDING", "Interrupted before completing release acceptance")
    finally:
        if runner:
            if status != PASS:
                runner.diagnostics()
            try:
                runner.close()
            except Exception as error:
                evidence.event("cleanup-error", {"error": str(error)})
                if status == PASS:
                    evidence.finish("FAIL", "Harness cleanup failed after checks")
                    status = FAIL
    summary = {"status": evidence.data["status"], "acceptanceComplete": evidence.data["acceptanceComplete"],
               "passedChecks": len(evidence.data["checks"]), "reason": evidence.data["reason"],
               "report": str(evidence.path)}
    print(json.dumps(summary))
    return status


if __name__ == "__main__":
    sys.exit(main())
