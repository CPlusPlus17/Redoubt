#!/bin/sh
# Sign the Redoubt release APKs. Run this ON THE KEY MACHINE, in this directory,
# with the keystore beside it (or pass its path as $1).
#
# Needs a JDK 17+ and nothing else: apksigner.jar sits next to this script and is
# pure Java, so no Android SDK is required. That is deliberate -- the key machine
# is not a build machine (docs/android/SIGNING.md custody rule 3).
set -e
KS="${1:-redoubt-release.p12}"
SIGNER="$(dirname "$0")/apksigner.jar"

command -v java >/dev/null || { echo "no java on PATH -- install a JDK 17+" >&2; exit 2; }
[ -f "$SIGNER" ] || { echo "apksigner.jar is not next to this script" >&2; exit 2; }
[ -f "$KS" ] || { echo "keystore not found: $KS   (pass its path: ./sign.sh /path/to/redoubt-release.p12)" >&2; exit 2; }

echo "== 1/3 checking what you received"
sha256sum -c SHA256SUMS 2>/dev/null || shasum -a 256 -c SHA256SUMS

echo "== 2/3 signing (v1 off, v2 on, v3 on)"
for a in fenix-*-release-unsigned.apk; do
    out="${a%-unsigned.apk}.apk"
    java -jar "$SIGNER" sign --ks "$KS" --ks-type PKCS12 \
        --v1-signing-enabled false --v2-signing-enabled true --v3-signing-enabled true \
        --out "$out" "$a"
    echo "   signed $out"
done

echo "== 3/3 verifying"
for a in fenix-*-release.apk; do
    case "$a" in *-unsigned.apk) continue ;; esac
    printf '%s\n' "$a"
    java -jar "$SIGNER" verify --verbose --print-certs "$a" 2>/dev/null \
        | grep -E 'Verified using v[123] scheme|SHA-256 digest' | sed 's/^/   /'
done

cat <<'MSG'

Done. Every APK above must show v2=true, v3=true, v1=false, and a SHA-256 digest
matching the fingerprint in docs/android/SIGNING.md.

Copy the four fenix-*-release.apk (NOT the -unsigned ones) to
  ~/redoubt-signed/
on the build host, and the checker there will confirm all of that in one command.
MSG
