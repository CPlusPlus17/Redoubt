"""Tap the centre of the first UI node whose text (or content-desc) equals one of the given strings.

usage: python3 -I tap_text.py SERIAL XML_PATH TEXT [TEXT ...]
Reads an existing uiautomator dump; prints the tapped text or "none". With REQUIRE=<substr>
in the environment, only taps when that substring appears somewhere in the dump.
"""
import html
import os
import re
import subprocess
import sys

serial, xml_path, wanted = sys.argv[1], sys.argv[2], sys.argv[3:]
xml = open(xml_path, encoding="utf-8", errors="replace").read()
need = os.environ.get("REQUIRE")
if need and need not in html.unescape(xml):
    print("none")
    sys.exit(0)
for node in re.finditer(r"<node [^>]*>", xml):
    n = node.group(0)
    text = html.unescape((re.search(r' text="([^"]*)"', n) or [None, ""])[1])
    desc = html.unescape((re.search(r' content-desc="([^"]*)"', n) or [None, ""])[1])
    for w in wanted:
        if text == w or desc == w:
            b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', n)
            x = (int(b.group(1)) + int(b.group(3))) // 2
            y = (int(b.group(2)) + int(b.group(4))) // 2
            subprocess.run(["adb", "-s", serial, "shell", "input", "tap", str(x), str(y)], check=False)
            print("tapped %r at %d,%d" % (w, x, y))
            sys.exit(0)
print("none")
