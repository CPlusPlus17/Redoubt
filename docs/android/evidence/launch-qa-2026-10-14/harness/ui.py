"""Dump the current UI of a device and list nodes that carry text or a content-desc.

usage: python3 -I ui.py SERIAL OUT_XML [FILTER]
Prints: index, class, text / desc, clickable/checkable/checked, bounds centre.
"""
import html
import re
import subprocess
import sys

serial, out = sys.argv[1], sys.argv[2]
flt = sys.argv[3].lower() if len(sys.argv) > 3 else None
adb = ["adb", "-s", serial]
subprocess.run(adb + ["shell", "uiautomator", "dump", "/sdcard/qa-ui.xml"], capture_output=True)
xml = subprocess.run(adb + ["exec-out", "cat", "/sdcard/qa-ui.xml"], capture_output=True).stdout.decode("utf-8", "replace")
open(out, "w").write(xml)


def attr(n, name):
    m = re.search(r' %s="([^"]*)"' % name, n)
    return html.unescape(m.group(1)) if m else ""


for i, m in enumerate(re.finditer(r"<node [^>]*>", xml)):
    n = m.group(0)
    text, desc, rid = attr(n, "text"), attr(n, "content-desc"), attr(n, "resource-id")
    if not (text or desc):
        continue
    line = "%s | %s | %s" % (text, desc, rid.split("/")[-1])
    if flt and flt not in line.lower():
        continue
    b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', n)
    cx, cy = (int(b.group(1)) + int(b.group(3))) // 2, (int(b.group(2)) + int(b.group(4))) // 2
    flags = "".join(c for c, a in (("C", "clickable"), ("K", "checkable")) if attr(n, a) == "true")
    if attr(n, "checked") == "true":
        flags += "*"
    print("%3d %-28s %-70s %-4s (%d,%d)" % (i, attr(n, "class").split(".")[-1][:28], line[:70], flags, cx, cy))
