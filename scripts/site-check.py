#!/usr/bin/env python3
"""Check the static site in site/ before it is published (docs/android/WEBSITE.md).

Fails (exit 1) on any of:
  * HTML that is not well formed: an unclosed or mismatched element, a duplicate
    id, a missing <!doctype html>, <html lang>, <title> or viewport meta;
  * anything loaded from another origin (script, stylesheet, image, font, frame)
    or any <script> at all -- the site must load nothing third-party and work
    without JavaScript;
  * an internal link or #anchor that does not resolve to a file / id in site/;
  * an external link outside the allowlist (the project's GitHub repository,
    librewolf.net for attribution, mozilla.org for the trademark notice);
  * a signing-certificate fingerprint that differs from the one in README.md;
  * a CNAME that is not exactly redoubtbrowser.org.

site/update/** belongs to the update endpoint (docs/android/DISTRIBUTION.md) and
is published verbatim; this checker only checks that links into it resolve.

The F-Droid repository (LW-M6-03, docs/android/FDROID.md) is hosted in the owner's
Hetzner Object Storage bucket, not on this site; only its human page is here.
Deliberate rules for it (2026-10-05, revised the same day for the bucket):
  * no *.apk anywhere under site/, and no site/fdroid/ directory (the old GitHub
    Pages layout): repository files are never committed;
  * assets/fdroid/deploy.conf is the hosting config. It must not set the test-only
    keys S3_ENDPOINT or PUBLIC_BASE_URL, so a page rendered for a local test server
    can never pass;
  * site/fdroid.html (rendered by fdroid-repo.sh publish-page, never by hand) needs
    the bucket in deploy.conf and must carry the repository fingerprint pinned in
    assets/fdroid/repo-fingerprint in its fdroidrepos:// link;
  * external links may also go to f-droid.org (where users get the client), and,
    from fdroid.html only, to the bucket named in deploy.conf:
    fdroidrepos://<bucket>.<location>.your-objectstorage.com/repo?fingerprint=<64 hex>
    and https://<bucket>.<location>.your-objectstorage.com/repo or /archive.

Usage: scripts/site-check.py [SITE_DIR]   (default: site/ next to scripts/)
"""
import html.parser
import pathlib
import re
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "source", "track", "wbr"}
# Elements whose end tag HTML allows to be omitted; we still require them closed,
# except <p>/<li> auto-closing is not used on this site, so treat all as strict.
ALLOWED_EXTERNAL = [
    re.compile(r"^https://github\.com/CPlusPlus17/Redoubt(/.*)?$"),
    re.compile(r"^https://librewolf\.net(/.*)?$"),
    re.compile(r"^https://(www\.)?mozilla\.org(/.*)?$"),
    re.compile(r"^https://f-droid\.org(/.*)?$"),
]
FDROID_PAGE = "fdroid.html"
LOCATIONS = ("fsn1", "nbg1", "hel1")
BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")
FDROID_LINK_RE = re.compile(r"fdroidrepos://[^\s\"'?]+\?fingerprint=([0-9A-Fa-f]{64})")
FPR_RE = re.compile(r"\b(?:[0-9A-F]{2}:){31}[0-9A-F]{2}\b")
DOMAIN = "redoubtbrowser.org"


def deploy_conf(errors):
    """The bucket host from assets/fdroid/deploy.conf, or None when no bucket is set."""
    path = ROOT / "assets" / "fdroid" / "deploy.conf"
    if not path.is_file():
        errors.append("assets/fdroid/deploy.conf is missing")
        return None
    conf = {}
    for line in path.read_text().splitlines():
        m = re.match(r"^([A-Z0-9_]+)=(.*)$", line.strip())
        if m:
            conf[m.group(1)] = m.group(2)
    for key in ("S3_ENDPOINT", "PUBLIC_BASE_URL"):
        if conf.get(key):
            errors.append(f"assets/fdroid/deploy.conf sets {key}, a throwaway-test override; never commit it")
    bucket, loc = conf.get("S3_BUCKET", ""), conf.get("S3_LOCATION", "")
    if loc not in LOCATIONS:
        errors.append(f"assets/fdroid/deploy.conf: S3_LOCATION {loc!r} is not one of {LOCATIONS}")
        return None
    if not bucket:
        return None
    if not BUCKET_RE.match(bucket):
        errors.append(f"assets/fdroid/deploy.conf: {bucket!r} is not a valid bucket name")
        return None
    return f"{bucket}.{loc}.your-objectstorage.com"


class Page(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.ids = [], [], []
        self.links, self.loads = [], []
        self.has_title = self.has_viewport = self.has_lang = False
        self.scripts = 0

    def handle_decl(self, decl):
        self.doctype = decl.lower()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "html" and a.get("lang"):
            self.has_lang = True
        if tag == "title":
            self.has_title = True
        if tag == "meta" and a.get("name") == "viewport":
            self.has_viewport = True
        if tag == "script":
            self.scripts += 1
        if tag == "a" and "href" in a:
            self.links.append((self.getpos()[0], a["href"]))
        for attr in ("src", "srcset", "data", "poster"):
            if attr in a:
                self.loads.append((self.getpos()[0], tag, a[attr]))
        if tag == "link" and "href" in a:
            self.loads.append((self.getpos()[0], tag, a["href"]))
        if tag == "style" or "style" in a:
            self.errors.append(f"line {self.getpos()[0]}: inline style (CSP is style-src 'self')")
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag in VOID:
            self.errors.append(f"line {self.getpos()[0]}: end tag for void element </{tag}>")
            return
        if not self.stack or self.stack[-1][0] != tag:
            want = self.stack[-1] if self.stack else ("nothing", 0)
            self.errors.append(f"line {self.getpos()[0]}: </{tag}> closes <{want[0]}> from line {want[1]}")
            # recover: pop to the matching tag if there is one
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]
                    break
            return
        self.stack.pop()


def is_external(url):
    return bool(urllib.parse.urlsplit(url).scheme) or url.startswith("//")


def main():
    site = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"
    errors = []
    readme = (ROOT / "README.md").read_text()
    readme_fprs = set(FPR_RE.findall(readme))
    if len(readme_fprs) != 1:
        errors.append(f"README.md: expected exactly one signing fingerprint, found {sorted(readme_fprs)}")

    cname = site / "CNAME"
    if not cname.is_file() or cname.read_text().strip() != DOMAIN:
        errors.append(f"{cname}: must contain exactly {DOMAIN}")

    apks = sorted(str(a.relative_to(site)) for a in site.rglob("*.apk"))
    if apks:
        errors.append(f"APKs committed under site/ {apks}: the F-Droid repository lives in the bucket, never in git")
    if (site / "fdroid").exists():
        errors.append("site/fdroid/ exists: the F-Droid repository lives in the Hetzner bucket, not on this site (FDROID.md)")
    bucket_host = deploy_conf(errors)
    fdroid_allowed = []
    if bucket_host:
        h = re.escape(bucket_host)
        fdroid_allowed = [re.compile(rf"^fdroidrepos://{h}/repo\?fingerprint=[0-9A-F]{{64}}$"),
                          re.compile(rf"^https://{h}/(repo|archive)/?$")]
    fdroid_page = site / FDROID_PAGE
    if fdroid_page.is_file():
        pin = ROOT / "assets" / "fdroid" / "repo-fingerprint"
        want = pin.read_text().strip().lower() if pin.is_file() else None
        got = {g.lower() for g in FDROID_LINK_RE.findall(fdroid_page.read_text())}
        if bucket_host is None:
            errors.append("fdroid.html: assets/fdroid/deploy.conf names no bucket (run fdroid-repo.sh init --bucket)")
        if want is None:
            errors.append("fdroid.html: assets/fdroid/repo-fingerprint is missing (run fdroid-repo.sh publish-page)")
        elif got != {want}:
            errors.append(f"fdroid.html: repository fingerprint(s) {sorted(got)} differ from assets/fdroid/repo-fingerprint {want}")

    pages = sorted(site.rglob("*.html"))
    parsed = {}
    for p in pages:
        rel = p.relative_to(site)
        text = p.read_text()
        parser = Page()
        parser.doctype = ""
        parser.feed(text)
        parser.close()
        parsed[p] = parser
        if rel.parts[0] == "update":
            continue  # owned by the update endpoint; only resolved into, not linted
        errs = [f"{rel}: {e}" for e in parser.errors]
        errs += [f"{rel}: <{t}> from line {ln} never closed" for t, ln in parser.stack]
        if parser.doctype != "doctype html":
            errs.append(f"{rel}: missing <!doctype html>")
        for flag, what in ((parser.has_lang, "<html lang>"), (parser.has_title, "<title>"),
                           (parser.has_viewport, "viewport meta")):
            if not flag:
                errs.append(f"{rel}: missing {what}")
        if parser.scripts:
            errs.append(f"{rel}: contains <script>; the site must work without JavaScript")
        dup = {i for i in parser.ids if parser.ids.count(i) > 1}
        if dup:
            errs.append(f"{rel}: duplicate ids {sorted(dup)}")
        for ln, tag, url in parser.loads:
            if is_external(url) or url.startswith("data:"):
                errs.append(f"{rel}:{ln}: <{tag}> loads {url!r}; the site loads nothing from elsewhere")
        fprs = set(FPR_RE.findall(text))
        if fprs - readme_fprs:
            errs.append(f"{rel}: fingerprint {sorted(fprs - readme_fprs)} differs from README.md")
        errors += errs

    for p in pages:
        rel = p.relative_to(site)
        if rel.parts[0] == "update":
            continue
        for ln, href in parsed[p].links:
            if href.startswith("mailto:"):
                errors.append(f"{rel}:{ln}: mailto link {href!r}; use the GitHub reporting link")
                continue
            if is_external(href):
                allowed = ALLOWED_EXTERNAL + (fdroid_allowed if rel == pathlib.Path(FDROID_PAGE) else [])
                if not any(r.match(href) for r in allowed):
                    errors.append(f"{rel}:{ln}: external link {href!r} is not on the allowlist")
                continue
            parts = urllib.parse.urlsplit(href)
            if parts.path:
                target = (site / parts.path.lstrip("/")) if parts.path.startswith("/") \
                    else (p.parent / parts.path)
                target = target.resolve()
                if target.is_dir():
                    target = target / "index.html"
            else:
                target = p.resolve()
            if site.resolve() not in target.parents and target != site.resolve():
                errors.append(f"{rel}:{ln}: {href!r} leaves the site")
                continue
            if not target.is_file():
                errors.append(f"{rel}:{ln}: {href!r} -> {target.relative_to(site.resolve())} does not exist")
                continue
            if parts.fragment:
                tp = next((q for q in parsed if q.resolve() == target), None)
                if tp is None or parts.fragment not in parsed[tp].ids:
                    errors.append(f"{rel}:{ln}: {href!r}: no id {parts.fragment!r} in target")
        for ln, tag, url in parsed[p].loads:
            if is_external(url):
                continue
            target = (site / url.lstrip("/")) if url.startswith("/") else (p.parent / url)
            if not target.is_file():
                errors.append(f"{rel}:{ln}: <{tag}> {url!r} does not exist")

    for e in errors:
        print("FAIL", e)
    print(f"{'FAIL' if errors else 'PASS'}: {len(pages)} pages checked in {site}, {len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
