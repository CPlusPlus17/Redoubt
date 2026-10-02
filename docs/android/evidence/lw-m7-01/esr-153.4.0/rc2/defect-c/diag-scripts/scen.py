#!/usr/bin/env python3
"""Scratch scenario for defect C: quiet Review action in normal vs private tab.

Modes:
  normal  fresh profile, normal tab, Review
  back    fresh, normal page, then New private tab + Review, then New tab + Review
  b2      as back, on Beta 2 (handles its uBO Retry dialog), plus a fresh-normal Review first
  rep N   fresh, then N times: private Review, normal Review (alternating mode switches)
  back-kbd  as back, but after each typed URL the stuck soft keyboard is closed the way the
          fixed graphics harness does it (1.5 s grace, then force-stop of the default IME);
          the typed pages use fix/delayed.html, whose requests come 4 s after load, as the
          harness's probes come after navigation
"""
import os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drv import *

URL = "http://localhost:8765/index.html"


def fresh():
    sh("pm clear " + PKG)
    sh("logcat -c", check=False)
    sh("monkey -p " + PKG + " -c android.intent.category.LAUNCHER 1 >/dev/null")
    end = time.monotonic() + 90
    while time.monotonic() < end:
        x = dump("start")
        r = find(x, text="Retry")
        if r is not None:  # Beta 2's known uBO setup failure; a real user action
            tap(r, "ubo-retry"); time.sleep(3); continue
        o = find(x, text="OK")
        if o is not None and find(x, text="uBlock Origin was added") is not None:
            tap(o, "ubo-ok"); time.sleep(1.5); log("fresh ready"); return
        time.sleep(1)
    raise SystemExit("not ready: %s" % texts(x))


def width(n):
    b = list(map(int, re.findall(r"\d+", n.get("bounds"))))
    return b[2] - b[0]


def counter(x):
    for n in nodes(x):
        d = n.get("content-desc") or ""
        if re.fullmatch(r"(?:Private |Non-private )?Tabs Open: .+\. Tap to switch tabs\.", d):
            return n
    return None


def type_url(url):
    x = dump("url-entry")
    f = find(x, rid="ADDRESSBAR_SEARCH_BOX")
    if f is None:
        f = find(x, rid="ADDRESSBAR_URL_BOX")
    tap(f, "url-field")
    time.sleep(0.8)
    sh("input text", "'" + url + "'")
    sh("input keyevent 66")
    log("url submitted", url)


def close_keyboard():
    """Mirror of android-graphics-smoke.py UI.close_soft_keyboard (scratch copy)."""
    def ime_window():
        out = sh("dumpsys input", check=False).split("Input Dispatcher State at time of last ANR")[0]
        m = re.search(r"name='Window\{\w+ u0 InputMethod\}'.*?visible=(\w+).*?touchableRegion=(\S+?),", out)
        return m if m and m.group(1) == "true" and m.group(2) != "<empty>" else None
    time.sleep(1.5)
    if ime_window() is None:
        log("keyboard closed by itself"); return
    ime = sh("settings get secure default_input_method").strip().split("/")[0]
    sh("am force-stop " + ime); log("keyboard stuck; force-stopped", ime)
    for _ in range(25):
        if ime_window() is None: return
        time.sleep(0.2)
    raise SystemExit("keyboard still takes touches")


def open_normal(url=URL):
    sh(f"am start -a android.intent.action.VIEW -d '{url}' {PKG} >/dev/null")
    log("normal VIEW intent sent")


def open_via_menu(item, url=URL, kbd=False):
    x = dump("before-counter")
    c = counter(x)
    sh("input swipe", c.get("cx"), c.get("cy"), c.get("cx"), c.get("cy"), "750")
    log("long-press counter")
    end = time.monotonic() + 15
    while True:
        x = dump("tab-menu")
        cands = [m for m in nodes(x) if m.get("package") == PKG and
                 item in (m.get("content-desc"), m.get("text")) and width(m) > 300]
        if cands:
            tap(cands[0], "menu-" + item)
            break
        if time.monotonic() > end:
            raise SystemExit("no menu item %s: %s" % (item, texts(x)))
    time.sleep(1.5)
    type_url(url)
    if kbd:
        close_keyboard()


def review(label):
    end = time.monotonic() + 25
    while True:
        x = dump(label + "-snack")
        n = find(x, text="Review", rid="snackbar_action")
        if n is not None:
            t_seen = time.monotonic(); log("snackbar seen"); break
        if time.monotonic() > end:
            log("NO SNACKBAR", texts(x)[:20]); return "no-snackbar"
    tap(n, "review")
    t_tap = time.monotonic()
    x, d = wait(8, label=label + "-after", rid="origin_permissions_dialog_list")
    if d is not None:
        log(f"DIALOG OPEN {label} (tap {t_tap - t_seen:.2f}s after seen)")
        close_dialog()
        return "open"
    log(f"NO DIALOG {label} (tap {t_tap - t_seen:.2f}s after seen)", texts(x)[:20])
    return "none"


def close_dialog():
    x = dump()
    n = find(x, text="Close")
    if n is not None:
        tap(n, "close"); time.sleep(1)


if __name__ == "__main__":
    mode = sys.argv[1]
    results = []
    if mode == "normal":
        fresh(); open_normal(); results.append(("normal-fresh", review("normal")))
    elif mode in ("back", "b2"):
        fresh(); open_normal(); results.append(("normal-fresh", review("normal-fresh")))
        open_via_menu("New private tab"); results.append(("private", review("private")))
        open_via_menu("New tab"); results.append(("normal-after-private", review("normal-after-private")))
    elif mode == "back-kbd":
        fresh(); open_normal(); results.append(("normal-fresh", review("normal-fresh")))
        delayed = URL.replace("index.html", "delayed.html")
        open_via_menu("New private tab", delayed, kbd=True); results.append(("private", review("private")))
        open_via_menu("New tab", delayed, kbd=True); results.append(("normal-after-private", review("normal-after-private")))
    elif mode == "rep":
        fresh(); open_normal(); results.append(("normal-fresh", review("normal-fresh")))
        for i in range(int(sys.argv[2])):
            open_via_menu("New private tab", URL + "?p=%d" % i); results.append(("private%d" % i, review("private%d" % i)))
            open_via_menu("New tab", URL + "?n=%d" % i); results.append(("normal%d" % i, review("normal%d" % i)))
    print("RESULT " + " ".join("%s=%s" % r for r in results), flush=True)


def winstate(label):
    open(os.path.join(OUT, label + "-windows.txt"), "w").write(sh("dumpsys window windows", check=False))
    open(os.path.join(OUT, label + "-input.txt"), "w").write(sh("dumpsys input", check=False))


def review_with_state(label):
    end = time.monotonic() + 25
    while True:
        x = dump(label + "-snack")
        n = find(x, text="Review", rid="snackbar_action")
        if n is not None:
            break
        if time.monotonic() > end:
            return "no-snackbar"
    winstate(label)
    return "captured"


if __name__ == "__main__" and sys.argv[1] == "win":
    fresh(); open_normal(); print("RESULT normal", review_with_state("w-normal"))
    time.sleep(4)
    open_via_menu("New private tab"); print("RESULT private", review_with_state("w-private"))
