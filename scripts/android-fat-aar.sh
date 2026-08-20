#!/usr/bin/env bash
#
# android-fat-aar.sh -- build the shipped Android ABIs and merge them into one
# fat GeckoView AAR, using the tree's own fat-AAR support.
#
# Owner: LW-M2-03.  Driven by `make android-aar`; usable standalone.
#
# ---------------------------------------------------------------------------
# What this does, and why it is N+1 passes and not one
# ---------------------------------------------------------------------------
#
# Gecko has no "build all ABIs at once" mode.  One objdir is one --target.  The
# multi-ABI artifact is assembled afterwards by the tree's own merger, and the
# shape of that merger is not ours to invent -- it is
# `python/mozbuild/mozbuild/action/fat_aar.py`, driven from `Makefile.in:70-76`
# through the `android-fat-aar-artifact` tier (`config/baseconfig.mk:46,54-56`).
# We drive it the way taskcluster does in
# `taskcluster/kinds/build-fat-aar/kind.yml`:
#
#   pass 1..N   one full `./mach build` per ABI, each in its own objdir.
#               Each produces a per-ABI GeckoView AAR published into
#               <objdir>/gradle/maven, which we pack into a target.maven.zip
#               (the exact input shape fat_aar.py consumes).
#
#   pass N+1    the merge.  MOZ_ANDROID_FAT_AAR_ARCHITECTURES + one
#               MOZ_ANDROID_FAT_AAR_<ABI> per input zip.  fat_aar.py unpacks
#               every input AAR, *verifies that everything except jni/** and
#               the per-ABI pref files is byte-identical across ABIs*, copies
#               the native libraries of all ABIs into dist/fat-aar/output/jni,
#               and `mobile/android/geckoview/build.gradle:131-135` then points
#               the AAR's jniLibs at that directory instead of this pass's own
#               dist/geckoview/lib.
#
# The merge pass runs **in the objdir of one of the ABIs already built** (the
# --fat-host-abi, armeabi-v7a by default), with the same mozconfig, the same
# --target and one extra set of environment variables.  Everything it needs is
# already compiled there, so it is an incremental build: it re-runs the merge,
# the packaging and Gradle, and nothing else.
#
# Upstream instead runs the merge as a separate no-compile build
# (`mobile/android/config/mozconfigs/android-arm/nightly-fat-aar` sources
# `build/mozconfig.no-compile`), because in CI the merge job is a different
# machine with no objdir at all.  Reproducing that locally was tried first and
# is a dead end for us on two counts, both measured rather than assumed:
#
#   - `--disable-compile-environment` makes configure reject every option that
#     is gated on the compile environment.  On assets/mozconfig.android that is
#     seven of them, --enable-hardening and --enable-stl-hardening included, and
#     a merge pass that silently drops hardening flags is exactly the sort of
#     artifact this project must not produce by accident;
#   - it then still fails on "Cannot find embedded-uniffi-bindgen", because
#     `mobile/android/moz.configure:189-210` switches those host tools from
#     "built by this build" to "must already exist" when there is no compile
#     environment.  Upstream supplies them as separate toolchain artifacts
#     (kind.yml fetches linux64-embedded-uniffi-bindgen and linux64-nimbus-fml);
#     we would have to reproduce that plumbing to buy nothing.
#
# Reusing the objdir keeps the merge pass on the *unmodified*
# assets/mozconfig.android, which is worth more than the few minutes the
# no-compile variant might have saved.
#
# ---------------------------------------------------------------------------
# Two things that silently produce a broken or unbuildable AAR
# ---------------------------------------------------------------------------
#
# 1. MOZ_BUILD_DATE must be identical across all passes.  Without it every
#    build stamps its own buildid (`build/variables.py:22-28`), the buildid
#    lands inside omni.ja (application.ini / platform.ini) and in the Gradle
#    version number (`build.gradle:223-233`), and fat_aar.py's cross-ABI
#    comparison then finds differing files that are not on its allow-list and
#    fails the merge.  This script pins one MOZ_BUILD_DATE for the whole run
#    and records it in the summary.
#
# 2. MOZILLA_OFFICIAL must be set (assets/mozconfig.android does).  Without it
#    `build.gradle:228-231` appends "-SNAPSHOT" to the version, and
#    `mobile/android/mach_commands.py:150-155` deliberately skips every
#    "-SNAPSHOT" path when packing the maven zip -- so the zip comes out empty
#    and the merge dies on "with more than one candidate AAR found: []".  The
#    per-ABI check below catches that with a message that says so.
#
# ---------------------------------------------------------------------------
# Which ABIs ship, and why 32-bit x86 does not
# ---------------------------------------------------------------------------
#
# armeabi-v7a, arm64-v8a and x86_64.  32-bit x86 is NOT built, and this is not
# a budget decision that could be revisited by spending another 22 minutes:
#
#   - `mobile/android/moz.configure:161-166` declares
#     MOZ_ANDROID_FAT_AAR_ARCHITECTURES with
#     choices=("armeabi-v7a", "arm64-v8a", "x86_64").  "x86" is rejected by
#     configure itself.
#   - `python/mozbuild/mozbuild/action/fat_aar.py:174` repeats the same list as
#     _ALL_ARCHS and argparse rejects anything else, and :28-33 has no x86 entry
#     in its arch->job map either.
#
# So the tree cannot put a 32-bit x86 slice in a fat AAR at all; shipping one
# would mean a second, separate artifact. 32-bit x86 Android devices are
# essentially emulator-only today, and the emulator has an x86_64 image. It is
# out of scope, and `--abis` will refuse it rather than build something the
# merger will drop on the floor.
#
# x86_64 has one prerequisite the two ARM ABIs do not: nasm.  The preflight
# below checks the image for it and says what to do; docs/android/BUILD.md's
# "no nasm/yasm is needed" is true of its aarch64-only baseline and of nothing
# else.
#
# ---------------------------------------------------------------------------
# Cost (measured; docs/android/BUILD.md has the single-ABI baseline)
# ---------------------------------------------------------------------------
#
# One cold three-ABI run, `make android-aar` at -j16 on a 32-core / 62 GB host
# that was NOT idle (five other agents on it), LibreWolf 153.0esr with the full
# 28-patch set, podman + the pinned image:
#
#   pass          wall clock   peak container memory
#   armeabi-v7a   19m20s       32.1 GB
#   arm64-v8a     15m31s       30.2 GB
#   x86_64        15m41s       31.2 GB
#   merge          8m28s       24.3 GB
#   TOTAL         59m01s
#
# armeabi-v7a is the outlier only because it goes first and pays for the Gradle
# distribution and the whole Maven graph; the shared Gradle home makes the next
# two ~15m30s each.  A warm merge on an unchanged tree is 55s.
#
# Memory is the binding constraint, not CPU (mach reported 42% CPU efficiency
# for the single-ABI baseline).  ~31 GB per pass at -j16 is why the passes run
# strictly sequentially: three of these in parallel does not fit on a 62 GB
# machine, and a runner with less than 32 GB should drop to -j8.
#
# Each ABI keeps its own objdir (~21 GB) and the merge reuses one of them, so
# budget ~65 GB of disk for a three-ABI run on top of the ~10 GB source tree.
# The merged AAR is ~238 MB (12 native libraries per ABI plus one omni.ja) and
# each per-ABI target.maven.zip is 86-95 MB.
#
# build-times.txt in the output directory records what each run actually cost.
#
set -u
set -o pipefail

progname=$(basename "$0")

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

# The three ABIs a fat AAR can hold.  Order matters only for readability; the
# merge pass sorts internally.
DEFAULT_ABIS="armeabi-v7a,arm64-v8a,x86_64"

# Which ABI's configuration hosts the merge pass.  Upstream uses arm
# (`taskcluster/kinds/build-fat-aar/kind.yml`: custom-build-variant-cfg: arm,
# mozconfig-variant *-fat-aar under android-arm/), so we default to the same.
# In 153 this is not load-bearing for the minimum SDK -- MOZ_ANDROID_MIN_SDK_VERSION
# is a flat 26 for every target (`build/moz.configure/android-sdk.configure:160`),
# not the 32/64-bit split that fat_aar.py's allow-list comment still mentions --
# but the merge pass does compile the Java/Kotlin half of the AAR, so keeping
# upstream's choice keeps our artifact comparable to theirs.
DEFAULT_FAT_HOST_ABI="armeabi-v7a"

# Same default as the Makefile's, and deliberately not auto-detected -- see the
# CONTAINER_ENGINE comment in the Makefile for why.
ENGINE=${CONTAINER_ENGINE:-docker}
IMAGE=${LW_ANDROID_IMAGE:-librewolf-android-build}

# SELinux label suffix for the bind mounts.  ":z" (shared) is correct on an
# Enforcing host where more than one container touches the path; ":Z" would
# relabel exclusively and break every other reader of the tree.  Set to an
# empty string with --mount-opt= if your engine does not understand it.
MOUNT_OPT=${LW_MOUNT_OPT:-z}

SRCDIR=""
OUTDIR=""
ABIS="$DEFAULT_ABIS"
FAT_HOST_ABI="$DEFAULT_FAT_HOST_ABI"
MOZCONFIG_SRC=""
JOBS=""
BUILD_DATE=""
DRY_RUN=0
SKIP_EXISTING=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log()  { printf '%s [%s] %s\n' "$(date -u +%H:%M:%S)" "$progname" "$*"; }
warn() { printf '%s [%s] WARNING: %s\n' "$(date -u +%H:%M:%S)" "$progname" "$*" >&2; }
die()  { printf '%s [%s] fatal: %s\n' "$(date -u +%H:%M:%S)" "$progname" "$*" >&2; exit 1; }

usage() {
    cat <<EOF
usage: $progname --srcdir DIR [options]

Builds one GeckoView AAR per Android ABI and merges them into a single fat AAR.

  --srcdir DIR      extracted, patched source tree to build in (required).
                    It gets one objdir per ABI, so give it its own copy.
  --outdir DIR      where mozconfigs, logs, the per-ABI maven zips and the
                    merged AAR are written.  Default: <srcdir>/../librewolf-android-aar
  --abis LIST       comma separated, subset of $DEFAULT_ABIS
                    (default: all three).  32-bit x86 is not accepted; see the
                    comment at the top of this file.
  --fat-host-abi A  ABI whose objdir hosts the merge pass, which runs there
                    incrementally after that ABI is built
                    (default: $DEFAULT_FAT_HOST_ABI, as upstream).  Must be in --abis.
  --mozconfig FILE  base mozconfig (default: assets/mozconfig.android next to
                    this script).  Its single --target line is rewritten per ABI;
                    nothing else in it is touched.
  --jobs N          -j for mach.  Default: min(16, nproc).  Memory, not CPU, is
                    the limit: ~2 GB of anonymous memory per job.
  --build-date S    MOZ_BUILD_DATE, 14 digits YYYYMMDDHHMMSS.  Default: now (UTC).
                    Pin it to reproduce a previous run byte for byte.
  --engine E        container engine (default: \$CONTAINER_ENGINE or docker)
  --image NAME      container image (default: $IMAGE)
  --mount-opt O     bind mount suffix, "z" on SELinux (default: $MOUNT_OPT; "" to disable)
  --skip-existing   reuse a per-ABI target.maven.zip already in --outdir instead
                    of rebuilding that ABI.  For iterating on the merge pass only.
  -n, --dry-run     run every preflight check, print the plan, build nothing.
  -h, --help        this text.

Exit status is 0 only if the merged AAR exists and contains exactly one
jni/<abi>/libxul.so for each requested ABI and no others.
EOF
}

# armeabi-v7a -> arm-linux-androideabi, and so on.  These are the target
# triples upstream uses, from mobile/android/config/mozconfigs/android-*/nightly.
abi_to_target() {
    case "$1" in
        armeabi-v7a) echo "arm-linux-androideabi" ;;
        arm64-v8a)   echo "aarch64-linux-android" ;;
        x86_64)      echo "x86_64-linux-android" ;;
        *)           return 1 ;;
    esac
}

# armeabi-v7a -> ARMEABI_V7A.  The spelling Makefile.in:73-75 expects for the
# MOZ_ANDROID_FAT_AAR_<ABI> variables.
abi_to_var() {
    printf '%s' "$1" | tr 'a-z-' 'A-Z_'
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

# `shift 2` on a lone trailing flag is a no-op that returns non-zero, which
# without this guard turns the loop below into an infinite one.
need_val() { [ "$1" -ge 2 ] || die "$2 needs a value"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --srcdir|--outdir|--abis|--fat-host-abi|--mozconfig|--jobs|-j|--build-date|--engine|--image|--mount-opt)
            need_val "$#" "$1" ;;
    esac
    case "$1" in
        --srcdir)        SRCDIR=${2:-}; shift 2 ;;
        --srcdir=*)      SRCDIR=${1#*=}; shift ;;
        --outdir)        OUTDIR=${2:-}; shift 2 ;;
        --outdir=*)      OUTDIR=${1#*=}; shift ;;
        --abis)          ABIS=${2:-}; shift 2 ;;
        --abis=*)        ABIS=${1#*=}; shift ;;
        --fat-host-abi)  FAT_HOST_ABI=${2:-}; shift 2 ;;
        --fat-host-abi=*) FAT_HOST_ABI=${1#*=}; shift ;;
        --mozconfig)     MOZCONFIG_SRC=${2:-}; shift 2 ;;
        --mozconfig=*)   MOZCONFIG_SRC=${1#*=}; shift ;;
        --jobs|-j)       JOBS=${2:-}; shift 2 ;;
        --jobs=*)        JOBS=${1#*=}; shift ;;
        --build-date)    BUILD_DATE=${2:-}; shift 2 ;;
        --build-date=*)  BUILD_DATE=${1#*=}; shift ;;
        --engine)        ENGINE=${2:-}; shift 2 ;;
        --engine=*)      ENGINE=${1#*=}; shift ;;
        --image)         IMAGE=${2:-}; shift 2 ;;
        --image=*)       IMAGE=${1#*=}; shift ;;
        --mount-opt)     MOUNT_OPT=${2:-}; shift 2 ;;
        --mount-opt=*)   MOUNT_OPT=${1#*=}; shift ;;
        --skip-existing) SKIP_EXISTING=1; shift ;;
        -n|--dry-run)    DRY_RUN=1; shift ;;
        -h|--help)       usage; exit 0 ;;
        *)               usage >&2; die "unknown argument: $1" ;;
    esac
done

# ---------------------------------------------------------------------------
# Preflight.  Everything that can be known before a 20 minute build is checked
# here, because the alternative is finding out at minute 20.
# ---------------------------------------------------------------------------

repo_root=$(cd "$(dirname "$0")/.." && pwd) || die "cannot resolve the repository root"

[ -n "$SRCDIR" ] || { usage >&2; die "--srcdir is required"; }
[ -d "$SRCDIR" ] || die "--srcdir '$SRCDIR' is not a directory"
SRCDIR=$(cd "$SRCDIR" && pwd)

[ -x "$SRCDIR/mach" ] || die "'$SRCDIR' has no executable mach -- is that an extracted Firefox tree?"
[ -f "$SRCDIR/python/mozbuild/mozbuild/action/fat_aar.py" ] ||
    die "'$SRCDIR' has no python/mozbuild/mozbuild/action/fat_aar.py -- this tree has no fat-AAR support"
[ -f "$SRCDIR/mobile/android/mach_commands.py" ] ||
    die "'$SRCDIR/mobile/android/mach_commands.py' is missing; the maven zip is packed with its create_maven_archive()"

if [ -z "$MOZCONFIG_SRC" ]; then
    MOZCONFIG_SRC="$repo_root/assets/mozconfig.android"
fi
[ -f "$MOZCONFIG_SRC" ] || die "base mozconfig '$MOZCONFIG_SRC' does not exist"
MOZCONFIG_SRC=$(cd "$(dirname "$MOZCONFIG_SRC")" && pwd)/$(basename "$MOZCONFIG_SRC")

# The per-ABI mozconfig is the base file with its --target line rewritten.  That
# is only safe if there is exactly one such line: zero means we would build
# whatever the host is, two means the last one wins and we would silently
# rewrite the wrong one.
target_lines=$(grep -c '^[[:space:]]*ac_add_options[[:space:]]*--target=' "$MOZCONFIG_SRC" || true)
[ "$target_lines" = "1" ] ||
    die "'$MOZCONFIG_SRC' has $target_lines 'ac_add_options --target=' lines, expected exactly 1"

# MOZILLA_OFFICIAL: see the header.  Without it the maven zip comes out empty.
grep -Eq '^[[:space:]]*export[[:space:]]+MOZILLA_OFFICIAL=1' "$MOZCONFIG_SRC" ||
    die "'$MOZCONFIG_SRC' does not export MOZILLA_OFFICIAL=1; the per-ABI maven zips would be
       empty (build.gradle:228-231 adds -SNAPSHOT, mach_commands.py:150-155 skips it)"

# ABI list.
abi_list=$(printf '%s' "$ABIS" | tr ',' ' ')
[ -n "$(printf '%s' "$abi_list" | tr -d '[:space:]')" ] || die "--abis is empty"
for abi in $abi_list; do
    abi_to_target "$abi" >/dev/null 2>&1 || {
        if [ "$abi" = "x86" ] || [ "$abi" = "i686" ]; then
            die "32-bit x86 cannot go in a fat AAR: mobile/android/moz.configure:161-166 and
       fat_aar.py:174 both allow only armeabi-v7a, arm64-v8a and x86_64.
       See the comment at the top of $progname."
        fi
        die "unknown ABI '$abi'; valid: $DEFAULT_ABIS"
    }
done
# Duplicates would build the same ABI twice and then hand fat_aar.py two
# identical inputs under one key.
dupes=$(printf '%s\n' $abi_list | sort | uniq -d)
[ -z "$dupes" ] || die "--abis lists $(printf '%s' "$dupes" | tr '\n' ' ' | sed 's/ *$//') more than once"

abi_to_target "$FAT_HOST_ABI" >/dev/null 2>&1 || die "--fat-host-abi '$FAT_HOST_ABI' is not a valid ABI"
# No `printf | grep -q` here either: see the SIGPIPE note further down.
case " $abi_list " in
    *" $FAT_HOST_ABI "*) ;;
    *) die "--fat-host-abi '$FAT_HOST_ABI' is not in --abis ($ABIS)" ;;
esac

# Jobs.
if [ -z "$JOBS" ]; then
    host_cpus=$(nproc 2>/dev/null || echo 4)
    JOBS=$host_cpus
    [ "$JOBS" -gt 16 ] && JOBS=16
fi
printf '%s' "$JOBS" | grep -Eq '^[1-9][0-9]*$' || die "--jobs '$JOBS' is not a positive integer"
[ "$JOBS" -le 16 ] || warn "-j$JOBS is above the only level ever measured (-j16), and peak memory
         scales with it: ~31 GB anonymous at -j16.  See docs/android/BUILD.md."

# Build date.  14 digits or build/variables.py:23-25 silently ignores it -- and
# "silently ignores it" here means every pass stamps a different buildid and the
# merge fails 70 minutes later.
if [ -z "$BUILD_DATE" ]; then
    BUILD_DATE=$(date -u +%Y%m%d%H%M%S)
fi
printf '%s' "$BUILD_DATE" | grep -Eq '^[0-9]{14}$' ||
    die "--build-date '$BUILD_DATE' is not 14 digits (YYYYMMDDHHMMSS); build/variables.py:23-25
       would ignore it and every pass would stamp a different buildid"

# Container engine and image.
command -v "$ENGINE" >/dev/null 2>&1 ||
    die "container engine '$ENGINE' not found in PATH.  Pass --engine=podman (or
       CONTAINER_ENGINE=podman) if that is what this machine has."
if ! "$ENGINE" image exists "$IMAGE" >/dev/null 2>&1; then
    # `image exists` is podman-only; fall back to the portable spelling.
    "$ENGINE" image inspect "$IMAGE" >/dev/null 2>&1 ||
        die "container image '$IMAGE' not found.  Build it with:
       make android-build-image CONTAINER_ENGINE=$ENGINE"
fi

# nasm, for the x86_64 ABI only.
#
# `toolkit/moz.configure:2631-2659` makes nasm a hard requirement whenever the
# target CPU is x86 or x86_64 -- AV1, FFVPX, JPEG and VPX all want it -- and
# dies with "Nasm is required to build with AV1, FFVPX, JPEG and VPX, but it was
# not found."  It is not needed for either ARM ABI, which is why
# docs/android/BUILD.md's aarch64-only baseline says nasm is not required and
# why the toolchain image does not (yet) ship it.
#
# Checked here by *running* the image, not by reading a Dockerfile, and checked
# before the first build rather than at the x86_64 pass, which on a three-ABI
# run is ~45 minutes later.  check_prog's bootstrap search path is
# $MOZBUILD_STATE_PATH/nasm, exactly where `mach artifact toolchain --from-build
# linux64-nasm` unpacks it.
case " $abi_list " in
    *" x86_64 "*)
        if ! "$ENGINE" run --rm "$IMAGE" \
                bash -c 'command -v nasm >/dev/null 2>&1 || [ -x "$MOZBUILD_STATE_PATH/nasm/nasm" ]' \
                >/dev/null 2>&1; then
            die "image '$IMAGE' has no nasm, so the x86_64 ABI cannot be configured
       (toolkit/moz.configure:2655-2659 dies with 'Nasm is required to build with
       AV1, FFVPX, JPEG and VPX').  Either add it to the image --

         cd \$MOZBUILD_STATE_PATH && mach artifact toolchain --from-build linux64-nasm

       which is the same pinned nasm upstream builds with
       (taskcluster/kinds/toolchain/nasm.yml:59-72, nasm 3.01) -- or drop the ABI
       with --abis=armeabi-v7a,arm64-v8a and ship a two-ABI AAR."
        fi ;;
esac

# Output directory.
if [ -z "$OUTDIR" ]; then
    OUTDIR="$(dirname "$SRCDIR")/librewolf-android-aar"
fi
# Checked before the directory is created, so a rejected --outdir does not leave
# the directory it was rejected for behind (inside the source tree, at that).
case "$(cd "$(dirname "$OUTDIR")" 2>/dev/null && pwd)/$(basename "$OUTDIR")" in
    "$SRCDIR"|"$SRCDIR"/*)
        die "--outdir must not be inside --srcdir: it is bind-mounted separately" ;;
esac
mkdir -p "$OUTDIR/logs" || die "cannot create output directory '$OUTDIR'"
OUTDIR=$(cd "$OUTDIR" && pwd)

# Disk.  One objdir per ABI at ~21 GB, plus the merge pass's own.
abi_count=$(printf '%s\n' $abi_list | wc -l)
need_gb=$(( abi_count * 22 ))
avail_gb=$(df -BG --output=avail "$SRCDIR" 2>/dev/null | tail -1 | tr -dc '0-9')
if [ -n "$avail_gb" ] && [ "$avail_gb" -lt "$need_gb" ]; then
    die "only ${avail_gb}GB free on the filesystem holding '$SRCDIR'; this run needs about
       ${need_gb}GB (${abi_count} objdirs at ~21GB each; the merge reuses one of them)"
fi

mount_suffix=""
[ -n "$MOUNT_OPT" ] && mount_suffix=":$MOUNT_OPT"

log "source tree     : $SRCDIR"
log "output          : $OUTDIR"
log "base mozconfig  : $MOZCONFIG_SRC"
log "ABIs            : $(printf '%s' "$abi_list" | tr '\n' ' ')(merge hosted by $FAT_HOST_ABI)"
log "engine / image  : $ENGINE / $IMAGE"
log "mach jobs       : -j$JOBS"
log "MOZ_BUILD_DATE  : $BUILD_DATE"

# ---------------------------------------------------------------------------
# mozconfig generation
# ---------------------------------------------------------------------------
#
# One generated mozconfig per pass, in $OUTDIR so it is archived next to the
# logs and the artifact it produced.  The base file is copied verbatim except
# for the --target line, so every hardening option, every export and every
# comment in assets/mozconfig.android is what actually gets built -- this script
# never edits, filters or "fixes up" the hardening flags.
#
# MOZ_OBJDIR is appended rather than passed in the environment because mach's
# mozconfig loader expands @TOPSRCDIR@ there (python/mozbuild/mozbuild/mozconfig.py:401-402),
# which keeps every objdir inside the tree it belongs to.

write_mozconfig() {
    # $1 = ABI, $2 = destination path
    local abi=$1 dest=$2 triple
    triple=$(abi_to_target "$abi") || die "internal: no triple for '$abi'"

    {
        printf '# Generated by %s on %s -- do not edit, it is overwritten.\n' \
            "$progname" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        printf '# Base: %s   ABI: %s\n' "$MOZCONFIG_SRC" "$abi"
        printf '# The only change from the base file is the --target line.\n\n'
        sed -E "s|^([[:space:]]*ac_add_options[[:space:]]*)--target=.*|\\1--target=$triple|" \
            "$MOZCONFIG_SRC"
        printf '\n\n# --- appended by %s ---\n' "$progname"
        printf 'mk_add_options MOZ_OBJDIR=@TOPSRCDIR@/obj-%s\n' "$abi"
    } > "$dest" || die "cannot write '$dest'"

    # Assert the rewrite actually happened.  A sed that matched nothing would
    # leave the base target in place and we would build the same ABI N times --
    # which looks perfectly healthy right up to the merge.
    local got
    got=$(grep -E '^[[:space:]]*ac_add_options[[:space:]]*--target=' "$dest" | tail -1)
    [ "$got" = "ac_add_options --target=$triple" ] ||
        die "generated mozconfig '$dest' has target line '$got', expected 'ac_add_options --target=$triple'"
}

# One objdir per ABI.  The merge pass has none of its own: it runs in the
# --fat-host-abi one, which is already built.
objdir_for() {
    if [ "$1" = "fat" ]; then printf '%s/obj-%s' "$SRCDIR" "$FAT_HOST_ABI"
    else printf '%s/obj-%s' "$SRCDIR" "$1"; fi
}

# ---------------------------------------------------------------------------
# Running a pass in the container
# ---------------------------------------------------------------------------
#
# One container per pass, not one for the whole run: a fresh cgroup per pass is
# the only way to get a per-pass memory peak (/sys/fs/cgroup/memory.peak is
# read-only from inside, so it cannot be reset between passes), and it also
# guarantees no Gradle or Kotlin daemon survives from the previous ABI.
#
# The Gradle user home is deliberately on the host and shared between passes:
# it holds the downloaded Gradle distribution and the whole Maven dependency
# graph, and re-downloading that four times is minutes of network per run.  The
# image's own /root/.gradle/gradle.properties (which points Gradle at the JDK)
# is copied in on first use rather than reproduced here, so this script does not
# have to know what the image put there.

# Interrupting the script kills the engine's client, not the container it
# started: the build keeps running, unattended, holding 30GB of the machine's
# memory, and `--rm` never fires.  Every container this script starts is
# therefore named and recorded here, and the trap removes it.
#
# The engine has to be started in the background and waited for, rather than run
# in the foreground.  Bash does not run a trap while a foreground child is
# running -- it queues the signal until that child exits -- so with a foreground
# `podman run` the cleanup would happen after the 20 minute build it was meant
# to cut short, which is no cleanup at all.  `wait` is interruptible, so the
# trap fires immediately.  (Observed, not theorised: the first version of this
# script ignored SIGTERM for exactly that reason.)
CURRENT_CONTAINER=""
cleanup_container() {
    if [ -n "$CURRENT_CONTAINER" ]; then
        warn "interrupted: removing container $CURRENT_CONTAINER"
        "$ENGINE" rm -f "$CURRENT_CONTAINER" >/dev/null 2>&1 || true
        CURRENT_CONTAINER=""
    fi
    exit 130
}
trap cleanup_container INT TERM HUP

container_run() {
    # $1 = pass name (for the container name and log), $2 = mozconfig path in
    # the container, rest = the command to run in the tree
    local pass=$1 mozconfig=$2; shift 2
    local name="lw-fataar-$pass-$$-$(date -u +%s)"
    local envs=()
    local rc=0
    # Local, because the caller of this function is itself looping over $abi.
    local abi

    envs+=(-e "MOZCONFIG=$mozconfig")
    envs+=(-e "MOZ_BUILD_DATE=$BUILD_DATE")
    envs+=(-e "GRADLE_USER_HOME=/work/out/gradle-home")
    if [ "$pass" = "fat" ]; then
        # Comma separated, exactly as taskcluster/kinds/build-fat-aar/kind.yml
        # spells it.  $abi_list is space separated, hence the join.
        envs+=(-e "MOZ_ANDROID_FAT_AAR_ARCHITECTURES=$(printf '%s\n' $abi_list | paste -sd, -)")
        for abi in $abi_list; do
            envs+=(-e "MOZ_ANDROID_FAT_AAR_$(abi_to_var "$abi")=/work/out/$abi/target.maven.zip")
        done
    fi

    CURRENT_CONTAINER="$name"
    "$ENGINE" run --rm --name "$name" \
        -v "$SRCDIR:/work/src$mount_suffix" \
        -v "$OUTDIR:/work/out$mount_suffix" \
        -w /work/src \
        "${envs[@]}" \
        "$IMAGE" \
        bash -c "$*" &
    wait $!
    rc=$?
    CURRENT_CONTAINER=""
    return $rc
}

# The body every pass runs inside the container.  Kept as one string so the
# exit status that comes back out of `$ENGINE run` is mach's, not a shell's.
#
# The exit status is the authoritative signal and is checked by the caller;
# nothing here decides success by grepping a log (see landmine L5 in
# docs/android/AGENTS.md).
#
# The merge pass runs `./mach configure` first, and that is not belt and braces.
# mach only re-runs configure when a *file* is newer than config.status --
# `MozbuildObject.build_out_of_date(config.status, config_status_deps.in)`
# (python/mozbuild/mozbuild/controller/building.py:1360-1366), over the list
# moz.configure:1001-1033 builds: the moz.configure sources, CLOBBER, configure,
# version.txt, and .mozconfig.json (which records only topsrcdir, topobjdir and
# the mozconfig *path*).  The merge pass changes none of those: it changes the
# environment.  So without an explicit configure, config.status keeps the
# per-ABI substs while `make` -- which reads MOZ_ANDROID_FAT_AAR_ARCHITECTURES
# straight out of the environment (config/baseconfig.mk:54) -- happily runs the
# merge tier.  The two halves then disagree: fat_aar.py fills
# dist/fat-aar/output/jni with all three ABIs, and Gradle, reading the stale
# substs (mobile/android/geckoview/build.gradle:131-135), packages
# dist/geckoview/lib instead and produces a *single-ABI* AAR that looks
# perfectly healthy.  The jni check at the end of this script catches it, but
# only after the whole pass has run.
pass_body() {
    # $1 = pass name, $2 = "reconfigure" to force ./mach configure first
    cat <<EOF
set -u
mkdir -p "\$GRADLE_USER_HOME" || exit 90
cp -n /root/.gradle/gradle.properties "\$GRADLE_USER_HOME"/ 2>/dev/null || true
date -u +'PASS $1 START %Y-%m-%dT%H:%M:%SZ'
EOF
    if [ "${2:-}" = "reconfigure" ]; then
        cat <<EOF
./mach configure
rc=\$?
echo "MACH_CONFIGURE_EXIT=\$rc"
[ \$rc -eq 0 ] || exit \$rc
EOF
    fi
    cat <<EOF
./mach build -j$JOBS
rc=\$?
date -u +'PASS $1 END %Y-%m-%dT%H:%M:%SZ'
echo "MACH_EXIT=\$rc"
cat /sys/fs/cgroup/memory.peak > /work/out/logs/$1.mempeak 2>/dev/null || true
exit \$rc
EOF
}

# ---------------------------------------------------------------------------
# Artifact checks.  Every one of these reads the produced file; none of them
# trusts a log line.
# ---------------------------------------------------------------------------

# Lists the ABI directories under jni/ in an AAR that contain libxul.so.
aar_jni_abis() {
    python3 - "$1" <<'PY'
import sys, zipfile, posixpath
with zipfile.ZipFile(sys.argv[1]) as z:
    abis = sorted({
        n.split("/")[1]
        for n in z.namelist()
        if n.startswith("jni/") and posixpath.basename(n) == "libxul.so"
    })
print("\n".join(abis))
PY
}

# The single geckoview AAR inside a maven zip, i.e. exactly what
# fat_aar.py:80-89 goes looking for.
maven_zip_aar() {
    python3 - "$1" <<'PY'
import sys, zipfile, fnmatch
with zipfile.ZipFile(sys.argv[1]) as z:
    aars = [n for n in z.namelist() if fnmatch.fnmatch(n, "*geckoview-*.aar")]
print("\n".join(sorted(aars)))
PY
}

# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

start_all=$(date +%s)
summary_file="$OUTDIR/build-times.txt"

# The maven packer.
#
# The zip a per-ABI build hands to the merge is not an arbitrary zip: fat_aar.py
# pattern-matches paths inside it, so its layout has to be the one mach produces
# in automation.  mach builds it in create_maven_archive()
# (mobile/android/mach_commands.py:149-175) but only calls it under
# MOZ_AUTOMATION (:200), and we do not set MOZ_AUTOMATION -- it also switches on
# the upload and symbol steps, which want credentials we neither have nor want
# in this loop.
#
# So this runs the tree's function without going through mach: it parses
# mobile/android/mach_commands.py, lifts the two module-level functions out of
# the AST and executes those.  Importing the module is not an option -- its
# @SubCommand decorators register mach commands at import time and blow up with
# "Cannot register a command to an undefined category: android -> devenv"
# outside a mach process (verified, not assumed).  Copying the function body
# into this script would work today and silently rot at the next rebase; lifting
# it fails loudly instead, either because the function is gone or because it
# grew a dependency the sandbox below does not provide.
cat > "$OUTDIR/pack-maven.py" <<'PY'
import ast
import os
import sys
import zipfile

topsrcdir, objdir = sys.argv[1], sys.argv[2]

maven = os.path.join(objdir, "gradle", "maven")
if not os.path.isdir(maven):
    raise SystemExit("no maven repository at %s" % maven)

src_path = os.path.join(topsrcdir, "mobile", "android", "mach_commands.py")
with open(src_path, encoding="utf-8") as fh:
    module = ast.parse(fh.read(), filename=src_path)

wanted = ["get_maven_archive_paths", "create_maven_archive"]
picked = [n for n in module.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
missing = set(wanted) - {n.name for n in picked}
if missing:
    raise SystemExit(
        "%s no longer defines %s at module level; the maven zip layout has moved"
        % (src_path, ", ".join(sorted(missing)))
    )

ns = {"os": os, "zipfile": zipfile}
exec(compile(ast.Module(body=picked, type_ignores=[]), src_path, "exec"), ns)
ns["create_maven_archive"](objdir)

out = os.path.join(objdir, "gradle", "target.maven.zip")
if not os.path.exists(out):
    raise SystemExit("create_maven_archive() did not produce %s" % out)
print("wrote %s (%d bytes)" % (out, os.path.getsize(out)))
PY

if [ "$DRY_RUN" = "1" ]; then
    log "dry run: preflight passed, nothing will be built."
    for abi in $abi_list; do
        log "  would build $abi ($(abi_to_target "$abi")) in $(objdir_for "$abi")"
    done
    log "  would then merge in $(objdir_for fat) (the $FAT_HOST_ABI objdir, incremental)"
    log "  would write $OUTDIR/geckoview-*.aar"
    exit 0
fi

{
    printf 'LibreWolf Android fat AAR -- %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'tree=%s\nabis=%s\njobs=%s\nMOZ_BUILD_DATE=%s\nengine=%s image=%s\n\n' \
        "$SRCDIR" "$ABIS" "$JOBS" "$BUILD_DATE" "$ENGINE" "$IMAGE"
    printf '%-14s %10s %12s  %s\n' pass seconds peak_mem_GB status
} > "$summary_file"

record() {
    # pass, seconds, status
    local peak="" peakgb="n/a"
    peak=$(cat "$OUTDIR/logs/$1.mempeak" 2>/dev/null || true)
    if printf '%s' "$peak" | grep -Eq '^[0-9]+$'; then
        peakgb=$(awk -v b="$peak" 'BEGIN { printf "%.2f", b/1000000000 }')
    fi
    printf '%-14s %10s %12s  %s\n' "$1" "$2" "$peakgb" "$3" >> "$summary_file"
}

# ---------------------------------------------------------------------------
# Pass 1..N: one full build per ABI
# ---------------------------------------------------------------------------

for abi in $abi_list; do
    zip_out="$OUTDIR/$abi/target.maven.zip"

    if [ "$SKIP_EXISTING" = "1" ] && [ -f "$zip_out" ]; then
        log "$abi: --skip-existing and $zip_out is present, reusing it"
        record "$abi" 0 "reused"
        continue
    fi

    mkdir -p "$OUTDIR/$abi" || die "cannot create '$OUTDIR/$abi'"
    write_mozconfig "$abi" "$OUTDIR/mozconfig.$abi"

    log "$abi: building (-j$JOBS), log: $OUTDIR/logs/$abi.log"
    # A stale peak from an earlier run would be reported as this run's.
    rm -f "$OUTDIR/logs/$abi.mempeak"
    t0=$(date +%s)
    container_run "$abi" "/work/out/mozconfig.$abi" "$(pass_body "$abi")" \
        > "$OUTDIR/logs/$abi.log" 2>&1
    rc=$?
    t1=$(date +%s)
    if [ "$rc" != "0" ]; then
        record "$abi" $((t1 - t0)) "FAILED rc=$rc"
        die "$abi: mach build failed (exit $rc) after $((t1 - t0))s.
       Log: $OUTDIR/logs/$abi.log"
    fi
    log "$abi: build ok in $((t1 - t0))s"

    objdir=$(objdir_for "$abi")
    [ -d "$objdir/gradle/maven" ] ||
        die "$abi: '$objdir/gradle/maven' does not exist after a successful build.
       The android-archive-geckoview tier should have published there
       (mobile/android/gradle.configure, GRADLE_ANDROID_ARCHIVE_GECKOVIEW_TASKS)."

    # Pack the maven repository the way the tree does it.  We call the tree's
    # own create_maven_archive() rather than reimplementing the layout, because
    # fat_aar.py:80-89 pattern-matches on paths inside this zip.  mach normally
    # calls it only under MOZ_AUTOMATION (mobile/android/mach_commands.py:200),
    # which we do not set: MOZ_AUTOMATION also switches on upload and symbol
    # steps we neither want nor have credentials for.
    log "$abi: packing target.maven.zip"
    python3 "$OUTDIR/pack-maven.py" "$SRCDIR" "$objdir" > "$OUTDIR/logs/$abi.maven.log" 2>&1
    rc=$?
    [ "$rc" = "0" ] ||
        die "$abi: packing the maven zip failed (exit $rc). Log: $OUTDIR/logs/$abi.maven.log"

    [ -f "$objdir/gradle/target.maven.zip" ] ||
        die "$abi: create_maven_archive() reported success but '$objdir/gradle/target.maven.zip'
       does not exist"
    cp "$objdir/gradle/target.maven.zip" "$zip_out" ||
        die "$abi: cannot copy the maven zip to '$zip_out'"

    # The merge consumes exactly one AAR per input zip.
    aars=$(maven_zip_aar "$zip_out")
    n_aars=$(printf '%s\n' "$aars" | grep -c . || true)
    if [ "$n_aars" != "1" ]; then
        if [ "$n_aars" = "0" ]; then
            die "$abi: '$zip_out' contains no geckoview-*.aar.  The usual cause is a build
       without MOZILLA_OFFICIAL: build.gradle:228-231 then versions the artifact
       -SNAPSHOT and mach_commands.py:150-155 skips every -SNAPSHOT path."
        fi
        die "$abi: '$zip_out' contains $n_aars geckoview AARs, fat_aar.py:86-89 requires
       exactly one:
$aars"
    fi

    # And that AAR must carry this ABI's native code, not somebody else's.  This
    # is the check that catches a --target rewrite that silently did not happen.
    tmp_aar="$OUTDIR/$abi/.check.aar"
    python3 - "$zip_out" "$aars" "$tmp_aar" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z, open(sys.argv[3], "wb") as out:
    out.write(z.read(sys.argv[2]))
PY
    [ -f "$tmp_aar" ] || die "$abi: cannot extract '$aars' from '$zip_out'"
    got_abis=$(aar_jni_abis "$tmp_aar" | tr '\n' ' ')
    rm -f "$tmp_aar"
    [ "$(printf '%s' "$got_abis" | tr -d ' ')" = "$abi" ] ||
        die "$abi: its AAR carries jni ABIs '$got_abis', expected exactly '$abi'.
       The generated mozconfig's --target did not take effect."

    log "$abi: target.maven.zip ok ($(du -h "$zip_out" | cut -f1)), jni: $got_abis"
    record "$abi" $((t1 - t0)) "ok"
done

# ---------------------------------------------------------------------------
# Pass N+1: the merge
# ---------------------------------------------------------------------------

for abi in $abi_list; do
    [ -f "$OUTDIR/$abi/target.maven.zip" ] ||
        die "merge: '$OUTDIR/$abi/target.maven.zip' is missing"
done

# The merge reuses the host ABI's mozconfig unchanged -- same file, same
# --target, same objdir -- so that nothing about the merge pass can differ from
# the build that produced its own half of the AAR.  It is only regenerated when
# it is missing, which happens when --skip-existing skipped that ABI.
[ -f "$OUTDIR/mozconfig.$FAT_HOST_ABI" ] ||
    write_mozconfig "$FAT_HOST_ABI" "$OUTDIR/mozconfig.$FAT_HOST_ABI"

fat_objdir=$(objdir_for fat)
[ -d "$fat_objdir" ] ||
    die "merge: '$fat_objdir' does not exist; the merge runs in the $FAT_HOST_ABI objdir
       and that ABI has to have been built (or --skip-existing reused a maven zip
       whose objdir is gone -- rebuild that ABI)"

# The merge publishes a *differently named* artifact into the same maven
# repository: with MOZ_ANDROID_FAT_AAR_ARCHITECTURES set,
# mobile/android/geckoview/build.gradle:389-392 stops appending the ABI to the
# artifact id, so `geckoview-default-omni-armeabi-v7a` becomes
# `geckoview-default-omni`.  Both would then sit in gradle/maven and "the AAR
# this run produced" would be ambiguous.  Whatever is there has already been
# packed into a target.maven.zip (or is a previous merge's output), so move it
# aside rather than delete it and let gradle recreate the directory.
if [ -d "$fat_objdir/gradle/maven" ]; then
    rm -rf "$fat_objdir/gradle/maven.previous"
    mv "$fat_objdir/gradle/maven" "$fat_objdir/gradle/maven.previous" ||
        die "merge: cannot move '$fat_objdir/gradle/maven' aside"
fi

log "merge: building in the $FAT_HOST_ABI objdir (incremental), log: $OUTDIR/logs/fat.log"
rm -f "$OUTDIR/logs/fat.mempeak"
t0=$(date +%s)
container_run "fat" "/work/out/mozconfig.$FAT_HOST_ABI" "$(pass_body fat reconfigure)" \
    > "$OUTDIR/logs/fat.log" 2>&1
rc=$?
t1=$(date +%s)
if [ "$rc" != "0" ]; then
    record "fat" $((t1 - t0)) "FAILED rc=$rc"
    die "merge: mach build failed (exit $rc) after $((t1 - t0))s. Log: $OUTDIR/logs/fat.log"
fi
record "fat" $((t1 - t0)) "ok"
log "merge: build ok in $((t1 - t0))s"

# fat_aar.py returns 1 when an input file differs across ABIs outside its
# allow-list, and the tier fails the build -- so a zero exit above already means
# the compatibility check passed.  Say so explicitly in the log, from the log of
# the tier that ran it, so the summary is not silent about the one check that
# makes a fat AAR legitimate rather than merely large.
if grep -q '^Disallowed: ' "$OUTDIR/logs/fat.log"; then
    die "merge: fat_aar.py reported disallowed cross-ABI differences yet the build exited 0.
       Read $OUTDIR/logs/fat.log"
fi

# ---------------------------------------------------------------------------
# Collect and verify
# ---------------------------------------------------------------------------

# The shippable artifact is the published maven one (that is what a consumer
# resolves); gradle also leaves an unpublished copy under outputs/aar.
fat_aar_path=$(find "$fat_objdir/gradle/maven" -name 'geckoview-*.aar' 2>/dev/null | sort)
n_fat=$(printf '%s\n' "$fat_aar_path" | grep -c . || true)
[ "$n_fat" = "1" ] ||
    die "merge: expected exactly one geckoview-*.aar under '$fat_objdir/gradle/maven', found $n_fat:
$fat_aar_path"

cp "$fat_aar_path" "$OUTDIR/" || die "cannot copy '$fat_aar_path' to '$OUTDIR'"
fat_aar_out="$OUTDIR/$(basename "$fat_aar_path")"

# Keep the whole maven repository too: the .pom/.module next to the AAR are what
# make it consumable by Gradle, and LW-M2-04 needs them.
rm -rf "$OUTDIR/maven"
cp -a "$fat_objdir/gradle/maven" "$OUTDIR/maven" ||
    die "cannot copy '$fat_objdir/gradle/maven' to '$OUTDIR/maven'"

# The acceptance check, done against the produced file: one jni/<abi>/libxul.so
# per requested ABI, and no ABI we did not ask for.
got=$(aar_jni_abis "$fat_aar_out" | tr '\n' ' ' | sed 's/ *$//')
want=$(printf '%s\n' $abi_list | sort | tr '\n' ' ' | sed 's/ *$//')
[ "$got" = "$want" ] ||
    die "merged AAR '$fat_aar_out' carries jni ABIs [$got], expected [$want]"

n_libxul=$(unzip -l "$fat_aar_out" | grep -c 'jni/.*/libxul.so' || true)
[ "$n_libxul" = "$abi_count" ] ||
    die "merged AAR has $n_libxul jni/*/libxul.so entries, expected $abi_count"

# A merge pass that packaged nothing would still satisfy the jni check, because
# the jni tree is copied in from the per-ABI inputs.  omni.ja and classes.jar are
# produced by this pass, so they are what proves it did its own half of the job.
#
# And inside omni.ja, one pref set per ABI.  This is the packaging half of the
# fat build and it is worth checking separately from the jni half, because the
# two are driven from different places: fat_aar.py:66-96 lifts each input's
# greprefs.js and geckoview-prefs.js out of its AAR, and modules/libpref/moz.build:173-181,
# mobile/android/app/moz.build:17-29 and
# mobile/android/installer/package-manifest.in:127-133 package every ABI's copy
# only when configure knows about MOZ_ANDROID_FAT_AAR_ARCHITECTURES.  A merge
# that ran the tier but was configured per-ABI produces exactly one pref set --
# see the pass_body comment about mach not noticing environment-only changes.
#
# Done in one python pass, with no `unzip -l | grep -q`.  That pipeline is a
# coin flip under `set -o pipefail`: grep -q exits at the first match, unzip
# takes SIGPIPE, and the pipeline reports 141 -- a *false* failure, and this is
# measured, not theorised (16 runs in 20 on the finished 250MB AAR).  A checker
# that fails when the artifact is fine is the mirror image of landmine L5 and
# costs just as much trust.
log "verifying the merge pass's own half of the AAR"
python3 - "$fat_aar_out" $abi_list <<'PY' || die "merged AAR '$fat_aar_out' failed the packaging checks (see above)"
import io
import sys
import zipfile

aar_path = sys.argv[1]
abis = sys.argv[2:]
problems = []

with zipfile.ZipFile(aar_path) as aar:
    names = set(aar.namelist())
    for member in ("assets/omni.ja", "classes.jar", "AndroidManifest.xml"):
        if member not in names:
            problems.append("missing %s" % member)
    omni = aar.read("assets/omni.ja") if "assets/omni.ja" in names else None

if omni is not None:
    with zipfile.ZipFile(io.BytesIO(omni)) as z:
        onames = set(z.namelist())
    for abi in abis:
        for wanted in ("%s/greprefs.js" % abi, "defaults/pref/%s/geckoview-prefs.js" % abi):
            if wanted not in onames:
                problems.append("omni.ja is missing %s" % wanted)
    unexpected = sorted(
        n for n in onames
        if (n.endswith("/greprefs.js") or n.endswith("/geckoview-prefs.js"))
        and n.split("/")[-2] not in abis
    )
    if unexpected:
        problems.append("omni.ja carries pref sets for unrequested ABIs: %s" % unexpected)

if problems:
    sys.exit("\n".join("  " + p for p in problems))
print("  omni.ja, classes.jar, AndroidManifest.xml present; per-ABI prefs for %s" % ", ".join(abis))
PY

# Every native library in the merged AAR must be byte-identical to the one the
# corresponding per-ABI build produced.  fat_aar.py:91-93 copies jni/** straight
# through, so this holds by construction -- which is exactly why it is worth
# asserting: it is the artifact-level proof that what ships is the output of the
# three hardened per-ABI builds and not something the merge pass produced on its
# own.  It is also what would catch a stale maven zip left over from an earlier,
# differently configured run.
log "verifying native libraries against the per-ABI builds"
for abi in $abi_list; do
    python3 - "$fat_aar_out" "$OUTDIR/$abi/target.maven.zip" "$abi" <<'PY' || die "$abi: the merged AAR's native libraries are not the per-ABI build's (see above)"
import fnmatch
import hashlib
import io
import sys
import zipfile

fat_path, maven_path, abi = sys.argv[1:4]


def digests(zf, prefix):
    out = {}
    for name in zf.namelist():
        if name.startswith(prefix) and not name.endswith("/"):
            out[name] = hashlib.sha256(zf.read(name)).hexdigest()
    return out


with zipfile.ZipFile(fat_path) as fat:
    fat_libs = digests(fat, "jni/%s/" % abi)

with zipfile.ZipFile(maven_path) as mz:
    aars = [n for n in mz.namelist() if fnmatch.fnmatch(n, "*geckoview-*.aar")]
    if len(aars) != 1:
        sys.exit("%s: expected one geckoview AAR in %s, found %d" % (abi, maven_path, len(aars)))
    with zipfile.ZipFile(io.BytesIO(mz.read(aars[0]))) as per_abi:
        abi_libs = digests(per_abi, "jni/%s/" % abi)

if not abi_libs:
    sys.exit("%s: the per-ABI AAR has no jni/%s/ entries at all" % (abi, abi))
if fat_libs != abi_libs:
    only_fat = sorted(set(fat_libs) - set(abi_libs))
    only_abi = sorted(set(abi_libs) - set(fat_libs))
    differ = sorted(n for n in set(fat_libs) & set(abi_libs) if fat_libs[n] != abi_libs[n])
    sys.exit(
        "%s: merged AAR native libraries differ from the per-ABI build\n"
        "  only in merged  : %s\n"
        "  only in per-ABI : %s\n"
        "  content differs : %s" % (abi, only_fat, only_abi, differ)
    )
print("  %s: %d native libraries, all sha256-identical to the per-ABI build" % (abi, len(fat_libs)))
PY
done

end_all=$(date +%s)
{
    printf '\n%-14s %10s\n' total $((end_all - start_all))
    printf '\nmerged AAR: %s\njni ABIs  : %s\n' "$fat_aar_out" "$got"
} >> "$summary_file"

log "merged AAR: $fat_aar_out ($(du -h "$fat_aar_out" | cut -f1))"
log "jni ABIs in it: $got"
log "maven repository: $OUTDIR/maven"
log "total wall clock: $((end_all - start_all))s"
echo
cat "$summary_file"
