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
#   0  the APK is signed with the published key, v2 and v3, and no v1;
#      with --unsigned-dir, its ZIP payload also matches the candidate
#   1  a real failure -- wrong key, missing scheme, or an unexpected v1
#   2  the check could not run (no apksigner, no such file)
#
# Usage:
#   ./scripts/android-verify-signature.sh [--signing-doc SIGNING.md] <apk> [<apk> ...]
#   ./scripts/android-verify-signature.sh --unsigned-dir candidate/apk signed/*.apk
#   APKSIGNER=/path/to/apksigner ./scripts/android-verify-signature.sh *.apk
# ---------------------------------------------------------------------------
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SIGNING_MD="$REPO/docs/android/SIGNING.md"

die()  { printf 'android-verify-signature: %s\n' "$1" >&2; exit 2; }
fail() { printf '  FAIL  %s\n' "$1" >&2; bad=1; }
ok()   { printf '  ok    %s\n' "$1"; }

SELF_TEST=0
UNSIGNED_DIR=""
while [ $# -gt 0 ]; do
    case "$1" in
        --self-test) SELF_TEST=1; shift ;;
        --signing-doc)
            [ $# -ge 2 ] || die "--signing-doc needs a path"
            SIGNING_MD="$2"; shift 2 ;;
        --unsigned-dir)
            [ $# -ge 2 ] || die "--unsigned-dir needs a path"
            [ -n "$2" ] || die "--unsigned-dir needs a nonempty path"
            UNSIGNED_DIR="$2"; shift 2 ;;
        --) shift; break ;;
        -*) die "unknown option: $1" ;;
        *) break ;;
    esac
done

[ $# -ge 1 ] || [ "$SELF_TEST" = "1" ] || die "usage: $0 [--self-test] [--signing-doc SIGNING.md] [--unsigned-dir DIR] <apk> [<apk> ...]"
[ "$SELF_TEST" -eq 0 ] || [ -z "$UNSIGNED_DIR" ] || die "--self-test and --unsigned-dir are separate checks"

# apksigner: from $APKSIGNER, then the SDK, then $PATH. Never guessed silently.
APKSIGNER="${APKSIGNER:-}"
if [ -z "$APKSIGNER" ]; then
    for c in "${ANDROID_SDK_ROOT:-}/build-tools"/*/apksigner \
             "${ANDROID_HOME:-}/build-tools"/*/apksigner; do
        [ -x "$c" ] && APKSIGNER="$c" && break
    done
fi
[ -n "$APKSIGNER" ] || APKSIGNER="$(command -v apksigner 2>/dev/null || true)"
# apksigner is a thin shell wrapper around lib/apksigner.jar, and the jar is pure
# Java: it runs anywhere a JDK does, with no SDK install. That matters because
# signing happens on the KEY machine, which is deliberately not this one and has
# no reason to carry an Android SDK. Accept either form.
case "$APKSIGNER" in
    *.jar)
        command -v java >/dev/null 2>&1 || die "APKSIGNER points at a .jar but there is no java on PATH"
        [ -f "$APKSIGNER" ] || die "no such jar: $APKSIGNER"
        APKSIGNER_CMD=(java -jar "$APKSIGNER") ;;
    *)
        [ -n "$APKSIGNER" ] && [ -x "$APKSIGNER" ] ||
            die "no apksigner. Set APKSIGNER to the binary OR to lib/apksigner.jar (which
       needs only a JDK), or ANDROID_SDK_ROOT to an SDK with build-tools installed."
        APKSIGNER_CMD=("$APKSIGNER") ;;
esac
# The self-test invokes this script again and must use the same discovered tool.
export APKSIGNER
if command -v unzip >/dev/null 2>&1; then
    ZIP_LIST=(unzip -Z1)
elif command -v jar >/dev/null 2>&1; then
    ZIP_LIST=(jar tf)
else
    die "unzip or the JDK jar command is required to inspect v1 signature entries"
fi

# The expected fingerprint is READ FROM SIGNING.md, not duplicated here: two
# copies of a fingerprint is one copy that can go stale, and the document is
# the thing a user is told to check against.
[ -f "$SIGNING_MD" ] || die "$SIGNING_MD is missing -- it holds the expected fingerprint"
EXPECTED=$(sed -n '/SHA-256 fingerprint/,/^$/p' "$SIGNING_MD" \
           | tr -d ' \n' | grep -oE '([0-9A-Fa-f]{2}:){31}[0-9A-Fa-f]{2}' | head -1)
[ -n "$EXPECTED" ] ||
    die "could not read a SHA-256 fingerprint out of SIGNING.md -- has its format changed?"
EXPECTED_N=$(printf '%s' "$EXPECTED" | tr -d ':' | tr 'A-F' 'a-f')

printf 'signing document         : %s\n' "$SIGNING_MD"
printf 'expected key             : %s\n' "$EXPECTED"
printf 'apksigner                : %s\n\n' "$APKSIGNER"

# Candidate binding is a build-host intake check. Python is deliberately optional
# for the offline signing helper, which calls this verifier without this flag.
candidate_payload() {
    python3 - "$UNSIGNED_DIR" "$@" <<'PY'
import hashlib
from pathlib import Path
import re
import sys
import zipfile


def fail(message, status=1):
    print("  CANDIDATE FAIL  " + message, file=sys.stderr)
    raise SystemExit(status)


def digest(file):
    value = hashlib.sha256()
    for chunk in iter(lambda: file.read(1024 * 1024), b""):
        value.update(chunk)
    return value.hexdigest()


folder = Path(sys.argv[1])
abis = ("arm64-v8a", "armeabi-v7a", "universal", "x86_64")
expected = {f"fenix-{abi}-release-unsigned.apk" for abi in abis}
manifest = folder / "SHA256SUMS"
if not manifest.is_file():
    fail(f"candidate checksum manifest missing: {manifest}", 2)
try:
    hashes = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](.+)", line)
        if not match or match[2] not in expected or match[2] in hashes:
            fail("SHA256SUMS must list each of the four candidate APKs exactly once")
        hashes[match[2]] = match[1].lower()
    if hashes.keys() != expected:
        fail("SHA256SUMS must list all four candidate APKs")

    # With no signed argument, check the complete candidate before processing any
    # signatures. For a pair, recheck the same open file used for ZIP comparison.
    if len(sys.argv) == 2:
        for name, expected_hash in hashes.items():
            path = folder / name
            if not path.is_file():
                fail(f"candidate APK missing: {path}", 2)
            with path.open("rb") as file:
                if digest(file) != expected_hash:
                    fail(f"candidate checksum mismatch: {name}")
        print("candidate checksums      : all four APKs verified\n")
        raise SystemExit(0)

    signed = Path(sys.argv[2])
    name = signed.name[:-4] + "-unsigned.apk" if signed.name.endswith(".apk") else ""
    if name not in expected:
        fail(f"no candidate counterpart for signed filename: {signed.name}", 2)
    source = folder / name
    if not source.is_file():
        fail(f"candidate APK missing: {source}", 2)
    with source.open("rb") as original:
        if digest(original) != hashes[name]:
            fail(f"candidate checksum mismatch: {name}")
        original.seek(0)
        with zipfile.ZipFile(original) as before, zipfile.ZipFile(signed) as after:
            for label, archive in (("candidate", before), ("signed APK", after)):
                names = archive.namelist()
                if len(names) != len(set(names)):
                    fail(f"duplicate ZIP entry names in {label}")
            if set(before.namelist()) != set(after.namelist()):
                fail(f"ZIP entry set differs from candidate: {signed.name}")
            for entry in before.infolist():
                other = after.getinfo(entry.filename)
                if entry.file_size != other.file_size or entry.compress_type != other.compress_type:
                    fail(f"ZIP entry size or compression differs: {entry.filename}")
                with before.open(entry) as left, after.open(other) as right:
                    if digest(left) != digest(right):
                        fail(f"ZIP payload differs: {entry.filename}")
    print(f"  ok    ZIP payload matches candidate {name}")
except (OSError, UnicodeError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
    fail(f"candidate payload comparison could not complete: {error}")
PY
}
if [ -n "$UNSIGNED_DIR" ]; then
    [ -d "$UNSIGNED_DIR" ] || die "candidate directory is missing: $UNSIGNED_DIR"
    command -v python3 >/dev/null 2>&1 || die "--unsigned-dir needs python3 on the intake host"
    candidate_payload
    candidate_rc=$?
    [ "$candidate_rc" -eq 0 ] || exit "$candidate_rc"
fi

# --------------------------------------------------------------------------
# --self-test: prove this script can return BOTH answers.
#
# Until 2026-09-06 it had only ever printed NOT PUBLISHABLE, because the only
# APKs that exist here are debug-signed. A checker that has never returned 0 is
# not a checker, it is a habit -- so this signs a throwaway copy with a key
# generated on the spot and asserts the two halves separately:
#
#   * a correctly signed APK is detected as v2 AND v3, no v1;
#   * the SAME APK is still REJECTED, because the key is not the published one.
#
# That second half is the important one. It is what stops a well-formed
# signature from a wrong key passing, which is the failure a release process
# cannot survive. The throwaway keystore lives in a temp dir and is deleted;
# it never touches the repo, and it is not and cannot be the release key.
# --------------------------------------------------------------------------
if [ "$SELF_TEST" = "1" ]; then
    src="${1:-}"
    [ -n "$src" ] && [ -f "$src" ] || die "--self-test needs an APK to copy: $0 --self-test <apk>"
    command -v keytool >/dev/null 2>&1 || die "--self-test needs keytool"
    tmp=$(mktemp -d) || die "cannot make a temp dir"
    trap 'rm -rf "$tmp"' EXIT
    printf 'self-test: signing a throwaway copy of %s\n' "$(basename "$src")"
    keytool -genkeypair -keystore "$tmp/t.p12" -storetype PKCS12 -storepass testtest \
        -keyalg RSA -keysize 2048 -validity 1 -alias t \
        -dname "CN=Redoubt Verifier Self Test, O=not a release key" >/dev/null 2>&1 ||
        die "keytool could not generate a throwaway key"
    cp "$src" "$tmp/unsigned.apk"
    "${APKSIGNER_CMD[@]}" sign --ks "$tmp/t.p12" --ks-type PKCS12 --ks-pass pass:testtest \
        --v1-signing-enabled false --v2-signing-enabled true --v3-signing-enabled true \
        --out "$tmp/signed.apk" "$tmp/unsigned.apk" >/dev/null 2>&1 ||
        die "apksigner could not sign the throwaway copy"
    out=$("${APKSIGNER_CMD[@]}" verify --verbose --print-certs "$tmp/signed.apk" 2>&1) ||
        die "apksigner could not verify the throwaway signature"
    st=0
    printf '%s' "$out" | grep -qi 'Verified using v2 scheme.*true' \
        && printf '  ok    self-test: v2 detected on a correctly signed APK\n' \
        || { printf '  FAIL  self-test: v2 NOT detected on a correctly signed APK\n' >&2; st=1; }
    printf '%s' "$out" | grep -qi 'Verified using v3 scheme.*true' \
        && printf '  ok    self-test: v3 detected on a correctly signed APK\n' \
        || { printf '  FAIL  self-test: v3 NOT detected on a correctly signed APK\n' >&2; st=1; }
    # Exercise a real PASS through this verifier using a temporary public
    # fingerprint document. The release document is never changed.
    keytool -list -v -keystore "$tmp/t.p12" -storetype PKCS12 -storepass testtest \
        -J-Duser.language=en -J-Duser.country=US >"$tmp/cert.txt" 2>&1 ||
        die "keytool could not read the throwaway certificate"
    test_fp=$(sed -n 's/^[[:space:]]*SHA256: //p' "$tmp/cert.txt")
    [ -n "$test_fp" ] || die "no fingerprint in the throwaway certificate"
    printf 'SHA-256 fingerprint\n    %s\n\n' "$test_fp" >"$tmp/SIGNING.md"
    if "$0" --signing-doc "$tmp/SIGNING.md" "$tmp/signed.apk" >"$tmp/positive.log" 2>&1; then
        printf '  ok    self-test: correct key, v2 + v3, no v1 accepted\n'
    else
        cat "$tmp/positive.log" >&2
        printf '  FAIL  self-test: the positive verification failed\n' >&2
        st=1
    fi
    "$0" --signing-doc "$SIGNING_MD" "$tmp/signed.apk" >"$tmp/negative.log" 2>&1
    negative_rc=$?
    if [ "$negative_rc" -eq 1 ] && grep -q 'WRONG KEY' "$tmp/negative.log"; then
        printf '  ok    self-test: correctly signed but wrong key is still rejected\n'
    else
        cat "$tmp/negative.log" >&2
        printf '  FAIL  self-test: expected WRONG KEY rejection (exit 1), got exit %s\n' "$negative_rc" >&2
        st=1
    fi
    [ "$st" -eq 0 ] && printf '\nself-test PASSED: the checker detects both schemes and refuses a wrong key.\n\n' \
                    || { printf '\nself-test FAILED\n' >&2; exit 1; }
    [ $# -gt 1 ] || exit 0
    shift
fi

rc=0
for apk in "$@"; do
    printf '%s\n' "$apk"
    bad=0
    [ -f "$apk" ] || { fail "no such file"; rc=2; printf '\n'; continue; }

    out=$("${APKSIGNER_CMD[@]}" verify --verbose --print-certs "$apk" 2>&1)
    if [ $? -ne 0 ]; then
        fail "apksigner could not verify it:"
        printf '%s\n' "$out" | sed 's/^/        /' >&2
        [ "$rc" -eq 2 ] || rc=1
        printf '\n'; continue
    fi

    v1=$(printf '%s' "$out" | grep -ci 'Verified using v1 scheme.*true')
    v2=$(printf '%s' "$out" | grep -ci 'Verified using v2 scheme.*true')
    v3=$(printf '%s' "$out" | grep -ci 'Verified using v3 scheme.*true')
    [ "$v2" -ge 1 ] && ok "v2 signature present" || fail "NO v2 signature"
    if [ "$v3" -ge 1 ]; then ok "v3 signature present"
    else fail "NO v3 signature -- Accrescent (LW-M6-04) rejects v2-only, and without v3 there is no rotation lineage"; fi
    # apksigner reports the schemes it USED, not every scheme present. With
    # minSdk >= 24 it can report v1=false even when JAR signatures are present.
    # Inspect the archive as well so redundant v1 signatures cannot slip through.
    entries=$("${ZIP_LIST[@]}" "$apk" 2>&1)
    if [ $? -ne 0 ]; then
        fail "could not inspect APK entries for v1 signatures"
    elif [ "$v1" -ne 0 ] || grep -qiE '^META-INF/([^/]+\.(SF|RSA|DSA|EC)|SIG-[^/]+)$' <<< "$entries"; then
        fail "v1 signature present -- SIGNING.md's procedure disables it"
    else
        ok "no v1 signature (as intended)"
    fi
    printf '%s\n' "$out" | grep -Eq '^Number of signers: 1[[:space:]]*$' ||
        fail "expected exactly one APK signer"

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

    if [ "$bad" -eq 0 ] && [ -n "$UNSIGNED_DIR" ]; then
        candidate_payload "$apk"
        candidate_rc=$?
        if [ "$candidate_rc" -ne 0 ]; then
            bad=1
            [ "$candidate_rc" -ne 2 ] || rc=2
        fi
    fi
    if [ "$bad" -eq 0 ]; then
        printf '  PASS\n\n'
    else
        printf '  NOT PUBLISHABLE\n\n'
        [ "$rc" -eq 2 ] || rc=1
    fi
done
exit $rc
