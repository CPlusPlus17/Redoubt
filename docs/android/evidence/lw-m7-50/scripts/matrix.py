"""LW-M7-50 video matrix: every case x mode, REPEATS rounds, fresh profile per round.
Derived from LW-M7-48's spike.py (evidence/lw-m7-48/scripts). Env: SERIAL, APPKEY
(dev|redoubt), CONFIG (none|iso-rdd), REPEATS, TAG, PORT, RUNS."""
import os, sys, time, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb import *
import spike_cfg
APPKEY = os.environ.get("APPKEY", "dev"); CONFIG = os.environ.get("CONFIG", "none")
REPEATS = int(os.environ.get("REPEATS", "3")); TAG = os.environ.get("TAG", "iso-on")
PORT = int(os.environ.get("PORT", "8796"))
extra = {} if CONFIG == "none" else spike_cfg.CONFIGS[CONFIG]
LONG = ["h264.mp4", "h264-noaudio.mp4", "aac.m4a", "vp9.webm", "av1.webm", "av1.mp4",
        "hls/index.m3u8", "hlsf/index.m3u8", "hls/index.m3u8&native=1"]
SHORT = {"short-h264-05.mp4": 15, "short-h264-03.mp4": 9, "short-h264-noaudio-05.mp4": 15,
         "short-aac-05.m4a": 0, "short-vp9-05.webm": 15}
SRCS = os.environ.get("SRCS"); SRCS = SRCS.split(",") if SRCS else LONG + list(SHORT)
MODES = os.environ.get("MODES", "muted,click").split(",")
U0 = "https://10.0.2.2:%d/t.html" % PORT
DBG = """let cb=arguments[arguments.length-1]; let v=document.getElementById('v');
try{ v.mozRequestDebugInfo().then(d=>{let r=(d&&d.decoder&&d.decoder.reader)||{};
 cb({audio:r.audioDecoderName||null,video:r.videoDecoderName||null,hw:!!r.videoHardwareAccelerated});}).catch(e=>cb({err:''+e})); }catch(e){cb({err:''+e})}"""
allrows = []
for rnd in range(1, REPEATS + 1):
    pkg = fresh(APPKEY, prefs=extra)
    logcat_clear()
    start_url(pkg, U0); time.sleep(6); dismiss_onboarding(); start_url(pkg, U0)
    assert_owner(pkg); m = connect(); assert_owner(pkg); trust_ca(m)
    if rnd == 1:
        print("UA", m.script("return navigator.userAgent")); sys.stdout.flush()
    for src in SRCS:
        short = src in SHORT
        for mode in MODES:
            open_fg(m, pkg, U0 + "?src=%s&mode=%s" % (src, mode)); time.sleep(4)
            if mode != "muted":
                try: click(m, "#go")
                except Exception as e: print("click fail", e)
            if short:
                b = None
                for _ in range(24):
                    time.sleep(0.5); b = m.script("return window.__st")
                    if b and (b.get("ended") or b.get("err")): break
                a = b
                exp = SHORT[src]
                ok = bool(b and b.get("ended") and not b.get("err") and (exp == 0 or (b.get("dec") or 0) >= exp))
            else:
                time.sleep(4)
                a = m.script("return window.__st"); time.sleep(2); b = m.script("return window.__st")
                ok = bool(b and a and b["ct"] > a["ct"] and not b["paused"])
            try:
                m.cmd("Marionette:SetContext", {"value": "content"})
                d = m.cmd("WebDriver:ExecuteAsyncScript", {"script": DBG, "args": [], "sandbox": "system"})
                d = d.get("value", d) if isinstance(d, dict) else d
            except Exception as e:
                d = {"err": str(e)[:200]}
            row = {"round": rnd, "src": src, "mode": mode, "short": short, "expect_frames": SHORT.get(src),
                   "ct1": a and a.get("ct"), "ct2": b and b.get("ct"), "ended": b and b.get("ended"),
                   "pass": ok, "err": b and b.get("err"), "dec": b and b.get("dec"), "vw": b and b.get("vw"),
                   "decoders": d, "ev": b and b.get("ev", [])[-10:]}
            allrows.append(row); print(json.dumps(row)); sys.stdout.flush()
    cpt = m.script("return window.__st")
    ps = sh("ps -A -o LABEL,USER,PID,PPID,NAME")
    psl = [l for l in ps.splitlines() if pkg in l or "LABEL" in l]
    open(RUNS + "/%s-r%d-ps.txt" % (TAG, rnd), "w").write("\n".join(psl) + "\n")
    logcat_dump(RUNS + "/%s-r%d.logcat" % (TAG, rnd))
    pidname = {}
    for l in psl[1:]:
        f = l.split()
        if len(f) >= 5: pidname[f[2]] = (f[0], f[4])
    alloc = {}; den = []
    for l in open(RUNS + "/%s-r%d.logcat" % (TAG, rnd), errors="replace"):
        mm = re.search(r" CCodec\s*: allocate\(([^)]*)\)", l)
        if mm:
            pid = l.split()[2]; who = pidname.get(pid, ("?", "exited-pid-" + pid))
            alloc.setdefault("%s %s" % (who[1], who[0]), []).append(mm.group(1))
        if "avc:" in l and "denied" in l and "isolated_app" in l:
            den.append(l.strip()[:260])
    summary = {"round": rnd, "cpt": cpt and cpt.get("cpt"), "mse": cpt and cpt.get("mse"),
               "ccodec_allocate": {k: sorted(set(v)) + ["x%d" % len(v)] for k, v in alloc.items()},
               "isolated_app_denials": den, "ps": psl}
    print("ROUND", json.dumps(summary)); sys.stdout.flush()
    allrows.append({"round_summary": summary})
    m.close()
json.dump({"tag": TAG, "app": APPKEY, "config": CONFIG, "repeats": REPEATS, "rows": allrows},
          open(RUNS + "/%s.json" % TAG, "w"), indent=1)
res = [r for r in allrows if "pass" in r]
print("TOTAL", sum(r["pass"] for r in res), "/", len(res))
