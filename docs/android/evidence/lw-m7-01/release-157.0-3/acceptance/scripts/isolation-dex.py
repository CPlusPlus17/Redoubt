#!/usr/bin/env python3
"""Read, from `dexdump -d` output, the boolean that GeckoProvider.createRuntime passes to
GeckoRuntimeSettings.Builder.isolatedProcessEnabled / appZygoteProcessEnabled.

usage: isolation-dex.py DEXDUMP_TXT
Prints the method, the call lines, and every instruction in the method body (before the
call) whose destination is the argument register; the last one on the straight-line path is
the value passed. Exit 0 if both calls take a register last set by `const/4 vN, #int 0`.
"""
import re, sys
lines = open(sys.argv[1], errors="replace").read().splitlines()
start = next(i for i, l in enumerate(lines) if "GeckoProvider.createRuntime:" in l and "|[" in l)
end = next(i for i in range(start + 1, len(lines)) if "|[" in lines[i] and "GeckoProvider.createRuntime:" not in lines[i])
body = [l.split("|", 1)[1] for l in lines[start + 1:end] if "|" in l and re.match(r"\s*[0-9a-f]{4}: ", l.split("|", 1)[1])]
print(lines[start].split("|", 1)[1].strip()[:120])
ok = True
for api in ("isolatedProcessEnabled", "appZygoteProcessEnabled"):
    idx = next(i for i, l in enumerate(body) if "GeckoRuntimeSettings$Builder;." + api + ":(Z)" in l)
    reg = re.search(r"\{v\d+, (v\d+)\}", body[idx]).group(1)
    defs = [l.strip() for l in body[:idx] if re.match(r"\s*[0-9a-f]{4}: [a-z/\-0-9]+ %s," % reg, l)
            and not re.match(r"\s*[0-9a-f]{4}: (if-|iput|sput|aput|invoke|check-cast|fill)", l)]
    branches = [l.strip() for l in body[:idx] if re.match(r"\s*[0-9a-f]{4}: (if-|goto|packed-switch|sparse-switch)", l)]
    last = defs[-1] if defs else None
    val = re.search(r"const/(?:4|16) %s, #int (-?\d+)" % reg, last or "")
    print("call: %s" % body[idx].strip()[:110])
    print("  argument register %s; writes to it earlier in the method: %d" % (reg, len(defs)))
    for d in defs[-4:]:
        print("   ", d[:110])
    print("  last write: %s -> passes %s" % (last[:80] if last else None, {None: "UNKNOWN", "0": "false", "1": "true"}.get(val.group(1) if val else None, "?")))
    ok &= bool(val and val.group(1) == "0")
print("RESULT: both literal false" if ok else "RESULT: NOT both literal false")
sys.exit(0 if ok else 1)
