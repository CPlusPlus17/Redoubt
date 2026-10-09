import os, sys, time, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb import *

CONFIGS = {
    "iso-base": {},
    # upstream's geckoview-isolated-process test variant (bug 1988531 part 1,
    # taskcluster/test_configs/variants.yml, landed 2026-10-06 for 159)
    "iso-rdd": {
        "media.android-media-codec.enabled": False,
        "media.android-media-codec.preferred": False,
        "media.ffmpeg.encoder.enabled": True,
        "media.ffvpx-hw.enabled": True,
        "media.rdd-ffvpx.enabled": True,
        "media.rdd-opus.enabled": True,
        "media.rdd-process.enabled": True,
        "media.rdd-vorbis.enabled": True,
        "media.rdd-vpx.enabled": True,
        "media.rdd-wav.enabled": True,
        "media.use-remote-encoder.video.platform": True,
    },
    # GPU-process variant: NDK MediaCodec via ffvpx in the GPU process,
    # AAC via the Java module in the utility process
    "iso-gpu": {
        "media.gpu-process-decoder": True,
        "media.ffvpx-hw.enabled": True,
        "media.utility-android-media-codec.enabled": True,
    },
}
PORT = int(os.environ.get("PORT", "8796"))
cfg = sys.argv[1]
tag = sys.argv[2] if len(sys.argv) > 2 else cfg
extra = CONFIGS[cfg]
pkg = fresh("redoubt", prefs=extra)
logcat_clear()
U0 = "https://10.0.2.2:%d/t.html" % PORT
start_url(pkg, U0)
time.sleep(6); print("onboarding rounds", dismiss_onboarding()); start_url(pkg, U0)
assert_owner(pkg); m = connect(); assert_owner(pkg); trust_ca(m)
print("UA", m.script("return navigator.userAgent")); sys.stdout.flush()
out = []
U = U0 + "?src=%s&mode=%s"
SRCS = os.environ.get("SRCS")
SRCS = SRCS.split(",") if SRCS else ["h264.mp4", "h264-noaudio.mp4", "aac.m4a", "vp9.webm", "av1.webm", "av1.mp4",
                                     "hls/index.m3u8", "hlsf/index.m3u8", "hls/index.m3u8&native=1"]
MODES = os.environ.get("MODES", "muted,click").split(",")
b = None
for src in SRCS:
    for mode in MODES:
        open_fg(m, pkg, U % (src, mode)); time.sleep(4)
        pre = m.script("return window.__st")
        if mode != "muted":
            try: click(m, "#go")
            except Exception as e: print("click fail", e)
        time.sleep(4)
        a = m.script("return window.__st"); time.sleep(2); b = m.script("return window.__st")
        ok = bool(b and a and b["ct"] > a["ct"] and not b["paused"])
        row = {"src": src, "mode": mode, "ct1": a and a["ct"], "ct2": b and b["ct"], "playing": ok,
               "err": b and b["err"], "dec": b and b["dec"], "vw": b and b["vw"], "ev": b and b["ev"][-8:]}
        out.append(row); print(json.dumps(row)); sys.stdout.flush()
        if src == "h264.mp4" and mode == "muted":
            shot(RUNS + "/%s-h264-muted.png" % tag)
print("CPT", json.dumps(b["cpt"]), "MSE", b["mse"])
pnames = sorted(set(list(extra.keys()) + ["media.rdd-process.enabled", "media.gpu-process-decoder",
        "media.ffvpx-hw.enabled", "media.utility-android-media-codec.enabled", "media.android-media-codec.enabled"]))
pv = prefs(m, pnames); print("PREFS", json.dumps(pv))
ps = sh("ps -A -Z -o LABEL,USER,PID,PPID,NAME")
psl = [l for l in ps.splitlines() if "redoubt" in l or "LABEL" in l]
open(RUNS + "/%s-ps.txt" % tag, "w").write("\n".join(psl) + "\n")
print("\n".join(psl))
logcat_dump(RUNS + "/%s.logcat" % tag)
pidname = {}
for l in psl[1:]:
    f = l.split()
    if len(f) >= 6: pidname[f[3]] = (f[0], f[5])
alloc = {}
for l in open(RUNS + "/%s.logcat" % tag, errors="replace"):
    mm = re.search(r" CCodec\s*: allocate\(([^)]*)\)", l)
    if mm:
        pid = l.split()[2]
        k = (pidname.get(pid, ("?", "pid " + pid))[1], mm.group(1))
        alloc[k] = alloc.get(k, 0) + 1
calloc = [{"proc": k[0], "codec": k[1], "n": v} for k, v in sorted(alloc.items())]
print("CCODEC", json.dumps(calloc))
den = {}
for l in open(RUNS + "/%s.logcat" % tag, errors="replace"):
    if "avc:  denied" in l and "isolated_app" in l:
        k = re.sub(r"ino=\d+ ", "", l.split("avc:  denied", 1)[1]).strip()
        k = re.sub(r"comm=\S+ ", "", k)
        den[k] = den.get(k, 0) + 1
print("ISO_DENIALS", json.dumps(den, indent=0))
json.dump({"isolated_app_denials": den, "config": cfg, "prefs_set": extra, "prefs_read": pv, "rows": out, "cpt": b["cpt"], "mse": b["mse"],
           "ps": psl, "ccodec_allocate": calloc}, open(RUNS + "/%s.json" % tag, "w"), indent=1)
