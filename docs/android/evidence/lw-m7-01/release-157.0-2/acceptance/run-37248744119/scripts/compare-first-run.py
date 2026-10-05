#!/usr/bin/env python3
"""Compare the named hosts and destinations of two --first-run-capture JSONs.
usage: compare-first-run.py NEW.json OLD.json [OLD_LABEL]
Named hosts are the TLS SNI and DNS query names of non-harness, non-OS-noise
events; unnamed destinations are addresses no SNI/DNS event in the run names."""
import json, sys
def load(p):
    d = json.load(open(p))
    c = next(c for c in d["checks"] if c["check"] == "first-run-capture")
    ev = [e for e in c["evidence"]["events"] if not e.get("harness") and not e.get("os_noise")]
    names = sorted({e["detail"].rstrip(".") for e in ev if e["kind"] in ("sni", "dns", "dns-query", "dot", "quic-sni") and e["detail"]})
    named_dst = {e["dst"] for e in ev if e["kind"] == "sni"}
    dsts = sorted({e["dst"] for e in ev if e["dst"] not in named_dst and e["kind"] != "sni"})
    kinds = sorted({e["kind"] for e in ev})
    return {"events": len(c["evidence"]["events"]), "counted_events": len(ev), "kinds": kinds,
            "named_hosts": names, "unnamed_destinations": dsts, "detail": c["detail"]}
new, old = load(sys.argv[1]), load(sys.argv[2])
label = sys.argv[3] if len(sys.argv) > 3 else "old"
out = {"this_run": new, label: old,
       "named_hosts_added": sorted(set(new["named_hosts"]) - set(old["named_hosts"])),
       "named_hosts_gone": sorted(set(old["named_hosts"]) - set(new["named_hosts"]))}
print(json.dumps(out, indent=1))
