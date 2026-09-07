#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/android-verify-signature.sh -- check a RELEASE-signed Redoubt APK.
#
# Reads for: LW-M6-01 (custody), LW-M6-04 (Accrescent), BETA.md entry
# criterion E7.
#
# The release procedure in docs/android/SIGNING.md ends with "the holder
# verifies the signed APK reports the fingerprint above".  That step was prose,
# and prose is not a check: the three things that can go wrong here are all
# silent.
#
#   1. v2-only. Every APK this project has built so far is v2-only, because
#      that is what Gradle's debug signing produces. Accrescent REJECTS
#      v2-only, and v3 is what carries a rotation lineage if the key ever has
#      to change (SIGNING.md, "Rotation, and its limits"). An APK can be
#      perfectly valid, install everywhere, and still be unpublishable.
#   2. The wrong key. A debug-signed build verifies happily; it just is not
#      ours. The fingerprint is the only thing that distinguishes them, and it
#      is a 32-byte hex string a human will not diff by eye at 1 a.m.
#   3. v1 present. Redundant on every supported API level and a second
#      signature surface; SIGNING.md's procedure disables it deliberately.
#
# Exit codes:
#   0  the APK is signed with the published key, v2 and v3, and no v1
#   1  a real failure -- wrong key, missing scheme, or an unexpected v1
#   2  the check could not run (no apksigner, no such file)
#
# Usage:
#   ./scripts/android-verify-signature.sh <apk> [<apk> ...]
#   APKSIGNER=/path/to/apksigner ./scripts/android-verify-signature.sh *.apk
# ---------------------------------------------------------------------------
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SIGNING_MD="$REPO/docs/android/SIGNING.md"

die()  { printf 'android-verify-signature: %s\n' "$1" >&2; exit 2; }
fail() { printf '  FAIL  %s\n' "$1" >&2; bad=1; }
ok()   { printf '  ok    %s\n' "$1"; }

[ $# -ge 1 ] || die "usage: $0 <apk> [<apk> ...]"

# apksigner: from $APKSIGNER, then the SDK, then $PATH. Never guessed silently.
APKSIGNER="${APKSIGNER:-}"
if [ -z "$APKSIGNER" ]; then
    for c in "${ANDROID_SDK_ROOT:-}/build-tools"/*/apksigner \
             "${ANDROID_HOME:-}/build-tools"/*/apksigner; do
        [ -x "$c" ] && APKSIGNER="$c" && break
    done
fi
[ -n "$APKSIGNER" ] || APKSIGNER="$(command -v apksigner 2>/dev/null || true)"
[ -n "$APKSIGNER" ] && [ -x "$APKSIGNER" ] ||
    die "no apksigner. Set APKSIGNER=/path/to/apksigner, or ANDROID_SDK_ROOT to an
       SDK with build-tools installed."

# The expected fingerprint is READ FROM SIGNING.md, not duplicated here: two
# copies of a fingerprint is one copy that can go stale, and the document is
# the thing a user is told to check against.
[ -f "$SIGNING_MD" ] || die "docs/android/SIGNING.md is missing -- it holds the expected fingerprint"
EXPECTED=$(sed -n '/SHA-256 fingerprint/,/^$/p' "$SIGNING_MD" \
           | tr -d ' \n' | grep -oE '([0-9A-Fa-f]{2}:){31}[0-9A-Fa-f]{2}' | head -1)
[ -n "$EXPECTED" ] ||
    die "could not read a SHA-256 fingerprint out of SIGNING.md -- has its format changed?"
EXPECTED_N=$(printf '%s' "$EXPECTED" | tr -d ':' | tr 'A-F' 'a-f')

printf 'expected key (SIGNING.md): %s\n' "$EXPECTED"
printf 'apksigner                : %s\n\n' "$APKSIGNER"

rc=0
for apk in "$@"; do
    printf '%s\n' "$apk"
    bad=0
    [ -f "$apk" ] || { fail "no such file"; rc=1; printf '\n'; continue; }

    out=$("$APKSIGNER" verify --verbose --print-certs "$apk" 2>&1)
    if [ $? -ne 0 ]; then
        fail "apksigner could not verify it:"
        printf '%s\n' "$out" | sed 's/^/        /' >&2
        rc=1; printf '\n'; continue
    fi

    v1=$(printf '%s' "$out" | grep -ci 'Verified using v1 scheme.*true')
    v2=$(printf '%s' "$out" | grep -ci 'Verified using v2 scheme.*true')
    v3=$(printf '%s' "$out" | grep -ci 'Verified using v3 scheme.*true')
    [ "$v2" -ge 1 ] && ok "v2 signature present" || fail "NO v2 signature"
    if [ "$v3" -ge 1 ]; then ok "v3 signature present"
    else fail "NO v3 signature -- Accrescent (LW-M6-04) rejects v2-only, and without v3 there is no rotation lineage"; fi
    [ "$v1" -eq 0 ] && ok "no v1 signature (as intended)" || fail "v1 signature present -- SIGNING.md's procedure disables it"

    got=$(printf '%s' "$out" | grep -iE 'certificate SHA-256 digest' | head -1 \
          | sed -E 's/.*digest: *//' | tr -d ' \r' | tr 'A-F' 'a-f')
    if [ -z "$got" ]; then
        fail "apksigner printed no SHA-256 certificate digest"
    elif [ "$got" = "$EXPECTED_N" ]; then
        ok "fingerprint matches the published key"
    else
        fail "WRONG KEY. expected $EXPECTED_N"
        printf '            got      %s\n' "$got" >&2
        printf '        A debug-signed build verifies too; it is simply not ours.\n' >&2
    fi

    if [ "$bad" -eq 0 ]; then printf '  PASS\n\n'; else printf '  NOT PUBLISHABLE\n\n'; rc=1; fi
done
exit $rc
