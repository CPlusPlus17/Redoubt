#!/bin/sh
# Run on the offline key machine. The bundle includes the public signing
# document and verifier. Never add the release key or passphrase to the bundle
# transferred from or returned to the build host.
set -eu

die() { printf 'sign: %s\n' "$*" >&2; exit 2; }
[ "$#" -le 1 ] || die "usage: $0 [/path/to/redoubt-release.p12]"
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case "${1:-}" in
    '') KS="$HERE/redoubt-release.p12" ;;
    /*) KS="$1" ;;
    *) KS="$(pwd)/$1" ;;
esac
cd "$HERE"
SIGNER="$HERE/apksigner.jar"
VERIFY="$HERE/android-verify-signature.sh"

command -v java >/dev/null || die "no java on PATH -- install a JDK 17+"
command -v unzip >/dev/null 2>&1 || command -v jar >/dev/null 2>&1 || die "unzip or the JDK jar command is required"
command -v bash >/dev/null || die "bash is required by the signature verifier"
[ -f "$SIGNER" ] || die "apksigner.jar is not next to this script"
[ -x "$VERIFY" ] || die "android-verify-signature.sh is not next to this script or is not executable"
[ -f "$HERE/SIGNING.md" ] || die "the bundle's public SIGNING.md is missing"
[ -f "$KS" ] || die "keystore not found: $KS (pass its path as the first argument)"
export APKSIGNER="$SIGNER"

checksums() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum -c "$1"
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 -c "$1"
    else
        die "sha256sum or shasum is required"
    fi
}

# Require an exact, complete manifest. Filename dots must not act as regular
# expression wildcards, and checking a manifest is insufficient if it omits a tool.
manifest_has() {
    awk -v file="$2" '
        NF == 2 && length($1) == 64 && $1 ~ /^[[:xdigit:]]+$/ &&
        ($2 == file || $2 == "*" file) { found++ }
        END { exit(found != 1) }
    ' "$1" || die "$2 has no unique checksum in $1"
}
ABIS='arm64-v8a armeabi-v7a universal x86_64'
[ -f SHA256SUMS ] || die "SHA256SUMS is missing"
[ "$(wc -l < SHA256SUMS | tr -d ' ')" -eq 4 ] || die "SHA256SUMS must contain exactly four APKs"
for abi in $ABIS; do
    a="fenix-$abi-release-unsigned.apk"
    [ -f "$a" ] || die "missing unsigned APK: $a"
    manifest_has SHA256SUMS "$a"
    [ ! -e "fenix-$abi-release.apk" ] || die "fenix-$abi-release.apk already exists; move previous signed outputs aside first"
done
[ -f SHA256SUMS.tools ] || die "SHA256SUMS.tools is missing"
[ "$(wc -l < SHA256SUMS.tools | tr -d ' ')" -eq 4 ] || die "SHA256SUMS.tools must contain exactly four tools"
for tool in apksigner.jar sign.sh android-verify-signature.sh SIGNING.md; do
    [ -f "$tool" ] || die "missing bundled tool: $tool"
    manifest_has SHA256SUMS.tools "$tool"
done
[ ! -e SHA256SUMS.signed ] || die "SHA256SUMS.signed already exists; move previous signed outputs aside first"

echo "== 1/3 checking the four APKs and bundled tools"
checksums SHA256SUMS
checksums SHA256SUMS.tools

WORK=$(mktemp -d "$HERE/.redoubt-sign.XXXXXX") || die "cannot create signing workspace"
trap 'rm -rf "$WORK"' 0
trap 'exit 130' HUP INT TERM
echo "== 2/3 signing and verifying (v1 off, v2 and v3 on, published key)"
for abi in $ABIS; do
    a="fenix-$abi-release-unsigned.apk"
    out="fenix-$abi-release.apk"
    java -jar "$SIGNER" sign --ks "$KS" --ks-type PKCS12 \
        --v1-signing-enabled false --v2-signing-enabled true --v3-signing-enabled true \
        --v4-signing-enabled false --out "$WORK/$out" "$a"
    "$VERIFY" --signing-doc "$HERE/SIGNING.md" "$WORK/$out"
done

echo "== 3/3 saving verified APKs and their checksums"
(
    cd "$WORK"
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum fenix-*-release.apk > SHA256SUMS.signed
    else
        shasum -a 256 fenix-*-release.apk > SHA256SUMS.signed
    fi
)
for abi in $ABIS; do
    mv "$WORK/fenix-$abi-release.apk" "$HERE/"
done
mv "$WORK/SHA256SUMS.signed" "$HERE/"
cat <<'MSG'

Verified all four APKs: published fingerprint, v2 and v3, no v1.
Copy fenix-*-release.apk and SHA256SUMS.signed to ~/redoubt-signed/ on the
build host for intake verification. Confirm the release keystore has been
moved off that host; signature verification alone cannot establish custody.
MSG
