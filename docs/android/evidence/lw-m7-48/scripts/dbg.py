import os,sys,time,json
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from vb import *
import spike_cfg
which=sys.argv[1]; pkg=fresh("redoubt",prefs=spike_cfg.CONFIGS[which])
U0="https://10.0.2.2:8796/t.html"
start_url(pkg,U0); time.sleep(6); dismiss_onboarding(); start_url(pkg,U0)
m=connect(); trust_ca(m)
res={}
for src in ["h264.mp4","aac.m4a","vp9.webm","av1.webm","hlsf/index.m3u8"]:
    open_fg(m,pkg,U0+"?src=%s&mode=muted"%src); time.sleep(6)
    m.cmd("Marionette:SetContext",{"value":"content"})
    r=m.cmd("WebDriver:ExecuteAsyncScript",{"script":"""let cb=arguments[arguments.length-1];
      let v=document.getElementById('v');
      try{ v.mozRequestDebugInfo().then(d=>cb(JSON.stringify(d))).catch(e=>cb('ERR '+e)); }catch(e){cb('EXC '+e)}""","args":[],"sandbox":"system"})
    val=r.get("value") if isinstance(r,dict) else r
    try:
        d=json.loads(val); dec=d.get("decoder",{}); rd=dec.get("reader",{})
        res[src]={"audio":rd.get("audioDecoderName"),"video":rd.get("videoDecoderName"),"hw":rd.get("videoHardwareAccelerated")}
    except Exception as e:
        res[src]=str(val)[:300]
    print(src,json.dumps(res[src])); sys.stdout.flush()
json.dump(res,open(RUNS+"/decoders-%s.json"%which,"w"),indent=1)
