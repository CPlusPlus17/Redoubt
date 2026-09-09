#!/usr/bin/env python3
"""Observe packaged cookie rules through real pages and real Fenix controls.

Use an installed release, pre-enabled transport-only Marionette, and a dedicated
test profile. No installation, policy/test-pref writes or engine exception writes.
Missing controls, fixture mapping or device coverage are PENDING, never PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import http.cookies
import http.server
import importlib.util
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

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("lw_cookie_transport", ROOT / "scripts/android-graphics-smoke.py")
g = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(g)
Pending, Failure, require = g.Pending, g.Failure, g.require
PASS, FAIL, PENDING = g.PASS, g.FAIL, g.PENDING
SNAPSHOT_HASH = "0ddab9560f17710fa1613825b1b8be0e190107dd679e2cd53c5a1822524958fd"
RULES = {
    "cookiebot": {"presence": "#CybotCookiebotDialog", "optOut": "#CybotCookiebotDialogBodyButtonDecline",
                  "optIn": "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"},
    "didomi": {"presence": "div#didomi-host", "optOut": "", "optIn": "button#didomi-notice-agree-button"},
}
REQUIRED = {"packaged-rule-inventory", "cookiebot-native-reject", "didomi-reject-only",
            "didomi-explicit-click-control", "normal-restart-and-existing-consent",
            "private-cookie-isolation-and-teardown", "private-global-controls",
            "normal-global-controls", "normal-site-controls", "private-site-controls-and-teardown",
            "native-domain-injection", "native-existing-consent", "native-private-injection-and-teardown"}


def cookie_value(header, name):
    jar = http.cookies.SimpleCookie()
    try:
        jar.load(header or "")
    except http.cookies.CookieError:
        raise Failure("Malformed fixture cookie evidence") from None
    return jar[name].value if name in jar else None


def grade_observation(state, requests, *, run, case_id, document_id, origin,
                      reject, accept, consent=None, initial=None, minimum_ms=0):
    require(isinstance(state, dict), "Missing actual page state")
    for field, expected in {"run": run, "caseId": case_id, "documentId": document_id,
                            "origin": g.canonical_origin(origin)}.items():
        require(state.get(field) == expected, "Wrong/stale page identity: " + field)
    require(state.get("loaded") is True and not state.get("errors"), "Page did not load cleanly")
    for field, expected in {"reject": reject, "accept": accept}.items():
        require(type(state.get(field)) is int and state[field] == expected, "Wrong actual callback counter: " + field)
    require(state.get("cookieValue") == consent, "Page cookie does not match the actual choice")
    require(state.get("initialCookie") == initial, "Initial cookie state differs from the required consent state")
    require(state.get("observedMillis", 0) >= minimum_ms, "Protected observation window was not completed")
    bound = [row for row in requests if row.get("caseId") == case_id and row.get("documentId") == document_id]
    for action, expected in [("reject", reject), ("accept", accept)]:
        events = [row for row in bound if row.get("route") == "/action" and row.get("action") == action]
        require(len(events) == expected, "Server action count differs from callback: " + action)
        for event in events:
            require(event.get("origin") == g.canonical_origin(origin) and event.get("run") == run,
                    "Server action belongs to another origin/run")
            require(event.get("requestCookie") == action, "Action request did not carry the page's choice cookie")
    heartbeats = [row for row in bound if row.get("route") == "/state"]
    require(bool(heartbeats), "No successful allowed page-to-server control request")
    require(heartbeats[-1].get("requestCookie") == consent, "Server cookie does not match the final page state")
    require(all(row.get("origin") == g.canonical_origin(origin) and row.get("run") == run for row in bound),
            "Mixed-origin request evidence")
    return {"origin": origin, "documentId": document_id, "caseId": case_id, "reject": reject,
            "accept": accept, "cookie": consent, "initialCookie": initial,
            "observedMillis": state.get("observedMillis"), "serverRequests": len(bound),
            "bannerPresent": state.get("bannerPresent"), "bannerVisible": state.get("bannerVisible")}


def grade_inventory(data):
    require(data.get("ready") is True, "List-service readiness promise was not fulfilled")
    require(data.get("snapshotSha256") == SNAPSHOT_HASH and data.get("snapshotBytes") == 262208,
            "Running APK does not expose the pinned packaged rules")
    require(data.get("ruleCount") == 558 and data.get("globalCount") == 9, "Actual native rule inventory is incomplete")
    for name, selectors in RULES.items():
        rule = data.get("selected", {}).get(name)
        require(rule is not None and rule.get("domains") == [] and rule.get("click") == selectors,
                "Actual packaged global rule differs: " + name)
    duh = data.get("selected", {}).get("duh")
    require(duh is not None and "duh.de" in duh.get("domains", []) and
            any(cookie.get("name") == "cookie_dismiss" and cookie.get("value") == "true"
                for cookie in duh.get("cookies", [])), "Native duh.de opt-out rule is missing")
    return data


def grade_pref_taint(prefs):
    values = {item["name"]: item for item in prefs}
    for name in ("cookiebanners.listService.testRules", "cookiebanners.listService.testSkipRemoteSettings",
                 "cookiebanners.bannerClicking.testing"):
        item = values.get(name)
        require(item is not None, "Missing test-override observation")
        expected = item["value"] is None or (item["value"] == "" if name.endswith(".testRules") else item["value"] is False)
        if item["hasUserValue"] or not expected:
            raise Pending("Production test override is set: " + name)
    return {name: item["value"] for name, item in values.items()}


def grade_controlled_origin(data, *, url, proof, ca_sha256):
    """Fail closed before navigating a controlled public hostname as a page."""
    if not isinstance(data, dict) or data.get("error"):
        raise Pending("Controlled HTTPS fixture verification did not succeed")
    if data.get("url") != url or data.get("status") != 200:
        raise Pending("Controlled fixture redirected or did not return HTTP 200")
    if data.get("proof") != proof:
        raise Pending("HTTPS origin did not reach this runner's private fixture challenge")
    if data.get("secure") is not True or data.get("overridden") is not False or \
            data.get("errorCode") != 0 or data.get("overridableErrorCategory") != 0:
        raise Pending("Controlled HTTPS fixture lacks clean verified TLS; certificate overrides are not accepted")
    chain = data.get("verifiedChainSha256")
    if not isinstance(chain, list) or not chain or not ca_sha256 or chain[-1] != ca_sha256:
        raise Pending("Controlled fixture verified chain does not end in the supplied CA SHA256")
    return {key: value for key, value in data.items() if key != "proof"}


def preference_switch(xml, title, package):
    """Bind a switch to its exact preference-row ancestor, never a later row."""
    tree = g.parse_ui(xml)
    g.select_node(xml, text=title, package=package)  # Reject duplicate/wrong-package titles first.
    parents = {child: parent for parent in tree.iter() for child in parent}
    label = next(node for node in tree.iter("node") if node.get("text") == title and node.get("package") == package)
    current = label
    while current in parents:
        current = parents[current]
        if current.tag == "hierarchy" or current.get("scrollable") == "true":
            break
        switches = [node for node in current.iter("node") if node.get("checkable") == "true"
                    and "Switch" in node.get("class", "") and node.get("package") == package]
        if switches:
            require(len(switches) == 1, "Ambiguous switch in the exact preference row")
            node = switches[0]
            return g.select_node(ET.tostring(node, encoding="unicode").replace("<node", "<hierarchy><node", 1)
                                 + "</hierarchy>", class_name=node.get("class"), package=package)
    raise Failure("The preference title has no switch in its own row")


def verify_site_scope(xml, domain, private, package):
    scope = g.select_node(xml, rid="cookie_banner_site_scope", package=package)
    lifetime = "Private browsing only. This choice expires when the last private tab closes." if private else \
        "Normal browsing only. Exceptions are remembered after restarting."
    expected = domain + " and all its subdomains, over HTTP and HTTPS. " + lifetime
    require(" ".join(scope.get("text", "").split()) == expected, "Cookie controls do not state the exact domain and browsing lifetime")


PREFS_JS = g.PREFS_JS.replace("const names = [", "const names = [" + ",".join(json.dumps(name) for name in [
    "cookiebanners.service.mode", "cookiebanners.service.mode.privateBrowsing", "cookiebanners.service.detectOnly",
    "cookiebanners.service.enableGlobalRules", "cookiebanners.service.enableGlobalRules.subFrames",
    "cookiebanners.cookieInjector.enabled", "cookiebanners.bannerClicking.enabled",
    "cookiebanners.bannerClicking.timeoutAfterLoad", "cookiebanners.bannerClicking.timeoutAfterDOMContentLoaded",
    "cookiebanners.bannerClicking.maxTriesPerSiteAndSession", "cookiebanners.listService.testRules",
    "cookiebanners.listService.testSkipRemoteSettings", "cookiebanners.bannerClicking.testing"]) + ",")
INVENTORY_JS = r"""
return (async()=>{
  const service=Cc['@mozilla.org/cookie-banner-list-service;1'].getService(Ci.nsICookieBannerListService);
  await service.initForTest();
  const response=await fetch('resource://app/defaults/settings/main/cookie-banner-rules-list.json');
  if (!response.ok) throw new Error('Packaged snapshot unavailable');
  const bytes=await response.arrayBuffer();
  const digest=await crypto.subtle.digest('SHA-256',bytes);
  const rules=Services.cookieBanners.rules;
  const pick=rule=>({id:rule.id,domains:rule.domains,
    click:rule.clickRule?{presence:rule.clickRule.presence,optOut:rule.clickRule.optOut,optIn:rule.clickRule.optIn}:null,
    cookies:rule.cookiesOptOut.map(c=>({name:c.cookie.name,value:c.cookie.value}))});
  const selected={};
  for(const rule of rules) {
    if(['cookiebot','didomi'].includes(rule.id)) selected[rule.id]=pick(rule);
    if(rule.domains.includes('duh.de')) selected.duh=pick(rule);
  }
  return {ready:true,ruleCount:rules.length,globalCount:rules.filter(r=>r.domains.length===0).length,selected,
    snapshotBytes:bytes.byteLength,snapshotSha256:Array.from(new Uint8Array(digest),n=>n.toString(16).padStart(2,'0')).join('')};
})();
"""
STATE_JS = "return JSON.parse(document.getElementById('cookie-state').textContent);"
DOMAIN_JS = r"""
try {const uri=Services.io.newURI(arguments[0]);return {domain:Services.eTLD.getBaseDomain(uri),
  mode:Services.cookieBanners.getDomainPref(uri,arguments[1])};}
catch(error) {return {error:String(error)};}
"""
COOKIE_JAR_JS = r"""
return Services.cookies.getCookiesWithOriginAttributes(JSON.stringify({privateBrowsingId:arguments[0]?1:0}),'duh.de')
  .filter(c=>c.name==='cookie_dismiss' && c.host.replace(/^\./,'')==='duh.de').map(c=>({host:c.host,path:c.path,value:c.value,
  private:(c.originAttributes.privateBrowsingId||0)!==0,isSecure:c.isSecure}));
"""
CONTROLLED_ORIGIN_JS = r"""
const url=arguments[0];
return new Promise(resolve=>{
  const request=new XMLHttpRequest({mozAnon:true});
  request.open('GET',url,true);request.timeout=12000;
  request.onload=()=>{
    try {
      const channel=request.channel.QueryInterface(Ci.nsIHttpChannel);
      const security=channel.securityInfo.QueryInterface(Ci.nsITransportSecurityInfo);
      const state=security.securityState;
      resolve({url:channel.URI.spec,status:request.status,proof:JSON.parse(request.responseText).proof,
        secure:!!(state & Ci.nsIWebProgressListener.STATE_IS_SECURE),
        overridden:!!(state & Ci.nsIWebProgressListener.STATE_CERT_USER_OVERRIDDEN),
        errorCode:security.errorCode,overridableErrorCategory:security.overridableErrorCategory,
        verifiedChainSha256:security.succeededCertChain.map(c=>c.sha256Fingerprint.replaceAll(':','').toLowerCase())});
    } catch(error) {resolve({error:String(error)});}
  };
  request.onerror=()=>resolve({error:'Controlled HTTPS request failed'});
  request.ontimeout=()=>resolve({error:'Controlled HTTPS request timed out'});
  request.send();
});
"""


FIXTURE_JS = r"""
const config=JSON.parse(document.getElementById('cookie-config').textContent);
const documentId=Array.from(crypto.getRandomValues(new Uint8Array(16)),n=>n.toString(16).padStart(2,'0')).join('');
const metadata={run:config.run,caseId:config.caseId,documentId,origin:location.origin,url:location.href,fixture:config.kind};
const readCookie=name=>document.cookie.split(';').map(p=>p.trim()).find(p=>p.startsWith(name+'='))?.slice(name.length+1)??null;
const state={...metadata,reject:0,accept:0,control:0,errors:[],loaded:false,initialCookie:readCookie(config.cookieName)};
document.getElementById('fixture-state').textContent=JSON.stringify(metadata);
let banner;
function snapshot() {
  state.cookieValue=readCookie(config.cookieName);
  state.bannerPresent=!!banner?.isConnected;
  state.bannerVisible=!!banner?.isConnected && getComputedStyle(banner).display!=='none' &&
    getComputedStyle(banner).visibility!=='hidden' && banner.getBoundingClientRect().height>0;
  document.getElementById('cookie-state').textContent=JSON.stringify(state);
  return {...state};
}
async function send(route,data) {
  try {
    const response=await fetch(route,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({...snapshot(),...data})});
    if(!response.ok) throw new Error(route+' status '+response.status);
  } catch(error) {state.errors.push(String(error));snapshot();}
}
function choose(action,event) {
  state[action]++;
  document.cookie=config.cookieName+'='+action+'; Path=/; Max-Age=86400; SameSite=Lax';
  banner?.remove();
  send('/action',{action,isTrusted:event.isTrusted});
}
function button(id,text,action) {
  const node=document.createElement('button');node.id=id;node.textContent=text;
  node.addEventListener('click',event=>choose(action,event));return node;
}
if(config.kind==='cookiebot' && (!state.initialCookie || config.forceBanner)) {
  banner=document.createElement('div');banner.id='CybotCookiebotDialog';
  banner.append(button('CybotCookiebotDialogBodyButtonDecline','Reject fixture cookies','reject'),
    button('CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll','Accept fixture cookies','accept'));
} else if(config.kind==='didomi' && !state.initialCookie) {
  banner=document.createElement('div');banner.id='didomi-host';
  banner.append(button('didomi-notice-agree-button','Accept fixture cookies','accept'));
}
if(banner) document.body.appendChild(banner);
if(config.kind==='injection') {
  const seed=document.createElement('button');seed.id='fixture-existing-consent';seed.textContent='Keep existing fixture consent';
  seed.addEventListener('click',event=>{
    state.control++;document.cookie='cookie_dismiss=existing-consent; Domain=duh.de; Path=/; Max-Age=86400; SameSite=Lax; Secure';
    send('/control',{action:'existing-consent',isTrusted:event.isTrusted});
  });document.body.appendChild(seed);
}
window.addEventListener('load',()=>{state.loaded=true;snapshot();});
snapshot();send('/register',{});
setInterval(()=>send('/state',{}),250);
"""


class Evidence(g.Evidence):
    def __init__(self, work, run, suite):
        self.work = Path(work)
        self.work.mkdir(parents=True, exist_ok=True)
        self.path = self.work / "cookie-results.json"
        self.counter, self.lock = 0, threading.RLock()
        self.data = {"schema": 1, "run": run, "suite": suite, "status": "PENDING", "acceptanceComplete": False,
                     "checks": [], "events": [], "artifacts": [], "pending": []}
        self.flush()

    def pending(self, criterion, reason):
        with self.lock:
            self.data["pending"].append({"criterion": criterion, "reason": reason})
            self.flush()
        print("[cookie] PENDING " + criterion + ": " + reason, file=sys.stderr, flush=True)

    def check(self, name, detail):
        with self.lock:
            self.data["checks"].append({"name": name, "status": "PASS", "evidence": detail})
            self.flush()
        print("[cookie] PASS " + name, file=sys.stderr, flush=True)


class Fixture:
    def __init__(self, run, evidence, port=0, site_origin=None, injection_origin=None):
        self.run, self.evidence = run, evidence
        self.proof = secrets.token_hex(32)
        self.cases, self.documents, self.requests = {}, {}, []
        self.lock = threading.RLock()
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def reply(self, body, status=200, html=False):
                raw = body.encode() if html else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8" if html else "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                try:
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # Real navigation may cancel an old heartbeat.

            def do_GET(self):
                uri = urllib.parse.urlsplit(self.path)
                query = urllib.parse.parse_qs(uri.query)
                if uri.path == "/cookie-fixture-probe" and query.get("run") == [owner.run]:
                    owner.evidence.event("controlled-fixture-probe-received", {"at": time.time()})
                    return self.reply({"proof": owner.proof})
                case_id = query.get("case", [None])[0]
                case = owner.cases.get(case_id)
                if uri.path != "/cookie" or query.get("run") != [owner.run] or not case:
                    return self.reply({"error": "unknown controlled fixture"}, 404)
                record = {"route": "/cookie", "at": time.time(), "run": owner.run, "caseId": case_id,
                          "requestCookie": cookie_value(self.headers.get("Cookie"), case["cookieName"])}
                with owner.lock:
                    owner.requests.append(record)
                owner.evidence.event("fixture-navigation-request", record)
                config = json.dumps(case).replace("<", "\\u003c")
                self.reply("<!doctype html><meta charset=utf-8><title>Cookie acceptance fixture</title>"
                    "<h1>Cookie rule acceptance</h1><pre id=fixture-state></pre><pre id=cookie-state></pre>"
                    "<pre id=frame-state></pre><pre id=fixture-error></pre>"
                    '<script id=cookie-config type=application/json>'+config+"</script><script>"+FIXTURE_JS+"</script>", html=True)

            def do_POST(self):
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 50000:
                        return self.reply({"error": "invalid body size"}, 400)
                    row = json.loads(self.rfile.read(length))
                    case = owner.cases.get(row.get("caseId"))
                    if not case or row.get("run") != owner.run or row.get("origin") != case["origin"]:
                        return self.reply({"error": "wrong fixture identity"}, 400)
                    if self.path not in ("/register", "/action", "/state", "/control"):
                        return self.reply({"error": "unknown route"}, 404)
                    row = dict(row, route=self.path, at=time.time(),
                               requestCookie=cookie_value(self.headers.get("Cookie"), case["cookieName"]))
                    with owner.lock:
                        owner.requests.append(row)
                        if self.path == "/register":
                            owner.documents[row["documentId"]] = dict(row, registeredAt=time.time())
                    if self.path != "/state":
                        owner.evidence.event("fixture-response", row)
                    self.reply({"ok": True})
                except (TypeError, ValueError, KeyError, Failure):
                    self.reply({"error": "invalid fixture response"}, 400)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.port = self.server.server_address[1]
        self.loopback_origin = f"http://localhost:{self.port}"
        self.origin = g.canonical_origin(site_origin or self.loopback_origin)
        self.injection_origin = injection_origin
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def case(self, kind, *, force=False, injection=False, bootstrap=False):
        case_id = secrets.token_hex(6)
        origin = self.loopback_origin if bootstrap else self.injection_origin if injection else self.origin
        require(origin is not None, "Controlled domain mapping was not supplied")
        self.cases[case_id] = {"run": self.run, "caseId": case_id, "kind": kind, "forceBanner": force,
                              "cookieName": "cookie_dismiss" if injection else "lw_cookie_" + case_id, "origin": origin}
        return case_id

    def url(self, role="bootstrap", child=None):
        require(child is None, "Cookie fixture does not use frame navigation")
        case = self.cases[role]
        return case["origin"] + "/cookie?" + urllib.parse.urlencode({"run": self.run, "case": role})

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class CookieUI(g.UI):
    def close_panels(self):
        for _ in range(4):
            xml = self.dump("close-cookie-controls")
            if self.node(xml, rid="cookie_banner_site_status", required=False):
                self.click(text="Close", label="close-cookie-site-dialog")
            elif self.node(xml, rid="cookie_banner_site_controls", required=False):
                self.back()
            else:
                return
        raise Failure("Cookie controls did not close")

    def scroll_to(self, title):
        for _ in range(9):
            xml = self.dump("find-cookie-preference")
            found = self.node(xml, text=title, required=False)
            if found:
                return xml
            scrolls = [node for node in g.parse_ui(xml).iter("node") if node.get("scrollable") == "true"
                       and node.get("package") == self.package and node.get("enabled", "true") == "true"]
            if len(scrolls) != 1:
                break
            bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", scrolls[0].get("bounds", ""))
            if not bounds:
                break
            left, top, right, bottom = map(int, bounds.groups())
            if bottom <= top or right <= left:
                break
            self.shell("input", "swipe", (left+right)//2, top+(bottom-top)*3//4,
                       (left+right)//2, top+(bottom-top)//4, 350)
        raise Pending("The current Fenix UI does not expose the exact control: " + title)

    def global_availability(self, scheme):
        self.shell("am", "start", "-a", "android.intent.action.VIEW", "-d", scheme+"://settings", self.package)
        try:
            for mode in ("normal", "private"):
                title = "Cookie Banner Blocker in " + mode + " browsing"
                preference_switch(self.scroll_to(title), title, self.package)
        finally:
            self.back()

    def global_mode(self, private, enabled, scheme):
        self.shell("am", "start", "-a", "android.intent.action.VIEW", "-d", scheme+"://settings", self.package)
        title = "Cookie Banner Blocker in " + ("private" if private else "normal") + " browsing"
        try:
            xml = self.scroll_to(title)
        except Pending:
            self.back()
            raise
        control = preference_switch(xml, title, self.package)
        require((control.get("checked") == "true") != enabled, "Global mode control did not start in the expected state")
        self.tap(control, ("private" if private else "normal") + "-cookie-global-" + str(enabled))
        after = preference_switch(self.dump("after-cookie-global-toggle", screenshot=True), title, self.package)
        require((after.get("checked") == "true") == enabled, "Cookie preference switch did not change")
        self.back()

    def open_site(self):
        self.close_panels()
        xml = self.dump("cookie-site-controls", screenshot=True)
        for rid in ("mozac_browser_toolbar_tracking_protection_indicator", "mozac_browser_toolbar_site_info_indicator"):
            indicator = self.node(xml, rid=rid, required=False)
            if indicator:
                self.tap(indicator, "open-real-site-controls")
                break
        else:
            indicator = self.node(xml, description="Site information", required=False)
            if not indicator:
                raise Pending("No real Fenix site-information control is exposed")
            self.tap(indicator, "open-real-site-information")
        xml = self.dump("cookie-site-panel")
        entry = self.node(xml, rid="cookie_banner_site_controls", required=False)
        if not entry:
            self.back()
            raise Pending("Current Fenix site panel does not expose Cookie Banner Blocker")
        self.tap(entry, "open-cookie-site-control")

    def site_disabled(self, *, domain, private):
        self.open_site()
        status = "Handling is off globally in this browsing mode. Enable it in Settings to change this domain. Existing exceptions are kept."
        xml, _ = self.wait(rid="cookie_banner_site_status", text=status, label="globally-disabled-site-controls")
        verify_site_scope(xml, domain, private, self.package)
        for rid in ("cookie_banner_site_switch", "cookie_banner_site_reset"):
            nodes = [node for node in g.parse_ui(xml).iter("node") if g.resource_matches(node.get("resource-id", ""), rid)
                     and node.get("package") == self.package]
            require(len(nodes) == 1 and nodes[0].get("enabled") == "false", "Global Off did not disable its exact site control")
        self.close_panels()

    def site(self, enabled, *, domain, private, reset=False):
        self.open_site()
        xml, switch = self.wait(rid="cookie_banner_site_switch", label="cookie-site-switch")
        verify_site_scope(xml, domain, private, self.package)
        status = self.node(xml, rid="cookie_banner_site_status")
        expected_status = "Handling is off for this domain. Cookies and saved site data are unchanged." if enabled else \
            "Rejection-only handling is on. Not every banner is supported. Cookies and saved site data are unchanged."
        require(status.get("text") == expected_status, "Cookie dialog status does not match the starting engine mode")
        require((switch.get("checked") == "true") != enabled, "Site exception switch did not start in the expected state")
        if reset:
            require(enabled, "Reset must inherit enabled rejection-only mode")
            self.click(rid="cookie_banner_site_reset", label="reset-cookie-domain-exception")
        else:
            self.tap(switch, "cookie-site-enabled-" + str(enabled))


class Runner(g.Runner):
    def __init__(self, args, evidence, protocol, adb):
        super().__init__(args, evidence, protocol, adb)
        self.evidence.data.pop("pixelChallenge", None)
        self.ui = CookieUI(adb, args.package, evidence, evidence.data["run"], args.ui_timeout, not args.no_screenshots)
        self.case_id = None
        self.observe_ms = 7000
        self.injection_verified = False

    def prerequisite(self):
        installed = self.adb.run("shell", shlex.join(["pm", "path", self.args.package]), timeout=30)
        if installed.returncode or not any(line.startswith("package:") for line in installed.stdout.splitlines()):
            raise Pending("Requested installed package is absent or cannot be read; this runner never installs an APK")
        super().prerequisite()

    def start_fixtures(self):
        fixture = Fixture(self.evidence.data["run"], self.evidence, self.args.fixture_port,
                          self.args.site_origin, self.args.injection_origin)
        self.fixtures = [fixture]
        self.fixture = fixture
        self.adb.run("reverse", "--no-rebind", f"tcp:{fixture.port}", f"tcp:{fixture.port}", check=True, timeout=30)
        self.reversed_ports.append(fixture.port)
        if self.args.marionette_port:
            self.forward_port = self.args.marionette_port
        else:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                self.forward_port = sock.getsockname()[1]
            self.adb.run("forward", "--no-rebind", f"tcp:{self.forward_port}", f"tcp:{self.args.device_marionette_port}",
                         check=True, timeout=30)
            self.forward_created = True
        self.evidence.event("controlled-origins", {"origin": fixture.origin, "injectionOrigin": fixture.injection_origin,
                            "hostFixturePort": fixture.port})

    def facts(self, inventory=True):
        prefs = self.marionette.script(PREFS_JS, chrome=True)
        self.evidence.event("effective-preferences", {"preferences": prefs})
        values = grade_pref_taint(prefs)
        for name in ("cookiebanners.service.mode", "cookiebanners.service.mode.privateBrowsing"):
            require(type(values.get(name)) is int and values[name] in (0, 1), "Cookie mode permits acceptance or is unknown: " + name)
        require(values.get("cookiebanners.service.detectOnly") is False, "Cookie service is detect-only")
        require(values.get("cookiebanners.service.enableGlobalRules") is True, "Global packaged rules are disabled")
        require(values.get("cookiebanners.bannerClicking.enabled") is True, "Native banner clicking is disabled")
        timeout = values.get("cookiebanners.bannerClicking.timeoutAfterLoad")
        require(type(timeout) is int and 0 <= timeout <= 60000, "Unknown native banner observation deadline")
        self.observe_ms = max(7000, timeout+2000)
        if inventory and any(values[name] == 1 for name in
                             ("cookiebanners.service.mode", "cookiebanners.service.mode.privateBrowsing")):
            data = self.marionette.script(INVENTORY_JS, chrome=True)
            self.evidence.artifact("native-cookie-rule-inventory", json.dumps(data, indent=2), "json")
            self.evidence.check("packaged-rule-inventory", grade_inventory(data))
        return values

    def verify_controlled_origins(self):
        for name, origin in [("site", self.args.site_origin), ("injection", self.args.injection_origin)]:
            if not origin:
                continue
            try:
                if not self.args.fixture_ca_sha256:
                    raise Pending("Controlled HTTPS setup requires the trusted fixture CA SHA256")
                url = origin + "/cookie-fixture-probe?" + urllib.parse.urlencode(
                    {"run": self.evidence.data["run"], "nonce": secrets.token_hex(16)})
                data = self.marionette.script(CONTROLLED_ORIGIN_JS, [url], chrome=True)
                # Never include the server's private proof in a verifier input
                # or URL; a different live server must not be able to echo it.
                safe = {key: value for key, value in data.items() if key != "proof"} if isinstance(data, dict) else data
                self.evidence.event("controlled-origin-verification", {"kind": name, "origin": origin, "response": safe})
                checked = grade_controlled_origin(data, url=url, proof=self.fixture.proof,
                                                 ca_sha256=self.args.fixture_ca_sha256)
                self.evidence.check("verified-controlled-" + name + "-origin", checked)
                if name == "injection":
                    self.injection_verified = True
            except Pending as error:
                self.evidence.pending("controlled-" + name + "-fixture", str(error))
                if name == "site":
                    self.fixture.origin = self.fixture.loopback_origin
                    self.evidence.event("bounded-core-uses-loopback", {"origin": self.fixture.origin,
                        "reason": "Requested controlled origin did not verify; its coverage remains pending"})

    def open_case(self, case_id, *, private=False, connect=False):
        self.case_id = case_id
        return super().open(self.fixture, role=case_id, private=private, connect=connect)

    def state(self):
        current = self.snapshot()
        state = self.marionette.script(STATE_JS)
        require(state["documentId"] == current["document"]["documentId"] and state["caseId"] == self.case_id,
                "Page state belongs to another current document/case")
        return state

    def observe(self, *, reject=0, accept=0, consent=None, initial=None, label, duration_ms=None):
        before = self.state()
        start = time.monotonic()
        duration = self.observe_ms if duration_ms is None else duration_ms
        samples = []
        while True:
            state = self.state()
            require(state["documentId"] == before["documentId"], "Document changed during cookie observation")
            require(state["accept"] <= accept and state["reject"] <= reject, "Unexpected automatic cookie choice")
            samples.append({"at": time.time(), "reject": state["reject"], "accept": state["accept"],
                            "cookie": state["cookieValue"], "bannerVisible": state["bannerVisible"]})
            elapsed = int((time.monotonic()-start)*1000)
            if elapsed >= duration:
                break
            time.sleep(.35)
        state["observedMillis"] = elapsed
        with self.fixture.lock:
            requests = [row.copy() for row in self.fixture.requests if row.get("documentId") == state["documentId"]]
        self.evidence.artifact(label+"-raw", json.dumps({"state": state, "samples": samples, "requests": requests}, indent=2), "json")
        verdict = grade_observation(state, requests, run=self.evidence.data["run"], case_id=self.case_id,
            document_id=before["documentId"], origin=state["origin"], reject=reject, accept=accept,
            consent=consent, initial=initial, minimum_ms=duration)
        self.evidence.check(label, verdict)
        return state

    def explicit_click(self, selector):
        before = self.state()
        self.evidence.event("explicit-page-click", {"selector": selector, "documentId": before["documentId"],
                                                  "caseId": self.case_id})
        self.marionette.cmd("Marionette:SetContext", {"value": "content"})
        element = self.marionette.cmd("WebDriver:FindElement", {"using": "css selector", "value": selector}).get("value")
        require(isinstance(element, dict), "Explicit control element was not found")
        element_id = element.get("element-6066-11e4-a52e-4f735466cecf") or element.get("ELEMENT")
        require(bool(element_id), "Explicit control returned no actual element")
        self.marionette.cmd("WebDriver:ElementClick", {"id": element_id})
        require(self.state()["documentId"] == before["documentId"], "Explicit click navigated an unexpected document")

    def core(self):
        cookie = self.fixture.case("cookiebot")
        self.open_case(cookie)
        self.observe(reject=1, consent="reject", label="cookiebot-native-reject")
        didomi = self.fixture.case("didomi")
        self.open_case(didomi)
        self.observe(label="didomi-reject-only")
        self.explicit_click(RULES["didomi"]["optIn"])
        state = self.observe(accept=1, consent="accept", label="didomi-explicit-click-control", duration_ms=1000)
        with self.fixture.lock:
            actions = [row for row in self.fixture.requests if row.get("documentId") == state["documentId"]
                       and row.get("route") == "/action"]
        require(len(actions) == 1 and actions[0]["isTrusted"] is True, "Positive control was not a real user/automation input event")
        self.normal_cookie_case = cookie

    def normal_restart(self):
        self.open_case(self.normal_cookie_case)
        # Restart into a retained consent case, avoiding the old process's
        # three-attempt per-site cooldown without clearing native records.
        super().restart(self.fixture)
        self.observe(consent="reject", initial="reject", label="normal-existing-consent-after-restart")
        fresh = self.fixture.case("cookiebot")
        self.open_case(fresh)
        self.observe(reject=1, consent="reject", label="normal-fresh-rejection-after-restart")
        self.evidence.check("normal-restart-and-existing-consent", {"retainedCase": self.normal_cookie_case, "freshCase": fresh})

    def private_lifetime(self):
        require(self.marionette.script(g.PRIVATE_WINDOWS_JS, chrome=True) == 0, "Pre-existing private tabs prevent isolated teardown")
        self.open_case(self.normal_cookie_case, private=True)
        self.observe(reject=1, consent="reject", label="private-does-not-inherit-normal-cookie")
        self.close_private()
        self.open_case(self.normal_cookie_case, private=True)
        self.observe(reject=1, consent="reject", label="new-private-session-has-no-old-consent")
        self.close_private()
        self.open_case(self.normal_cookie_case)
        self.observe(consent="reject", initial="reject", label="normal-consent-survives-private-teardown")
        self.evidence.check("private-cookie-isolation-and-teardown", {"caseId": self.normal_cookie_case})

    def global_controls(self):
        self.ui.global_availability(self.args.scheme)
        force = self.fixture.case("cookiebot", force=True)
        # A real process restart supplies a fresh native attempt budget. The
        # fixture always presents its banner in mode/exception tests so retained
        # cookies cannot conceal an enabled/disabled actor.
        self.open_case(force)
        super().restart(self.fixture)
        initial = self.state()["initialCookie"]
        require(initial in (None, "reject"), "Unexpected seeded consent before global controls")
        self.observe(reject=1, consent="reject", initial=initial, label="normal-enabled-before-global-control")
        before = self.snapshot()
        self.ui.global_mode(False, False, self.args.scheme)
        self.wait_pref("cookiebanners.service.mode", 0, other_expected=1)
        self.wait_reload(before)
        self.observe(consent="reject", initial="reject", label="normal-global-disabled-no-choice")
        before = self.snapshot()
        self.ui.global_mode(True, False, self.args.scheme)
        self.wait_pref("cookiebanners.service.mode.privateBrowsing", 0)
        self.wait_reload(before)
        require(self.marionette.script("return Services.cookieBanners.isEnabled;", chrome=True) is False,
                "Cookie service remained enabled after both actual global controls were off")
        super().restart(self.fixture)
        persisted = self.facts(inventory=False)
        require(persisted["cookiebanners.service.mode"] == 0 and
                persisted["cookiebanners.service.mode.privateBrowsing"] == 0,
                "Actual global Off choices did not both survive process restart")
        self.observe(consent="reject", initial="reject", label="both-global-off-choices-survive-restart")
        self.open_case(force, private=True)
        self.observe(label="both-global-modes-disabled-private-control")
        self.explicit_click(RULES["cookiebot"]["optOut"])
        self.observe(reject=1, consent="reject", label="disabled-reject-button-control", duration_ms=1000)
        before = self.snapshot()
        self.ui.global_mode(False, True, self.args.scheme)
        self.wait_pref("cookiebanners.service.mode", 1, other_expected=0)
        self.wait_reload(before)
        self.facts()  # Await production data reload after the real service shutdown.
        self.observe(consent="reject", initial="reject", label="normal-reenable-keeps-private-disabled")
        before = self.snapshot()
        self.ui.global_mode(True, True, self.args.scheme)
        self.wait_pref("cookiebanners.service.mode.privateBrowsing", 1, other_expected=1)
        self.wait_reload(before)
        self.observe(reject=1, consent="reject", initial="reject", label="private-global-reenabled-rejects")
        self.close_private()
        normal = self.fixture.case("cookiebot")
        self.open_case(normal)
        self.observe(reject=1, consent="reject", label="normal-global-reenabled-rejects")
        self.evidence.check("normal-global-controls", {"disabledMode": 0, "restoredMode": 1,
            "bothDisabledServiceShutdown": True, "offPersistedAcrossRestart": True})
        self.evidence.check("private-global-controls", {"disabledMode": 0, "restoredMode": 1,
            "normalReenableDidNotEnablePrivate": True, "offPersistedAcrossRestart": True})

    def wait_pref(self, name, expected, other_expected=0):
        deadline = time.monotonic()+15
        while time.monotonic() < deadline:
            values = self.facts(inventory=False)
            if values.get(name) == expected:
                other = "cookiebanners.service.mode" if name.endswith(".privateBrowsing") else "cookiebanners.service.mode.privateBrowsing"
                require(values.get(other) == other_expected, "A global cookie control changed the other browsing mode")
                return
            time.sleep(.3)
        raise Failure("Real Fenix control did not change effective " + name)

    def domain_mode(self, origin, private):
        return self.marionette.script(DOMAIN_JS, [origin, private], chrome=True)

    def wait_domain_mode(self, origin, private, expected):
        deadline = time.monotonic()+20
        while time.monotonic() < deadline:
            observed = self.domain_mode(origin, private)
            if observed.get("mode") == expected:
                return observed
            time.sleep(.3)
        raise Failure("Expected cookie domain mode did not become effective: " + str(observed))

    def site_choice(self, origin, enabled, *, reset=False):
        before = self.snapshot()
        domain = self.domain_mode(origin, self.private).get("domain")
        require(bool(domain), "Per-site action has no confirmed registrable domain")
        self.ui.site(enabled, domain=domain, private=self.private, reset=reset)
        observed = self.wait_domain_mode(origin, self.private, 3 if enabled else 0)
        self.wait_reload(before)
        self.ui.close_panels()
        self.evidence.check("real-site-mode-change", {"origin": origin, "private": self.private, "mode": observed})

    def site_controls(self, private):
        origin = self.fixture.origin
        observation = self.domain_mode(origin, private)
        if "error" in observation:
            raise Pending("The fixture has no registrable domain for real per-site modes; provide --site-origin with a controlled HTTPS mapping")
        if observation.get("mode") != 3:
            raise Pending("The controlled fixture domain already has an exception; use its real controls to prepare a clean test")
        case_id = self.fixture.case("cookiebot", force=True)
        mode = "private" if private else "normal"
        self.open_case(case_id, private=private)
        if not private:
            super().restart(self.fixture)
        initial = self.state()["initialCookie"]
        require(initial in (None, "reject"), "Unexpected existing consent before site controls")
        self.observe(reject=1, consent="reject", initial=initial, label=mode+"-site-initial-reject")
        self.site_choice(origin, False)
        self.observe(consent="reject", initial="reject", label=mode+"-site-exception-preserves-consent-and-prevents-choice")
        before = self.snapshot()
        self.ui.global_mode(private, False, self.args.scheme)
        pref = "cookiebanners.service.mode" + (".privateBrowsing" if private else "")
        self.wait_pref(pref, 0, other_expected=1)
        self.wait_reload(before)
        self.ui.site_disabled(domain=observation["domain"], private=private)
        self.wait_domain_mode(origin, private, 0)
        before = self.snapshot()
        self.ui.global_mode(private, True, self.args.scheme)
        self.wait_pref(pref, 1, other_expected=1)
        self.wait_reload(before)
        self.wait_domain_mode(origin, private, 0)
        self.observe(consent="reject", initial="reject", label=mode+"-global-toggle-keeps-existing-site-exception")
        self.site_choice(origin, True)
        self.observe(reject=1, consent="reject", initial="reject", label=mode+"-site-exception-removal-restores-choice")
        self.site_choice(origin, False)
        self.observe(consent="reject", initial="reject", label=mode+"-site-exception-before-reset")
        if not private:
            super().restart(self.fixture)
            self.wait_domain_mode(origin, False, 0)
            self.observe(consent="reject", initial="reject", label="normal-site-exception-survives-restart")
        self.site_choice(origin, True, reset=True)
        self.observe(reject=1, consent="reject", initial="reject", label=mode+"-site-reset-restores-rejection-without-data-loss")
        if not private:
            self.evidence.check("normal-site-controls", {"origin": origin, "domain": observation["domain"], "persistedAcrossRestart": True})
            return
        self.site_choice(origin, False)
        self.observe(consent="reject", initial="reject", label="private-site-exception-before-teardown")
        self.close_private()
        self.wait_domain_mode(origin, True, 3)
        self.open_case(case_id, private=True)
        self.observe(reject=1, consent="reject", label="private-site-choice-cleared-after-teardown")
        self.close_private()
        self.evidence.check("private-site-controls-and-teardown", {"origin": origin})

    def native_injection(self):
        if not self.args.injection_origin:
            raise Pending("Native cookie injection needs a controlled HTTPS duh.de mapping; supply --injection-origin and --fixture-port")
        if not self.injection_verified:
            raise Pending("Controlled duh.de mapping and CA verification did not pass; no page navigation attempted")
        if self.marionette.script(COOKIE_JAR_JS, [False], chrome=True):
            raise Pending("duh.de already has cookie_dismiss; use a clean dedicated profile to establish fresh native injection")
        case_id = self.fixture.case("injection", injection=True)
        self.open_case(case_id)
        state = self.observe(consent="true", initial="true", label="native-domain-page-and-heartbeat")
        with self.fixture.lock:
            navigations = [row for row in self.fixture.requests if row["route"] == "/cookie" and row["caseId"] == case_id]
        require(navigations and navigations[0]["requestCookie"] == "true", "Native injector did not place cookie_dismiss on the actual document request")
        jar = self.marionette.script(COOKIE_JAR_JS, [False], chrome=True)
        require(len(jar) == 1 and jar[0]["value"] == "true", "Native cookie store does not match page/header evidence")
        self.evidence.check("native-domain-injection", {"origin": self.args.injection_origin, "cookie": jar,
            "navigationCookie": navigations[0]["requestCookie"], "documentId": state["documentId"]})
        self.explicit_click("#fixture-existing-consent")
        self.observe(consent="existing-consent", initial="true", label="explicit-existing-consent-control", duration_ms=1000)
        with self.fixture.lock:
            controls = [row for row in self.fixture.requests if row.get("documentId") == state["documentId"]
                        and row.get("route") == "/control"]
        require(len(controls) == 1 and controls[0].get("isTrusted") is True and
                controls[0].get("requestCookie") == "existing-consent", "Existing consent was not set by the real explicit page control")
        self.open_case(case_id)
        self.observe(consent="existing-consent", initial="existing-consent", label="native-existing-consent")
        self.evidence.event("native-cookie-injection-record", {"documentId": state["documentId"], "cookies": jar,
                            "navigationCookie": navigations[0]["requestCookie"]})
        require(self.marionette.script(g.PRIVATE_WINDOWS_JS, chrome=True) == 0, "Native private injection requires isolated private teardown")
        require(not self.marionette.script(COOKIE_JAR_JS, [True], chrome=True), "Private duh.de cookie already exists before injection")
        self.open_case(case_id, private=True)
        self.observe(consent="true", initial="true", label="native-private-cookie-does-not-inherit-normal-consent")
        private_jar = self.marionette.script(COOKIE_JAR_JS, [True], chrome=True)
        require(len(private_jar) == 1 and private_jar[0]["value"] == "true" and private_jar[0]["private"] is True,
                "Native cookie was not stored in the private cookie jar")
        with self.fixture.lock:
            latest = [row for row in self.fixture.requests if row["route"] == "/cookie" and row["caseId"] == case_id][-1]
        require(latest["requestCookie"] == "true", "Private native injector did not affect the actual document request")
        self.close_private()
        require(not self.marionette.script(COOKIE_JAR_JS, [True], chrome=True), "Native private cookie survived last private context")
        normal_jar = self.marionette.script(COOKIE_JAR_JS, [False], chrome=True)
        require(len(normal_jar) == 1 and normal_jar[0]["value"] == "existing-consent", "Private native injection changed normal consent")
        self.evidence.check("native-private-injection-and-teardown", {"privateCookie": private_jar, "normalCookie": normal_jar})

    def optional(self, name, action):
        try:
            action()
        except Pending as error:
            self.evidence.pending(name, str(error))
            # Do not silently close an unknown or unrelated tab. Close only the
            # private tab this runner knows it created, through its real menu.
            self.ui.close_panels()
            if self.private:
                self.close_private()

    def run(self):
        self.prerequisite()
        self.start_fixtures()
        bootstrap = self.fixture.case("plain", bootstrap=True)
        self.open_case(bootstrap, connect=True)
        prefs = self.facts()
        self.verify_controlled_origins()
        if any(prefs.get(name) != 1 for name in
               ("cookiebanners.service.mode", "cookiebanners.service.mode.privateBrowsing")):
            raise Pending("The dedicated profile must start with both real global controls enabled; "
                          "an existing saved Off choice is not evidence of a broken shipped default")
        self.core()
        if self.args.core_only:
            raise Pending("Packaged global-rule core passed; full lifecycle/controls/injection coverage was not requested")
        self.normal_restart()
        self.private_lifetime()
        self.optional("global-controls", self.global_controls)
        self.optional("normal-site-controls", lambda: self.site_controls(False))
        self.optional("private-site-controls-and-teardown", lambda: self.site_controls(True))
        self.optional("native-domain-injection", self.native_injection)
        for item in self.evidence.data["installed"]["apk"]:
            require(self.shell("sha256sum", item["path"]).strip().split()[0] == item["sha256"], "Installed APK changed during cookie checks")
        completed = {check["name"] for check in self.evidence.data["checks"]}
        missing = sorted(REQUIRED-completed)
        if missing or self.evidence.data["pending"]:
            raise Pending("Cookie acceptance incomplete: " + ", ".join(missing))
        self.evidence.finish("PASS", "All installed-release cookie acceptance criteria passed", True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default=shutil.which("adb"))
    parser.add_argument("--serial")
    parser.add_argument("--package", default="org.redoubtbrowser")
    parser.add_argument("--apk", type=Path)
    parser.add_argument("--work", type=Path, default=Path.home()/".cache/redoubt-cookie-smoke")
    parser.add_argument("--dedicated-test-profile", action="store_true")
    parser.add_argument("--marionette-port", type=int)
    parser.add_argument("--device-marionette-port", type=int, default=2828)
    parser.add_argument("--connect-timeout", type=int, default=60)
    parser.add_argument("--ui-timeout", type=int, default=25)
    parser.add_argument("--no-screenshots", action="store_true")
    parser.add_argument("--core-only", action="store_true", help="diagnostic core; full acceptance deliberately remains PENDING")
    parser.add_argument("--scheme", default="redoubt", help="actual installed app's Settings deep-link scheme")
    parser.add_argument("--fixture-port", type=int, default=0, help="fixed host HTTP port for an externally prepared HTTPS fixture mapping")
    parser.add_argument("--site-origin", help="controlled HTTPS origin mapped to this fixture, required for registrable per-site modes")
    parser.add_argument("--injection-origin", help="controlled HTTPS duh.de origin mapped to this fixture; no DNS/certificate changes are made")
    parser.add_argument("--fixture-ca-sha256", help="SHA256 of the trusted fixture CA certificate; required for controlled HTTPS origins")
    args = parser.parse_args(argv)
    if args.fixture_ca_sha256:
        args.fixture_ca_sha256 = args.fixture_ca_sha256.replace(":", "").lower()
        if not re.fullmatch(r"[0-9a-f]{64}", args.fixture_ca_sha256):
            parser.error("Fixture CA SHA256 must contain 64 hexadecimal digits")
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.]+", args.package) or not re.fullmatch(r"[a-z][a-z0-9+.-]*", args.scheme):
        parser.error("Invalid package or deep-link scheme")
    if args.connect_timeout <= 0 or args.ui_timeout <= 0 or not 0 <= args.fixture_port <= 65535:
        parser.error("Timeouts must be positive and fixture port between 0 and 65535")
    for port in (args.marionette_port, args.device_marionette_port):
        if port is not None and not 1 <= port <= 65535:
            parser.error("Transport ports must be between 1 and 65535")
    for name in ("site_origin", "injection_origin"):
        value = getattr(args, name)
        if value:
            try:
                parsed = urllib.parse.urlsplit(value)
                if parsed.scheme != "https" or not parsed.hostname or parsed.path not in ("", "/") or \
                        parsed.query or parsed.fragment or parsed.username is not None or parsed.password is not None or \
                        (parsed.port is not None and not 1 <= parsed.port <= 65535):
                    raise ValueError()
                origin = g.canonical_origin(value)
            except (ValueError, Failure):
                parser.error("Controlled origins must be valid HTTPS origins without paths, credentials or queries")
            if name == "injection_origin" and parsed.hostname != "duh.de":
                parser.error("Native packaged injection requires the actual duh.de domain")
            if not args.fixture_port:
                parser.error("Controlled mappings require an explicit --fixture-port")
            setattr(args, name, origin)
    run = secrets.token_hex(8)
    evidence = Evidence(args.work/run, run, "core" if args.core_only else "full")
    evidence.data["inputs"] = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                              for name in ["scripts/android-cookie-banner-smoke.py", "scripts/android-graphics-smoke.py"]}
    runner, status = None, PENDING
    try:
        if not args.adb or not shutil.which(args.adb):
            raise Pending("adb is unavailable; no cookie behavior was tested")
        protocol = g.foundation()
        adb = protocol.Adb(args.adb, args.serial)
        devices = adb.devices()
        if args.serial and args.serial not in devices:
            raise Pending("Requested device is not connected and authorized")
        if not args.serial:
            if len(devices) != 1:
                raise Pending("Select one connected device; no cookie behavior was tested")
            adb.serial = devices[0]
        if not args.dedicated_test_profile:
            raise Pending("Consent, process and private-lifecycle tests require a dedicated test profile")
        runner = Runner(args, evidence, protocol, adb)
        runner.run()
        if evidence.data["status"] != "PASS" or evidence.data["acceptanceComplete"] is not True:
            raise Pending("Runner returned without complete cookie acceptance evidence")
        status = PASS
    except Pending as error:
        evidence.finish("PENDING", str(error))
    except Exception as error:
        evidence.finish("FAIL", str(error))
        status = FAIL
    except KeyboardInterrupt:
        evidence.finish("PENDING", "Interrupted before complete cookie acceptance")
    finally:
        if runner:
            if status != PASS:
                runner.diagnostics()
            try:
                runner.close()
            except Exception as error:
                evidence.event("cleanup-error", {"error": str(error)})
                if status == PASS:
                    evidence.finish("FAIL", "Cleanup failed after cookie checks")
                    status = FAIL
    print(json.dumps({"status": evidence.data["status"], "acceptanceComplete": evidence.data["acceptanceComplete"],
                      "passedChecks": len(evidence.data["checks"]), "pending": evidence.data["pending"],
                      "reason": evidence.data["reason"], "report": str(evidence.path)}))
    return status


if __name__ == "__main__":
    sys.exit(main())
