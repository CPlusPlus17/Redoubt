import os,sys,time,json; from vb import *
which=sys.argv[1]; tag=sys.argv[2] if len(sys.argv)>2 else which
extra=json.loads(sys.argv[3]) if len(sys.argv)>3 else None
pkg=fresh(which,prefs=extra)
logcat_clear()
start_url(pkg,"https://10.0.2.2:8766/t.html")
time.sleep(6); print("onboarding rounds",dismiss_onboarding()); start_url(pkg,"https://10.0.2.2:8766/t.html")
assert_owner(pkg); m=connect(); assert_owner(pkg); trust_ca(m)
print("UA",m.script("return navigator.userAgent")); sys.stdout.flush()
out=[]
U="https://10.0.2.2:8766/t.html?src=%s&mode=%s"
SRCS=os.environ.get("SRCS"); MODES=os.environ.get("MODES","muted,autoplay,click").split(",")
for src in (SRCS.split(",") if SRCS else ["h264.mp4","h264-noaudio.mp4","aac.m4a","vp9.webm","av1.webm","av1.mp4","hls/index.m3u8","hlsf/index.m3u8"]):
  for mode in MODES:
    open_fg(m,pkg,U%(src,mode)); time.sleep(4)
    pre=m.script("return window.__st")
    if mode!="muted":
        try: click(m,"#go")
        except Exception as e: print("click fail",e)
    time.sleep(4)
    a=m.script("return window.__st"); time.sleep(2); b=m.script("return window.__st")
    ok = b and b["ct"]>a["ct"] and not b["paused"]
    row={"src":src,"mode":mode,"pre_ct":pre and pre["ct"],"pre_paused":pre and pre["paused"],"ct1":a and a["ct"],"ct2":b and b["ct"],"playing":bool(ok),"err":b and b["err"],"dec":b and b["dec"],"vw":b and b["vw"],"ev":b and b["ev"][-8:]}
    out.append(row); print(json.dumps(row)); sys.stdout.flush()
    if src=="h264.mp4": shot(RUNS+"/local-%s-%s-%s.png"%(tag,src.replace("/","_"),mode))
print("CPT",json.dumps(b["cpt"]),b["mse"])
print("PREFS",json.dumps(prefs(m,["media.utility-android-media-codec.enabled","media.gpu-process-decoder","media.rdd-process.enabled","media.android-media-codec.enabled","media.utility-process.enabled"])))
json.dump(out,open(RUNS+"/local-%s.json"%tag,"w"),indent=1)
logcat_dump(RUNS+"/local-%s.logcat"%tag)
