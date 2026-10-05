#!/usr/bin/env python3
"""Put the Redoubt F-Droid repository's APKs into the GitHub Pages site (LW-M6-03).

Only the small, signed F-Droid index is committed (site/fdroid/repo/, written by
`scripts/fdroid-repo.sh publish`). The APKs are not in git: at deploy time
.github/workflows/pages.yaml runs `assemble`, which fetches every APK the signed
index names from the GitHub release it came from and places it next to the index
before the site is uploaded. docs/android/FDROID.md is the design.

  check     --site DIR
            Offline. Verifies the committed index exactly as an F-Droid client
            would trust it, and the deploy budget:
              * entry.jar, index-v1.jar and index.jar are JAR-signed (PKCS#7,
                checked with openssl) by ONE certificate whose SHA-256 is the
                pinned repository fingerprint (assets/fdroid/repo-fingerprint);
                the .SF covers MANIFEST.MF, MANIFEST.MF covers the signed file;
              * the signed entry.json names index-v2.json by sha256 and size,
                and the plain entry.json equals the signed one;
              * index-v2.json and the signed index-v1.json list the same APKs
                with the same sha256; every APK is org.redoubtbrowser_<code>.apk
                and its signer is the release key (docs/android/SIGNING.md);
              * site/fdroid/sources.json maps every APK to a release asset of
                https://github.com/CPlusPlus17/Redoubt;
              * no .apk is committed anywhere under site/;
              * the site plus every APK fits the budget (default 1 GB, GitHub
                Pages' limit on a published site).
            Without site/fdroid/repo/ it prints that there is no repository and
            succeeds: the site deploys as before.

  assemble  --site DIR --out DIR [--cache DIR] [--offline]
            `check`, then copy the site to --out, fetch each APK (from --cache
            when a file there has the index's sha256, else from GitHub; never
            with --offline), require sha256 AND size == the signed index, run
            scripts/android-verify-signature.sh on every APK (release key, v2+v3,
            no v1; needs apksigner: $APKSIGNER or $ANDROID_HOME/build-tools,
            which GitHub's ubuntu runners carry), and measure the assembled
            directory against the budget again. Any failure exits 1 and nothing
            is uploaded.

Options for both: --repo-fingerprint-file F (default assets/fdroid/repo-fingerprint),
--signing-doc F (default docs/android/SIGNING.md), --max-bytes N (default 1000000000).
Needs python3 and openssl only (plus apksigner for assemble).
"""
import argparse
import base64
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = "org.redoubtbrowser"
APK_NAME = re.compile(r"^org\.redoubtbrowser_[0-9]{1,12}\.apk$")
SOURCE_URL = re.compile(
    r"^https://github\.com/CPlusPlus17/Redoubt/releases/download/"
    r"android-[0-9][0-9.]*(esr)?-[0-9]+(-beta\.[0-9]+)?/fenix-(arm64-v8a|armeabi-v7a|x86_64)-release\.apk$")
# GitHub Pages: "Published GitHub Pages sites may be no larger than 1 GB."
# (docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits,
# read 2026-10-05). Decimal, the stricter reading.
DEFAULT_MAX_BYTES = 1_000_000_000
SIGNED_JARS = {"entry.jar": "entry.json", "index-v1.jar": "index-v1.json", "index.jar": "index.xml"}


class Refused(Exception):
    pass


def say(msg):
    print(msg, flush=True)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_fp(text):
    fp = re.sub(r"[\s:]", "", text).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", fp):
        raise Refused(f"not a SHA-256 fingerprint: {text.strip()!r}")
    return fp


def release_fingerprint(signing_doc):
    text = pathlib.Path(signing_doc).read_text()
    m = re.search(r"SHA-256 fingerprint(.*?)\n\s*\n", text, re.S)
    block = m.group(1) if m else ""
    m = re.search(r"(?:[0-9A-Fa-f]{2}:){31}[0-9A-Fa-f]{2}", re.sub(r"[ \n]", "", block))
    if not m:
        raise Refused(f"no SHA-256 fingerprint in {signing_doc}")
    return norm_fp(m.group(0))


def manifest_sections(data):
    """JAR manifest -> list of dicts; continuation lines start with one space."""
    lines = data.decode("utf-8").replace("\r\n", "\n").split("\n")
    sections, cur, last = [], {}, None
    for line in lines:
        if line == "":
            if cur:
                sections.append(cur)
            cur, last = {}, None
        elif line.startswith(" ") and last:
            cur[last] += line[1:]
        else:
            k, _, v = line.partition(": ")
            cur[k] = v
            last = k
    if cur:
        sections.append(cur)
    return sections


def openssl(*args, data=None):
    # fdroidserver signs entry.jar with SHA-256 but index-v1.jar and index.jar
    # with SHA1withRSA, for old clients. Fedora's OpenSSL refuses SHA-1
    # signatures by policy unless this variable is set; upstream OpenSSL (the
    # GitHub runner's) ignores it. Only signature VERIFICATION runs here.
    env = {**os.environ, "OPENSSL_ENABLE_SHA1_SIGNATURES": "1"}
    r = subprocess.run(["openssl", *args], input=data, capture_output=True, env=env)
    return r.returncode, r.stdout, r.stderr


def verify_jar(jar_path, member, want_fp):
    """Return the bytes of `member`, verified the way a JAR signature is."""
    try:
        z = zipfile.ZipFile(jar_path)
    except (OSError, zipfile.BadZipFile) as e:
        raise Refused(f"{jar_path.name}: not a JAR ({e})")
    names = z.namelist()
    sigs = [n for n in names if re.fullmatch(r"META-INF/[^/]+\.(RSA|EC|DSA)", n)]
    sfs = [n for n in names if re.fullmatch(r"META-INF/[^/]+\.SF", n)]
    if len(sigs) != 1 or len(sfs) != 1 or sigs[0].rsplit(".", 1)[0] != sfs[0].rsplit(".", 1)[0]:
        raise Refused(f"{jar_path.name}: expected exactly one signature block and its .SF, found {sigs + sfs}")
    extra = {n for n in names if not n.endswith("/")} - {member, "META-INF/MANIFEST.MF", sigs[0], sfs[0]}
    if extra:
        raise Refused(f"{jar_path.name}: unexpected entries {sorted(extra)}")
    sig, sf, mf, body = (z.read(n) for n in (sigs[0], sfs[0], "META-INF/MANIFEST.MF", member))
    with tempfile.TemporaryDirectory() as t:
        (pathlib.Path(t) / "sig").write_bytes(sig)
        (pathlib.Path(t) / "sf").write_bytes(sf)
        rc, _, err = openssl("cms", "-verify", "-binary", "-inform", "DER", "-noverify",
                             "-in", f"{t}/sig", "-content", f"{t}/sf", "-out", os.devnull)
        if rc != 0:
            raise Refused(f"{jar_path.name}: the signature over {sfs[0]} does not verify: "
                          f"{err.decode(errors='replace').strip()[:300]}")
        rc, pem, err = openssl("pkcs7", "-inform", "DER", "-in", f"{t}/sig", "-print_certs")
    certs = re.findall(rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", pem, re.S)
    if rc != 0 or len(certs) != 1:
        raise Refused(f"{jar_path.name}: expected exactly one certificate in the signature block, found {len(certs)}")
    rc, der, _ = openssl("x509", "-outform", "DER", data=certs[0])
    if rc != 0:
        raise Refused(f"{jar_path.name}: unreadable signer certificate")
    got = hashlib.sha256(der).hexdigest()
    if got != want_fp:
        raise Refused(f"{jar_path.name}: signed by {got.upper()}, the pinned repository fingerprint is {want_fp.upper()}")

    # The digest chain: .SF -> MANIFEST.MF -> member. SHA-256 (entry.jar) or
    # SHA1 (index-v1.jar, index.jar: fdroidserver's choice for old clients).
    sf_main = manifest_sections(sf)[0]
    entry = next((s for s in manifest_sections(mf) if s.get("Name") == member), None) or {}
    for label, algo in (("SHA-256", hashlib.sha256), ("SHA1", hashlib.sha1)):
        if f"{label}-Digest-Manifest" in sf_main:
            b64 = lambda d: base64.b64encode(algo(d).digest()).decode()
            if sf_main[f"{label}-Digest-Manifest"] != b64(mf):
                raise Refused(f"{jar_path.name}: {sfs[0]} does not cover MANIFEST.MF ({label}-Digest-Manifest)")
            if entry.get(f"{label}-Digest") != b64(body):
                raise Refused(f"{jar_path.name}: MANIFEST.MF does not carry the {label} digest of {member}")
            return body
    raise Refused(f"{jar_path.name}: {sfs[0]} has no SHA-256 or SHA1 manifest digest")


def load_sources(site):
    p = site / "fdroid" / "sources.json"
    if not p.is_file():
        raise Refused("site/fdroid/sources.json is missing (scripts/fdroid-repo.sh publish writes it)")
    try:
        apks = json.loads(p.read_text())["apks"]
    except (ValueError, KeyError) as e:
        raise Refused(f"site/fdroid/sources.json: unreadable ({e})")
    for name, src in apks.items():
        if not APK_NAME.match(name) or not SOURCE_URL.match(str(src.get("url", ""))):
            raise Refused(f"site/fdroid/sources.json: {name} -> {src.get('url')!r} is not a Redoubt release asset")
    return apks


def site_bytes(site):
    return sum(f.stat().st_size for f in site.rglob("*") if f.is_file() and not f.is_symlink())


def check(args):
    """Returns the APK list [(name, sha256, size, url)], or [] when there is no repository."""
    site = pathlib.Path(args.site)
    repo = site / "fdroid" / "repo"
    committed_apks = sorted(str(p.relative_to(site)) for p in site.rglob("*.apk"))
    if committed_apks:
        raise Refused(f"APKs are committed under site/: {committed_apks}. They are fetched at deploy time, never committed.")
    links = [str(p.relative_to(site)) for p in site.rglob("*") if p.is_symlink()]
    if links:
        raise Refused(f"symlinks under site/: {links}")
    if not repo.exists():
        say("no F-Droid repository committed (site/fdroid/repo/ is absent); nothing to fetch")
        return []

    pin = pathlib.Path(args.repo_fingerprint_file)
    if not pin.is_file():
        raise Refused(f"site/fdroid/repo/ exists but {pin} does not pin the repository fingerprint")
    repo_fp = norm_fp(pin.read_text())
    rel_fp = release_fingerprint(args.signing_doc)
    say(f"repository fingerprint (pinned): {repo_fp.upper()}")
    say(f"release key (SIGNING.md):        {rel_fp.upper()}")

    signed = {}
    for jar, member in SIGNED_JARS.items():
        if not (repo / jar).is_file():
            if jar == "index.jar":
                continue  # the v0 index is optional
            raise Refused(f"site/fdroid/repo/{jar} is missing")
        signed[member] = verify_jar(repo / jar, member, repo_fp)
        say(f"  ok    {jar}: signed by the repository key, covers {member}")

    entry = json.loads(signed["entry.json"])
    plain_entry = repo / "entry.json"
    if plain_entry.is_file() and plain_entry.read_bytes() != signed["entry.json"]:
        raise Refused("site/fdroid/repo/entry.json differs from the signed copy inside entry.jar")
    idx_ref = entry.get("index", {})
    idx_path = repo / idx_ref.get("name", "/index-v2.json").lstrip("/")
    if not idx_path.is_file():
        raise Refused(f"the signed entry names {idx_ref.get('name')}, which is not committed")
    data = idx_path.read_bytes()
    if hashlib.sha256(data).hexdigest() != idx_ref.get("sha256") or len(data) != idx_ref.get("size"):
        raise Refused(f"{idx_path.name}: sha256/size differ from the signed entry.json")
    say(f"  ok    {idx_path.name}: sha256 and size match the signed entry.json")
    for d in entry.get("diffs", {}).values():
        dp = repo / d["name"].lstrip("/")
        if dp.is_file() and sha256_file(dp) != d["sha256"]:
            raise Refused(f"{d['name']}: sha256 differs from the signed entry.json")

    v2 = json.loads(data)
    apks = {}
    for pkg_name, pkg in v2.get("packages", {}).items():
        if pkg_name != PACKAGE:
            raise Refused(f"the index lists {pkg_name}; this repository serves only {PACKAGE}")
        for v in pkg.get("versions", {}).values():
            f = v["file"]
            name = f["name"].lstrip("/")
            if not APK_NAME.match(name) or f["name"] != "/" + name:
                raise Refused(f"unexpected file name in the index: {f['name']!r}")
            signers = (v.get("manifest", {}).get("signer") or {}).get("sha256", [])
            if signers != [rel_fp]:
                raise Refused(f"{name}: the index says it is signed by {signers}, not the release key")
            apks[name] = (f["sha256"], int(f["size"]))
    v1 = json.loads(signed["index-v1.json"])
    v1_apks = {p["apkName"]: p["hash"] for p in v1.get("packages", {}).get(PACKAGE, [])
               if p.get("hashType") == "sha256"}
    if v1_apks != {n: s for n, (s, _) in apks.items()}:
        raise Refused("index-v1.json and index-v2.json do not list the same APKs with the same sha256")
    if not apks:
        raise Refused("the index lists no APK")
    say(f"  ok    index-v1 and index-v2 agree on {len(apks)} APK(s), all signed by the release key")

    sources = load_sources(site)
    missing = sorted(set(apks) - set(sources))
    if missing:
        raise Refused(f"site/fdroid/sources.json has no release asset for {missing}")

    total = site_bytes(site) + sum(size for _, size in apks.values())
    say(f"  budget: site {site_bytes(site)} B + APKs {sum(s for _, s in apks.values())} B = {total} B "
        f"of {args.max_bytes} B")
    if total > args.max_bytes:
        raise Refused(f"the assembled site would be {total} bytes, over the {args.max_bytes}-byte limit "
                      f"(GitHub Pages: 1 GB per published site). Keep fewer releases (KEEP_RELEASES) and publish again.")
    return [(n, s, size, sources[n]["url"]) for n, (s, size) in sorted(apks.items())]


def fetch(url, dest, size):
    req = urllib.request.Request(url, headers={"User-Agent": "redoubt-pages-assemble"})
    h = hashlib.sha256()
    n = 0
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as out:
        for chunk in iter(lambda: r.read(1 << 20), b""):
            n += len(chunk)
            if n > size:
                raise Refused(f"{url}: larger than the {size} bytes the signed index names")
            h.update(chunk)
            out.write(chunk)
    return h.hexdigest(), n


def assemble(args):
    apks = check(args)
    site, out = pathlib.Path(args.site), pathlib.Path(args.out)
    if out.exists() and any(out.iterdir()):
        raise Refused(f"{out} exists and is not empty")
    if out.exists():
        out.rmdir()
    shutil.copytree(site, out)
    say(f"copied {site} -> {out}")
    if not apks:
        return
    repo = out / "fdroid" / "repo"
    cache = pathlib.Path(args.cache) if args.cache else None
    for name, sha, size, url in apks:
        dest = repo / name
        cached = cache / name if cache else None
        if cached and cached.is_file() and cached.stat().st_size == size and sha256_file(cached) == sha:
            shutil.copyfile(cached, dest)
            say(f"  cache {name}")
        else:
            if args.offline:
                raise Refused(f"{name}: not in the cache with sha256 {sha}, and --offline forbids a download")
            say(f"  fetch {name} <- {url}")
            got, n = fetch(url, dest.with_suffix(".part"), size)
            dest.with_suffix(".part").rename(dest)
        got, n = sha256_file(dest), dest.stat().st_size
        if got != sha or n != size:
            raise Refused(f"{name}: sha256 {got} / {n} bytes, the signed index says {sha} / {size} bytes. "
                          "The release asset is not the file the repository key signed for; nothing is deployed.")
        say(f"  ok    {name}  {sha}")

    apksigner = os.environ.get("APKSIGNER", "")
    if not apksigner:
        for base in (os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT")):
            found = sorted(pathlib.Path(base).glob("build-tools/*/apksigner")) if base else []
            if found:
                apksigner = str(found[-1])
                break
    if not apksigner:
        raise Refused("no apksigner (set APKSIGNER, or ANDROID_HOME with build-tools): the release "
                      "certificate of every APK must be checked before it is deployed")
    r = subprocess.run([str(ROOT / "scripts" / "android-verify-signature.sh"), "--signing-doc", args.signing_doc,
                        *[str(repo / n) for n, *_ in apks]], env={**os.environ, "APKSIGNER": apksigner},
                       capture_output=True, text=True)
    sys.stdout.write("".join(f"    {l}\n" for l in r.stdout.splitlines() if "FAIL" in l or "fingerprint" in l))
    if r.returncode != 0:
        sys.stdout.write(r.stdout[-3000:] + r.stderr[-3000:])
        raise Refused("an APK does not carry the release certificate (android-verify-signature.sh)")
    say(f"  ok    {len(apks)} APK(s): release certificate, v2+v3, no v1")

    total = site_bytes(out)
    say(f"assembled {out}: {total} bytes of {args.max_bytes}")
    if total > args.max_bytes:
        raise Refused(f"the assembled site is {total} bytes, over the {args.max_bytes}-byte limit")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "assemble"):
        p = sub.add_parser(name)
        p.add_argument("--site", default=str(ROOT / "site"))
        p.add_argument("--repo-fingerprint-file", default=str(ROOT / "assets" / "fdroid" / "repo-fingerprint"))
        p.add_argument("--signing-doc", default=str(ROOT / "docs" / "android" / "SIGNING.md"))
        p.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
        if name == "assemble":
            p.add_argument("--out", required=True)
            p.add_argument("--cache")
            p.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    try:
        (check if args.cmd == "check" else assemble)(args)
    except Refused as e:
        print(f"fdroid-pages: REFUSED: {e}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError) as e:
        print(f"fdroid-pages: FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    say(f"fdroid-pages: {args.cmd} PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
