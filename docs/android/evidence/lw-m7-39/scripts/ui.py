#!/usr/bin/env python3
"""Small uiautomator helper for one emulator serial (never another device).
usage from Python: U = UI(serial); U.dump(); U.find(text_re); U.tap(text_re); U.scroll_to(text_re)"""
import re, subprocess, time, xml.etree.ElementTree as ET
import os
ADB = os.path.expanduser("~/redoubt-artifacts/android-sdk/platform-tools/adb")

class UI:
    def __init__(self, serial):
        assert serial.startswith("emulator-"), serial
        self.s = serial
    def sh(self, *a, check=False):
        return subprocess.run([ADB, "-s", self.s, "shell", *a], capture_output=True, text=True, check=check).stdout
    def dump(self, save=None):
        for _ in range(5):
            self.sh("uiautomator", "dump", "/sdcard/ui.xml")
            x = subprocess.run([ADB, "-s", self.s, "exec-out", "cat", "/sdcard/ui.xml"], capture_output=True, text=True).stdout
            if x.startswith("<?xml"):
                if save:
                    open(save, "w").write(x)
                self.root = ET.fromstring(x)
                return x
            time.sleep(1)
        raise RuntimeError("uiautomator dump failed")
    def nodes(self):
        return list(self.root.iter("node"))
    def find(self, pat, attrs=("text", "content-desc")):
        r = re.compile(pat)
        return [n for n in self.nodes() if any(r.search(n.get(a) or "") for a in attrs)]
    @staticmethod
    def center(n):
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", n.get("bounds")))
        return (x1 + x2) // 2, (y1 + y2) // 2
    def tap(self, pat, dump=True, idx=0):
        if dump:
            self.dump()
        m = self.find(pat)
        if not m:
            raise LookupError(f"no node matches {pat!r}")
        x, y = self.center(m[idx])
        self.sh("input", "tap", str(x), str(y))
        time.sleep(1.5)
        return m[idx]
    def scroll_to(self, pat, tries=8):
        """scroll down up to `tries` times, then up up to 2*tries times, until a node matches"""
        for i in range(3 * tries):
            self.dump()
            if self.find(pat):
                return True
            a, b = ("1500", "700") if i < tries else ("700", "1500")
            self.sh("input", "swipe", "540", a, "540", b, "400")
            time.sleep(1)
        return False
    def texts(self):
        return [t for n in self.nodes() for t in (n.get("text"), n.get("content-desc")) if t]
