#!/bin/sh
# Run by the key holder, on the machine that holds the release key (see
# docs/android/SIGNING.md for where that is today). The bundle includes the
# public signing document and verifier. Never add the release key or passphrase
# to the bundle transferred from or returned to the build host.
#
# Two ways to reach the key:
#   sign.sh [/path/to/redoubt-release.p12]   a PKCS12 keystore file (prompts for
#                                            its passphrase once per APK)
#   REDOUBT_SIGN_PKCS11_CFG=<cfg> REDOUBT_SIGN_KEY_ALIAS=<alias> sign.sh
#                                            a hardware token (YubiKey PIV) through
#                                            Java's SunPKCS11 provider; prompts for
#                                            the PIN once per APK, and the token may
#                                            ask for a touch per signature
#                                            (docs/android/YUBIKEY.md)
set -eu

die() { printf 'sign: %s\n' "$*" >&2; exit 2; }
[ "$#" -le 1 ] || die "usage: $0 [/path/to/redoubt-release.p12]"
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
P11_CFG=${REDOUBT_SIGN_PKCS11_CFG:-}
P11_ALIAS=${REDOUBT_SIGN_KEY_ALIAS:-}
if [ -n "$P11_CFG" ]; then
    [ "$#" -eq 0 ] || die "REDOUBT_SIGN_PKCS11_CFG is set: sign with the token, without a keystore argument"
    [ -n "$P11_ALIAS" ] || die "REDOUBT_SIGN_KEY_ALIAS is required with REDOUBT_SIGN_PKCS11_CFG (list it with keytool, docs/android/YUBIKEY.md)"
    case "$P11_CFG" in /*) ;; *) P11_CFG="$(pwd)/$P11_CFG" ;; esac
    [ -f "$P11_CFG" ] || die "PKCS#11 config not found: $P11_CFG"
    KS=NONE
else
    [ -z "$P11_ALIAS" ] || die "REDOUBT_SIGN_KEY_ALIAS is set without REDOUBT_SIGN_PKCS11_CFG"
    case "${1:-}" in
        '') KS="$HERE/redoubt-release.p12" ;;
        /*) KS="$1" ;;
        *) KS="$(pwd)/$1" ;;
    esac
fi
cd "$HERE"
SIGNER="$HERE/apksigner.jar"
VERIFY="$HERE/android-verify-signature.sh"

command -v java >/dev/null || die "no java on PATH -- install a JDK 17+"
command -v unzip >/dev/null 2>&1 || command -v jar >/dev/null 2>&1 || die "unzip or the JDK jar command is required"
command -v bash >/dev/null || die "bash is required by the signature verifier"
[ -f "$SIGNER" ] || die "apksigner.jar is not next to this script"
[ -x "$VERIFY" ] || die "android-verify-signature.sh is not next to this script or is not executable"
[ -f "$HERE/SIGNING.md" ] || die "the bundle's public SIGNING.md is missing"
[ -n "$P11_CFG" ] || [ -f "$KS" ] || die "keystore not found: $KS (pass its path as the first argument)"
export APKSIGNER="$SIGNER"

# Key-source arguments for apksigner: a PKCS12 file, or the token's PKCS#11
# keystore ("NONE" is apksigner's name for a keystore without a file).
sign_one() {
    if [ -n "$P11_CFG" ]; then
        java -jar "$SIGNER" sign --ks NONE --ks-type PKCS11 \
            --provider-class sun.security.pkcs11.SunPKCS11 --provider-arg "$P11_CFG" \
            --ks-key-alias "$P11_ALIAS" "$@"
    else
        java -jar "$SIGNER" sign --ks "$KS" --ks-type PKCS12 "$@"
    fi
}

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
    sign_one \
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
build host for intake verification. Signature verification alone cannot
establish custody: SIGNING.md records where the key lives.
MSG
