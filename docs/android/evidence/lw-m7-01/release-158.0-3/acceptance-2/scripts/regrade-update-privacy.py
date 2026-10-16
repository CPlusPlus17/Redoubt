#!/usr/bin/env python3
"""Re-grade the two --check-update-privacy runs of this acceptance offline,
with the name-based rule (grade_update_privacy_flows in scripts/android-smoke.sh).

The device runs recorded their events but not their capture byte windows, so
the windows are rebuilt from the run's own capture and recorded JSON:
  OFF  from the check's first capture byte (exit-status.jsonl) to the end of
       the packet carrying the last recorded OFF event.  The JSON keeps only
       the first 100 OFF events, so this is a LOWER bound of the window the
       harness judged: fewer names seen with the check off, a stricter grade.
  ON   the burst after the relaunch gap (>5 s silence before the first recorded
       ON event) up to 31 s after that event (the harness idles 30 s).  Before
       grading, summarise_capture over this window must reproduce the recorded
       ON events exactly, and over the OFF window the recorded first 100.

Usage: regrade-update-privacy.py CAPTURE.pcap HARNESS.sh OUT_DIR
"""
import hashlib
import json
import os
import struct
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "..", "device", "smoke")
GUEST = {"10.0.2.16", "fec0::648b:6123:fd17:210e"}
RUNS = ("check-update-privacy", "check-update-privacy-rerun")


def load_harness(path):
    src = open(path).read().split("<<'PYDRIVEREOF'\n", 1)[1].split("\nPYDRIVEREOF", 1)[0]
    mod = types.ModuleType("android_smoke")
    exec(compile(src, path, "exec"), mod.__dict__)
    return mod


def packets(pcap, lo, hi):
    out = []
    with open(pcap, "rb") as f:
        f.seek(lo)
        while f.tell() < hi:
            o = f.tell()
            ts, us, cl, _ol = struct.unpack("<IIII", f.read(16))
            f.seek(cl, 1)
            out.append((o, f.tell(), ts + us / 1e6))
    return out


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def key(r):
    return (r["kind"], r["detail"], r["src"], r["dst"], r["port"])


def main(pcap, harness_path, out_dir):
    h = load_harness(harness_path)
    status = {}
    with open(os.path.join(SMOKE, "exit-status.jsonl")) as f:
        for line in f:
            row = json.loads(line)
            status[row["check"]] = row
    os.makedirs(out_dir, exist_ok=True)
    summary = {"capture": {"path": pcap, "bytes": os.path.getsize(pcap), "sha256": sha256(pcap)},
               "harness": {"path": harness_path, "sha256": sha256(harness_path)},
               "update_hosts": list(h.UPDATE_CHECK_HOSTS), "runs": {}}
    all_ok = True
    for name in RUNS:
        lo, hi = status[name]["capture_pcap_bytes"]
        ev = json.load(open(os.path.join(SMOKE, name, name + ".json")))["checks"][0]["evidence"]
        off_events, on_events = ev["off_window_app_events"], ev["on_window_app_events"]
        pk = packets(pcap, lo, hi)
        off_end = max(e for _o, e, t in pk if t <= off_events[-1]["ts"])
        on0 = on_events[0]["ts"]
        gap_before_on = max(t for _o, _e, t in pk if t < on0 - 5)
        on_start = min(o for o, _e, t in pk if t > gap_before_on)
        on_end = max(e for _o, e, t in pk if t <= on0 + 31)

        def app(start, end):
            return [r for r in h.summarise_capture(pcap, start, guest_ips=GUEST)
                    if not r["os_noise"] and not r["harness"]
                    and r["ts"] <= max(t for _o, e, t in pk if e <= end)]
        rebuilt_on, rebuilt_off = app(on_start, on_end), app(lo, off_end)
        windows_match = {
            "on_events_equal_recorded": [key(r) for r in rebuilt_on] == [key(r) for r in on_events],
            "off_first_100_equal_recorded": [key(r) for r in rebuilt_off[:100]] == [key(r) for r in off_events],
        }
        off = h.attribute_typing_flows(pcap, GUEST, lo, off_end)
        on = h.attribute_typing_flows(pcap, GUEST, on_start, on_end)
        grade = h.grade_update_privacy_flows(off, on, h.UPDATE_CHECK_HOSTS)
        on_hits = [r for r in rebuilt_on if any(u in (r["detail"] or "").lower() for u in h.UPDATE_CHECK_HOSTS)]
        off_hits = [r for r in rebuilt_off if any(u in (r["detail"] or "").lower() for u in h.UPDATE_CHECK_HOSTS)]
        ok = (all(windows_match.values()) and not grade["on_failed"] and not grade["off_update_flows"]
              and bool(on_hits) and not off_hits)
        all_ok = all_ok and ok
        result = {"check": name, "ok": ok, "windows": {"off": [lo, off_end], "on": [on_start, on_end]},
                  "windows_match": windows_match,
                  "recorded_device_detail": json.load(open(os.path.join(SMOKE, name, name + ".json")))["checks"][0]["detail"],
                  "off_window_update_events": off_hits, "off_update_flows": grade["off_update_flows"],
                  "on_window_update_events": len(on_hits),
                  "off_names": grade["off_names"], "on_flows": grade["on_flows"],
                  "on_failed": [h.describe_update_privacy_failure(r) for r in grade["on_failed"]]}
        with open(os.path.join(out_dir, name + ".json"), "w") as f:
            json.dump(result, f, indent=1, sort_keys=True)
        summary["runs"][name] = {"ok": ok, "windows": result["windows"], "windows_match": windows_match,
                                 "on_failed": result["on_failed"],
                                 "on_verdicts": ["%s %s:%d %s %s" % (r["protocol"], r["dst"], r["port"], r["verdict"],
                                                                     ",".join("%s=%s" % kv for kv in sorted(r["names"].items())))
                                                 for r in grade["on_flows"]]}
        print("%-28s %s" % (name, "PASS" if ok else "FAIL"))
        for line in summary["runs"][name]["on_verdicts"]:
            print("   " + line)
        for line in result["on_failed"]:
            print("   FAILED " + line)
    summary["ok"] = all_ok
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1, sort_keys=True)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
