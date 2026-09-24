#!/usr/bin/env python3
"""Fetch and package the reviewed uBlock Origin XPI without changing its bytes.

The checked-in pin is the build's trust anchor. Bumping it requires reviewing a
specific AMO release and recording its version, digest, size and Android minimum.
The build checks those values, ZIP integrity and signature-file presence; Gecko
performs Mozilla's cryptographic signature verification at installation time.

An existing cache entry is verified every time, including offline builds. Use
--xpi (or LIBREWOLF_UBO_XPI) to supply an existing download without populating the
cache. --asset-dir must name the existing Fenix src/main/assets directory.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile


PIN_FILE = Path(__file__).resolve().parents[1] / "assets/ubo-extension.json"
EXTENSION_ID = "uBlock0@raymondhill.net"
XPI_ASSET = "extensions/ublock_origin.xpi"
METADATA_ASSET = "extensions/ubo-extension.json"
SIGNATURE_FILES = ("META-INF/manifest.mf", "META-INF/mozilla.sf", "META-INF/mozilla.rsa")


class ValidationError(ValueError):
    """The pin or artifact is unsuitable for packaging."""


def read_pin(path):
    with Path(path).open(encoding="utf-8") as source:
        pin = json.load(source)
    if not isinstance(pin, dict) or type(pin.get("schema")) is not int or pin["schema"] != 1:
        raise ValidationError("uBO pin must be a schema 1 object")
    if pin.get("id") != EXTENSION_ID:
        raise ValidationError("uBO pin has the wrong extension ID")
    if pin.get("asset") != XPI_ASSET:
        raise ValidationError(f"uBO pin asset must be {XPI_ASSET}")
    for field in ("version", "android_min_version"):
        if not isinstance(pin.get(field), str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", pin[field]):
            raise ValidationError(f"uBO pin has an invalid {field}")
    if not isinstance(pin.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", pin["sha256"]):
        raise ValidationError("uBO pin must contain a lowercase SHA-256 digest")
    if type(pin.get("size")) is not int or pin["size"] <= 0:
        raise ValidationError("uBO pin size must be a positive integer")
    expected_url = r"https://addons\.mozilla\.org/firefox/downloads/file/[0-9]+/ublock_origin-" + re.escape(pin["version"]) + r"\.xpi"
    if not isinstance(pin.get("url"), str) or not re.fullmatch(expected_url, pin["url"]):
        raise ValidationError("uBO pin URL must identify a specific versioned AMO download")
    return pin


def validate_xpi(path, pin):
    path = Path(path)
    if path.stat().st_size != pin["size"]:
        raise ValidationError(f"uBO XPI size mismatch: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != pin["sha256"]:
        raise ValidationError(f"uBO XPI SHA-256 mismatch: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValidationError("uBO XPI contains duplicate ZIP members")
            for name in ("manifest.json", *SIGNATURE_FILES):
                if name not in names or archive.getinfo(name).file_size == 0:
                    raise ValidationError(f"uBO XPI lacks required member: {name}")
            if archive.testzip() is not None:
                raise ValidationError("uBO XPI failed ZIP integrity verification")
            manifest = json.loads(archive.read("manifest.json"))
    except (zipfile.BadZipFile, UnicodeError, json.JSONDecodeError) as error:
        raise ValidationError("uBO XPI has an invalid ZIP or manifest") from error
    if not isinstance(manifest, dict):
        raise ValidationError("uBO XPI manifest must be an object")
    if manifest.get("version") != pin["version"]:
        raise ValidationError("uBO XPI manifest version differs from the pin")
    settings = manifest.get("browser_specific_settings")
    if not isinstance(settings, dict) or not isinstance(settings.get("gecko"), dict):
        raise ValidationError("uBO XPI manifest lacks Gecko settings")
    if settings["gecko"].get("id") != pin["id"]:
        raise ValidationError("uBO XPI manifest has the wrong extension ID")
    android = settings.get("gecko_android")
    if not isinstance(android, dict):
        raise ValidationError("uBO XPI manifest lacks explicit Android support")
    if android.get("strict_min_version") != pin["android_min_version"]:
        raise ValidationError("uBO XPI Android minimum version differs from the pin")


class HTTPSRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        if urllib.parse.urlsplit(new_url).scheme != "https":
            raise ValidationError("uBO download redirected to a non-HTTPS URL")
        return super().redirect_request(request, response, code, message, headers, new_url)


def fetch_xpi(pin, cache_dir, *, offline=False):
    cache_dir = Path(cache_dir)
    cached = cache_dir / (pin["sha256"] + ".xpi")
    if cached.exists():
        # A damaged cache is an error, not a reason to silently trust or replace it.
        validate_xpi(cached, pin)
        return cached
    if offline:
        raise ValidationError(f"no cached uBO XPI for offline use: {cached}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    partial = None
    try:
        with tempfile.NamedTemporaryFile(dir=cache_dir, prefix=".ubo-", suffix=".xpi", delete=False) as output:
            partial = Path(output.name)
            opener = urllib.request.build_opener(HTTPSRedirectHandler())
            request = urllib.request.Request(pin["url"], headers={"User-Agent": "Redoubt-build/1"})
            with opener.open(request, timeout=60) as response:
                if urllib.parse.urlsplit(response.geturl()).scheme != "https":
                    raise ValidationError("uBO download did not use HTTPS")
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > pin["size"]:
                        raise ValidationError("uBO download exceeds the pinned size")
                    output.write(chunk)
        validate_xpi(partial, pin)
        partial.chmod(0o644)
        os.replace(partial, cached)
        return cached
    finally:
        if partial is not None:
            partial.unlink(missing_ok=True)


def package_xpi(path, pin, asset_dir):
    asset_dir = Path(asset_dir)
    if not asset_dir.is_dir():
        raise ValidationError(f"Fenix asset directory is missing: {asset_dir}")
    validate_xpi(path, pin)
    destination = asset_dir / pin["asset"]
    metadata = asset_dir / METADATA_ASSET
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Verify the actual copied bytes before either final asset is replaced. This
    # also catches an input file changed concurrently after initial validation.
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix=".ubo-") as staging:
        staged_xpi = Path(staging) / "ublock_origin.xpi"
        staged_metadata = Path(staging) / "ubo-extension.json"
        shutil.copyfile(path, staged_xpi)
        validate_xpi(staged_xpi, pin)
        staged_metadata.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")
        staged_xpi.chmod(0o644)
        staged_metadata.chmod(0o644)
        os.replace(staged_xpi, destination)
        os.replace(staged_metadata, metadata)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pin-file", type=Path, default=PIN_FILE)
    parser.add_argument("--xpi", type=Path, default=os.environ.get("LIBREWOLF_UBO_XPI"),
                        help="use an existing XPI, or set LIBREWOLF_UBO_XPI")
    cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    parser.add_argument("--cache-dir", type=Path, default=cache_root / "redoubt/extensions")
    parser.add_argument("--asset-dir", type=Path, help="package into an existing Fenix src/main/assets directory")
    parser.add_argument("--offline", action="store_true", help="fail if the verified cache is unavailable")
    parser.add_argument("-n", "--no-execute", "--dry-run", action="store_true",
                        help="describe the operation without downloads or filesystem changes")
    args = parser.parse_args(argv)
    try:
        pin = read_pin(args.pin_file)
        if args.no_execute:
            source = args.xpi or (args.cache_dir / (pin["sha256"] + ".xpi"))
            print(f"Would verify uBO {pin['version']} at {source} against {pin['sha256']}")
            if args.xpi is None and not args.offline:
                print(f"Would fetch on cache miss: {pin['url']}")
            if args.asset_dir:
                print(f"Would package {args.asset_dir / pin['asset']} and {args.asset_dir / METADATA_ASSET}")
            return 0
        path = args.xpi or fetch_xpi(pin, args.cache_dir, offline=args.offline)
        validate_xpi(path, pin)
        if args.asset_dir:
            path = package_xpi(path, pin, args.asset_dir)
        print(f"Verified uBO {pin['version']}: {path} (SHA-256 {pin['sha256']})")
        return 0
    except (OSError, ValueError, urllib.error.URLError, zipfile.BadZipFile) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
