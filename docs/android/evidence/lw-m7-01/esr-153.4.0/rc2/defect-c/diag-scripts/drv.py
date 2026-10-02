#!/usr/bin/env python3
"""Scratch driver for defect C diagnosis. Not part of the repo."""
import os, re, subprocess, sys, time, xml.etree.ElementTree as ET

ADB = [os.path.expanduser("~/redoubt-artifacts/android-sdk/platform-tools/adb"), "-s", os.environ.get("SERIAL", "emulator-5584")]
PKG = os.environ.get("PKG", "org.redoubtbrowser")
OUT = os.environ.get("OUT", "runs")
os.makedirs(OUT, exist_ok=True)
T0 = time.monotonic()


def log(*a):
    print(f"[{time.monotonic()-T0:7.2f}]", *a, flush=True)


def sh(*args, check=True):
    return subprocess.run(ADB + ["shell"] + [" ".join(args)], capture_output=True, text=True, check=check).stdout


def dump(label=None):
    sh("uiautomator dump /sdcard/d.xml >/dev/null")
    x = sh("cat /sdcard/d.xml")
    if label:
        open(os.path.join(OUT, label + ".xml"), "w").write(x)
    return x


def nodes(x):
    try:
        root = ET.fromstring(x)
    except ET.ParseError:
        return []
    out = []
    for n in root.iter("node"):
        b = list(map(int, re.findall(r"\d+", n.get("bounds", "[0,0][0,0]"))))
        n.set("cx", str((b[0] + b[2]) // 2)); n.set("cy", str((b[1] + b[3]) // 2))
        out.append(n)
    return out


def find(x, text=None, desc=None, rid=None):
    for n in nodes(x):
        if n.get("package") != PKG:
            continue
        if text is not None and n.get("text") != text:
            continue
        if desc is not None and n.get("content-desc") != desc:
            continue
        if rid is not None and not n.get("resource-id", "").endswith(rid):
            continue
        return n
    return None


def tap(n, label=""):
    log("tap", label, n.get("text") or n.get("content-desc") or n.get("resource-id"), n.get("cx"), n.get("cy"))
    sh("input tap", n.get("cx"), n.get("cy"))


def wait(timeout=20, label=None, **sel):
    end = time.monotonic() + timeout
    while True:
        x = dump(label)
        n = find(x, **sel)
        if n is not None:
            return x, n
        if time.monotonic() > end:
            return x, None
        time.sleep(0.2)


def texts(x):
    return sorted({(n.get("text") or n.get("content-desc")) for n in nodes(x)
                   if n.get("package") == PKG and (n.get("text") or n.get("content-desc"))})


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "dump":
        x = dump(sys.argv[2] if len(sys.argv) > 2 else "adhoc")
        for t in texts(x):
            print(" ", t[:100])
