#!/bin/sh
# sign-update-manifest.sh -- sign the update-check document on the key machine.
#
# Owner-run, like docs/android/evidence/lw-m6-01/sign.sh, and deliberately
# separate from it: this uses the UPDATE-SIGNING key (ECDSA P-256), never the
# APK release keystore. docs/android/SIGNING.md "The update-signing key" says
# why the two are different keys and how this one is held.
#
#   ./sign-update-manifest.sh /path/to/redoubt-update-signing.pem latest.json
#
# Writes latest.json.sig next to latest.json: base64 of the DER ECDSA
# signature over the exact bytes of latest.json, which is what
# org.mozilla.fenix.lw.UpdateChecker.verify expects.
#
# Before anything is written, the fresh signature is verified against the
# PINNED public key -- update-check.android.pubkey next to this script, or the
# repository's assets/update-check.android.pubkey -- which is the key the app
# embeds. A signature from any other key (a test key, a stale copy) is
# refused, not written, because the app would refuse it silently and forever.
#
# Needs only a POSIX shell and openssl (OpenSSL 3 or LibreSSL). The key file
# is read by openssl alone (it prompts for the passphrase); this script never
# sees the key's bytes or its passphrase.
set -eu

die() { printf 'sign-update-manifest: %s\n' "$*" >&2; exit 2; }
[ "$#" -eq 2 ] || [ "$#" -eq 3 ] || die "usage: $0 <update-signing-key.pem> <latest.json> [<pinned pubkey file>]"
KEY=$1
DOC=$2
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "$#" -eq 3 ]; then
    PIN=$3
elif [ -f "$HERE/update-check.android.pubkey" ]; then
    PIN="$HERE/update-check.android.pubkey"
else
    PIN="$HERE/../assets/update-check.android.pubkey"
fi
SIG="$DOC.sig"

command -v openssl >/dev/null 2>&1 || die "openssl is required"
[ -f "$KEY" ] || die "key not found: $KEY"
[ -f "$DOC" ] || die "document not found: $DOC"
[ -f "$PIN" ] || die "pinned public key not found: $PIN (the base64 SubjectPublicKeyInfo the app embeds)"
[ ! -e "$SIG" ] || die "$SIG already exists; move it aside first"
size=$(wc -c < "$DOC" | tr -d ' ')
[ "$size" -gt 0 ] && [ "$size" -le 65536 ] || die "$DOC is $size bytes; the app reads at most 65536"
grep -q '"latest_version"' "$DOC" && grep -q '"download_url"' "$DOC" ||
    die "$DOC does not look like an update document (generate it with scripts/update-manifest.py)"

WORK=$(mktemp -d "${TMPDIR:-/tmp}/redoubt-update-sign.XXXXXX") || die "cannot create a work directory"
trap 'rm -rf "$WORK"' 0
trap 'exit 130' HUP INT TERM

# The pinned key, as PEM, built from its base64 without trusting openssl's
# base64 decoder flags (which differ between OpenSSL and LibreSSL).
pin=$(tr -d ' \t\r\n' < "$PIN")
case "$pin" in ''|*[!A-Za-z0-9+/=]*) die "$PIN is not one line of base64" ;; esac
{
    echo '-----BEGIN PUBLIC KEY-----'
    printf '%s\n' "$pin" | fold -w 64
    echo '-----END PUBLIC KEY-----'
} > "$WORK/pin.pem"
openssl pkey -pubin -in "$WORK/pin.pem" -noout -text_pub 2>/dev/null > "$WORK/pin.txt" ||
    openssl ec -pubin -in "$WORK/pin.pem" -noout -text 2>/dev/null > "$WORK/pin.txt" ||
    die "$PIN is not a public key openssl can read"
grep -q -e prime256v1 -e P-256 "$WORK/pin.txt" || die "$PIN is not an EC P-256 key"

if command -v sha256sum >/dev/null 2>&1; then
    digest=$(sha256sum "$DOC" | cut -d' ' -f1)
else
    digest=$(shasum -a 256 "$DOC" | cut -d' ' -f1)
fi
echo "== document: $DOC"
echo "   sha256   $digest"
echo "   compare this digest with the one printed on the build host before going on."
sed 's/^/   | /' "$DOC"

echo "== signing (openssl will ask for the update-signing key's passphrase)"
openssl dgst -sha256 -sign "$KEY" -out "$WORK/sig.der" "$DOC" || die "openssl could not sign"

echo "== verifying against the pinned public key"
if ! openssl dgst -sha256 -verify "$WORK/pin.pem" -signature "$WORK/sig.der" "$DOC" >/dev/null 2>&1; then
    die "the signature does NOT verify against $PIN -- wrong key? Nothing was written."
fi
openssl base64 -A -in "$WORK/sig.der" > "$WORK/sig.b64"
echo >> "$WORK/sig.b64"
mv "$WORK/sig.b64" "$SIG"
echo "Verified OK. Wrote $SIG."
echo "Return $DOC and $SIG to the build host; check them there with"
echo "  ./scripts/update-manifest.py verify $(basename "$DOC") --metadata <apk dir>/output-metadata.json"
