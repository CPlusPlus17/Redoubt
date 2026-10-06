import sys,time,json; from vb import *
which=sys.argv[1]; extra=json.loads(sys.argv[2]) if len(sys.argv)>2 else None
pkg=fresh(which,prefs=extra)
start_url(pkg,"https://10.0.2.2:8766/t.html"); time.sleep(6); dismiss_onboarding(); start_url(pkg,"https://10.0.2.2:8766/t.html")
assert_owner(pkg); m=connect(); assert_owner(pkg)
BR=["media.","autoplay","privacy.","webgl.","gfx.","dom.","security.","network.","javascript.options.","layers.","browser.","fission.","extensions.webextensions"]
d=m.script("""let out={};for(const n of Services.prefs.getChildList("")){ if(!arguments[0].some(b=>n.startsWith(b)||n.includes(b))) continue;
 let t=Services.prefs.getPrefType(n),v=null;try{v=t==32?Services.prefs.getStringPref(n):t==64?Services.prefs.getIntPref(n):t==128?Services.prefs.getBoolPref(n):null}catch(e){v="?"}
 out[n]=[v,Services.prefs.prefIsLocked(n),Services.prefs.prefHasUserValue(n)]}return out""",[BR],chrome=True)
# remote / process facts
d["__proc"]=m.script("""return {remoteTypes:Services.appinfo.remoteType||null, fission:Services.appinfo.fissionAutostart, os:Services.appinfo.OS}""",chrome=True)
json.dump(d,open(RUNS+"/prefs-%s.json"%which,"w"),indent=0,sort_keys=True)
print(which,len(d))
ps=sh("ps -A -Z | grep %s"%pkg); print(ps); open(RUNS+"/ps-%s.txt"%which,"w").write(ps)
