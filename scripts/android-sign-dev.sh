#!/usr/bin/env bash
#
# android-sign-dev.sh -- sign a "Redoubt Dev" APK (org.redoubtbrowser.dev) with a
# DEV key, and refuse everything else.
#
# Owner: LW-M7-50. Owner decision 2026-10-10, verbatim: "Yes, separate dev app"
# -- applicationId org.redoubtbrowser.dev, name "Redoubt Dev", signed with a
# throwaway/dev key and never with the release key.
#
# The dev app is the output of the dev-app overlay (patches/android/dev-app.patch,
# `make android-dir TARGETS=android OVERLAYS=...,dev-app`). This script is the
# only signing step it needs, and it fails closed:
#
#   * the input must be an UNSIGNED APK whose package is org.redoubtbrowser.dev
#     (read with aapt2 from the APK itself, not from the file name);
#   * the keystore path must not be the release keystore. The script never opens
#     a file whose name says redoubt-release, and never reads one to compare;
#   * the password comes from a FILE (apksigner --ks-pass file:...), never from
#     the command line or the environment, so it is not in ps or shell history;
#   * after signing, the certificate's SHA-256 must NOT be the release
#     fingerprint published in docs/android/SIGNING.md. If it is, the signed
#     output is deleted and the script fails.
#
# Usage:
#   scripts/android-sign-dev.sh --ks KEYSTORE.p12 --ks-pass-file FILE \
#       [--alias ALIAS] --out SIGNED.apk UNSIGNED.apk
#
# Tools: APKSIGNER and AAPT2 from the environment, else build-tools under
# $ANDROID_HOME / $ANDROID_SDK_ROOT (newest version first).
#
set -euo pipefail
progname=$(basename "$0")
die() { printf '%s: fatal: %s\n' "$progname" "$*" >&2; exit 1; }
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SIGNING_MD="$REPO/docs/android/SIGNING.md"
DEV_PACKAGE="org.redoubtbrowser.dev"

KS="" PASSFILE="" ALIAS="" OUT="" IN=""
while [ $# -gt 0 ]; do
    case "$1" in
        --ks)           KS=${2:-}; shift 2 ;;
        --ks-pass-file) PASSFILE=${2:-}; shift 2 ;;
        --alias)        ALIAS=${2:-}; shift 2 ;;
        --out)          OUT=${2:-}; shift 2 ;;
        -h|--help)      sed -n '2,32p' "$0"; exit 0 ;;
        -*)             die "unknown option $1" ;;
        *)              [ -z "$IN" ] || die "one input APK only"; IN=$1; shift ;;
    esac
done
[ -n "$KS" ] && [ -n "$PASSFILE" ] && [ -n "$OUT" ] && [ -n "$IN" ] ||
    die "usage: $progname --ks KEYSTORE --ks-pass-file FILE [--alias A] --out SIGNED.apk UNSIGNED.apk"
[ -f "$IN" ] || die "no such APK: $IN"
[ -f "$PASSFILE" ] || die "no such password file: $PASSFILE"
case "$(basename "$KS")" in
    *redoubt-release*) die "refusing $KS: that is the release keystore name; the dev app is never release-signed" ;;
esac
[ -f "$KS" ] || die "no such keystore: $KS"
case "$(cd "$(dirname "$PASSFILE")" && pwd)/" in
    "$REPO"/*) die "the password file is inside the repository ($PASSFILE); keep it outside" ;;
esac

find_tool() {
    local name=$1 var=$2 sdk d
    if [ -n "${!var:-}" ]; then printf '%s' "${!var}"; return; fi
    for sdk in "${ANDROID_HOME:-}" "${ANDROID_SDK_ROOT:-}"; do
        [ -n "$sdk" ] && [ -d "$sdk/build-tools" ] || continue
        for d in $(ls -1 "$sdk/build-tools" | sort -rV); do
            [ -x "$sdk/build-tools/$d/$name" ] && { printf '%s' "$sdk/build-tools/$d/$name"; return; }
        done
    done
    command -v "$name" || true
}
APKSIGNER=$(find_tool apksigner APKSIGNER)
AAPT2=$(find_tool aapt2 AAPT2)
[ -n "$APKSIGNER" ] || die "apksigner not found (set APKSIGNER or ANDROID_HOME)"
[ -n "$AAPT2" ] || die "aapt2 not found (set AAPT2 or ANDROID_HOME)"

pkg=$("$AAPT2" dump packagename "$IN" 2>/dev/null) || die "aapt2 cannot read $IN"
[ "$pkg" = "$DEV_PACKAGE" ] ||
    die "$IN is package '$pkg', not $DEV_PACKAGE: only the dev-app overlay's APK is signed here"
if "$APKSIGNER" verify "$IN" >/dev/null 2>&1; then
    die "$IN is already signed; give the unsigned APK (fenix-*-release-unsigned.apk)"
fi

EXPECTED=$(sed -n '/SHA-256 fingerprint/,/^$/p' "$SIGNING_MD" \
           | tr -d ' \n' | grep -oE '([0-9A-Fa-f]{2}:){31}[0-9A-Fa-f]{2}' | head -1 \
           | tr -d ':' | tr 'A-F' 'a-f')
[ -n "$EXPECTED" ] || die "cannot read the release fingerprint from $SIGNING_MD"

args=(sign --ks "$KS" --ks-pass "file:$PASSFILE" --v1-signing-enabled false
      --v2-signing-enabled true --v3-signing-enabled true --out "$OUT")
[ -z "$ALIAS" ] || args+=(--ks-key-alias "$ALIAS" --key-pass "file:$PASSFILE")
"$APKSIGNER" "${args[@]}" "$IN"
rm -f "$OUT.idsig"

got=$("$APKSIGNER" verify --print-certs "$OUT" | sed -n 's/.*certificate SHA-256 digest: //p' | head -1)
[ -n "$got" ] || { rm -f "$OUT"; die "signed APK does not verify"; }
if [ "$got" = "$EXPECTED" ]; then
    rm -f "$OUT"
    die "the key you used IS the release key (SIGNING.md fingerprint); output deleted"
fi
printf 'signed %s\n  package      %s\n  certificate  sha256 %s (not the release key)\n  apk sha256   %s\n' \
    "$OUT" "$pkg" "$got" "$(sha256sum "$OUT" | cut -d' ' -f1)"
