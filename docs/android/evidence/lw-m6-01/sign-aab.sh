#!/bin/sh
# Sign the Google Play bundle with the owner's Play UPLOAD key (LW-M6-12).
#
# Run by the owner, in the owner's terminal, on the key machine (box A), from
# the play/ directory of the signing bundle (docs/android/PLAY.md, "Every
# release"). The agent never runs this with a real key.
#
# What it signs: fenix-release-unsigned.aab, an Android App Bundle built by
# scripts/android-apk.sh --bundle (CI input `bundle=true`). What it signs WITH:
# the Play upload key, NOT the app signing key. Google re-signs every APK it
# generates from the bundle with the app signing key it holds (the existing
# release key, uploaded once with PEPK). The upload key only proves to Google
# that the upload came from us, and Google can reset it if it is lost.
#
# Why jarsigner and not apksigner: "You cannot use apksigner to sign your app
# bundle" (developer.android.com/build/building-cmdline, checked 2026-10-05).
# An AAB is a JAR-signed zip.
#
# Refuses, before writing anything:
#   * an AAB whose sha256 is not the one in SHA256SUMS.aab;
#   * a signer certificate that is the APP SIGNING key (the fingerprint in the
#     bundled SIGNING.md): that key is used once, for the PEPK export, and
#     never as the upload key, so that a lost upload key stays resettable;
#   * a signer certificate other than the registered upload certificate
#     (play-upload-cert.sha256 in this directory, or --upload-cert-sha256 for
#     a rehearsal with a throwaway key);
#   * a signed bundle whose content differs from the unsigned one in anything
#     but its META-INF signature files.
#
# usage: ./sign-aab.sh [--upload-cert-sha256 HEX] [--alias upload] /path/to/redoubt-play-upload.p12
set -eu

die() { printf 'sign-aab: %s\n' "$*" >&2; exit 2; }
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ALIAS=upload
EXPECT=""
while [ "$#" -gt 1 ]; do
    case "$1" in
        --alias) ALIAS=$2; shift 2 ;;
        --upload-cert-sha256) EXPECT=$2; shift 2 ;;
        *) die "unknown argument: $1" ;;
    esac
done
[ "$#" -eq 1 ] || die "usage: $0 [--upload-cert-sha256 HEX] [--alias upload] /path/to/upload-keystore.p12"
case "$1" in /*) KS="$1" ;; *) KS="$(pwd)/$1" ;; esac
[ -f "$KS" ] || die "upload keystore not found: $KS"
cd "$HERE"

command -v jarsigner >/dev/null || die "no jarsigner on PATH -- install a full JDK 17+ (Fedora: java-21-openjdk-devel)"
command -v python3 >/dev/null || die "python3 is required (android-aab.py checks the result)"
command -v sha256sum >/dev/null || die "sha256sum is required"
for f in fenix-release-unsigned.aab SHA256SUMS.aab android-aab.py SIGNING.md; do
    [ -f "$f" ] || die "missing from the play/ bundle: $f"
done
[ ! -e fenix-release.aab ] || die "fenix-release.aab already exists; move the previous output aside first"

if [ -z "$EXPECT" ]; then
    [ -f play-upload-cert.sha256 ] ||
        die "play-upload-cert.sha256 is missing: copy assets/play-upload-cert.sha256 into the
       bundle (committed once the owner has generated the upload key, PLAY.md), or pass
       --upload-cert-sha256 for a rehearsal"
    EXPECT=$(tr -d ' \t\r\n' < play-upload-cert.sha256)
fi
EXPECT=$(printf '%s' "$EXPECT" | tr -d ':' | tr 'A-F' 'a-f')
printf '%s' "$EXPECT" | grep -Eq '^[0-9a-f]{64}$' || die "upload certificate digest is not 64 hex digits"

# The app signing (release) key's fingerprint, read from the one place it lives.
RELEASE=$(awk '/SHA-256 fingerprint/{f=1;next} f&&NF{gsub(/[ :]/,"");s=s $0; if(length(s)>=64){print tolower(s); exit}}' SIGNING.md)
printf '%s' "$RELEASE" | grep -Eq '^[0-9a-f]{64}$' || die "cannot read the release fingerprint from SIGNING.md"
[ "$EXPECT" != "$RELEASE" ] ||
    die "the expected upload certificate IS the app signing key. Generate a separate upload key (PLAY.md)."

echo "== 1/3 checking the unsigned bundle"
sha256sum -c SHA256SUMS.aab
python3 android-aab.py inspect fenix-release-unsigned.aab --expect-unsigned --expect-package org.redoubtbrowser

WORK=$(mktemp -d "$HERE/.redoubt-sign-aab.XXXXXX") || die "cannot create a workspace"
trap 'rm -rf "$WORK"' 0
trap 'exit 130' HUP INT TERM

echo "== 2/3 signing with the upload key (jarsigner asks for the passphrase)"
jarsigner -keystore "$KS" -storetype PKCS12 -sigalg SHA256withRSA -digestalg SHA-256 \
    -signedjar "$WORK/fenix-release.aab" fenix-release-unsigned.aab "$ALIAS"

echo "== 3/3 verifying the signed bundle"
# Not -strict: an upload key is self-signed (Play wants exactly that, PLAY.md
# step 4), and -strict turns "self-signed" and "no PKIX path" into errors
# (exit 4), so it would reject every correct upload. What is required instead:
# exit 0, "jar verified.", and no unsigned or unverifiable entries. Which
# certificate signed is checked by android-aab.py right after.
vout=$(jarsigner -verify "$WORK/fenix-release.aab" 2>&1) ||
    die "jarsigner -verify rejects the signed bundle: $vout"
printf '%s\n' "$vout" | grep -q '^jar verified\.' ||
    die "jarsigner -verify did not report 'jar verified.': $vout"
if printf '%s\n' "$vout" | grep -qiE 'unsigned entries|not signed|has been modified|tampered'; then
    die "jarsigner reports unsigned or modified entries: $vout"
fi
python3 android-aab.py inspect "$WORK/fenix-release.aab" --expect-package org.redoubtbrowser \
    --expect-signer-sha256 "$EXPECT" --forbid-signer-sha256 "$RELEASE"
python3 - fenix-release-unsigned.aab "$WORK/fenix-release.aab" <<'PY'
import re, sys, zipfile
sig = re.compile(r"^META-INF/([^/]+\.(SF|RSA|DSA|EC)|MANIFEST\.MF)$", re.I)
a, b = (zipfile.ZipFile(p) for p in sys.argv[1:3])
na = {n for n in a.namelist() if not sig.match(n)}
nb = {n for n in b.namelist() if not sig.match(n)}
if na != nb:
    sys.exit(f"sign-aab: entry sets differ: {sorted(na ^ nb)[:5]}")
bad = [n for n in sorted(na) if a.read(n) != b.read(n)]
if bad:
    sys.exit(f"sign-aab: signed bundle differs from the unsigned one in {bad[:5]}")
print(f"payload: {len(na)} entries identical to the unsigned bundle")
PY
mv "$WORK/fenix-release.aab" "$HERE/fenix-release.aab"
sha256sum fenix-release.aab > SHA256SUMS.aab.signed
cat SHA256SUMS.aab.signed
cat <<'MSG'

Signed with the registered upload key; payload identical to the CI bundle.
Upload fenix-release.aab in Play Console (Test and release > the track > Create
new release). Google re-signs the APKs it serves with the app signing key it holds.
MSG
