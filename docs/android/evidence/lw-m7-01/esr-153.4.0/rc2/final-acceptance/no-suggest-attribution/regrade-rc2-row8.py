#!/usr/bin/env python3
"""Re-grade rc2 final-acceptance row 8 (check-no-suggest, harness aabbb7a7) with the
committed harness's attribute_typing_flows, on the SAME capture and offsets.
usage: regrade-rc2-row8.py PCAP > regrade-rc2-row8.json   (run from the repo root)"""
import json, sys, types, hashlib
src = open('scripts/android-smoke.sh').read()
h = types.ModuleType('h')
exec(compile(src.split("<<'PYDRIVEREOF'\n", 1)[1].split('\nPYDRIVEREOF', 1)[0], 'driver', 'exec'), h.__dict__)
row = json.load(open('docs/android/evidence/lw-m7-01/esr-153.4.0/rc2/final-acceptance/smoke/'
                     'check-no-suggest/check-no-suggest.json'))['checks'][0]['evidence']
config = json.load(open('assets/search-config-v2.json'))['data']
result = h.attribute_typing_flows(sys.argv[1], set(row['guest_ips']), row['typing_capture_offset'],
                                  row['enter_capture_offset'], h.search_endpoint_hosts(config))
json.dump({"harness_sha256": hashlib.sha256(src.encode()).hexdigest(),
           "typing_capture_offset": row['typing_capture_offset'],
           "enter_capture_offset": row['enter_capture_offset'], **result}, sys.stdout, indent=1)
