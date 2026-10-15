#!/usr/bin/env python3
"""(lw-m7-51's drm-flow.py, LW-M7-39 rerun: EME_OUT env = eme-server.py's OUTDIR; choice "Play" opens
play.html ("PlayLow": lowest H.264 variant, 60 s; "PlaySwitch": highest H.264 variant from 10 s on, 50 s), a real Widevine stream, and waits for its report.)
LW-M7-39 device flow on ONE emulator: EME probe by default, then after each choice in
Settings > Site settings > DRM-controlled content. Assumes the APK under test is installed and
eme-server.py is listening on PORT with `adb reverse tcp:PORT tcp:PORT` in place.
usage: drm-flow.py SERIAL LABEL OUTDIR PORT [choice ...]   (choices: Allowed, Ask, Blocked)"""
import json, os, re, subprocess, sys, time
from ui import UI, ADB
serial, label, out, port = sys.argv[1:5]
choices = sys.argv[5:]
assert serial.startswith("emulator-")
os.makedirs(out, exist_ok=True)
u = UI(serial)
EME = os.path.expanduser(os.environ["EME_OUT"])
def shot(name):
    with open(os.path.join(out, name + ".png"), "wb") as f:
        f.write(subprocess.run([ADB, "-s", serial, "exec-out", "screencap", "-p"], capture_output=True).stdout)
def play(tag, wait=90, extra=""):
    tag = f"{label}-{tag}"
    p = os.path.join(EME, tag + ".json")
    if os.path.exists(p):
        os.remove(p)
    u.sh("input", "keyevent", "KEYCODE_WAKEUP")
    u.sh("am", "start", "-a", "android.intent.action.VIEW", "-d", "'" + f"http://127.0.0.1:{port}/play.html?tag={tag}{extra}" + "'", "org.redoubtbrowser")   # quoted: adb shell runs one string through sh, and '&' would end the am command
    for i in range(wait):
        time.sleep(1)
        if i == 20:
            shot(f"{tag}-20s")
        if os.path.exists(p):
            break
    shot(tag)
    r = json.load(open(p)) if os.path.exists(p) else {"tag": tag, "error": "no report within %ds" % wait}
    json.dump(r, open(os.path.join(out, tag + ".json"), "w"), indent=1)
    print(tag, "ok=%s t=%s frames=%s variant=%s errors=%s" % (r.get("ok"), r.get("currentTime"), r.get("decodedFrames"), r.get("activeVariant"), r.get("errors")))
    return r
def probe(tag, wait=60):
    tag = f"{label}-{tag}"
    p = os.path.join(EME, tag + ".json")
    if os.path.exists(p):
        os.remove(p)
    u.sh("input", "keyevent", "KEYCODE_WAKEUP")
    u.sh("am", "start", "-a", "android.intent.action.VIEW", "-d", f"http://127.0.0.1:{port}/eme-probe.html?tag={tag}", "org.redoubtbrowser")
    prompt = None
    for i in range(wait):
        time.sleep(1)
        if i in (6, 12):   # while a request may be pending: is there a DRM prompt on screen?
            u.dump(save=os.path.join(out, f"{tag}-ui-{i}s.xml"))
            t = u.texts()
            hit = [x for x in t if re.search(r"DRM|protected content|Allow|Don.t allow|Block", x)]
            if hit and prompt is None:
                prompt = hit
                shot(f"{tag}-prompt")
        if os.path.exists(p):
            break
    shot(tag)
    r = json.load(open(p)) if os.path.exists(p) else {"tag": tag, "error": "no report within %ds" % wait}
    r["ui_prompt_texts"] = prompt
    json.dump(r, open(os.path.join(out, tag + ".json"), "w"), indent=1)
    print(tag, [(x["ks"], x["result"], x.get("message")) for x in r.get("results", [])], "prompt:", prompt)
    return r
def drm_screen(select=None):
    u.sh("am", "start", "-a", "android.intent.action.VIEW", "-d", "redoubt://settings", "org.redoubtbrowser")
    time.sleep(3)
    assert u.scroll_to(r"^Site settings$"), "no Site settings"
    u.tap(r"^Site settings$")
    assert u.scroll_to(r"^DRM-controlled content$"), "no DRM-controlled content"
    labels = u.texts()
    i = labels.index("DRM-controlled content")
    summary = labels[i + 1] if i + 1 < len(labels) else None
    u.tap(r"^DRM-controlled content$")
    u.dump()
    radios = [(n.get("text"), n.get("checked")) for n in u.nodes() if n.get("class") == "android.widget.RadioButton"]
    state = {"site_settings_summary": summary, "radios_before": radios}
    if select:
        pat = {"Allowed": r"^Allowed$", "Ask": r"^Ask to allow", "Blocked": r"^Blocked"}[select]
        u.tap(pat)
        u.dump()
        state["selected"] = select
        state["radios_after"] = [(n.get("text"), n.get("checked")) for n in u.nodes() if n.get("class") == "android.widget.RadioButton"]
    shot(f"{label}-drm-screen-{select or 'view'}")
    for _ in range(3):
        u.sh("input", "keyevent", "KEYCODE_BACK"); time.sleep(0.7)
    print("drm screen:", json.dumps(state))
    return state
log = {"serial": serial, "label": label, "steps": []}
log["steps"].append({"probe": probe("default")})
log["steps"].append({"screen": drm_screen()})
for c in choices:
    if c == "Play":
        log["steps"].append({"play": play("play")})
        continue
    if c == "PlayLow":   # lowest H.264 variant pinned, no quality switch, 60 s
        log["steps"].append({"play": play("play-low", wait=110, extra="&abr=0&secs=60")})
        continue
    if c == "PlaySwitch":   # switch to the highest H.264 variant after 10 s, 50 s
        log["steps"].append({"play": play("play-switch", wait=100, extra="&switch=10&secs=50")})
        continue
    log["steps"].append({"screen": drm_screen(c)})
    log["steps"].append({"probe": probe("after-" + c.lower())})
json.dump(log, open(os.path.join(out, label + "-flow.json"), "w"), indent=1)
