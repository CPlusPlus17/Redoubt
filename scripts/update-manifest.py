#!/usr/bin/env python3
"""Generate and verify the signed update-check document (LW-M6-06).

The in-app update check (patches/android/update-check.patch, contract in
docs/android/DISTRIBUTION.md) fetches two static files:

    https://redoubtbrowser.org/update/android/latest.json
    https://redoubtbrowser.org/update/android/latest.json.sig

This script writes the first one from a release's APK output-metadata.json and
tag, and verifies a pair of them exactly the way the app does. It never signs:
signing is the maintainer's step on the key machine,
scripts/sign-update-manifest.sh, with a key that never comes near this script.

    generate   output-metadata.json + tag -> latest.json
    verify     latest.json + latest.json.sig + public key -> the app's verdict
    fetch      the same, but from the live URL, refusing redirects as the app does

The verification mirrors org.mozilla.fenix.lw.UpdateChecker: ECDSA P-256 with
SHA-256 over the exact bytes of latest.json, DER signature in base64 in the
.sig file (whitespace trimmed), public key as base64 DER SubjectPublicKeyInfo;
then `latest_version` non-empty, `download_url` https, and the decision
`UpdateChecker.offers`: the versionCode decides when both sides have one, else
the version strings. The signature itself is checked with the openssl CLI so
the result does not depend on a Python crypto package being installed.
"""

import argparse
import base64
import binascii
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

ENDPOINT = "https://redoubtbrowser.org/update/android/latest.json"
PUBKEY_FILE = ROOT / "assets" / "update-check.android.pubkey"
APPLICATION_ID = "org.redoubtbrowser"
REPO = "CPlusPlus17/Redoubt"
MAX_BYTES = 64 * 1024  # UpdateChecker.MAX_BYTES
USER_AGENT = "Redoubt-UpdateCheck/1"  # UpdateChecker.USER_AGENT
# android-157.0-1-beta.6, android-153.4.0esr-1-beta.3, android-157.0.1-2
TAG_RE = re.compile(r"^android-(?P<version>\d+(?:\.\d+)*(?:esr)?)-(?P<release>\d+)(?P<suffix>-beta\.\d+)?$")
EXPECTED_ABIS = {"arm64-v8a", "armeabi-v7a", "x86_64", "universal"}


class ManifestError(Exception):
    pass


# ---------------------------------------------------------------------------
# The app's logic, mirrored. Keep in step with UpdateCheck.kt.
# ---------------------------------------------------------------------------

def _numbers(text):
    return [int(n) for n in re.findall(r"\d+", text)]


def _split(version):
    dash = version.rfind("-")
    if dash < 0:
        return _numbers(version), []
    return _numbers(version[:dash]), _numbers(version[dash + 1:])


def _compare(a, b):
    for i in range(max(len(a), len(b))):
        x = a[i] if i < len(a) else 0
        y = b[i] if i < len(b) else 0
        if x != y:
            return (x > y) - (x < y)
    return 0


def is_newer(latest, current):
    """UpdateChecker.isNewer."""
    latest_ff, latest_rel = _split(latest)
    current_ff, current_rel = _split(current)
    if not latest_ff and not latest_rel:
        return False
    order = _compare(latest_ff, current_ff)
    return order > 0 if order != 0 else _compare(latest_rel, current_rel) > 0


def parse(document_bytes):
    """UpdateChecker.parse: the fields the app reads, or None where it gives up."""
    try:
        obj = json.loads(document_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(obj, dict):
        return None
    latest, download = obj.get("latest_version"), obj.get("download_url")
    # JSONObject.getString coerces numbers; the generator only ever writes strings.
    if not isinstance(latest, str) or not isinstance(download, str):
        return None
    latest, download = latest.strip(), download.strip()
    if not latest or not download.startswith("https://"):
        return None
    code = obj.get("version_code", 0)
    code = code if isinstance(code, int) and not isinstance(code, bool) and code > 0 else 0
    notes = obj.get("release_notes_url")
    return {
        "latest_version": latest,
        "download_url": download,
        "release_notes_url": notes if isinstance(notes, str) and notes.startswith("https://") else None,
        "version_code": code,
    }


def offers(parsed, current_version, current_code):
    """UpdateChecker.offers."""
    if parsed["version_code"] > 0 and current_code > 0:
        return parsed["version_code"] > current_code
    return is_newer(parsed["latest_version"], current_version)


def decode_pubkey(text):
    text = "".join(text.split())
    try:
        der = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as e:
        raise ManifestError("public key is not base64: %s" % e)
    return der


def check_pubkey(der):
    """Refuse anything but an EC P-256 SubjectPublicKeyInfo."""
    with tempfile.TemporaryDirectory(prefix="redoubt-update-") as tmp:
        path = Path(tmp) / "pub.der"
        path.write_bytes(der)
        out = subprocess.run(["openssl", "pkey", "-pubin", "-inform", "DER", "-in", str(path),
                              "-noout", "-text_pub"], capture_output=True, text=True)
    if out.returncode != 0:
        raise ManifestError("public key is not a DER SubjectPublicKeyInfo: %s" % out.stderr.strip())
    if "prime256v1" not in out.stdout and "P-256" not in out.stdout:
        raise ManifestError("public key is not on the P-256 curve (the app verifies SHA256withECDSA on P-256)")


def signature_valid(document_bytes, sig_text, pubkey_der):
    """UpdateChecker.verify: True/False, never raises on bad input."""
    try:
        sig = base64.b64decode("".join(sig_text.split()), validate=True)
    except (binascii.Error, ValueError):
        return False
    if not sig:
        return False
    with tempfile.TemporaryDirectory(prefix="redoubt-update-") as tmp:
        tmp = Path(tmp)
        (tmp / "pub.der").write_bytes(pubkey_der)
        (tmp / "doc").write_bytes(document_bytes)
        (tmp / "sig").write_bytes(sig)
        pem = subprocess.run(["openssl", "pkey", "-pubin", "-inform", "DER", "-in", str(tmp / "pub.der"),
                              "-out", str(tmp / "pub.pem")], capture_output=True)
        if pem.returncode != 0:
            return False
        out = subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(tmp / "pub.pem"),
                              "-signature", str(tmp / "sig"), str(tmp / "doc")],
                             capture_output=True, text=True)
    return out.returncode == 0 and "Verified OK" in out.stdout


def app_verdict(document_bytes, sig_bytes, pubkey_der, current_version="", current_code=0):
    """What UpdateChecker.check() would return: ('update'|'uptodate'|'noresult', detail)."""
    if len(document_bytes) > MAX_BYTES or len(sig_bytes) > MAX_BYTES:
        return "noresult", "body larger than %d bytes" % MAX_BYTES
    try:
        sig_text = sig_bytes.decode("utf-8").strip()
    except UnicodeDecodeError:
        return "noresult", "signature is not text"
    if not signature_valid(document_bytes, sig_text, pubkey_der):
        return "noresult", "signature did not verify"
    parsed = parse(document_bytes)
    if parsed is None:
        return "noresult", "document did not parse"
    if offers(parsed, current_version, current_code):
        return "update", parsed
    return "uptodate", parsed


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------

def read_metadata(path):
    try:
        meta = json.loads(Path(path).read_text())
    except (OSError, ValueError) as e:
        raise ManifestError("cannot read %s: %s" % (path, e))
    if meta.get("applicationId") != APPLICATION_ID:
        raise ManifestError("applicationId is %r, not %r" % (meta.get("applicationId"), APPLICATION_ID))
    if meta.get("variantName") != "release":
        raise ManifestError("variantName is %r; only release builds are published" % meta.get("variantName"))
    elements = meta.get("elements") or []
    abis, codes, names = set(), [], set()
    for el in elements:
        filters = [f.get("value") for f in el.get("filters", []) if f.get("filterType") == "ABI"]
        abi = filters[0] if filters else ("universal" if el.get("type") == "UNIVERSAL" else None)
        code = el.get("versionCode")
        if abi is None or not isinstance(code, int) or code <= 0:
            raise ManifestError("unexpected element in %s: %r" % (path, el))
        abis.add(abi)
        codes.append(code)
        names.add(el.get("versionName"))
    if abis != EXPECTED_ABIS:
        raise ManifestError("%s describes %s, expected exactly %s"
                            % (path, sorted(abis), sorted(EXPECTED_ABIS)))
    if len(names) != 1:
        raise ManifestError("APKs disagree on versionName: %s" % sorted(map(str, names)))
    return {"version_name": names.pop(), "min_code": min(codes), "max_code": max(codes), "codes": codes}


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_document(meta, tag, download_url=None, release_notes_url=None, published_at=None):
    m = TAG_RE.match(tag)
    if not m:
        raise ManifestError("tag %r is not android-<firefox>-<release>[-beta.N]" % tag)
    base = "%s-%s" % (m.group("version"), m.group("release"))
    vname = meta["version_name"]
    if vname != base and not vname.startswith(base + "-"):
        raise ManifestError("tag %s says %s but the APKs' versionName is %s" % (tag, base, vname))
    release_page = "https://github.com/%s/releases/tag/%s" % (REPO, tag)
    download_url = download_url or release_page
    release_notes_url = release_notes_url or release_page
    for name, url in (("download_url", download_url), ("release_notes_url", release_notes_url)):
        if not url.startswith("https://") or any(c.isspace() for c in url):
            raise ManifestError("%s must be an https URL without whitespace: %r" % (name, url))
    published_at = published_at or utc_now()
    if not re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", published_at):
        raise ManifestError("published_at must be YYYY-MM-DDTHH:MM:SSZ, got %r" % published_at)
    doc = {
        # Shown in the dialog title ("Redoubt %s is available") and used by the
        # app to offer each release once; the tag without its "android-" prefix.
        "latest_version": tag[len("android-"):],
        # The lowest versionCode among the release's APKs: any APK of an older
        # build is below it, any APK of this build is not (UpdateChecker.offers).
        "version_code": meta["min_code"],
        "download_url": download_url,
        "release_notes_url": release_notes_url,
        "published_at": published_at,
    }
    # No "sha256": a release has four APKs; the release page's
    # SHA256SUMS.signed is the one list of digests, and a single field here
    # would name one of them arbitrarily.
    data = (json.dumps(doc, indent=2, ensure_ascii=True) + "\n").encode("ascii")
    parsed = parse(data)
    if parsed is None or parsed["version_code"] != meta["min_code"] or len(data) > MAX_BYTES:
        raise ManifestError("internal: the generated document would not be accepted by the app")
    # Every APK of the build this document describes must read it as up to date.
    for code in meta["codes"]:
        if offers(parsed, vname, code):
            raise ManifestError("internal: versionCode %d would be offered its own release" % code)
    return data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def load_pubkey(arg):
    if arg is None:
        if not PUBKEY_FILE.is_file():
            raise ManifestError("no --pubkey given and %s does not exist (the owner has not "
                                "committed the update-signing public key yet)" % PUBKEY_FILE.relative_to(ROOT))
        arg = "@" + str(PUBKEY_FILE)
    text = Path(arg[1:]).read_text() if arg.startswith("@") else arg
    der = decode_pubkey(text)
    check_pubkey(der)
    return der


def report(verdict, detail, as_json):
    if as_json:
        print(json.dumps({"verdict": verdict, "detail": detail}, indent=2))
    elif verdict == "noresult":
        print("REJECTED: %s (the app would show nothing)" % detail)
    else:
        print("signature OK; latest_version=%s version_code=%s download_url=%s"
              % (detail["latest_version"], detail["version_code"], detail["download_url"]))
        print("verdict for the given install: %s" % ("update offered" if verdict == "update" else "up to date"))


def cmd_generate(args):
    meta = read_metadata(args.metadata)
    data = build_document(meta, args.tag, args.download_url, args.release_notes_url, args.published)
    if args.out == "-":
        sys.stdout.write(data.decode("ascii"))
    else:
        out = Path(args.out)
        if out.exists() and not args.force:
            raise ManifestError("%s exists; pass --force to replace it (and re-sign)" % out)
        sig = Path(str(out) + ".sig")
        if sig.exists():
            raise ManifestError("%s exists and would no longer match; move it aside first" % sig)
        out.write_bytes(data)
        print("wrote %s (%d bytes): %s, version_code %d (APK codes %d..%d)"
              % (out, len(data), args.tag, meta["min_code"], meta["min_code"], meta["max_code"]), file=sys.stderr)
        # sign-update-manifest.sh prints the same digest on the key machine.
        print("sha256 %s" % hashlib.sha256(data).hexdigest(), file=sys.stderr)
    return 0


def cmd_verify(args):
    pub = load_pubkey(args.pubkey)
    doc = Path(args.document).read_bytes()
    sig = Path(args.signature or (args.document + ".sig")).read_bytes()
    verdict, detail = app_verdict(doc, sig, pub, args.current_version, args.current_code)
    report(verdict, detail, args.json)
    if verdict == "noresult":
        return 1
    if args.metadata:
        meta = read_metadata(args.metadata)
        if detail["version_code"] != meta["min_code"]:
            print("MISMATCH: version_code %d, but the release's lowest APK versionCode is %d"
                  % (detail["version_code"], meta["min_code"]))
            return 1
        for code in meta["codes"]:
            if offers(detail, meta["version_name"], code):
                print("MISMATCH: an APK of this release (versionCode %d) would be offered it" % code)
                return 1
        print("matches %s: version_code is the lowest of %s" % (args.metadata, sorted(meta["codes"])))
    return 0


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=10) as r:
            if r.status != 200:
                raise ManifestError("%s: HTTP %d (the app only accepts 2xx and follows no redirect)" % (url, r.status))
            return r.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise ManifestError("%s: HTTP %d%s" % (url, e.code, " -> " + e.headers.get("Location", "")
                                                if 300 <= e.code < 400 else ""))
    except urllib.error.URLError as e:
        raise ManifestError("%s: %s" % (url, e.reason))


def cmd_fetch(args):
    pub = load_pubkey(args.pubkey)
    doc, sig = _get(args.url), _get(args.url + ".sig")
    verdict, detail = app_verdict(doc, sig, pub, args.current_version, args.current_code)
    report(verdict, detail, args.json)
    if verdict == "noresult":
        return 1
    if args.expect_tag and detail["latest_version"] != args.expect_tag[len("android-"):]:
        print("MISMATCH: live document names %s, expected %s" % (detail["latest_version"], args.expect_tag))
        return 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="write latest.json for a release")
    g.add_argument("--metadata", required=True, help="the release's apk/output-metadata.json")
    g.add_argument("--tag", required=True, help="release tag, e.g. android-157.0-1-beta.6")
    g.add_argument("--download-url", help="default: the tag's GitHub release page")
    g.add_argument("--release-notes-url", help="default: the tag's GitHub release page")
    g.add_argument("--published", help="YYYY-MM-DDTHH:MM:SSZ (default: now, UTC)")
    g.add_argument("--out", default="-", help="output file (default: stdout)")
    g.add_argument("--force", action="store_true", help="replace an existing output file")
    g.set_defaults(func=cmd_generate)

    def common(p):
        p.add_argument("--pubkey", help="base64 SPKI, or @file (default: @%s)" % PUBKEY_FILE.relative_to(ROOT))
        p.add_argument("--current-version", default="", help="versionName of a hypothetical install")
        p.add_argument("--current-code", type=int, default=0, help="versionCode of a hypothetical install")
        p.add_argument("--json", action="store_true", help="machine-readable verdict")

    v = sub.add_parser("verify", help="verify latest.json + latest.json.sig as the app does")
    v.add_argument("document")
    v.add_argument("signature", nargs="?", help="default: <document>.sig")
    v.add_argument("--metadata", help="also check version_code against this output-metadata.json")
    common(v)
    v.set_defaults(func=cmd_verify)

    f = sub.add_parser("fetch", help="verify the live endpoint, refusing redirects as the app does")
    f.add_argument("--url", default=ENDPOINT)
    f.add_argument("--expect-tag", help="fail unless the live document names this tag")
    common(f)
    f.set_defaults(func=cmd_fetch)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except ManifestError as e:
        print("update-manifest: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
