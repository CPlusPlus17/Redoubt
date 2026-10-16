#!/usr/bin/env python3
"""api31-33-fix (LW-M7-39): counts in one flow's logcat (plain or .gz), MOZ_LOG EME:5 on.
Per EME session (MediaKeySession pointer + session id): the key messages the CDM sent to the page,
split into Widevine service certificate requests (message '0804') and license requests (any other
license-request message), plus renewals. Also: NDK "invalid event data size=0", the fix's two logcat
lines, tab deaths, fatal errors, Java crypto-query exceptions. usage: count.py LOGCAT [PKG]"""
import gzip, json, re, sys
path = sys.argv[1]; pkg = sys.argv[2] if len(sys.argv) > 2 else "org.redoubtbrowser"
op = gzip.open if path.endswith(".gz") else open
text = op(path, "rt", errors="replace").read()
sessions = {}
for m in re.finditer(r"MediaKeySession\[(0x[0-9a-f]+),'([^']*)'\] DispatchKeyMessage\(\) type=([a-z-]+) message='([0-9a-f]*)", text):
    k = m.group(1) + "/" + m.group(2)
    s = sessions.setdefault(k, {"service-certificate": 0, "license-request": 0, "license-renewal": 0, "other": 0})
    t, msg = m.group(3), m.group(4)
    if t == "license-request" and msg == "0804":
        s["service-certificate"] += 1
    elif t in ("license-request", "license-renewal"):
        s[t] += 1
    else:
        s["other"] += 1
out = {
    "sessions": sessions,
    "sessions_with_exactly_one_license_request": sum(1 for s in sessions.values() if s["license-request"] == 1),
    "sessions_total": len(sessions),
    "invalid_event_data_size_0": text.count("invalid event data size=0"),
    "fix_key_request_lines": text.count("Redoubt isolation-eme: service certificate provided"),
    "fix_duplicate_skipped_lines": text.count("arrived after all; the license was already requested"),
    "tab_deaths": len(re.findall(r"Process %s:[^ ]*[Tt]ab[^ ]* \(pid [0-9]+\) has died" % re.escape(pkg), text)),
    "rdd_deaths": len(re.findall(r"Process %s:media[^ ]* \(pid [0-9]+\) has died" % re.escape(pkg), text)),
    "fatal": len(re.findall(r"FATAL EXCEPTION|Fatal signal|ANR in " + re.escape(pkg), text)),
    "crypto_query_exceptions": text.count("Failed to query crypto scheme support"),
    "parent_line": text.count("Redoubt isolation-eme: parent found"),
}
print(json.dumps(out))
