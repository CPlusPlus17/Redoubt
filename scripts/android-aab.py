#!/usr/bin/env python3
"""Inspect a Redoubt Android App Bundle (.aab) for the Google Play channel (LW-M6-12).

The AAB is the Play artifact (docs/android/PLAY.md). It is built by
`scripts/android-apk.sh --bundle` from the same fat GeckoView AAR, the same tree
and the same MOZ_BUILD_DATE as the release's four direct-download APKs, with the
in-app update check compiled OUT (Play's Device and Network Abuse policy: an app
from Play updates only through Play). This tool reads the bundle itself and
never trusts a log line:

  inspect   package, versionCode/versionName, min/target SDK from the bundle's
            proto manifest; the ABIs and libxul.so digests under base/lib/; the
            signature state (unsigned, or the jarsigner signer certificate's
            SHA-256); and, when asked, that no dex carries an update-check key,
            that the versionCode is the Fenix scheme's AAB code for the build
            date, that it is at least every APK's code in output-metadata.json,
            and that each libxul.so is byte-identical to the AAR input.

  versioncode  print the versionCode Fenix computes for an ABI and build date
               (the same arithmetic as ConfigPlugin.generateFennecVersionCode).

Exit 0 only when every requested check holds. No third-party modules: the
manifest is aapt2's protobuf XmlNode, decoded by the 40 lines below.

Usage:
  android-aab.py inspect BUNDLE.aab [--expect-unsigned | --expect-signer-sha256 HEX]
        [--forbid-signer-sha256 HEX] [--forbid-key-file FILE]... [--build-date YYYYMMDDHHMMSS]
        [--apk-metadata output-metadata.json] [--maven-zip ABI=target.maven.zip]...
        [--expect-package org.redoubtbrowser] [--json OUT]
  android-aab.py versioncode --build-date YYYYMMDDHHMMSS [--abi universal]
"""
import argparse
import datetime
import fnmatch
import hashlib
import io
import json
import re
import sys
import zipfile

MANIFEST = "base/manifest/AndroidManifest.xml"
SIG_RE = re.compile(r"^META-INF/[^/]+\.(RSA|DSA|EC)$", re.IGNORECASE)
ABIS = ("armeabi-v7a", "arm64-v8a", "x86_64")


# --------------------------------------------------------------------------
# versionCode: ConfigPlugin.generateFennecVersionCode, Redoubt's MOZ_BUILD_DATE
# input (android-components/plugins/config/src/main/java/ConfigPlugin.kt).
# 0x78200000 | hours since 2014-12-28T00 UTC << 3 | x << 2 | p << 1 | g
# x = x86/x86_64 or universal, p = 64-bit or universal, g = universal (AAB).
# A bundle has no ABI filter, so AGP hands Fenix's onVariants "universal".
# --------------------------------------------------------------------------
def version_code(build_date, abi):
    t = datetime.datetime.strptime(build_date, "%Y%m%d%H%M%S")
    hours = int((t - datetime.datetime(2014, 12, 28)).total_seconds() // 3600)
    if not 0 <= hours <= 0x20000 - 366 * 24:
        raise ValueError(f"build date {build_date} is outside the Fennec versionCode range")
    v = 0x78200000 | (hours << 3)
    if abi in ("universal", "x86_64", "x86"):
        v |= 1 << 2
    if abi in ("universal", "arm64-v8a", "x86_64"):
        v |= 1 << 1
    if abi == "universal":
        v |= 1
    return v


# --------------------------------------------------------------------------
# Minimal protobuf reader for aapt2's Resources.proto XmlNode:
#   XmlNode      { XmlElement element = 1; string text = 2; SourcePosition source = 3; }
#   XmlElement   { repeated XmlNamespace namespace_declaration = 1; string namespace_uri = 2;
#                  string name = 3; repeated XmlAttribute attribute = 4; repeated XmlNode child = 5; }
#   XmlAttribute { string namespace_uri = 1; string name = 2; string value = 3; ... }
# aapt2 keeps the attribute's source string in `value`, which is all we read.
# --------------------------------------------------------------------------
def _varint(buf, i):
    shift = val = 0
    while True:
        b = buf[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not b & 0x80:
            return val, i
        shift += 7


def _fields(buf):
    i = 0
    while i < len(buf):
        key, i = _varint(buf, i)
        num, wt = key >> 3, key & 7
        if wt == 0:
            val, i = _varint(buf, i)
        elif wt == 2:
            ln, i = _varint(buf, i)
            val, i = buf[i:i + ln], i + ln
        elif wt == 1:
            val, i = buf[i:i + 8], i + 8
        elif wt == 5:
            val, i = buf[i:i + 4], i + 4
        else:
            raise ValueError(f"unsupported protobuf wire type {wt}")
        yield num, wt, val


def _element(node_bytes):
    for num, wt, val in _fields(node_bytes):
        if num == 1 and wt == 2:
            name, attrs, children = "", {}, []
            for n2, w2, v2 in _fields(val):
                if n2 == 3 and w2 == 2:
                    name = v2.decode()
                elif n2 == 4 and w2 == 2:
                    a = {k: v.decode() for k, w, v in _fields(v2) if w == 2 and k in (2, 3)}
                    attrs[a.get(2, "")] = a.get(3, "")
                elif n2 == 5 and w2 == 2:
                    children.append(v2)
            return name, attrs, children
    return None


def read_manifest(z):
    root = _element(z.read(MANIFEST))
    if not root or root[0] != "manifest":
        raise ValueError(f"{MANIFEST} is not a proto manifest with a <manifest> root")
    _, attrs, children = root
    out = {
        "package": attrs.get("package", ""),
        "versionCode": attrs.get("versionCode", ""),
        "versionName": attrs.get("versionName", ""),
        "minSdkVersion": "",
        "targetSdkVersion": "",
        "permissions": [],
    }
    for c in children:
        el = _element(c)
        if not el:
            continue
        if el[0] == "uses-sdk":
            out["minSdkVersion"] = el[1].get("minSdkVersion", "")
            out["targetSdkVersion"] = el[1].get("targetSdkVersion", "")
        elif el[0].startswith("uses-permission"):
            out["permissions"].append(el[1].get("name", ""))
    return out


def signer_sha256(z):
    """SHA-256 of the jarsigner signer certificate(s), or [] when unsigned."""
    blocks = [n for n in z.namelist() if SIG_RE.match(n)]
    certs = []
    for b in blocks:
        certs.extend(_pkcs7_cert_digests(z.read(b)))
    return blocks, certs


def _pkcs7_cert_digests(der):
    """Digest every certificate in a PKCS#7 SignedData's [0] certificates set.

    A tiny DER walker: ContentInfo SEQ { OID, [0] { SignedData SEQ { INT, SET,
    SEQ, [0] IMPLICIT certificates, ... } } }. Each certificate is a SEQUENCE
    whose full TLV bytes are what keytool/apksigner fingerprint.
    """
    def tlv(buf, i):
        tag = buf[i]
        ln = buf[i + 1]
        j = i + 2
        if ln & 0x80:
            n = ln & 0x7F
            ln = int.from_bytes(buf[j:j + n], "big")
            j += n
        return tag, j, j + ln  # tag, content start, content end

    _, s, e = tlv(der, 0)               # ContentInfo
    _, s, e2 = tlv(der, s)              # contentType OID
    tag, s, e = tlv(der, e2)            # [0] EXPLICIT
    _, s, e = tlv(der, s)               # SignedData SEQUENCE
    i = s
    while i < e:
        tag, cs, ce = tlv(der, i)
        if tag == 0xA0:                 # certificates [0] IMPLICIT SET OF
            out, k = [], cs
            while k < ce:
                _, xs, xe = tlv(der, k)
                out.append(hashlib.sha256(der[k:xe]).hexdigest())
                k = xe
            return out
        i = ce
    return []


def norm_hex(h):
    return h.replace(":", "").strip().lower()


def cmd_versioncode(a):
    print(version_code(a.build_date, a.abi))
    return 0


def cmd_inspect(a):
    problems, notes = [], []
    with zipfile.ZipFile(a.bundle) as z:
        names = z.namelist()
        for need in (MANIFEST, "BundleConfig.pb"):
            if need not in names:
                problems.append(f"{need} missing: not an Android App Bundle")
        if problems:
            print("\n".join("FAIL " + p for p in problems))
            return 1
        man = read_manifest(z)

        libs = {}
        for n in names:
            m = re.match(r"^base/lib/([^/]+)/([^/]+)$", n)
            if m:
                libs.setdefault(m.group(1), {})[m.group(2)] = n
        xul = {abi: hashlib.sha256(z.read(f["libxul.so"])).hexdigest()
               for abi, f in libs.items() if "libxul.so" in f}

        dex = [n for n in names if re.match(r"^base/dex/classes\d*\.dex$", n)]
        key_hits = {}
        for kf in a.forbid_key_file or []:
            key = "".join(open(kf, encoding="ascii").read().split())
            if key:
                key_hits[kf] = sum(z.read(d).count(key.encode()) for d in dex)

        blocks, certs = signer_sha256(z)

    info = dict(man)
    info.update({
        "bundle": a.bundle,
        "sha256": hashlib.sha256(open(a.bundle, "rb").read()).hexdigest(),
        "abis": sorted(libs),
        "libxul_sha256": xul,
        "dex_files": len(dex),
        "signature_blocks": blocks,
        "signer_sha256": certs,
        "update_check": "compiled out" if key_hits and not any(key_hits.values())
                        else ("COMPILED IN" if any(key_hits.values()) else "not checked"),
    })

    if a.expect_package and man["package"] != a.expect_package:
        problems.append(f"package is {man['package']!r}, expected {a.expect_package!r}")
    if not man["versionCode"].isdigit():
        problems.append(f"versionCode {man['versionCode']!r} is not a number")
    for abi in libs:
        if "libxul.so" not in libs[abi]:
            problems.append(f"base/lib/{abi}/ has no libxul.so: installable on {abi} and dead on arrival")
    if not xul:
        problems.append("no base/lib/<abi>/libxul.so at all")

    if a.expect_unsigned:
        if blocks:
            problems.append(f"expected an UNSIGNED bundle, found {blocks}")
    if a.expect_signer_sha256:
        want = norm_hex(a.expect_signer_sha256)
        if certs != [want]:
            problems.append(f"signer certificate(s) {certs or 'none'}, expected exactly [{want}]")
    for bad in a.forbid_signer_sha256 or []:
        if norm_hex(bad) in certs:
            problems.append(f"signed with forbidden certificate {norm_hex(bad)}"
                            " (the APP SIGNING key must never be the Play upload key)")

    for kf, hits in key_hits.items():
        if hits:
            problems.append(f"{hits} dex occurrence(s) of the update-check key from {kf}:"
                            " the Play bundle must have the check compiled out")

    if a.build_date and man["versionCode"].isdigit():
        want = version_code(a.build_date, "universal")
        info["expected_versionCode"] = want
        if int(man["versionCode"]) != want:
            problems.append(f"versionCode {man['versionCode']} != {want}, the AAB code for"
                            f" MOZ_BUILD_DATE {a.build_date}")

    if a.apk_metadata and man["versionCode"].isdigit():
        meta = json.load(open(a.apk_metadata, encoding="utf-8"))
        codes = {e.get("outputFile"): e.get("versionCode") for e in meta.get("elements", [])}
        names_ = {e.get("versionName") for e in meta.get("elements", [])}
        info["apk_versionCodes"] = codes
        top = max(codes.values()) if codes else None
        if top is None or int(man["versionCode"]) < top:
            problems.append(f"AAB versionCode {man['versionCode']} is below the highest APK"
                            f" versionCode of the same build ({top})")
        if names_ != {man["versionName"]}:
            problems.append(f"AAB versionName {man['versionName']!r} differs from the APKs' {sorted(names_)}")

    for spec in a.maven_zip or []:
        abi, _, path = spec.partition("=")
        with zipfile.ZipFile(path) as mz:
            aars = [n for n in mz.namelist() if fnmatch.fnmatch(n, "*geckoview-*.aar")]
            if len(aars) != 1:
                problems.append(f"{path}: expected one geckoview AAR, found {len(aars)}")
                continue
            with zipfile.ZipFile(io.BytesIO(mz.read(aars[0]))) as aar:
                want = hashlib.sha256(aar.read(f"jni/{abi}/libxul.so")).hexdigest()
        if xul.get(abi) != want:
            problems.append(f"base/lib/{abi}/libxul.so {xul.get(abi, 'absent')[:16]} is not the"
                            f" AAR input's ({want[:16]})")
        else:
            notes.append(f"{abi}: libxul.so sha256-identical to the AAR input ({want[:16]})")

    for k in ("package", "versionCode", "versionName", "minSdkVersion", "targetSdkVersion"):
        print(f"{k:17} {info[k]}")
    print(f"{'abis':17} {' '.join(info['abis'])}")
    print(f"{'signature':17} {'unsigned' if not blocks else ', '.join(certs)}")
    print(f"{'update check':17} {info['update_check']}")
    print(f"{'sha256':17} {info['sha256']}")
    for n in notes:
        print("ok   " + n)
    for p in problems:
        print("FAIL " + p)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(info, fh, indent=2, sort_keys=True)
            fh.write("\n")
    return 1 if problems else 0


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("inspect")
    i.add_argument("bundle")
    g = i.add_mutually_exclusive_group()
    g.add_argument("--expect-unsigned", action="store_true")
    g.add_argument("--expect-signer-sha256")
    i.add_argument("--forbid-signer-sha256", action="append")
    i.add_argument("--forbid-key-file", action="append")
    i.add_argument("--build-date")
    i.add_argument("--apk-metadata")
    i.add_argument("--maven-zip", action="append")
    i.add_argument("--expect-package")
    i.add_argument("--json")
    i.set_defaults(func=cmd_inspect)
    v = sub.add_parser("versioncode")
    v.add_argument("--build-date", required=True)
    v.add_argument("--abi", default="universal", choices=("universal",) + ABIS)
    v.set_defaults(func=cmd_versioncode)
    a = p.parse_args()
    if getattr(a, "build_date", None) and not re.fullmatch(r"[0-9]{14}", a.build_date):
        p.error("--build-date must be YYYYMMDDHHMMSS")
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
