#!/usr/bin/env python3
"""158.0-2 (LW-M7-50): read, from `dexdump -d` output, what GeckoProvider.createRuntime passes to
GeckoRuntimeSettings.Builder.isolatedProcessEnabled / appZygoteProcessEnabled.

New for the 158.0-2 acceptance (158.0-1 used isolation-dex.py, which requires a literal false).
In 158.0-2 the value is GeckoProvider.isolatedContentEnabled() = Build.VERSION.SDK_INT >= 31
(patches/android/isolation-media-process.patch), which R8 inlines into createRuntime as

    sget vA, Landroid/os/Build$VERSION;.SDK_INT:I
    const/16 vB, #int 31
    const/4 vZ, #int 0
    if-lt vA, vB, L
    const/4 vA, #int 1
    goto ...
  L:move vA, vZ

usage: isolation-gate-dex.py DEXDUMP_TXT
Exit 0 if both calls take the same register, every write to it before the calls is one of
the four gate instructions above (sget SDK_INT, const/4 1, move from a register holding 0), and
the method compares it with a register holding 31 by `if-lt`. Otherwise exit 1 and print what
was found, for a person to read.
"""
import re, sys

lines = open(sys.argv[1], errors="replace").read().splitlines()
start = next(i for i, l in enumerate(lines) if "GeckoProvider.createRuntime:" in l and "|[" in l)
end = next(i for i in range(start + 1, len(lines)) if "|[" in lines[i] and "GeckoProvider.createRuntime:" not in lines[i])
body = [l.split("|", 1)[1].strip() for l in lines[start + 1:end]
        if "|" in l and re.match(r"\s*[0-9a-f]{4}: ", l.split("|", 1)[1])]
print(lines[start].split("|", 1)[1].strip()[:120])
WRITE_EXCL = r"[0-9a-f]{4}: (if-|iput|sput|aput|invoke|check-cast|fill|return|throw|monitor)"


def writes(reg, upto):
    return [l for l in body[:upto] if re.match(r"[0-9a-f]{4}: [a-z/\-0-9]+ %s[, ]" % reg, l + " ")
            and not re.match(WRITE_EXCL, l)]


def const_value(reg, upto):
    w = writes(reg, upto)
    vals = {re.search(r"#int (-?\d+)", x).group(1) for x in w if re.match(r"[0-9a-f]{4}: const(/4|/16)? ", x)}
    return vals if len(vals) == len(w) else None   # None: some write is not a constant


ok = True
regs = {}
for api in ("isolatedProcessEnabled", "appZygoteProcessEnabled"):
    idx = next(i for i, l in enumerate(body) if "GeckoRuntimeSettings$Builder;." + api + ":(Z)" in l)
    reg = re.search(r"\{v\d+, (v\d+)\}", body[idx]).group(1)
    regs[api] = (reg, idx)
    print("call: %s" % body[idx][:110])
    w = writes(reg, idx)
    print("  argument register %s; writes to it earlier in the method: %d" % (reg, len(w)))
    for x in w:
        print("   ", x[:110])
    sdk = [x for x in w if re.match(r"[0-9a-f]{4}: sget %s, Landroid/os/Build\$VERSION;\.SDK_INT:I" % reg, x)]
    one = [x for x in w if re.match(r"[0-9a-f]{4}: const/4 %s, #int 1 " % reg, x + " ")]
    mv = [x for x in w if re.match(r"[0-9a-f]{4}: move %s, (v\d+)" % reg, x)]
    # a source register's value is read at the instruction that uses it (registers are reused later)
    zero_ok = all(const_value(re.search(r"move %s, (v\d+)" % reg, x).group(1), body.index(x)) == {"0"} for x in mv)
    other = [x for x in w if x not in sdk + one + mv]
    cmp_ = [x for x in body[:idx] if re.match(r"[0-9a-f]{4}: if-lt %s, (v\d+)," % reg, x)]
    cmp_ok = bool(cmp_) and all(const_value(re.search(r"if-lt %s, (v\d+)," % reg, x).group(1), body.index(x)) == {"31"} for x in cmp_)
    good = bool(sdk) and bool(one) and bool(mv) and zero_ok and not other and cmp_ok
    print("  SDK_INT read into it: %s; compared by if-lt with a register holding 31: %s; set to 1 when not below: %s;"
          " else copied from a register holding 0: %s; other writes: %d -> %s"
          % (bool(sdk), cmp_ok, bool(one), bool(mv) and zero_ok, len(other),
             "passes (SDK_INT >= 31)" if good else "NOT the gate pattern"))
    ok &= good
same = regs["isolatedProcessEnabled"][0] == regs["appZygoteProcessEnabled"][0]
print("both calls take the same register: %s" % same)
ok &= same
print("RESULT: both calls take SDK_INT >= 31" if ok else "RESULT: NOT the SDK_INT >= 31 gate (read the lines above)")
sys.exit(0 if ok else 1)
