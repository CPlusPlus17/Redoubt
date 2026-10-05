#!/bin/sh
# Run Google's bundletool, pinned by version AND sha256 (LW-M6-12, docs/android/PLAY.md).
#
# Used to turn the Play bundle into installable APKs for testing exactly what
# Play would serve (build-apks --mode=universal or --connected-device), and to
# cross-check the bundle's manifest (dump manifest). Never used to sign a
# release: the owner signs the AAB with sign-aab.sh, and Google signs the APKs.
#
# The jar is downloaded once into $BUNDLETOOL_CACHE (default
# ~/.cache/redoubt/bundletool) and refused unless its sha256 is the pinned one.
# The pin is GitHub's own asset digest for the 1.18.3 release
# (https://github.com/google/bundletool/releases/tag/1.18.3, published
# 2025-12-15, checked 2026-10-05 with `gh api repos/google/bundletool/releases/latest`)
# and was re-measured with sha256sum on the downloaded file.
#
# usage: scripts/bundletool.sh <bundletool arguments...>
#        scripts/bundletool.sh --path      print the verified jar's path
set -eu

VERSION=1.18.3
SHA256=a099cfa1543f55593bc2ed16a70a7c67fe54b1747bb7301f37fdfd6d91028e29
URL="https://github.com/google/bundletool/releases/download/$VERSION/bundletool-all-$VERSION.jar"
CACHE=${BUNDLETOOL_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/redoubt/bundletool}
JAR="$CACHE/bundletool-all-$VERSION.jar"

die() { printf 'bundletool.sh: %s\n' "$*" >&2; exit 2; }

if [ ! -f "$JAR" ]; then
    command -v curl >/dev/null || die "curl is needed to fetch $URL"
    mkdir -p "$CACHE"
    tmp="$JAR.part.$$"
    curl -fsSL --proto '=https' -o "$tmp" "$URL" || { rm -f "$tmp"; die "download failed: $URL"; }
    mv "$tmp" "$JAR"
fi
got=$(sha256sum "$JAR" | cut -c1-64)
if [ "$got" != "$SHA256" ]; then
    die "$JAR has sha256 $got, pinned $SHA256 -- refusing to run it (delete it to re-fetch)"
fi
if [ "${1:-}" = "--path" ]; then
    printf '%s\n' "$JAR"
    exit 0
fi
command -v java >/dev/null || die "java (17+) is required"
exec java -jar "$JAR" "$@"
