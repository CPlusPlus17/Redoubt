#!/usr/bin/env bash
# scripts/android-verify-repro.sh — LW-M6-02: APK build reproducibility check.
#
# Runs TWO independent builds of the unsigned release APK from the same
# source tree, the same per-ABI Gecko AAR inputs, and the same pinned
# MOZ_BUILD_DATE (plus the Glean build timestamp derived from it, see
# GLEAN_BUILD_DATE), then compares the produced APKs byte for byte.  Each build
# runs in its own fresh container with its own GRADLE_USER_HOME, and the
# shared Gradle intermediate outputs are wiped between the two, so the second
# build is a real rebuild, not an up-to-date no-op.
#
# Scope: the APK assembly pass (./mach gradle fenix:assembleRelease).  The
# gecko pass and the per-ABI AARs are shared prebuilt inputs here; their
# reproducibility is a separate question and is listed as unverified in
# docs/android/REPRODUCIBLE.md, together with everything else this test does
# not cover.
#
# Cross-machine reproducibility is NOT claimed: this is a same-machine test
# (one machine exists), and the residual cross-machine sources are enumerated
# in docs/android/REPRODUCIBLE.md.
#
# Why an *unsigned* release build: the debug keystore is auto-generated per
# container (the image ships no /root/.android/debug.keystore), so any
# debug-signed APK is guaranteed to differ between two builds even on the
# same machine.  -PdisableDebugSigning (fenix/app/build.gradle:107) is the
# same mechanism upstream uses for official automation builds, where signing
# happens in a separate service.  This script asserts the result is actually
# unsigned (apksigner must reject it) instead of trusting the flag.
#
# Why -PdisableOptimization (R8 off): in this tree the R8-minified release
# build crashes on launch (LW-M4-09: JNA field-order reflection vs R8
# renaming; the fix is LW-M6-07, not applied here), and every release APK
# the project has actually built and booted used R8 off.  Testing a known
# broken configuration would measure the determinism of a build nobody
# ships.  R8's determinism is therefore a RESIDUAL, unverified surface,
# listed with that reason in docs/android/REPRODUCIBLE.md.
#
# Usage:
#   scripts/android-verify-repro.sh [options]
#     --srcdir DIR       source tree with a configured obj-x86_64
#     --aar-dir DIR      per-ABI target.maven.zip inputs
#     --build-date STR   pinned MOZ_BUILD_DATE (same value for both builds)
#     --gradle-seed DIR  dependency cache copied into each outdir's gradle-home
#     --base DIR         where out1/ out2/ and evidence/ land
#     --engine NAME      podman | docker
#     --image NAME       container image
#     --jobs N           mach build -j
#     --skip-build       compare the existing out1/out2 APKs and run the
#                        negative control, without building (evidence recheck)
#
# Exit 0 only if both builds succeeded, every APK is byte-identical across
# the two runs, every APK is unsigned, and the negative control proves the
# comparator detects a difference.

set -euo pipefail

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "[verify-repro] $*"; }

SRCDIR="/home/mgysin/lw-m4-10/src"
AARDIR="/home/mgysin/lw-m2-03/aar"
BUILD_DATE="20260816204534"
# Glean's generated GleanBuildInfo.kt embeds a build timestamp.  The Glean
# Gradle plugin (glean-gradle-plugin 67.3.2, GleanPlugin$_setupTasks_closure1
# $_closure11) passes it to `glean_parser translate` as build_date=<value>,
# taken from the project property gleanBuildDate; when the property is absent
# glean_parser (util.build_date) falls back to the current wall-clock time,
# which is what made classes6.dex differ between the two first builds (the
# two const/16 minute/second immediates of a Calendar.set(...) in
# org.mozilla.fenix.GleanMetrics.GleanBuildInfo).  glean_parser accepts
# "0" (unix epoch) or an ISO8601 string; we pin the same instant as
# MOZ_BUILD_DATE so the app-visible build date and the Glean one agree.
GLEAN_BUILD_DATE="${BUILD_DATE:0:4}-${BUILD_DATE:4:2}-${BUILD_DATE:6:2}T${BUILD_DATE:8:2}:${BUILD_DATE:10:2}:${BUILD_DATE:12:2}"
GRADLE_SEED="/home/mgysin/lw-m4-10/out-combined/gradle-home"
BASE="/home/mgysin/lw-m6-02"
ENGINE="${CONTAINER_ENGINE:-podman}"
IMAGE="localhost/librewolf-android-build:latest"
JOBS=16
SKIP_BUILD=0
NO_CLEAN=0
# SELinux label suffix for the bind mounts -- same as scripts/android-apk.sh.
# On an Enforcing host the container is denied writes to unlabelled mounts
# (measured: mach's `state_dir.mkdir` -> EACCES), so this is load-bearing,
# not a cache nicety.
MOUNT_OPT="${LW_MOUNT_OPT:-z}"

while [ $# -gt 0 ]; do
    case "$1" in
        --srcdir)      SRCDIR=${2:-}; shift 2 ;;
        --srcdir=*)    SRCDIR=${1#*=}; shift ;;
        --aar-dir)     AARDIR=${2:-}; shift 2 ;;
        --aar-dir=*)   AARDIR=${1#*=}; shift ;;
        --build-date)  BUILD_DATE=${2:-}; shift 2 ;;
        --build-date=*) BUILD_DATE=${1#*=}; shift ;;
        --gradle-seed) GRADLE_SEED=${2:-}; shift 2 ;;
        --gradle-seed=*) GRADLE_SEED=${1#*=}; shift ;;
        --base)        BASE=${2:-}; shift 2 ;;
        --base=*)      BASE=${1#*=}; shift ;;
        --engine)      ENGINE=${2:-}; shift 2 ;;
        --engine=*)    ENGINE=${1#*=}; shift ;;
        --image)       IMAGE=${2:-}; shift 2 ;;
        --image=*)     IMAGE=${1#*=}; shift ;;
        --jobs)        JOBS=${2:-}; shift 2 ;;
        --jobs=*)      JOBS=${1#*=}; shift ;;
        --skip-build)  SKIP_BUILD=1; shift ;;
        --no-clean)    NO_CLEAN=1; shift ;;
        -h|--help)     sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)             die "unknown option: $1 (see --help)" ;;
    esac
done

ABIS="armeabi-v7a arm64-v8a x86_64"
HOST_ABI="x86_64"
TRIPLE="x86_64-linux-android"
OBJDIR_NAME="obj-${HOST_ABI}"
OUT1="$BASE/out1"
OUT2="$BASE/out2"
EVIDENCE="$BASE/evidence"
REPO=$(cd "$(dirname "$0")/.." && pwd)
MOZCONFIG_BASE="$REPO/assets/mozconfig.android"

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

command -v "$ENGINE" >/dev/null 2>&1 ||
    die "container engine '$ENGINE' not found in PATH"
"$ENGINE" image inspect "$IMAGE" >/dev/null 2>&1 ||
    die "container image '$IMAGE' not found (make android-build-image)"
[ -f "$MOZCONFIG_BASE" ] || die "base mozconfig '$MOZCONFIG_BASE' not found"
[ -f "$SRCDIR/$OBJDIR_NAME/config.status" ] ||
    die "'$SRCDIR/$OBJDIR_NAME/config.status' missing: --srcdir must be a tree
       that has already been ./mach configure'd for $HOST_ABI (the gecko pass
       is out of scope here, see the header)"
for abi in $ABIS; do
    [ -f "$AARDIR/$abi/target.maven.zip" ] ||
        die "AAR input '$AARDIR/$abi/target.maven.zip' missing"
done
[ -d "$GRADLE_SEED" ] ||
    die "gradle seed '$GRADLE_SEED' is not a directory"
for d in "$SRCDIR" "$BASE"; do
    avail=$(df -BG --output=avail "$(dirname "$d")" 2>/dev/null | tail -1 | tr -dc '0-9')
    # `}` must be the first word of a command to close the group (a `}` after
    # another word is parsed as an argument and the group stays open).
    [ -z "$avail" ] || { [ "$avail" -ge 30 ] ||
        die "only ${avail}GB free on the filesystem holding '$d'"; }
done

# Where the image keeps mach's state directory (the Glean parser virtualenv
# lives under it).  Asked of the image, not hardcoded -- same approach as
# scripts/android-apk.sh.
STATE_PATH=$("$ENGINE" run --rm "$IMAGE" \
    bash -c 'printf "%s" "${MOZBUILD_STATE_PATH:-}"' 2>/dev/null) || STATE_PATH=""
[ -n "$STATE_PATH" ] ||
    die "image '$IMAGE' does not export MOZBUILD_STATE_PATH"

# apksigner, used to assert the APKs are really unsigned.
"$ENGINE" run --rm "$IMAGE" \
    bash -c 'ls "$ANDROID_SDK_ROOT"/build-tools/*/apksigner >/dev/null 2>&1' \
    >/dev/null 2>&1 ||
    die "image '$IMAGE' has no build-tools/*/apksigner"

# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------

write_mozconfig() {
    # Same recipe as scripts/android-apk.sh: the base file verbatim except the
    # --target line, plus the objdir pin.  Never add or drop hardening flags.
    local dest=$1
    {
        printf '# Generated by android-verify-repro.sh -- do not edit.\n'
        printf '# Base: %s   host ABI: %s\n\n' "$MOZCONFIG_BASE" "$HOST_ABI"
        sed -E "s|^([[:space:]]*ac_add_options[[:space:]]*)--target=.*|\\1--target=$TRIPLE|" \
            "$MOZCONFIG_BASE"
        printf '\n# --- appended by android-verify-repro.sh ---\n'
        printf 'mk_add_options MOZ_OBJDIR=@TOPSRCDIR@/obj-%s\n' "$HOST_ABI"
    } > "$dest" || die "cannot write '$dest'"
    grep -Eq '^[[:space:]]*ac_add_options[[:space:]]*--enable-android-subproject=fenix[[:space:]]*$' \
        "$dest" || die "generated mozconfig lost the subproject option"
    grep -Eq '^[[:space:]]*ac_add_options[[:space:]]*--target=.*' "$dest" ||
        die "generated mozconfig has no --target line"
}

prepare_outdir() {
    # $1 = outdir.  AAR inputs are COPIED in (never bind-mounted): the outdir
    # must be self-contained, same as scripts/android-apk.sh.
    local out=$1 abi
    mkdir -p "$out/logs" "$out/mozbuild-srcdirs"
    for abi in $ABIS; do
        mkdir -p "$out/input/$abi"
        cp -f "$AARDIR/$abi/target.maven.zip" "$out/input/$abi/" ||
            die "cannot copy AAR input for $abi"
    done
    if [ ! -d "$out/gradle-home" ]; then
        log "seeding $out/gradle-home from $GRADLE_SEED"
        cp -a "$GRADLE_SEED" "$out/gradle-home" ||
            die "cannot seed the gradle home"
    fi
    write_mozconfig "$out/mozconfig.$HOST_ABI"
}

clean_gradle_outputs() {
    # Wipe the shared per-module Gradle build outputs so a build is a real
    # rebuild, not an up-to-date no-op.  objdir/gradle/maven is the published
    # geckoview AAR (a gecko-pass product and a build INPUT) and is kept.
    local g="$SRCDIR/$OBJDIR_NAME/gradle"
    if [ -d "$g/build" ]; then
        log "wiping $g/build (forcing a real rebuild)"
        rm -rf "$g/build"
    fi
    # The source-tree .gradle holds the configuration cache, shared by both
    # builds.  It is disabled per build (gradle.properties), but wipe the stale
    # entries too so build 2 cannot inherit build 1's resolved state.
    local cc="$SRCDIR/.gradle/configuration-cache"
    if [ -d "$cc" ]; then
        log "wiping $cc (stale configuration cache)"
        rm -rf "$cc"
    fi
}

CURRENT_CONTAINER=""
cleanup_container() {
    if [ -n "$CURRENT_CONTAINER" ]; then
        "$ENGINE" rm -f "$CURRENT_CONTAINER" >/dev/null 2>&1 || true
        CURRENT_CONTAINER=""
    fi
}
trap cleanup_container INT TERM HUP

run_build_pass() {
    # $1 = outdir.  One fresh container per build (no daemon or layer state
    # survives into the other build), same mount layout as android-apk.sh.
    local out=$1 name rc
    name="lw-repro-$$-$(date -u +%s)"
    CURRENT_CONTAINER="$name"
    "$ENGINE" run --rm --name "$name" \
        -v "$SRCDIR:/work/src:$MOUNT_OPT" \
        -v "$out:/work/out:$MOUNT_OPT" \
        -v "$out/mozbuild-srcdirs:$STATE_PATH/srcdirs:$MOUNT_OPT" \
        -w /work/src \
        -e "MOZCONFIG=/work/out/mozconfig.$HOST_ABI" \
        -e "MOZ_BUILD_DATE=$BUILD_DATE" \
        -e "GRADLE_USER_HOME=/work/out/gradle-home" \
        -e "MOZ_ANDROID_FAT_AAR_ARCHITECTURES=$(printf '%s ' $ABIS | sed 's/ /,/g; s/,$//')" \
        -e "MOZ_ANDROID_FAT_AAR_ARMEABI_V7A=/work/out/input/armeabi-v7a/target.maven.zip" \
        -e "MOZ_ANDROID_FAT_AAR_ARM64_V8A=/work/out/input/arm64-v8a/target.maven.zip" \
        -e "MOZ_ANDROID_FAT_AAR_X86_64=/work/out/input/x86_64/target.maven.zip" \
        "$IMAGE" \
        bash -c "
set -u
mkdir -p \"\$GRADLE_USER_HOME\" || exit 90
cp -n /root/.gradle/gradle.properties \"\$GRADLE_USER_HOME\"/ 2>/dev/null || true
# KGP dual-classloader FUS crash fix (gradle/gradle#31278), same as
# scripts/android-apk.sh: telemetry only, cannot change build output.
grep -qx 'kotlin.internal.collectFUSMetrics=false' \"\$GRADLE_USER_HOME/gradle.properties\" 2>/dev/null || \
    echo 'kotlin.internal.collectFUSMetrics=false' >> \"\$GRADLE_USER_HOME/gradle.properties\"
# The two builds share one objdir but have SEPARATE gradle-homes.  Gradle's
# configuration cache (and the build cache) live in the shared objdir / the
# seeded home, so build 2 would otherwise reuse build 1's resolved dependency
# paths and fail on AARs only build 1 downloaded (measured: lifecycle-livedata
# 2.9.4 'No such file or directory').  Disable both caches so every build does
# fresh dependency resolution and actually executes its tasks -- which is also
# the stronger reproducibility claim (no cached output can mask
# nondeterminism).
for p in org.gradle.configuration-cache=false org.gradle.caching=false; do
    grep -qx \"\$p\" \"\$GRADLE_USER_HOME/gradle.properties\" 2>/dev/null || \
        echo \"\$p\" >> \"\$GRADLE_USER_HOME/gradle.properties\"
done
date -u +'PASS apk START %Y-%m-%dT%H:%M:%SZ'

# The Glean Gradle plugin runs the interpreter whose path configure recorded in
# GRADLE_GLEAN_PARSER_VENV; each outdir has its own mozbuild-srcdirs, so on a
# fresh one the venv must be recreated with a quick ./mach configure.
venv=\$(sed -n \"s/.*'GRADLE_GLEAN_PARSER_VENV': '\([^']*\)'.*/\1/p\" \
        $OBJDIR_NAME/config.status 2>/dev/null | head -1)
echo \"GLEAN_PARSER_VENV=\$venv\"
if [ -n \"\$venv\" ] && [ ! -x \"\$venv/bin/python\" ]; then
    echo \"glean parser venv missing, running ./mach configure to recreate it\"
    ./mach configure || exit 92
fi
if [ -n \"\$venv\" ] && [ ! -x \"\$venv/bin/python\" ]; then
    echo \"fatal: \$venv/bin/python still does not exist after ./mach configure\" >&2
    exit 91
fi

# Safe Args first: in the parallel graph :fenix:compileReleaseKotlin can start
# before the generated sources exist (scripts/android-apk.sh measured this).
# -PdisableOptimization: R8 off -- see the header (LW-M4-09 / LW-M6-07).
# -PgleanBuildDate: pin the GleanBuildInfo build timestamp -- see the
# GLEAN_BUILD_DATE comment in the defaults section (reproducibility).
./mach gradle fenix:generateSafeArgsRelease -PdisableDebugSigning -PdisableOptimization -PgleanBuildDate=$GLEAN_BUILD_DATE
rc=\$?
if [ \$rc -ne 0 ]; then
    date -u +'PASS apk END %Y-%m-%dT%H:%M:%SZ'
    echo \"MACH_EXIT=\$rc\"
    exit \$rc
fi
# -PdisableDebugSigning: fenix/app/build.gradle:107 skips signingConfigs.debug
# for release build types when the property is set, so the APKs come out
# unsigned -- the thing under test.  (The debug keystore is auto-generated per
# container, so a signed APK would differ between any two builds.)
# -PgleanBuildDate: same pin as above; the Glean Kotlin translation task runs
# in this invocation and is the one that embeds the timestamp.
./mach gradle fenix:assembleRelease -PfenixSplitAbi=\"\$(printf '%s ' $ABIS | sed 's/ /,/g; s/,$//')\" -PdisableDebugSigning -PdisableOptimization -PgleanBuildDate=$GLEAN_BUILD_DATE
rc=\$?
date -u +'PASS apk END %Y-%m-%dT%H:%M:%SZ'
echo \"MACH_EXIT=\$rc\"
exit \$rc
"
    rc=$?
    CURRENT_CONTAINER=""
    return $rc
}

collect_apks() {
    # $1 = outdir.  Reads AGP's output directory and output-metadata.json,
    # never a log line.
    local out=$1 src n=0 f
    src="$SRCDIR/$OBJDIR_NAME/gradle/build/mobile/android/fenix/app/outputs/apk/release"
    [ -d "$src" ] ||
        die "'$src' missing after a successful fenix:assembleRelease"
    rm -rf "$out/apk"
    mkdir -p "$out/apk"
    for f in "$src"/*.apk; do
        [ -f "$f" ] || continue
        cp "$f" "$out/apk/" || die "cannot copy '$f'"
        n=$((n + 1))
    done
    [ "$n" -gt 0 ] || die "no *.apk in '$src'"
    cp "$src/output-metadata.json" "$out/apk/" 2>/dev/null || true
    ( cd "$out" && sha256sum apk/*.apk > apk.sha256 )
    log "collected $n APKs into $out/apk"
}

check_unsigned() {
    # $1 = outdir.  apksigner must REJECT every APK: an unsigned APK has no v1
    # and no v2/v3 signature block.  Trusting -PdisableDebugSigning instead of
    # the bytes would be exactly the fail-open this test exists to avoid.
    local out=$1 f res rc
    for f in "$out"/apk/*.apk; do
        # The container run exits non-zero for an unsigned APK, which under
        # `set -e` would kill the script at the assignment, so guard it.
        res=$("$ENGINE" run --rm \
                -v "$out:/work/out:$MOUNT_OPT" \
                "$IMAGE" \
                bash -c 's=$(ls "$ANDROID_SDK_ROOT"/build-tools/*/apksigner | head -1); set +e; "$s" verify --print-certs "$1" 2>&1; exit $?' \
                _ "/work/out/apk/$(basename "$f")") && rc=0 || rc=$?
        [ "$rc" -ne 0 ] ||
            die "'$(basename "$f")' VERIFIED as signed; expected unsigned:
$res"
        log "  $(basename "$f"): unsigned (apksigner verify rc=$rc)"
    done
}

# ---------------------------------------------------------------------------
# Comparator
# ---------------------------------------------------------------------------

# Returns 0 iff the two files are byte-identical.  On a mismatch, prints the
# sha256 pair and localises the difference to the zip entries that differ.
compare_apks() {
    local a=$1 b=$2 ha hb
    ha=$(sha256sum "$a" | awk '{print $1}')
    hb=$(sha256sum "$b" | awk '{print $1}')
    if [ "$ha" = "$hb" ]; then
        cmp -s "$a" "$b" && return 0
        echo "sha256 matched but cmp disagrees (hash collision or I/O error): $a vs $b"
        return 1
    fi
    echo "DIFFERENT: $(basename "$a")  vs  $(basename "$b")"
    echo "  A: $ha  ($(stat -c%s "$a") bytes)"
    echo "  B: $hb  ($(stat -c%s "$b") bytes)"
    diff_entries "$a" "$b"
    return 1
}

diff_entries() {
    # Unzip both and compare entry by entry, so a mismatch is attributed to
    # the entry (dex / resources.arsc / lib/*.so / assets/...) that moved.
    local a=$1 b=$2 da db ea eb f n_diff=0 n_same=0
    da=$(mktemp -d) db=$(mktemp -d)
    unzip -q -o "$a" -d "$da" >/dev/null 2>&1 || true
    unzip -q -o "$b" -d "$db" >/dev/null 2>&1 || true
    ea=$(cd "$da" && find . -type f | sort)
    eb=$(cd "$db" && find . -type f | sort)
    if [ "$ea" != "$eb" ]; then
        echo "  entry sets differ (first 40 diff lines):"
        diff <(printf '%s\n' "$ea") <(printf '%s\n' "$eb") | head -40 | sed 's/^/    /'
    fi
    while IFS= read -r f; do
        [ -n "$f" ] || continue
        if [ -f "$da/$f" ] && [ -f "$db/$f" ]; then
            if cmp -s "$da/$f" "$db/$f"; then
                n_same=$((n_same + 1))
            else
                n_diff=$((n_diff + 1))
                echo "    DIFFERS: $f  ($(stat -c%s "$da/$f") vs $(stat -c%s "$db/$f") bytes)"
            fi
        fi
    done <<< "$ea"
    echo "  entries compared: $n_same identical, $n_diff different"
    rm -rf "$da" "$db"
}

# Negative control: the comparator must catch a real difference.  Flip one
# byte in a copy of a real APK and require compare_apks to fail.
# Writes its own evidence log: it must NOT be run through a pipe, because a
# pipe would mask the die() below.
negative_control() {
    local ref=$1 tmp m size off
    tmp=$(mktemp -d)
    m="$tmp/negative-control.apk"
    cp "$ref" "$m"
    size=$(stat -c%s "$m")
    off=$((size / 2))
    printf '\x00' | dd of="$m" bs=1 seek="$off" conv=notrunc status=none
    if compare_apks "$ref" "$m" > "$tmp/result.txt" 2>&1; then
        rm -rf "$tmp"
        die "negative control FAILED: comparator reported two differing APKs as identical"
    fi
    {
        echo "negative control: one byte flipped at offset $off of $(basename "$ref")"
        sed 's/^/  /' "$tmp/result.txt" | head -8
        echo "  comparator verdict: DIFFERENT (correct)"
    } > "$EVIDENCE/negative-control.log"
    log "negative control OK: comparator detected a 1-byte difference"
    rm -rf "$tmp"
}

zip_listing() {
    # Entry names + sizes + timestamps, for the evidence record.
    local apk=$1 out=$2
    unzip -l "$apk" | sed 's/^/  /' > "$out" 2>/dev/null ||
        echo "  (unzip -l failed)" > "$out"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

mkdir -p "$EVIDENCE"
start_all=$(date +%s)
log "srcdir      : $SRCDIR"
log "aar inputs  : $AARDIR"
log "build date  : $BUILD_DATE"
log "out1 / out2 : $OUT1 / $OUT2"
log "engine/image: $ENGINE / $IMAGE   jobs=$JOBS"

if [ "$SKIP_BUILD" != "1" ]; then
    log "=== build 1/2 ==="
    prepare_outdir "$OUT1"
    [ "$NO_CLEAN" = "1" ] || clean_gradle_outputs
    if run_build_pass "$OUT1" > "$OUT1/logs/apk.log" 2>&1; then
        log "build 1 ok"
    else
        tail -30 "$OUT1/logs/apk.log" >&2
        die "build 1 failed; log: $OUT1/logs/apk.log"
    fi
    collect_apks "$OUT1"
    check_unsigned "$OUT1"

    log "=== build 2/2 ==="
    prepare_outdir "$OUT2"
    [ "$NO_CLEAN" = "1" ] || clean_gradle_outputs
    if run_build_pass "$OUT2" > "$OUT2/logs/apk.log" 2>&1; then
        log "build 2 ok"
    else
        tail -30 "$OUT2/logs/apk.log" >&2
        die "build 2 failed; log: $OUT2/logs/apk.log"
    fi
    collect_apks "$OUT2"
    check_unsigned "$OUT2"
else
    log "--skip-build: comparing existing APKs in $OUT1/apk and $OUT2/apk"
    [ -d "$OUT1/apk" ] && [ -d "$OUT2/apk" ] || die "no existing apk/ dirs to compare"
fi

# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------

log "=== comparing the two builds ==="
all_same=1
first_apk=""
while IFS= read -r f; do
    [ -n "$f" ] || continue
    name=$(basename "$f")
    [ -n "$first_apk" ] || first_apk="$f"
    if [ ! -f "$OUT2/apk/$name" ]; then
        log "  $name: MISSING in build 2"
        all_same=0
        continue
    fi
    # compare_apks' status must come from PIPESTATUS[0]: a plain
    # `if a | tee` tests tee's status, which would always pass.
    set +e
    compare_apks "$f" "$OUT2/apk/$name" 2>&1 | tee -a "$EVIDENCE/compare.log"
    cmp_rc=${PIPESTATUS[0]}
    set -e
    if [ "$cmp_rc" -eq 0 ]; then
        log "  $name: IDENTICAL"
    else
        log "  $name: DIFFERS (see above)"
        all_same=0
    fi
done < <(find "$OUT1/apk" -maxdepth 1 -name '*.apk' | sort)

# Zip entry listings for the record (timestamps included: evidence for whether
# AGP normalises them).
for f in "$OUT1"/apk/*.apk; do
    zip_listing "$f" "$EVIDENCE/zip-listing-$(basename "$f").txt"
done

log "=== negative control ==="
[ -n "$first_apk" ] || die "no APK to run the negative control on"
negative_control "$first_apk"

# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------

{
    printf 'android-verify-repro.sh -- %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'tree=%s\naar=%s\nMOZ_BUILD_DATE=%s\nengine=%s image=%s\n\n' \
        "$SRCDIR" "$AARDIR" "$BUILD_DATE" "$ENGINE" "$IMAGE"
    printf 'build 1 sha256:\n'
    sed 's/^/  /' "$OUT1/apk.sha256" 2>/dev/null || printf '  (none)\n'
    printf '\nbuild 2 sha256:\n'
    sed 's/^/  /' "$OUT2/apk.sha256" 2>/dev/null || printf '  (none)\n'
    printf '\nverdict: %s\n' "$([ "$all_same" = "1" ] && echo IDENTICAL || echo DIFFERENT)"
} > "$EVIDENCE/summary.txt"

end_all=$(date +%s)
log "evidence: $EVIDENCE"
log "total wall clock: $((end_all - start_all))s"

if [ "$all_same" = "1" ]; then
    log "PASS: the two independent builds produced byte-identical unsigned APKs"
    exit 0
fi
log "FAIL: the two builds differ (details above); the nondeterminism sources are in docs/android/REPRODUCIBLE.md"
exit 1
