import json, os, socket, subprocess, sys, time
ADB=[os.path.expanduser("~/redoubt-artifacts/android-sdk/platform-tools/adb"),"-s","emulator-5570"]
os.environ["ANDROID_USER_HOME"]=os.path.expanduser("~/redoubt-artifacts/video-bug/emuhome")
RUNS=os.path.expanduser("~/redoubt-artifacts/video-bug/runs")
PKGS={"redoubt":"org.redoubtbrowser","fenix":"org.mozilla.firefox"}
def adb(*a,timeout=120,check=False):
    return subprocess.run(ADB+list(a),capture_output=True,text=True,timeout=timeout,check=check)
def sh(cmd,timeout=120): return adb("shell",cmd,timeout=timeout).stdout
class Marionette:
    def __init__(self, port, timeout=120):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=20); self.sock.settimeout(timeout)
        self.buf=b""; self.msgid=0; self.hello=self._recv()
    def close(self):
        try: self.sock.close()
        except Exception: pass
    def _recv(self):
        while b":" not in self.buf:
            d=self.sock.recv(65536)
            if not d: raise RuntimeError("closed")
            self.buf+=d
        n,_,rest=self.buf.partition(b":"); n=int(n)
        while len(rest)<n:
            d=self.sock.recv(65536)
            if not d: raise RuntimeError("closed mid")
            rest+=d
        self.buf=rest[n:]; return json.loads(rest[:n].decode())
    def cmd(self,name,params=None):
        self.msgid+=1; mid=self.msgid
        p=json.dumps([0,mid,name,params or {}]).encode()
        self.sock.sendall(str(len(p)).encode()+b":"+p)
        while True:
            m=self._recv()
            if isinstance(m,list) and len(m)==4 and m[0]==1 and m[1]==mid:
                if m[2] is not None: raise RuntimeError("%s: %s"%(name,m[2]))
                return m[3]
    def script(self,js,args=None,chrome=False):
        self.cmd("Marionette:SetContext",{"value":"chrome" if chrome else "content"})
        return self.cmd("WebDriver:ExecuteScript",{"script":js,"args":args or [],"sandbox":None}).get("value")
GV="""args:
  - "-remote-allow-system-access"
env:
  MOZ_MARIONETTE: "1"
prefs:
  remote.prefs.recommended: false
  marionette.port: 2828
"""
def fresh(which, prefs=None, marionette=True):
    pkg=PKGS[which]
    for other in PKGS.values(): sh("am force-stop %s"%other)
    sh("am force-stop %s"%pkg); r=adb("shell","pm","clear",pkg).stdout.strip()
    assert r=="Success",r
    for p in ("android.permission.POST_NOTIFICATIONS",):
        sh("pm revoke %s %s"%(pkg,p))
    sh("rm -f /data/local/tmp/*-geckoview-config.yaml")
    if marionette or prefs:
        body=GV if marionette else "prefs:\n"
        for k,v in sorted((prefs or {}).items()): body+="  %s: %s\n"%(k,json.dumps(v))
        open("/tmp/claude-gv.yaml","w").write(body) if False else None
        loc=os.path.join(RUNS,"gv-%s.yaml"%which); open(loc,"w").write(body)
        adb("push",loc,"/data/local/tmp/%s-geckoview-config.yaml"%pkg,check=True); sh("chmod 644 /data/local/tmp/%s-geckoview-config.yaml"%pkg)
        sh("am set-debug-app --persistent %s"%pkg)
    else:
        sh("am clear-debug-app")
    return pkg
def start_url(pkg,url):
    sh("am start -a android.intent.action.VIEW -d '%s' %s"%(url,pkg))
def connect(port=28280,timeout=120):
    adb("forward","tcp:%d"%port,"tcp:2828")
    dl=time.time()+timeout; last=None
    while time.time()<dl:
        try:
            m=Marionette(port); m.cmd("WebDriver:NewSession",{"capabilities":{"alwaysMatch":{}}}); return m
        except Exception as e: last=e; time.sleep(3)
    raise RuntimeError("no marionette: %s"%last)
def shot(path): 
    with open(path,"wb") as f: f.write(subprocess.run(ADB+["exec-out","screencap","-p"],capture_output=True,timeout=60).stdout)
def logcat_clear(): adb("logcat","-c")
def logcat_dump(path): open(path,"w").write(adb("logcat","-d","-v","threadtime",timeout=120).stdout)
def tap(x,y): sh("input tap %d %d"%(x,y))
def uidump():
    sh("uiautomator dump /sdcard/ui.xml"); return sh("cat /sdcard/ui.xml")
CA_B64="".join(l for l in open(os.path.expanduser("~/redoubt-artifacts/video-bug/tls/ca.pem")).read().splitlines() if "-----" not in l)
def trust_ca(m):
    return m.script("""const db=Cc["@mozilla.org/security/x509certdb;1"].getService(Ci.nsIX509CertDB);
      db.addCertFromBase64(arguments[0],"C,,"); return true;""",[CA_B64],chrome=True)
def nav(m,url):
    m.cmd("Marionette:SetContext",{"value":"content"})
    try: m.cmd("WebDriver:Navigate",{"url":url})
    except Exception as e: return str(e)
def prefs(m,names):
    return m.script("""let o={};for(const n of arguments[0]){let t=Services.prefs.getPrefType(n);
      o[n]= t==32?Services.prefs.getStringPref(n):t==64?Services.prefs.getIntPref(n):t==128?Services.prefs.getBoolPref(n):null}return o""",[names],chrome=True)
def setpref(m,name,val):
    return m.script("""let [n,v]=arguments; if(typeof v=="boolean")Services.prefs.setBoolPref(n,v);else if(typeof v=="number")Services.prefs.setIntPref(n,v);else Services.prefs.setStringPref(n,v);return Services.prefs.prefIsLocked(n)""",[name,val],chrome=True)
def click(m,css):
    m.cmd("Marionette:SetContext",{"value":"content"})
    el=m.cmd("WebDriver:FindElement",{"using":"css selector","value":css})["value"]
    m.cmd("WebDriver:ElementClick",{"id":list(el.values())[0]})

def assert_owner(pkg):
    # the marionette listener on 2828 must belong to pkg: no other browser may run
    for other in PKGS.values():
        if other!=pkg and sh("pidof %s"%other).strip(): raise RuntimeError("%s still running"%other)
import re as _re
DISMISS=("Continue","Not now","Skip","Maybe later","Not Now","NOT NOW","No thanks","Got it","Close","Dismiss")
def dismiss_onboarding(rounds=8, log=print):
    for i in range(rounds):
        x=uidump()
        hit=None
        for mm in _re.finditer(r'<node [^>]*?text="([^"]*)"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',x):
            t=mm.group(1)
            if t in DISMISS:
                hit=(t,(int(mm.group(2))+int(mm.group(4)))//2,(int(mm.group(3))+int(mm.group(5)))//2); break
        if not hit:
            # content-desc variants
            for mm in _re.finditer(r'<node [^>]*?content-desc="([^"]*)"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',x):
                if mm.group(1) in DISMISS:
                    hit=(mm.group(1),(int(mm.group(2))+int(mm.group(4)))//2,(int(mm.group(3))+int(mm.group(5)))//2); break
        if not hit: return i
        log("dismiss",hit); tap(hit[1],hit[2]); time.sleep(2)
    return rounds
def open_fg(m,pkg,url,wait=1.0):
    """Open url through a VIEW intent (a foreground tab, as a user would) and
    point Marionette at that tab; close every other tab first."""
    m.cmd("Marionette:SetContext",{"value":"content"})
    before=set(m.cmd("WebDriver:GetWindowHandles"))
    start_url(pkg,url)
    dl=time.time()+30; new=None
    while time.time()<dl:
        hs=m.cmd("WebDriver:GetWindowHandles"); n=[h for h in hs if h not in before]
        if n: new=n[-1]; break
        try:
            if m.cmd("WebDriver:GetCurrentURL").get("value")==url: new=m.cmd("WebDriver:GetWindowHandle").get("value"); break
        except Exception: pass
        time.sleep(0.3)
    if not new:
        # the intent reused the selected tab
        new=hs[-1]
    m.cmd("WebDriver:SwitchToWindow",{"handle":new})
    for h in before:
        if h!=new:
            try:
                m.cmd("WebDriver:SwitchToWindow",{"handle":h}); m.cmd("WebDriver:CloseWindow")
            except Exception: pass
    m.cmd("WebDriver:SwitchToWindow",{"handle":new})
    time.sleep(wait)
    return new
