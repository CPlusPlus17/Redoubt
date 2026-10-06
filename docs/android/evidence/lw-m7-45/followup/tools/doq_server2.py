#!/usr/bin/env python3
"""LW-M7-45 device-test server. The emulator reaches it at http://10.0.2.2:8765.

Follow-up (2026-10-06): times in ms ("t"), and /h1.html -> /h2.html, two
no-store pages in one tab, so the tab has back/forward history; h1 navigates
on to h2 only on a fresh navigation, not on Back.

/a.html, /b.html  set a persistent cookie (header + JS) and localStorage
/report.html?tag= reports document.cookie and localStorage back to /log
Every request is logged as one JSON line with the Cookie header it carried.
"""
import json, sys, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG = sys.argv[1]

PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width">
<title>DOQ {name}</title><h1 id=h>DOQ {name}</h1><p id=out></p><script src="/cached.js"></script><script>
localStorage.setItem('doq_ls_{name}', '1');
document.cookie = 'doq_js_{name}=1; max-age=86400; path=/';
document.getElementById('out').textContent = 'cookie=' + document.cookie + ' ls=' + Object.keys(localStorage).join(',');
fetch('/log?tag=set-{name}&cookie=' + encodeURIComponent(document.cookie) + '&ls=' + encodeURIComponent(Object.keys(localStorage).join(',')));
</script>"""

REPORT = """<!doctype html><meta charset=utf-8><title>DOQ report</title><p id=out></p><script src="/cached.js"></script><script>
const tag = new URLSearchParams(location.search).get('tag') || 'report';
const ls = Object.keys(localStorage).join(',');
document.getElementById('out').textContent = 'cookie=[' + document.cookie + '] ls=[' + ls + ']';
fetch('/log?tag=' + encodeURIComponent(tag) + '&cookie=' + encodeURIComponent(document.cookie) + '&ls=' + encodeURIComponent(ls));
</script>"""

HIST = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width">
<title>DOQ {name}</title><h1>DOQ {name}</h1><p id=out></p><script>
document.cookie = 'doq_js_{name}=1; max-age=86400; path=/';
const nav = (performance.getEntriesByType('navigation')[0] || {{}}).type;
document.getElementById('out').textContent = 'nav=' + nav + ' cookie=' + document.cookie;
fetch('/seen/{name}/' + nav + '.txt');  // a path no filter list blocks; logged even as a 404
if ('{name}' === 'h1' && nav === 'navigate') setTimeout(() => location.assign('/h2.html'), 1500);
</script>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        now = time.time()
        rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)) + ".%03d" % int((now % 1) * 1000), "path": u.path, "query": q,
               "cookie_header": self.headers.get("Cookie", "")}
        with open(LOG, "a") as f:
            f.write(json.dumps(rec) + "\n")
        body, extra = b"", []
        if u.path in ("/a.html", "/b.html"):
            name = u.path[1]
            body = PAGE.format(name=name).encode()
            extra = [("Set-Cookie", f"doq_hdr_{name}=1; Max-Age=86400; Path=/")]
        elif u.path in ("/h1.html", "/h2.html"):
            name = u.path[1:3]
            body = HIST.format(name=name).encode()
            extra = [("Set-Cookie", f"doq_hdr_{name}=1; Max-Age=86400; Path=/")]
        elif u.path == "/report.html":
            body = REPORT.encode()
        elif u.path == "/cached.js":
            body = b"window.doqCached = 1;"
        elif u.path == "/log":
            body = b"ok"
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8" if u.path.endswith(".html") else ("text/javascript" if u.path.endswith(".js") else "text/plain"))
        self.send_header("Cache-Control", "no-store" if u.path in ("/h1.html", "/h2.html") else "max-age=3600")
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)


ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()
