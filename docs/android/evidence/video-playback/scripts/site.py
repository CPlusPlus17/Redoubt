import sys,time,json; from vb import *
which,site,tag=sys.argv[1],sys.argv[2],sys.argv[3]
opts=sys.argv[4].split(",") if len(sys.argv)>4 else []
pkg=fresh(which)
logcat_clear()
start_url(pkg,"https://10.0.2.2:8766/t.html")
time.sleep(6); print("onboarding rounds",dismiss_onboarding()); start_url(pkg,"https://10.0.2.2:8766/t.html")
assert_owner(pkg); m=connect(); assert_owner(pkg)
m.cmd("WebDriver:SetTimeouts",{"script":60000,"pageLoad":60000})
pfx=RUNS+"/site-%s-%s"%(site,tag)
log=open(pfx+".txt","w")
def P(*a):
    s=" ".join(str(x) for x in a); print(s); log.write(s+"\n"); log.flush(); sys.stdout.flush()
P("UA",m.script("return navigator.userAgent"))
if "noubo" in opts:
    P("ubo-disable",m.script("""const {AddonManager}=ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
      let a=await AddonManager.getAddonByID("uBlock0@raymondhill.net"); if(!a) return "absent"; await a.disable(); return "disabled";""".replace("let a=await","return (async()=>{let a=await").replace('return "disabled";','return "disabled";})()'),chrome=True))
PROBE="""return {url:location.href,title:document.title,webdriver:navigator.webdriver,
 mse_avc:(typeof MediaSource!='undefined')&&MediaSource.isTypeSupported('video/mp4; codecs="avc1.4d401f"'),
 cpt_avc:document.createElement('video').canPlayType('video/mp4; codecs="avc1.4d401f"'),
 videos:[...document.querySelectorAll('video')].slice(0,6).map(v=>({src:(v.currentSrc||v.src||'').slice(0,120),ct:+v.currentTime.toFixed(2),rs:v.readyState,ns:v.networkState,paused:v.paused,muted:v.muted,err:v.error?v.error.code+':'+v.error.message:null,w:v.videoWidth,box:(()=>{const r=v.getBoundingClientRect();return Math.round(r.width)+'x'+Math.round(r.height)})(),dec:v.getVideoPlaybackQuality?v.getVideoPlaybackQuality().totalVideoFrames:null}))}"""
def probe(lbl):
    try: r=m.script(PROBE)
    except Exception as e: r=str(e)[:300]
    P(lbl,json.dumps(r)); return r
def jsclick(js):
    try: return m.script(js)
    except Exception as e: return "ERR "+str(e)[:200]
if site=="redgifs":
    P("nav",open_fg(m,pkg,"https://www.redgifs.com/"))
    time.sleep(12); shot(pfx+"-1-home.png"); probe("home-t12")
    P("agegate",jsclick("""for(const b of document.querySelectorAll('button,a')){const t=(b.innerText||'').trim().toLowerCase(); if(/i am 18|i'm 18|18\\+|continue|enter|accept|agree/.test(t)){b.click();return t}} return null"""))
    time.sleep(3)
    href=jsclick("""const a=[...document.querySelectorAll('a[href*="/watch/"]')][0]; return a?a.href:null""")
    P("watch",href)
    if href and href.startswith("http"):
        nav(m,href); time.sleep(12)
    else:
        nav(m,"https://www.redgifs.com/browse"); time.sleep(12)
    shot(pfx+"-2-watch.png"); a=probe("watch-t12")
    P("click-video",jsclick("""const v=document.querySelector('video'); if(!v) return null; const p=v.play(); return p?'play() called':'no promise'"""))
    time.sleep(6); probe("watch-t18"); time.sleep(4); probe("watch-t22"); shot(pfx+"-3-after.png")
elif site=="pornhub":
    P("nav",open_fg(m,pkg,"https://www.pornhub.com/"))
    time.sleep(10); shot(pfx+"-1-home.png"); probe("home")
    P("agegate",jsclick("""for(const b of document.querySelectorAll('button,a,div[role=button]')){const t=(b.innerText||'').trim().toLowerCase(); if(/i am 18|18 or older|enter$|^enter/.test(t)){b.click();return t}} return null"""))
    time.sleep(4); shot(pfx+"-2-after-gate.png")
    href=jsclick("""const a=[...document.querySelectorAll('a[href*="view_video.php"]')][0]; return a?a.href:null""")
    P("video-page",href)
    if href and href.startswith("http"):
        nav(m,href); time.sleep(12); shot(pfx+"-3-video.png"); probe("video-t12")
        P("agegate2",jsclick("""for(const b of document.querySelectorAll('button,a')){const t=(b.innerText||'').trim().toLowerCase(); if(/i am 18|18 or older/.test(t)){b.click();return t}} return null"""))
        P("consent",jsclick("""for(const b of document.querySelectorAll('button,a')){const t=(b.innerText||'').trim().toLowerCase(); if(/only essential|reject all|necessary only/.test(t)){b.click();return t}} return null"""))
        time.sleep(2)
        r=jsclick("""const c=document.querySelector('#player, .mgp_container, [id^=playerDiv], .playerFlvContainer'); if(!c) return null; c.scrollIntoView({block:'center'}); const r=c.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2,w:r.width,h:r.height,dpr:devicePixelRatio,id:c.id||c.className}""")
        P("player",r)
        time.sleep(1)
        if isinstance(r,dict):
            r=jsclick("""const c=document.querySelector('#player, .mgp_container, [id^=playerDiv], .playerFlvContainer'); const r=c.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2,dpr:devicePixelRatio,iw:innerWidth}""")
            k=1080.0/r["iw"]; X=int(r["x"]*k); Y=int(231+r["y"]*k); P("adb-tap",X,Y); tap(X,Y)
            time.sleep(3); shot(pfx+"-3b-tapped.png")
            time.sleep(2); probe("video-after-tap5")
        time.sleep(10); probe("video-t20"); time.sleep(5); probe("video-t30"); shot(pfx+"-4-after.png")
        P("play-err",jsclick("return window.__pe||null"))
logcat_dump(pfx+".logcat")
