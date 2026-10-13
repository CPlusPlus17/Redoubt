#!/usr/bin/env python3
"""Release-channel defaults of every Nimbus feature, 157 vs 158b3.
Value = variable defaults, overlaid by the feature's `defaults` entries whose
channel is release (or unset), then by any import override in an including
file for channel release. Prints features added/removed/changed."""
import json, sys, yaml
from pathlib import Path

def load(root):
    feats = {}
    overrides = {}
    for f in sorted(Path(root).glob("mobile/android/**/*.fml.yaml")):
        rel = str(f.relative_to(root))
        d = yaml.safe_load(f.read_text())
        for name, spec in (d.get("features") or {}).items():
            val = {k: v.get("default") for k, v in (spec.get("variables") or {}).items()}
            for ent in spec.get("defaults") or []:
                ch = ent.get("channel")
                chs = ch if isinstance(ch, list) else ([ch] if ch else [None])
                if None in chs or "release" in chs:
                    val.update(ent.get("value") or {})
            feats[name] = (rel, val)
        for imp in d.get("import") or []:
            for name, ents in (imp.get("features") or {}).items():
                for ent in ents:
                    ch = ent.get("channel")
                    if ch in (None, "release"):
                        overrides.setdefault(name, {}).update(ent.get("value") or {})
    for name, val in overrides.items():
        if name in feats:
            feats[name][1].update(val)
        else:
            feats[name] = ("(import override only)", val)
    return feats

a, b = load(sys.argv[1]), load(sys.argv[2])
for n in sorted(set(a) | set(b)):
    if n not in b:
        print(f"REMOVED {n} ({a[n][0]})")
    elif n not in a:
        print(f"ADDED   {n} ({b[n][0]}): {json.dumps(b[n][1], sort_keys=True)}")
    elif a[n][1] != b[n][1]:
        print(f"CHANGED {n} ({b[n][0]})")
        for k in sorted(set(a[n][1]) | set(b[n][1])):
            if a[n][1].get(k, "<absent>") != b[n][1].get(k, "<absent>"):
                print(f"    {k}: {json.dumps(a[n][1].get(k, '<absent>'))[:300]}  ->  {json.dumps(b[n][1].get(k, '<absent>'))[:300]}")
