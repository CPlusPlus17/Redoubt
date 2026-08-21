#!/usr/bin/env bash
#
# android-apk.sh -- build an installable LibreWolf-for-Android APK by feeding
# the fat GeckoView AAR into the in-tree mobile/android/fenix Gradle build.
#
# Owner: LW-M2-04.  Driven by `make android-apk`; usable standalone.
#
# ---------------------------------------------------------------------------
# What this does, and why it is two passes and not one
# ---------------------------------------------------------------------------
#
# The APK is produced by the *tree's own* Gradle build, driven through mach,
# exactly the way upstream's "Build Android Fenix Debug From Root" job does it
# (`taskcluster/kinds/build/fenix.yml` -> mozharness
# `testing/mozharness/configs/builds/releng_sub_android_configs/64_aarch64_fenix_debug.py`,
# whose whole content is a mozconfig variant plus one postflight command,
# `["gradle", "fenix:assembleDebug"]`).  So:
#
#   pass 1  "gecko"   ./mach configure && ./mach build   in one objdir, with
#                     --enable-android-subproject=fenix in the mozconfig and
#                     the three per-ABI target.maven.zip files from
#                     `make android-aar` in the environment.  This compiles
#                     Gecko for the host ABI, runs the fat-AAR merge tier, and
#                     publishes a *fat* GeckoView AAR into <objdir>/gradle/maven.
#
#   pass 2  "apk"     ./mach gradle fenix:assembleDebug   in the same objdir
#                     with the same mozconfig.  Fenix depends on
#                     :android-components:browser-engine-gecko, which depends on
#                     `project(':geckoview')` (android-components/components/
#                     browser/engine-gecko/build.gradle:41), so the APK's
#                     GeckoView is the one pass 1 just built -- not a prebuilt.
#
# `mach build` alone does NOT build the APK.  `mach android archive-geckoview`
# (the android-archive-geckoview tier, Makefile.in:83-84) adds the *subproject*
# task list only when MOZ_ANDROID_SUBPROJECT is unset or "geckoview_example"
# (mobile/android/mach_commands.py:186-191); with it set to "fenix" it stops at
# the AAR.  GRADLE_ANDROID_ARCHIVE_FENIX_SUBPROJECT_TASKS exists in
# mobile/android/gradle.configure:425-435 and has no consumer anywhere in the
# tree.  Hence the separate `mach gradle` pass, which is what upstream does too.
#
# ---------------------------------------------------------------------------
# Why the Gradle build must be the ROOT one (and not `cd mobile/android/fenix`)
# ---------------------------------------------------------------------------
#
# Two independent reasons, both mechanical:
#
#   - `settings.gradle:55-62` includes :fenix only when MOZ_ANDROID_SUBPROJECT
#     is unset or "fenix", and the fenix projectDir it sets is
#     mobile/android/fenix/app.  There is no standalone settings.gradle under
#     mobile/android/fenix that wires :geckoview in.
#   - app-services.  With --enable-appservices-in-tree, ProjectPlugin.kt:112
#     substitutes `project(':<mod>')` for the `org.mozilla.appservices:<mod>`
#     maven coordinates only when :geckoview is part of *this* Gradle build (or
#     DOWNLOAD_ALL_GRADLE_DEPENDENCIES is set).  A Gradle invocation rooted in
#     mobile/android/fenix has no :geckoview, so the substitution silently does
#     not happen and the APK links Mozilla's *prebuilt* app-services AARs while
#     --enable-appservices-in-tree is still set and looks honoured.  That is a
#     silent parity loss, and it is why this script never leaves topsrcdir.
#
# ---------------------------------------------------------------------------
# The fat AAR, and what "feeding it in" means concretely
# ---------------------------------------------------------------------------
#
# scripts/android-fat-aar.sh (LW-M2-03) produces, per ABI, a target.maven.zip
# containing that ABI's GeckoView AAR.  This script does not re-run those builds
# and does not re-implement the merge: it hands the same three zips to the same
# tier (`Makefile.in:70-76` -> `python/mozbuild/mozbuild/action/fat_aar.py`) via
# MOZ_ANDROID_FAT_AAR_ARCHITECTURES + MOZ_ANDROID_FAT_AAR_<ABI>, in a *fresh*
# objdir that also carries --enable-android-subproject=fenix.
#
# fat_aar.py unpacks all three, checks them against each other, and writes
# dist/fat-aar/output/jni; `mobile/android/geckoview/build.gradle:130-136` then
# points the AAR's jniLibs at that directory instead of this objdir's own
# dist/geckoview/lib.  So the APK's native libraries are the three per-ABI
# builds', and `mobile/android/fenix/app/build.gradle:230-246` splits them into
# one APK per ABI plus a universal one.
#
# Everything else in the AAR -- omni.ja, classes.jar, AndroidManifest.xml --
# comes from *this* objdir, i.e. from the --fat-host-abi pass.  Two consequences
# worth knowing before you pick --fat-host-abi:
#
#   - about:buildconfig is chrome/toolkit/content/global/buildconfig.html inside
#     omni.ja, so every ABI's APK reports the host ABI's compiler flags.
#     (fat_aar.py:120-131 explicitly allow-lists that file as ABI-varying.)
#     Its "Configure options" line, however, is the whole mozconfig, which is
#     identical across ABIs bar --target -- that is what makes about:buildconfig
#     a usable proof that the GeckoView in the APK is ours.
#   - the default here is x86_64, NOT armeabi-v7a as in android-fat-aar.sh.  An
#     x86_64 host is the only choice whose buildconfig.html describes the code
#     an emulator on an x86_64 machine actually runs, and this APK exists to be
#     verified.  Pass --fat-host-abi=arm64-v8a for a shipping-shaped artifact.
#
# MOZ_BUILD_DATE is pinned to the value the AAR run used (read out of the AAR
# directory's build-times.txt) so that the omni.ja this pass builds carries the
# same buildid as the libxul.so it is packaged next to.  Nothing in 153 refuses
# to *run* on a mismatch -- MOZ_APP_BUILDID reaches only telemetry, crash tags
# and the About screen on Android -- but "the About screen lies about which
# build this is" is not a thing to ship, and a pinned date also makes two runs
# of this script comparable.
#
# ---------------------------------------------------------------------------
# Branding and applicationId are deliberately STOCK
# ---------------------------------------------------------------------------
#
# The debug build type is org.mozilla.fenix.debug (applicationId "org.mozilla" +
# applicationIdSuffix ".fenix.debug", mobile/android/fenix/app/build.gradle:60,121);
# the release build type is org.mozilla.firefox (same applicationId + the release
# block's applicationIdSuffix ".firefox").  The branding is
# mobile/android/branding/unofficial.  LW-M4-07 changes all of it.
# Changing it here would make the first failure of the first APK ambiguous.
#
# Both build types are debug-signed in this configuration: the releaseTemplate
# closure sets signingConfig = signingConfigs.debug whenever MOZ_AUTOMATION is
# unset and disableDebugSigning is not passed, and assets/mozconfig.android sets
# neither.  So the apksigner check at the end ("CN=Android Debug") is the same
# for debug and release, and that is asserted, not assumed.
#
# --variant=release is the first thing in this project that runs R8
# (releaseTemplate: minifyEnabled = !disableOptimization).  It needs
# third_party/application-services/proguard-rules-consumer-jna.pro in the tree
# (patches/android/r8-keep-rules.patch, LW-M6-07), which the ESR tarball does
# not ship; without it the APK crashes on launch.  The preflight enforces that
# for release only.
#
# ---------------------------------------------------------------------------
# Cost (measured on the reference host: 32 core / 62 GB, podman, not idle)
# ---------------------------------------------------------------------------
#
#   pass          wall clock   peak container memory
#   gecko         see build-times.txt in --outdir
#   apk           see build-times.txt in --outdir
#
# The gecko pass is one full Gecko build (~22 min at -j16, ~31 GB peak; see
# docs/android/BUILD.md) plus the merge; the apk pass is Gradle only.  With an
# objdir already built by a previous run both are incremental -- that is what
# --skip-gecko is for.
#
set -u
set -o pipefail

progname=$(basename "$0")

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

# The ABIs a fat AAR can hold; see scripts/android-fat-aar.sh for why 32-bit x86
# is not one of them.
DEFAULT_ABIS="armeabi-v7a,arm64-v8a,x86_64"

# See the header: x86_64 so that about:buildconfig describes what an emulator
# runs.  Must be one of --abis.
DEFAULT_FAT_HOST_ABI="x86_64"

# The mozconfig option this task exists to turn on.  Checked for, never
# injected: assets/mozconfig.android is owned by another task, and a script that
# silently appends an option builds something the repository does not describe.
SUBPROJECT_OPTION="ac_add_options --enable-android-subproject=fenix"

# Same default as the Makefile's, and deliberately not auto-detected -- see the
# CONTAINER_ENGINE comment in the Makefile for why.
ENGINE=${CONTAINER_ENGINE:-docker}
IMAGE=${LW_ANDROID_IMAGE:-librewolf-android-build}

# SELinux label suffix for the bind mounts.  ":z" (shared) is correct on an
# Enforcing host where more than one container touches the path; ":Z" would
# relabel exclusively and break every other reader of the tree.
MOUNT_OPT=${LW_MOUNT_OPT:-z}

SRCDIR=""
AARDIR=""
OUTDIR=""
ABIS=""
VARIANT="debug"
FAT_HOST_ABI="$DEFAULT_FAT_HOST_ABI"
MOZCONFIG_SRC=""
JOBS=""
BUILD_DATE=""
GRADLE_HOME_SEED=""
DRY_RUN=0
SKIP_GECKO=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log()  { printf '%s [%s] %s\n' "$(date -u +%H:%M:%S)" "$progname" "$*"; }
warn() { printf '%s [%s] WARNING: %s\n' "$(date -u +%H:%M:%S)" "$progname" "$*" >&2; }
die()  { printf '%s [%s] fatal: %s\n' "$(date -u +%H:%M:%S)" "$progname" "$*" >&2; exit 1; }

usage() {
    cat <<EOF
usage: $progname --srcdir DIR --aar-dir DIR [options]

Builds a debug-signed Fenix APK (debug or release build type) whose GeckoView
is the fat AAR built by scripts/android-fat-aar.sh.

  --variant V       debug (default) or release build type.  Both are
                    debug-signed in this configuration (see the header), but
                    only release runs R8, and release refuses to build without
                    third_party/application-services/proguard-rules-consumer-
                    jna.pro in the tree (patches/android/r8-keep-rules.patch,
                    LW-M6-07) -- without it the APK crashes on launch.
  --srcdir DIR      extracted, patched source tree to build in (required).
                    It gets one objdir; give it its own copy.
  --aar-dir DIR     output directory of scripts/android-fat-aar.sh, i.e. what
                    \`make android-aar\` wrote (required).  Read only: the
                    per-ABI target.maven.zip files are copied into --outdir
                    before anything mounts them.
  --outdir DIR      APKs, logs, generated mozconfig, build-times.txt.
                    Default: <srcdir>/../librewolf-android-apk
  --abis LIST       comma separated subset of $DEFAULT_ABIS.
                    Default: whatever --aar-dir contains.
  --fat-host-abi A  ABI whose objdir hosts both passes (default: $DEFAULT_FAT_HOST_ABI).
                    Must be in --abis.  Supplies omni.ja, classes.jar and the
                    about:buildconfig page for every ABI -- see the header.
  --mozconfig FILE  base mozconfig (default: assets/mozconfig.android next to
                    this script).  Must contain
                      $SUBPROJECT_OPTION
                    Only its --target line is rewritten.
  --jobs N          -j for mach.  Default: min(16, nproc).
  --build-date S    MOZ_BUILD_DATE, 14 digits.  Default: the MOZ_BUILD_DATE
                    recorded in <aar-dir>/build-times.txt.
  --gradle-home DIR seed \$GRADLE_USER_HOME from this directory (e.g. the
                    gradle-home an AAR run left behind) instead of downloading
                    the Maven graph again.  Copied, never written through.
  --engine E        container engine (default: \$CONTAINER_ENGINE or docker)
  --image NAME      container image (default: $IMAGE)
  --mount-opt O     bind mount suffix, "z" on SELinux (default: $MOUNT_OPT; "" to disable)
  --skip-gecko      skip pass 1 and go straight to Gradle.  Only valid when the
                    objdir already exists and was built by a previous run.
  -n, --dry-run     run every preflight check, print the plan, build nothing.
  -h, --help        this text.

Exit status is 0 only if an APK exists for every requested ABI, each carries
that ABI's libxul.so and no other ABI's, and each is debug-signed.
EOF
}

# armeabi-v7a -> arm-linux-androideabi, and so on: the target triples upstream
# uses in mobile/android/config/mozconfigs/android-*/nightly.
abi_to_target() {
    case "$1" in
        armeabi-v7a) echo "arm-linux-androideabi" ;;
        arm64-v8a)   echo "aarch64-linux-android" ;;
        x86_64)      echo "x86_64-linux-android" ;;
        *)           return 1 ;;
    esac
}

# armeabi-v7a -> ARMEABI_V7A: the spelling Makefile.in:71-75 expects for the
# MOZ_ANDROID_FAT_AAR_<ABI> variables.
abi_to_var() {
    printf '%s' "$1" | tr 'a-z-' 'A-Z_'
}

# ELF e_machine for each ABI, so an APK's native library can be checked against
# the ABI directory it was found in without trusting the directory name.
abi_to_elf_machine() {
    case "$1" in
        armeabi-v7a) echo 40 ;;   # EM_ARM
        arm64-v8a)   echo 183 ;;  # EM_AARCH64
        x86_64)      echo 62 ;;   # EM_X86_64
        *)           return 1 ;;
    esac
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

# `shift 2` on a lone trailing flag is a no-op that returns non-zero, which
# without this guard turns the loop below into an infinite one.
need_val() { [ "$1" -ge 2 ] || die "$2 needs a value"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --srcdir|--aar-dir|--outdir|--variant|--abis|--fat-host-abi|--mozconfig|--jobs|-j|--build-date|--gradle-home|--engine|--image|--mount-opt)
            need_val "$#" "$1" ;;
    esac
    case "$1" in
        --srcdir)         SRCDIR=${2:-}; shift 2 ;;
        --srcdir=*)       SRCDIR=${1#*=}; shift ;;
        --aar-dir)        AARDIR=${2:-}; shift 2 ;;
        --aar-dir=*)      AARDIR=${1#*=}; shift ;;
        --outdir)         OUTDIR=${2:-}; shift 2 ;;
        --outdir=*)       OUTDIR=${1#*=}; shift ;;
        --variant)        VARIANT=${2:-}; shift 2 ;;
        --variant=*)      VARIANT=${1#*=}; shift ;;
        --abis)           ABIS=${2:-}; shift 2 ;;
        --abis=*)         ABIS=${1#*=}; shift ;;
        --fat-host-abi)   FAT_HOST_ABI=${2:-}; shift 2 ;;
        --fat-host-abi=*) FAT_HOST_ABI=${1#*=}; shift ;;
        --mozconfig)      MOZCONFIG_SRC=${2:-}; shift 2 ;;
        --mozconfig=*)    MOZCONFIG_SRC=${1#*=}; shift ;;
        --jobs|-j)        JOBS=${2:-}; shift 2 ;;
        --jobs=*)         JOBS=${1#*=}; shift ;;
        --build-date)     BUILD_DATE=${2:-}; shift 2 ;;
        --build-date=*)   BUILD_DATE=${1#*=}; shift ;;
        --gradle-home)    GRADLE_HOME_SEED=${2:-}; shift 2 ;;
        --gradle-home=*)  GRADLE_HOME_SEED=${1#*=}; shift ;;
        --engine)         ENGINE=${2:-}; shift 2 ;;
        --engine=*)       ENGINE=${1#*=}; shift ;;
        --image)          IMAGE=${2:-}; shift 2 ;;
        --image=*)        IMAGE=${1#*=}; shift ;;
        --mount-opt)      MOUNT_OPT=${2:-}; shift 2 ;;
        --mount-opt=*)    MOUNT_OPT=${1#*=}; shift ;;
        --skip-gecko)     SKIP_GECKO=1; shift ;;
        -n|--dry-run)     DRY_RUN=1; shift ;;
        -h|--help)        usage; exit 0 ;;
        *)                usage >&2; die "unknown argument: $1" ;;
    esac
done

# ---------------------------------------------------------------------------
# Preflight.  Everything knowable before a 25 minute build is checked here.
# ---------------------------------------------------------------------------

repo_root=$(cd "$(dirname "$0")/.." && pwd) || die "cannot resolve the repository root"

# The Gradle build types mobile/android/fenix/app/build.gradle defines are
# debug, nightly, beta, release and benchmark; this script knows the output
# directory and applicationId of exactly two of them, so those are the only
# ones it will accept.
case "$VARIANT" in
    debug)   VARIANT_CAP="Debug" ;;
    release) VARIANT_CAP="Release" ;;
    *)       die "--variant must be 'debug' or 'release' (got '$VARIANT')" ;;
esac

[ -n "$SRCDIR" ] || { usage >&2; die "--srcdir is required"; }
[ -d "$SRCDIR" ] || die "--srcdir '$SRCDIR' is not a directory"
SRCDIR=$(cd "$SRCDIR" && pwd)

[ -x "$SRCDIR/mach" ] || die "'$SRCDIR' has no executable mach -- is that an extracted Firefox tree?"
[ -f "$SRCDIR/mobile/android/fenix/app/build.gradle" ] ||
    die "'$SRCDIR' has no mobile/android/fenix/app/build.gradle -- this tree has no in-tree Fenix"
[ -f "$SRCDIR/python/mozbuild/mozbuild/action/fat_aar.py" ] ||
    die "'$SRCDIR' has no python/mozbuild/mozbuild/action/fat_aar.py -- this tree has no fat-AAR support"
# settings.gradle is what turns MOZ_ANDROID_SUBPROJECT into a :fenix project.
# If upstream ever moves that, the build would succeed and produce no APK.
grep -q "include ':fenix'" "$SRCDIR/settings.gradle" ||
    die "'$SRCDIR/settings.gradle' does not include ':fenix'; the subproject wiring this
       script depends on (settings.gradle:55-62) has moved"

# Release is the first build type that runs R8 (releaseTemplate:
# minifyEnabled = !disableOptimization), and R8 needs the app-services AAR's
# consumer ProGuard rules: third_party/application-services/
# proguard-rules-consumer-jna.pro, declared by build-scripts/
# component-common.gradle but ABSENT from the ESR tarball.  Without it R8
# strips @Structure.FieldOrder from the uniffi RustBuffer classes,
# Structure.getFieldOrder() returns an empty name list, and the APK dies on
# launch (LW-M6-07; the LW-M4-09 crash, reproduced in
# ~/lw-m4-09/evidence/release-r8-crash.logcat).  Debug is immune because it
# never minifies, which is exactly how the crash stayed invisible until now.
# patches/android/r8-keep-rules.patch (LW-M6-07) restores the file; check the
# tree, not the patch list, because that is what the build reads.
if [ "$VARIANT" = "release" ]; then
    [ -f "$SRCDIR/third_party/application-services/proguard-rules-consumer-jna.pro" ] ||
        die "release: '$SRCDIR/third_party/application-services/proguard-rules-consumer-jna.pro' is missing.
       component-common.gradle declares it as the AAR's consumerProguardFiles, but the
       ESR tarball does not ship it, so R8 would strip @Structure.FieldOrder from the
       uniffi RustBuffer classes and the APK would crash on launch (LW-M6-07).
       Apply patches/android/r8-keep-rules.patch to the tree and re-run."
fi

[ -n "$AARDIR" ] || { usage >&2; die "--aar-dir is required"; }
[ -d "$AARDIR" ] || die "--aar-dir '$AARDIR' is not a directory"
AARDIR=$(cd "$AARDIR" && pwd)

if [ -z "$MOZCONFIG_SRC" ]; then
    MOZCONFIG_SRC="$repo_root/assets/mozconfig.android"
fi
[ -f "$MOZCONFIG_SRC" ] || die "base mozconfig '$MOZCONFIG_SRC' does not exist"
MOZCONFIG_SRC=$(cd "$(dirname "$MOZCONFIG_SRC")" && pwd)/$(basename "$MOZCONFIG_SRC")

# The per-pass mozconfig is the base file with its --target line rewritten.  That
# is only safe if there is exactly one such line: zero means we would build
# whatever the host is, two means the last one wins and we would silently
# rewrite the wrong one.
target_lines=$(grep -c '^[[:space:]]*ac_add_options[[:space:]]*--target=' "$MOZCONFIG_SRC" || true)
[ "$target_lines" = "1" ] ||
    die "'$MOZCONFIG_SRC' has $target_lines 'ac_add_options --target=' lines, expected exactly 1"

# MOZILLA_OFFICIAL: without it build.gradle:228-231 versions the AAR -SNAPSHOT,
# and fenix/app/build.gradle:242-245 also drops the universal APK.
grep -Eq '^[[:space:]]*export[[:space:]]+MOZILLA_OFFICIAL=1' "$MOZCONFIG_SRC" ||
    die "'$MOZCONFIG_SRC' does not export MOZILLA_OFFICIAL=1"

# The one option this task turns on.  Not injected on the fly: see the comment
# on SUBPROJECT_OPTION above.
grep -Eq '^[[:space:]]*ac_add_options[[:space:]]*--enable-android-subproject=fenix[[:space:]]*$' \
        "$MOZCONFIG_SRC" ||
    die "'$MOZCONFIG_SRC' does not enable the Fenix subproject.  Add exactly this line:

         $SUBPROJECT_OPTION

       Without it settings.gradle:55-62 leaves :fenix out of the Gradle build and
       there is no fenix:assemble$VARIANT_CAP task to run.  assets/mozconfig.android is
       owned by LW-M5-03 this batch; until that line lands there, point
       --mozconfig at your own copy (make android-apk ANDROID_MOZCONFIG=...)."

# Known API skew between the vendored app-services and this tree's
# android-components, checked here because the alternative is finding out ~10
# minutes into Gradle.
#
# `--enable-appservices-in-tree` (assets/mozconfig.android) makes
# ProjectPlugin.kt substitute project(':logins') for
# org.mozilla.appservices:logins:153.0, so android-components compiles against
# `third_party/application-services`, which moz.yaml:20-36 describes as the
# vendoring "as used by Desktop builds" and pins to a git revision months older
# than the maven artifact.  In 153.0esr that snapshot's hand-written wrapper
# `components/logins/android/.../DatabaseLoginsStorage.kt` has no addMany(),
# while `mobile/android/android-components/.../SyncableLoginsStorage.kt:211-214`
# calls it -- so :components:service-sync-logins:compileDebugKotlin fails with
# "Unresolved reference 'addMany'".  The uniffi-generated LoginStore *does* have
# it (logins.udl:182); only the wrapper is behind.
#
# This is the one skew a full `--continue` run found (3079 tasks, one failing),
# and it is a tree problem, not a problem with this script: fixing it means
# either bumping third_party/application-services or carrying a patch that adds
# the method.  The check is deliberately narrow and named, so that when the
# tree is fixed it simply stops firing.
if grep -Eq '^[[:space:]]*ac_add_options[[:space:]]*--enable-appservices-in-tree' "$MOZCONFIG_SRC"; then
    wrapper="$SRCDIR/third_party/application-services/components/logins/android/src/main/java/mozilla/appservices/logins/DatabaseLoginsStorage.kt"
    if [ -f "$wrapper" ] && ! grep -q 'fun addMany' "$wrapper"; then
        die "the vendored app-services in '$SRCDIR' is behind this tree's android-components:
       $wrapper
       has no addMany(), but
       mobile/android/android-components/.../SyncableLoginsStorage.kt:211-214 calls it.
       With --enable-appservices-in-tree that file *is* the compile target, so
       :components:service-sync-logins:compileDebugKotlin will fail with
       \"Unresolved reference 'addMany'\" after ~10 minutes of Gradle.
       Fix the tree (bump third_party/application-services, or patch the wrapper);
       do not work around it by dropping --enable-appservices-in-tree, which would
       silently link Mozilla's prebuilt app-services AARs instead."
    fi
fi

# ABI list.  Default: whatever the AAR run produced, so the two stay in step
# without the caller having to repeat themselves.
if [ -z "$ABIS" ]; then
    for abi in $(printf '%s' "$DEFAULT_ABIS" | tr ',' ' '); do
        [ -f "$AARDIR/$abi/target.maven.zip" ] && ABIS="${ABIS:+$ABIS,}$abi"
    done
    [ -n "$ABIS" ] ||
        die "'$AARDIR' contains no <abi>/target.maven.zip for any of $DEFAULT_ABIS.
       Is that really the output directory of \`make android-aar\`?"
fi

abi_list=$(printf '%s' "$ABIS" | tr ',' ' ')
[ -n "$(printf '%s' "$abi_list" | tr -d '[:space:]')" ] || die "--abis is empty"
for abi in $abi_list; do
    abi_to_target "$abi" >/dev/null 2>&1 || {
        if [ "$abi" = "x86" ] || [ "$abi" = "i686" ]; then
            die "32-bit x86 cannot go in a fat AAR: mobile/android/moz.configure:161-166 and
       fat_aar.py:174 both allow only $DEFAULT_ABIS."
        fi
        die "unknown ABI '$abi'; valid: $DEFAULT_ABIS"
    }
    [ -f "$AARDIR/$abi/target.maven.zip" ] ||
        die "--aar-dir '$AARDIR' has no $abi/target.maven.zip.  Build it first:
       make android-aar TARGETS=android"
done
dupes=$(printf '%s\n' $abi_list | sort | uniq -d)
[ -z "$dupes" ] || die "--abis lists $(printf '%s' "$dupes" | tr '\n' ' ' | sed 's/ *$//') more than once"

abi_to_target "$FAT_HOST_ABI" >/dev/null 2>&1 || die "--fat-host-abi '$FAT_HOST_ABI' is not a valid ABI"
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
[ "$JOBS" -le 16 ] || warn "-j$JOBS is above the only level ever measured (-j16); peak memory
         scales with it.  See docs/android/BUILD.md."

# Build date.  Default: the one the AAR run used, so the omni.ja built here and
# the libxul.so it ships next to agree on the buildid.
aar_times="$AARDIR/build-times.txt"
if [ -z "$BUILD_DATE" ]; then
    [ -f "$aar_times" ] ||
        die "'$aar_times' does not exist, so MOZ_BUILD_DATE cannot be taken from the AAR run.
       Pass --build-date=YYYYMMDDHHMMSS (the value that run used)."
    BUILD_DATE=$(sed -n 's/^MOZ_BUILD_DATE=\([0-9]*\).*/\1/p' "$aar_times" | head -1)
    [ -n "$BUILD_DATE" ] ||
        die "'$aar_times' has no MOZ_BUILD_DATE= line; pass --build-date explicitly"
fi
printf '%s' "$BUILD_DATE" | grep -Eq '^[0-9]{14}$' ||
    die "--build-date '$BUILD_DATE' is not 14 digits (YYYYMMDDHHMMSS); build/variables.py:23-25
       would ignore it and this pass would stamp a different buildid from the AAR's"

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

# nasm, needed only when the ABI we actually *compile* is x86_64 -- which is the
# default --fat-host-abi here, so this fires more often than it does for the AAR
# script.  Checked by running the image, not by reading the Dockerfile.
if [ "$FAT_HOST_ABI" = "x86_64" ]; then
    "$ENGINE" run --rm "$IMAGE" \
        bash -c 'command -v nasm >/dev/null 2>&1 || [ -x "$MOZBUILD_STATE_PATH/nasm/nasm" ]' \
        >/dev/null 2>&1 ||
        die "image '$IMAGE' has no nasm, so an x86_64 host pass cannot be configured
       (toolkit/moz.configure:2655-2659).  Rebuild the image, or pass
       --fat-host-abi=arm64-v8a."
fi

# Where the image keeps mach's state directory.  Asked of the image rather than
# hardcoded, because a bind mount path is resolved by the engine and cannot be a
# shell expansion inside the container -- see the srcdirs mount in
# container_run() below for what it is for.
STATE_PATH=$("$ENGINE" run --rm "$IMAGE" bash -c 'printf "%s" "${MOZBUILD_STATE_PATH:-}"' 2>/dev/null)
[ -n "$STATE_PATH" ] ||
    die "image '$IMAGE' does not export MOZBUILD_STATE_PATH; this script needs it to keep
       mach's per-srcdir state (and the Glean parser virtualenv) across passes"

# apksigner, used by the signature check at the end.  Same reasoning: ask the
# image, before the build rather than after it.
"$ENGINE" run --rm "$IMAGE" \
    bash -c 'ls "$ANDROID_SDK_ROOT"/build-tools/*/apksigner >/dev/null 2>&1' >/dev/null 2>&1 ||
    die "image '$IMAGE' has no build-tools/*/apksigner; the APK signature check cannot run"

# Output directory.
if [ -z "$OUTDIR" ]; then
    OUTDIR="$(dirname "$SRCDIR")/librewolf-android-apk"
fi
# Checked before the directory is created, so a rejected --outdir does not leave
# the directory it was rejected for behind (inside the source tree, at that).
case "$(cd "$(dirname "$OUTDIR")" 2>/dev/null && pwd)/$(basename "$OUTDIR")" in
    "$SRCDIR"|"$SRCDIR"/*)
        die "--outdir must not be inside --srcdir: it is bind-mounted separately" ;;
esac
mkdir -p "$OUTDIR/logs" "$OUTDIR/mozbuild-srcdirs" || die "cannot create output directory '$OUTDIR'"
OUTDIR=$(cd "$OUTDIR" && pwd)
[ "$OUTDIR" != "$AARDIR" ] || die "--outdir and --aar-dir must be different directories"

objdir="$SRCDIR/obj-$FAT_HOST_ABI"

if [ "$SKIP_GECKO" = "1" ]; then
    [ -f "$objdir/config.status" ] ||
        die "--skip-gecko needs an objdir that has already been configured, and
       '$objdir/config.status' does not exist.  Run without --skip-gecko."
fi

# Disk.  One objdir at ~21 GB plus the APKs.
avail_gb=$(df -BG --output=avail "$SRCDIR" 2>/dev/null | tail -1 | tr -dc '0-9')
if [ -n "$avail_gb" ] && [ "$avail_gb" -lt 25 ] && [ "$SKIP_GECKO" != "1" ]; then
    die "only ${avail_gb}GB free on the filesystem holding '$SRCDIR'; the objdir alone is ~21GB"
fi

if [ -n "$GRADLE_HOME_SEED" ]; then
    [ -d "$GRADLE_HOME_SEED" ] || die "--gradle-home '$GRADLE_HOME_SEED' is not a directory"
    GRADLE_HOME_SEED=$(cd "$GRADLE_HOME_SEED" && pwd)
fi

mount_suffix=""
[ -n "$MOUNT_OPT" ] && mount_suffix=":$MOUNT_OPT"

log "source tree     : $SRCDIR"
log "fat AAR inputs  : $AARDIR"
log "output          : $OUTDIR"
log "base mozconfig  : $MOZCONFIG_SRC"
log "variant         : $VARIANT (fenix:assemble$VARIANT_CAP)"
log "ABIs            : $(printf '%s' "$abi_list" | tr '\n' ' ')(host $FAT_HOST_ABI)"
log "objdir          : $objdir"
log "engine / image  : $ENGINE / $IMAGE"
log "mach jobs       : -j$JOBS"
log "MOZ_BUILD_DATE  : $BUILD_DATE"

# ---------------------------------------------------------------------------
# mozconfig generation
# ---------------------------------------------------------------------------
#
# The base file is copied verbatim except for the --target line, so every
# hardening option, every export and every comment in assets/mozconfig.android
# is what actually gets built.  This script never edits, filters or "fixes up"
# the hardening flags -- and it never adds the subproject option either; that is
# checked for above and has to be in the base file.

write_mozconfig() {
    # $1 = ABI, $2 = destination path
    local abi=$1 dest=$2 triple
    triple=$(abi_to_target "$abi") || die "internal: no triple for '$abi'"

    {
        printf '# Generated by %s on %s -- do not edit, it is overwritten.\n' \
            "$progname" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        printf '# Base: %s   host ABI: %s\n' "$MOZCONFIG_SRC" "$abi"
        printf '# The only change from the base file is the --target line.\n\n'
        sed -E "s|^([[:space:]]*ac_add_options[[:space:]]*)--target=.*|\\1--target=$triple|" \
            "$MOZCONFIG_SRC"
        printf '\n\n# --- appended by %s ---\n' "$progname"
        printf 'mk_add_options MOZ_OBJDIR=@TOPSRCDIR@/obj-%s\n' "$abi"
    } > "$dest" || die "cannot write '$dest'"

    # Assert both edits landed.  A sed that matched nothing would leave the base
    # target in place and we would build the wrong ABI, which looks perfectly
    # healthy until the APK refuses to install.
    local got
    got=$(grep -E '^[[:space:]]*ac_add_options[[:space:]]*--target=' "$dest" | tail -1)
    [ "$got" = "ac_add_options --target=$triple" ] ||
        die "generated mozconfig '$dest' has target line '$got', expected 'ac_add_options --target=$triple'"
    grep -Eq '^[[:space:]]*ac_add_options[[:space:]]*--enable-android-subproject=fenix[[:space:]]*$' "$dest" ||
        die "generated mozconfig '$dest' lost the subproject option"
}

# ---------------------------------------------------------------------------
# Running a pass in the container
# ---------------------------------------------------------------------------
#
# Same shape as scripts/android-fat-aar.sh, and for the same reasons: one
# container per pass so /sys/fs/cgroup/memory.peak is per pass and no Gradle or
# Kotlin daemon survives into the next one; the engine started in the background
# and waited for, because bash does not run a trap while a foreground child is
# running and an interrupted 25 minute build would otherwise keep running
# unattended, holding 30 GB.

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
    # $1 = pass name, rest = the command to run in the tree
    local pass=$1; shift
    local name="lw-apk-$pass-$$-$(date -u +%s)"
    local envs=()
    local rc=0
    local abi

    envs+=(-e "MOZCONFIG=/work/out/mozconfig.$FAT_HOST_ABI")
    envs+=(-e "MOZ_BUILD_DATE=$BUILD_DATE")
    envs+=(-e "GRADLE_USER_HOME=/work/out/gradle-home")
    # Comma separated, exactly as taskcluster/kinds/build-fat-aar/kind.yml spells
    # it.  Set for BOTH passes: the Gradle pass reads the substs configure wrote,
    # but a stray reconfigure inside it must not silently drop back to a
    # single-ABI AAR (mobile/android/geckoview/build.gradle:130-136).
    envs+=(-e "MOZ_ANDROID_FAT_AAR_ARCHITECTURES=$(printf '%s\n' $abi_list | paste -sd, -)")
    for abi in $abi_list; do
        envs+=(-e "MOZ_ANDROID_FAT_AAR_$(abi_to_var "$abi")=/work/out/input/$abi/target.maven.zip")
    done

    CURRENT_CONTAINER="$name"
    # $STATE_PATH/srcdirs is mounted from the host, and that is load-bearing
    # rather than a cache optimisation.  mach keeps its per-srcdir state there,
    # including the "build" virtualenv, and
    # `mobile/android/gradle.configure:733-739` records *that venv's path* as
    # GRADLE_GLEAN_PARSER_VENV -- the Python the Glean Gradle plugin then
    # executes for every gleanGenerateMetricsSourceFor<Variant> task.  Without
    # the mount the venv lives in the writable layer of the container that ran
    # configure and dies with it, so the next pass fails with
    #
    #   Cannot run program ".../srcdirs/src-<hash>/_virtualenvs/build/bin/python"
    #   (in directory "/work/src"): error=2, No such file or directory
    #
    # on :fxaclient:gleanGenerateMetricsSourceForDebug -- measured, not
    # theorised.  The hash is derived from the topsrcdir path, which is the same
    # /work/src in every pass, so one host directory serves them all.
    "$ENGINE" run --rm --name "$name" \
        -v "$SRCDIR:/work/src$mount_suffix" \
        -v "$OUTDIR:/work/out$mount_suffix" \
        -v "$OUTDIR/mozbuild-srcdirs:$STATE_PATH/srcdirs$mount_suffix" \
        -w /work/src \
        "${envs[@]}" \
        "$IMAGE" \
        bash -c "$*" &
    wait $!
    rc=$?
    CURRENT_CONTAINER=""
    return $rc
}

# The body each pass runs inside the container.  Kept as one string so the exit
# status that comes back out of `$ENGINE run` is mach's, not a shell's.  Nothing
# here decides success by grepping a log (landmine L5 in docs/android/AGENTS.md).
#
# `./mach configure` is explicit and is not belt and braces.  mach re-runs
# configure only when a *file* is newer than config.status
# (python/mozbuild/mozbuild/controller/building.py:1360-1366 over the list
# moz.configure:1001-1033 builds, which records the mozconfig *path*, not its
# contents).  Both the subproject option and MOZ_ANDROID_FAT_AAR_ARCHITECTURES
# change the environment and the mozconfig body, not those files, so without an
# explicit configure an objdir from an earlier run would keep its old substs
# while `make` read the new environment -- and the two halves would disagree
# exactly as described in scripts/android-fat-aar.sh.
pass_body_gecko() {
    cat <<EOF
set -u
mkdir -p "\$GRADLE_USER_HOME" || exit 90
cp -n /root/.gradle/gradle.properties "\$GRADLE_USER_HOME"/ 2>/dev/null || true
# KGP registers its FUS build service in the build-wide shared services
# registry when the configuration cache is on, and this build carries two KGP
# classloaders (2.3.21 on the main buildscript classpath, 2.3.20 embedded for
# the kotlin-dsl plugin builds).  Whichever registers first wins the service
# name; the other then wires the foreign service into its KotlinCompile tasks,
# and Gradle dies decoding the work graph with "Could not load the value of
# field __buildFusService__ ... Cannot set the value of a property of type
# ...BuildFusService using a provider of type ...FlowActionBuildFusService"
# (gradle/gradle#31278).  Disabling FUS keeps both copies from registering;
# it is JetBrains first-use telemetry and cannot change build output.
grep -qx 'kotlin.internal.collectFUSMetrics=false' "\$GRADLE_USER_HOME/gradle.properties" 2>/dev/null || echo 'kotlin.internal.collectFUSMetrics=false' >> "\$GRADLE_USER_HOME/gradle.properties"
date -u +'PASS gecko START %Y-%m-%dT%H:%M:%SZ'
./mach configure
rc=\$?
echo "MACH_CONFIGURE_EXIT=\$rc"
[ \$rc -eq 0 ] || exit \$rc
./mach build -j$JOBS
rc=\$?
date -u +'PASS gecko END %Y-%m-%dT%H:%M:%SZ'
echo "MACH_EXIT=\$rc"
cat /sys/fs/cgroup/memory.peak > /work/out/logs/gecko.mempeak 2>/dev/null || true
exit \$rc
EOF
}

pass_body_apk() {
    cat <<EOF
set -u
mkdir -p "\$GRADLE_USER_HOME" || exit 90
cp -n /root/.gradle/gradle.properties "\$GRADLE_USER_HOME"/ 2>/dev/null || true
# Same FUS fix as the gecko pass: fenix's Gradle build runs with the same
# configuration cache and dual-KGP classloader setup, so the
# __buildFusService__ work-graph decode crash reaches it the same way.  (The
# batch build sidestepped it with --no-configuration-cache on that pass;
# disabling FUS lets us keep the cache.)
grep -qx 'kotlin.internal.collectFUSMetrics=false' "\$GRADLE_USER_HOME/gradle.properties" 2>/dev/null || echo 'kotlin.internal.collectFUSMetrics=false' >> "\$GRADLE_USER_HOME/gradle.properties"
date -u +'PASS apk START %Y-%m-%dT%H:%M:%SZ'

# The Glean Gradle plugin runs the interpreter whose path configure recorded in
# GRADLE_GLEAN_PARSER_VENV.  With --skip-gecko on a fresh --outdir that venv has
# never been created, and the failure arrives 6 minutes into Gradle rather than
# now, so recreate it here.  ./mach configure is what populates it (it runs *in*
# that venv), and it is ~30s against an already configured objdir.
venv=\$(sed -n "s/.*'GRADLE_GLEAN_PARSER_VENV': '\([^']*\)'.*/\1/p" \
        obj-$FAT_HOST_ABI/config.status 2>/dev/null | head -1)
echo "GLEAN_PARSER_VENV=\$venv"
if [ -n "\$venv" ] && [ ! -x "\$venv/bin/python" ]; then
    echo "glean parser venv missing, running ./mach configure to recreate it"
    ./mach configure || exit \$?
fi
if [ -n "\$venv" ] && [ ! -x "\$venv/bin/python" ]; then
    echo "fatal: \$venv/bin/python still does not exist after ./mach configure;" >&2
    echo "the Glean tasks (:fxaclient:gleanGenerateMetricsSourceForDebug) will fail" >&2
    exit 91
fi

# :fenix:compileReleaseKotlin consumes the Safe Args generated sources
# (*Directions / *Args).  In the full parallel build it can start before
# :fenix:generateSafeArgsRelease has written them and fail with ~100
# "Unresolved reference" errors.  The generator itself is sound -- run in
# isolation it emits all 191 files under both the configuration cache and
# --no-configuration-cache -- so this is a task-ordering race, not a broken
# generator.  Pre-generating in a dedicated invocation puts the sources on
# disk before the assemble graph runs, so the compile always sees them.
./mach gradle fenix:generateSafeArgs$VARIANT_CAP
rc=\$?
if [ \$rc -ne 0 ]; then
    date -u +'PASS apk END %Y-%m-%dT%H:%M:%SZ'
    echo "MACH_EXIT=\$rc"
    exit \$rc
fi
# fenixSplitAbi drives the fenix/app/build.gradle splits block so the AGP split
# matches --abis exactly (the apk_index check asserts produced == requested and
# is right to do so).  MOZ_ANDROID_FAT_AAR_ARCHITECTURES is already set in the
# container env for both passes, so reuse it; \$ keeps it for the container
# shell, not the heredoc's host shell.  When unset (it is never unset here) the
# build falls back to the original three-ABI split.
./mach gradle fenix:assemble$VARIANT_CAP -PfenixSplitAbi="\$MOZ_ANDROID_FAT_AAR_ARCHITECTURES"
rc=\$?
date -u +'PASS apk END %Y-%m-%dT%H:%M:%SZ'
echo "MACH_EXIT=\$rc"
cat /sys/fs/cgroup/memory.peak > /work/out/logs/apk.mempeak 2>/dev/null || true
exit \$rc
EOF
}

# ---------------------------------------------------------------------------
# Artifact checks.  Every one reads the produced file; none trusts a log line.
# ---------------------------------------------------------------------------

# Lists the ABI directories under a prefix in a zip that contain libxul.so.
# Used for both jni/ (AAR) and lib/ (APK).
zip_abis_with_libxul() {
    # $1 = zip, $2 = prefix ("jni/" or "lib/")
    python3 - "$1" "$2" <<'PY'
import sys, zipfile, posixpath
path, prefix = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(path) as z:
    abis = sorted({
        n[len(prefix):].split("/")[0]
        for n in z.namelist()
        if n.startswith(prefix) and posixpath.basename(n) == "libxul.so"
    })
print("\n".join(abis))
PY
}

# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

start_all=$(date +%s)
summary_file="$OUTDIR/build-times.txt"

if [ "$DRY_RUN" = "1" ]; then
    log "dry run: preflight passed, nothing will be built."
    log "  would copy $(printf '%s\n' $abi_list | wc -l) target.maven.zip files into $OUTDIR/input"
    if [ "$SKIP_GECKO" = "1" ]; then
        log "  would skip the gecko pass (--skip-gecko)"
    else
        log "  would build $FAT_HOST_ABI ($(abi_to_target "$FAT_HOST_ABI")) in $objdir, merging in the fat AAR"
    fi
    log "  would run ./mach gradle fenix:assemble$VARIANT_CAP"
    log "  would collect APKs into $OUTDIR"
    exit 0
fi

# Copy the inputs in rather than bind-mounting --aar-dir: it belongs to the AAR
# run (possibly to another task), and a bind mount with an SELinux relabel is
# not a read-only operation on it.  The copy is also what makes this run
# reproducible from --outdir alone.
log "copying per-ABI maven zips from $AARDIR"
for abi in $abi_list; do
    mkdir -p "$OUTDIR/input/$abi" || die "cannot create '$OUTDIR/input/$abi'"
    cp "$AARDIR/$abi/target.maven.zip" "$OUTDIR/input/$abi/target.maven.zip" ||
        die "cannot copy '$AARDIR/$abi/target.maven.zip'"
done

if [ -n "$GRADLE_HOME_SEED" ] && [ ! -d "$OUTDIR/gradle-home" ]; then
    log "seeding gradle home from $GRADLE_HOME_SEED"
    cp -a "$GRADLE_HOME_SEED" "$OUTDIR/gradle-home" ||
        die "cannot seed the gradle home from '$GRADLE_HOME_SEED'"
fi

{
    printf 'LibreWolf Android APK -- %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'tree=%s\naar=%s\nabis=%s host=%s\njobs=%s\nMOZ_BUILD_DATE=%s\nengine=%s image=%s\n\n' \
        "$SRCDIR" "$AARDIR" "$ABIS" "$FAT_HOST_ABI" "$JOBS" "$BUILD_DATE" "$ENGINE" "$IMAGE"
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

write_mozconfig "$FAT_HOST_ABI" "$OUTDIR/mozconfig.$FAT_HOST_ABI"

# ---------------------------------------------------------------------------
# Pass 1: Gecko + the fat merge, in the host ABI's objdir
# ---------------------------------------------------------------------------

if [ "$SKIP_GECKO" = "1" ]; then
    log "skipping the gecko pass (--skip-gecko); reusing $objdir"
    # Drop any peak an earlier run left behind: record() would otherwise print
    # that run's memory figure next to "skipped", i.e. report a measurement this
    # run did not make.
    rm -f "$OUTDIR/logs/gecko.mempeak"
    record gecko 0 "skipped"
else
    log "gecko: building $FAT_HOST_ABI (-j$JOBS), log: $OUTDIR/logs/gecko.log"
    rm -f "$OUTDIR/logs/gecko.mempeak"
    t0=$(date +%s)
    container_run gecko "$(pass_body_gecko)" > "$OUTDIR/logs/gecko.log" 2>&1
    rc=$?
    t1=$(date +%s)
    if [ "$rc" != "0" ]; then
        record gecko $((t1 - t0)) "FAILED rc=$rc"
        die "gecko: mach build failed (exit $rc) after $((t1 - t0))s.
       Log: $OUTDIR/logs/gecko.log"
    fi
    record gecko $((t1 - t0)) "ok"
    log "gecko: build ok in $((t1 - t0))s"
fi

# fat_aar.py returns 1 when an input differs across ABIs outside its allow-list
# and the tier fails the build, so a zero exit already means the check passed.
# Say so from the log of the tier that ran it, and fail if the two disagree.
#
# The pattern is NOT anchored at the start of the line, and that is the whole
# point: fat_aar.py prints "Disallowed: ..." on its own stdout, but this log is
# mach's, and mach prefixes every line with an elapsed time (" 0:02.69 Allowed:
# Path ..." is what the real log contains).  An anchored '^Disallowed: ' can
# therefore never match, which would make this check quietly always pass -- the
# fail-open shape of landmine L5, in the checker that exists to catch it.
# Measured against a real run's log, not assumed.
if [ "$SKIP_GECKO" != "1" ] && grep -Eq '(^|[[:space:]])Disallowed: ' "$OUTDIR/logs/gecko.log"; then
    die "gecko: fat_aar.py reported disallowed cross-ABI differences yet the build exited 0.
       Read $OUTDIR/logs/gecko.log"
fi

# The merge really ran, and produced every ABI.  Checked in the objdir rather
# than inferred from the log.
for abi in $abi_list; do
    [ -f "$objdir/dist/fat-aar/output/jni/$abi/libxul.so" ] ||
        die "gecko: '$objdir/dist/fat-aar/output/jni/$abi/libxul.so' is missing; the
       android-fat-aar-artifact tier did not unpack $abi"
done

# And configure knew about it, which is the half that decides what Gradle
# packages.  Reading config.status is reading what the build actually used.
#
# Presence of the key is NOT the check.  geckoview/build.gradle:130-136 branches
# on the list's truthiness, and a ./mach configure run without the fat-AAR
# environment (a host-only configure) records the key with an EMPTY list -- the
# exact state that packages dist/geckoview/lib, i.e. the host ABI alone.  A
# `grep -q` on the key name passes on that state, so it must read the value.
# Measured 2026-08-21: an objdir left in that state by an earlier host-only
# configure produced fenix-armeabi-v7a-release.apk (43M) with zero gecko
# native libraries while fenix-x86_64-release.apk (123M) carried libxul; the
# per-APK verification below caught it, which is exactly where this check
# should have.  The empty-list state is the one --skip-gecko can be handed, so
# it has to die here with a say-why, not build a broken arm split.
fat_archs=$(python3 - "$objdir/config.status" <<'PY'
import ast, re, sys
src = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"['\"]MOZ_ANDROID_FAT_AAR_ARCHITECTURES['\"]\s*:\s*(\[[^\]]*\])", src)
print(" ".join(ast.literal_eval(m.group(1)) if m else []))
PY
)
[ -n "$fat_archs" ] ||
    die "'$objdir/config.status' records MOZ_ANDROID_FAT_AAR_ARCHITECTURES as an empty
       list: this objdir was configured without the fat inputs (a host-only ./mach
       configure), so mobile/android/geckoview/build.gradle:130-136 would package
       dist/geckoview/lib -- the host ABI only -- and the other split APKs would
       ship with no gecko native libraries. Re-run without --skip-gecko so the
       gecko pass reconfigures with $ABIS."
for abi in $abi_list; do
    case " $fat_archs " in
    *" $abi "*) ;;
    *) die "'$objdir/config.status' records MOZ_ANDROID_FAT_AAR_ARCHITECTURES =
       [$fat_archs], which lacks $abi. Re-run without --skip-gecko so the gecko pass
       reconfigures with $ABIS." ;;
    esac
done
grep -q "'MOZ_ANDROID_SUBPROJECT': 'fenix'" "$objdir/config.status" ||
    die "'$objdir/config.status' does not record MOZ_ANDROID_SUBPROJECT == fenix"

# ---------------------------------------------------------------------------
# Pass 2: the APK
# ---------------------------------------------------------------------------

log "apk: ./mach gradle fenix:assemble$VARIANT_CAP, log: $OUTDIR/logs/apk.log"
rm -f "$OUTDIR/logs/apk.mempeak"
t0=$(date +%s)
container_run apk "$(pass_body_apk)" > "$OUTDIR/logs/apk.log" 2>&1
rc=$?
t1=$(date +%s)
if [ "$rc" != "0" ]; then
    record apk $((t1 - t0)) "FAILED rc=$rc"
    die "apk: mach gradle fenix:assemble$VARIANT_CAP failed (exit $rc) after $((t1 - t0))s.
       Log: $OUTDIR/logs/apk.log"
fi
record apk $((t1 - t0)) "ok"
log "apk: gradle ok in $((t1 - t0))s"

# ---------------------------------------------------------------------------
# Collect and verify
# ---------------------------------------------------------------------------

# AGP's per-build-type output directory is outputs/apk/<buildType>, spelled in
# lowercase (outputs/apk/debug, outputs/apk/release) -- the same spelling
# upstream uses in taskcluster/kinds/build/fenix.yml:52-55.
apk_src_dir="$objdir/gradle/build/mobile/android/fenix/app/outputs/apk/$VARIANT"
[ -d "$apk_src_dir" ] ||
    die "'$apk_src_dir' does not exist after a successful fenix:assemble$VARIANT_CAP.
       (Upstream names the same directory in
       taskcluster/kinds/build/fenix.yml:52-55.)"

rm -rf "$OUTDIR/apk"
mkdir -p "$OUTDIR/apk" || die "cannot create '$OUTDIR/apk'"
n_copied=0
# No `find | while read`: that loop body runs in a subshell, so a failing cp
# could not stop the script from there.
for f in "$apk_src_dir"/*.apk; do
    [ -f "$f" ] || continue
    cp "$f" "$OUTDIR/apk/" || die "cannot copy '$f' to '$OUTDIR/apk'"
    n_copied=$((n_copied + 1))
done
[ "$n_copied" -gt 0 ] || die "no *.apk in '$apk_src_dir'"

# AGP's own record of which file is which.  This is *not* a convenience: the
# split APK file names are <archivesBaseName>-<filter>-<buildType>.apk and this
# tree's base name is "fenix", while upstream's artifact path in
# taskcluster/kinds/build/fenix.yml:52-55 still says app-arm64-v8a-debug.apk.
# Guessing either spelling gets it wrong on the other tree, so read the mapping
# AGP wrote next to the APKs instead of reconstructing it.
[ -f "$apk_src_dir/output-metadata.json" ] ||
    die "'$apk_src_dir/output-metadata.json' is missing; AGP writes it next to the
       APKs and this script reads the ABI -> file mapping out of it"
cp "$apk_src_dir/output-metadata.json" "$OUTDIR/apk/" ||
    die "cannot copy output-metadata.json"

log "APKs produced:"
for f in "$OUTDIR"/apk/*.apk; do
    log "  $(basename "$f")  $(du -h "$f" | cut -f1)"
done

# abi -> file name, and "universal" -> file name, from the metadata; also
# asserts the set of ABIs AGP split for is exactly the set we asked for.
apk_index=$(python3 - "$OUTDIR/apk/output-metadata.json" $abi_list <<'PY'
import json
import sys

meta_path = sys.argv[1]
want = set(sys.argv[2:])

with open(meta_path, encoding="utf-8") as fh:
    meta = json.load(fh)

lines = []
universal = [e for e in meta["elements"] if e.get("type") == "UNIVERSAL"]
if len(universal) != 1:
    sys.exit(f"  expected exactly one UNIVERSAL element, found {len(universal)}")
lines.append("universal\t" + universal[0]["outputFile"])

got = {}
for e in meta["elements"]:
    if e.get("type") != "ONE_OF_MANY":
        continue
    abis = [f["value"] for f in e.get("filters", []) if f.get("filterType") == "ABI"]
    if len(abis) != 1:
        sys.exit(f"  element {e.get('outputFile')} has ABI filters {abis}, expected one")
    got[abis[0]] = e["outputFile"]

if set(got) != want:
    sys.exit(
        f"  AGP split for {sorted(got)}, expected {sorted(want)}\n"
        "  (mobile/android/fenix/app/build.gradle:230-246 decides the split set)"
    )
for abi in sorted(got):
    lines.append(abi + "\t" + got[abi])

# applicationId is in here too; the aapt2 check below reads it out of the binary
# manifest instead, and the two are cross-checked.
lines.append("applicationId\t" + meta.get("applicationId", ""))
print("\n".join(lines))
PY
) || die "output-metadata.json does not describe the expected APK set (see above)"

apk_for() {
    # $1 = ABI or "universal"
    local file
    file=$(printf '%s\n' "$apk_index" | awk -F'\t' -v k="$1" '$1 == k { print $2; exit }')
    [ -n "$file" ] || die "internal: no APK recorded for '$1'"
    printf '%s' "$OUTDIR/apk/$file"
}

meta_appid=$(printf '%s\n' "$apk_index" | awk -F'\t' '$1 == "applicationId" { print $2 }')

# Per-ABI APK: exactly its own ABI's libxul.so, and that libxul.so is the one
# the per-ABI Gecko build produced.  This is the check that distinguishes "our
# GeckoView" from any prebuilt one, and it is done by hashing bytes out of the
# two artifacts rather than by reading a version string.

log "verifying each APK against the per-ABI GeckoView builds"
for abi in $abi_list; do
    apk=$(apk_for "$abi")
    [ -f "$apk" ] ||
        die "the APK output-metadata.json names '$apk' for $abi and it is not there.
       Present: $(cd "$OUTDIR/apk" && echo *.apk)"

    got=$(zip_abis_with_libxul "$apk" "lib/" | tr '\n' ' ' | sed 's/ *$//')
    [ "$got" = "$abi" ] ||
        die "'$apk' carries libxul.so for [$got], expected exactly [$abi]"

    python3 - "$apk" "$OUTDIR/input/$abi/target.maven.zip" "$abi" "$BUILD_DATE" \
             "$(abi_to_elf_machine "$abi")" <<'PY' || die "$abi: APK native library check failed (see above)"
import fnmatch
import hashlib
import io
import struct
import sys
import zipfile

apk_path, maven_path, abi, build_date, want_machine = sys.argv[1:6]
want_machine = int(want_machine)

with zipfile.ZipFile(apk_path) as apk:
    apk_lib = apk.read(f"lib/{abi}/libxul.so")

with zipfile.ZipFile(maven_path) as mz:
    aars = [n for n in mz.namelist() if fnmatch.fnmatch(n, "*geckoview-*.aar")]
    if len(aars) != 1:
        sys.exit(f"  {abi}: expected one geckoview AAR in {maven_path}, found {len(aars)}")
    with zipfile.ZipFile(io.BytesIO(mz.read(aars[0]))) as aar:
        aar_lib = aar.read(f"jni/{abi}/libxul.so")

problems = []

# ELF header: the ABI directory name is a claim, e_machine is the fact.
if apk_lib[:4] != b"\x7fELF":
    problems.append(f"lib/{abi}/libxul.so is not an ELF file")
else:
    machine = struct.unpack_from("<H", apk_lib, 18)[0]
    if machine != want_machine:
        problems.append(
            f"lib/{abi}/libxul.so has ELF e_machine {machine}, expected {want_machine}"
        )

# The buildid this run pinned has to be inside the shipped library, or the APK
# is carrying a libxul from some other build.
if build_date.encode() not in apk_lib:
    problems.append(
        f"lib/{abi}/libxul.so does not contain the pinned build id {build_date}"
    )

apk_sha = hashlib.sha256(apk_lib).hexdigest()
aar_sha = hashlib.sha256(aar_lib).hexdigest()
if apk_sha == aar_sha:
    verdict = "sha256-identical to the per-ABI build"
else:
    # AGP may run its own strip over jniLibs.  That is a transformation of our
    # library, not a substitution of somebody else's, and the two checks above
    # already pin identity -- so report it loudly instead of failing.
    verdict = (
        f"DIFFERS from the per-ABI build (apk {len(apk_lib)}B {apk_sha[:16]}, "
        f"aar {len(aar_lib)}B {aar_sha[:16]}) -- expected only if AGP stripped it"
    )

if problems:
    sys.exit("\n".join("  " + p for p in problems))
print(f"  {abi}: libxul.so {len(apk_lib)} bytes, buildid {build_date} present, {verdict}")
PY
done

# The universal APK is the one a human installs without knowing their ABI, so
# check it carries all of them rather than assuming the split logic did.
universal=$(apk_for universal)
if [ -f "$universal" ]; then
    got=$(zip_abis_with_libxul "$universal" "lib/" | tr '\n' ' ' | sed 's/ *$//')
    want=$(printf '%s\n' $abi_list | sort | tr '\n' ' ' | sed 's/ *$//')
    [ "$got" = "$want" ] ||
        die "'$universal' carries libxul.so for [$got], expected [$want]"
    log "  universal: libxul.so for $got"
else
    # universalApk is gated on MOZILLA_OFFICIAL (fenix/app/build.gradle:242-245),
    # which the preflight already required, so its absence means the splits
    # block changed under us.
    die "output-metadata.json names '$universal' as the universal APK and it is not
       there.  universalApk is gated on MOZILLA_OFFICIAL
       (mobile/android/fenix/app/build.gradle:242-245), which the preflight required."
fi

# applicationId, read out of the built APK rather than out of build.gradle.
# LW-M2-04 keeps branding and the app id STOCK on purpose -- LW-M4-07 changes
# them, and changing them here would make the first failure of the first APK
# ambiguous.  When LW-M4-07 lands, this expectation moves with it.
# debug: org.mozilla.fenix.debug (applicationIdSuffix ".fenix.debug");
# release: org.mozilla.firefox (applicationIdSuffix ".firefox").
log "checking the applicationId is still stock for the $VARIANT build type"
appid=$("$ENGINE" run --rm \
        -v "$OUTDIR:/work/out$mount_suffix" \
        "$IMAGE" \
        bash -c 'set -e; a=$(ls "$ANDROID_SDK_ROOT"/build-tools/*/aapt2 | head -1); "$a" dump packagename "$1"' \
        _ "/work/out/apk/$(basename "$(apk_for universal)")" 2>&1) ||
    die "aapt2 could not read the package name from the universal APK:
$appid"
appid=$(printf '%s' "$appid" | tr -d '\r' | tail -1)
if [ "$VARIANT" = "debug" ]; then
    expected_appid="org.mozilla.fenix.debug"
    appid_note="mobile/android/fenix/app/build.gradle:60 applicationId + :121 debug applicationIdSuffix"
else
    expected_appid="org.mozilla.firefox"
    appid_note="mobile/android/fenix/app/build.gradle:60 applicationId + the release block's applicationIdSuffix .firefox"
fi
[ "$appid" = "$expected_appid" ] ||
    die "APK applicationId is '$appid', expected the stock $VARIANT id $expected_appid
       ($appid_note).
       If this is LW-M4-07 rebranding on purpose, update this check with it."
[ "$appid" = "$meta_appid" ] ||
    die "aapt2 reads applicationId '$appid' out of the APK's binary manifest while AGP's
       output-metadata.json says '$meta_appid'; they must agree"
log "  applicationId: $appid (stock, and output-metadata.json agrees)"

# What the APK does and does not carry of the LibreWolf configuration layer.
# This is a *measurement*, not a pass/fail: on Android none of librewolf.cfg,
# local-settings.js or policies.json is packaged, which is the M3 gap LW-M3-08
# exists to close.  Recorded here so that task starts from a number rather than
# from an assumption, and asserted so that the day one of them does start
# shipping, this script says so.
log "recording the LibreWolf configuration layer present in the APK"
# NOTE the `|| die` is on the SAME line as the heredoc redirection.  Put it on
# the next line and that line becomes the first line of the here-document
# instead: python then dies with "IndentationError: unexpected indent" and
# nothing checks its exit status, because the `||` was never a shell operator.
# That is a fail-open in the checker, and it happened here once already.
python3 - "$(apk_for "$FAT_HOST_ABI")" "$OUTDIR/apk-config-layer.txt" <<'PY' || die "the APK configuration-layer measurement failed (see above)"
import io
import sys
import zipfile

apk_path, report_path = sys.argv[1:3]
WANTED = (
    "librewolf.cfg",
    "local-settings.js",
    "policies.json",
    "autoconfig.js",
    "distribution.ini",
)

lines = []
with zipfile.ZipFile(apk_path) as apk:
    apk_names = apk.namelist()
    omni = apk.read("assets/omni.ja") if "assets/omni.ja" in apk_names else None
if omni is None:
    sys.exit("  assets/omni.ja is not in the APK at all")
with zipfile.ZipFile(io.BytesIO(omni)) as z:
    omni_names = z.namelist()
    prefs = {n: z.read(n) for n in omni_names
             if n.endswith("greprefs.js") or n.endswith("geckoview-prefs.js")}

lines.append(f"apk={apk_path}")
lines.append(f"apk entries={len(apk_names)}  omni.ja entries={len(omni_names)}")
for want in WANTED:
    hits = [n for n in apk_names if n.split("/")[-1] == want]
    hits += [f"assets/omni.ja!/{n}" for n in omni_names if n.split("/")[-1] == want]
    lines.append(f"{want}: {'PRESENT ' + str(hits) if hits else 'absent'}")

lw = 0
for name, blob in sorted(prefs.items()):
    n = sum(1 for line in blob.decode("utf-8", "replace").splitlines()
            if '"librewolf.' in line)
    lw += n
    lines.append(f"{name}: {n} librewolf.* pref lines")
lines.append(f"total librewolf.* pref lines in omni.ja pref files: {lw}")

report = "\n".join(lines) + "\n"
with open(report_path, "w", encoding="utf-8") as fh:
    fh.write(report)
print(report, end="")
PY

# Debug signature -- for BOTH build types in this configuration: the
# releaseTemplate closure (fenix/app/build.gradle) sets
# signingConfig = signingConfigs.debug unless MOZ_AUTOMATION or
# disableDebugSigning is set, and assets/mozconfig.android sets neither, so a
# release APK signed with anything other than the debug certificate is a
# surprise and fails here.  `apksigner verify` is the tool that actually
# validates the APK signature blocks; a `META-INF/*.RSA` listing would only
# prove something was signed, not that the signature verifies.
# No prebuilt GeckoView, and no prebuilt app-services.
#
# This is the criterion the mozconfig's --enable-appservices-in-tree comment
# warns can fail *invisibly*: if :geckoview is not part of the Gradle build,
# ProjectPlugin.kt:112 does not substitute project(':<mod>') for the
# org.mozilla.appservices:<mod> coordinates, and the APK links Mozilla's
# prebuilt AARs while the flag still looks honoured.  The observable difference
# is whether Gradle had to *resolve* those coordinates, so look for them in the
# Gradle cache this run wrote.
#
# Scoped to files this run created (-newermt), not to the cache as a whole: a
# --gradle-home seeded from some other build may legitimately contain them, and
# a check that fails on somebody else's cache contents would just get disabled.
log "checking no prebuilt GeckoView or app-services artifact was resolved"
for coord in org.mozilla.appservices org.mozilla.geckoview; do
    hits=$(find "$OUTDIR/gradle-home" -path "*$coord*" -newermt "@$start_all" -type f 2>/dev/null | head -5)
    [ -z "$hits" ] ||
        die "this run resolved prebuilt $coord artifacts into the Gradle cache:
$hits
       Both must come from the in-tree projects (:geckoview and
       third_party/application-services).  If app-services is the one that
       appeared, the ProjectPlugin.kt:112 substitution did not happen -- check
       that :geckoview is in this Gradle build (see the header of this script)."
done
log "  none resolved: GeckoView and app-services are both in-tree"

log "verifying the APK signatures"
for f in "$OUTDIR"/apk/*.apk; do
    name=$(basename "$f")
    out=$("$ENGINE" run --rm \
            -v "$OUTDIR:/work/out$mount_suffix" \
            "$IMAGE" \
            bash -c 'set -e; s=$(ls "$ANDROID_SDK_ROOT"/build-tools/*/apksigner | head -1); "$s" verify --print-certs "$1"' \
            _ "/work/out/apk/$name" 2>&1) ||
        die "apksigner could not verify '$name':
$out"
    printf '%s' "$out" | grep -q 'CN=Android Debug' ||
        die "'$name' is not signed with the Android debug certificate:
$out"
    # apksigner spells this "V2 Signer: certificate DN: ..." (checked against its
    # real output, not guessed), and only the CN part is stable across machines --
    # the debug keystore's key differs per builder, so the DN, not a fingerprint,
    # is what can be asserted.
    log "  $name: signature verifies, $(printf '%s' "$out" | sed -n 's/.*certificate DN: /DN=/p' | head -1)"
done

end_all=$(date +%s)
{
    printf '\n%-14s %10s\n' total $((end_all - start_all))
    printf '\nAPKs:\n'
    for f in "$OUTDIR"/apk/*.apk; do
        printf '  %-32s %s\n' "$(basename "$f")" "$(du -h "$f" | cut -f1)"
    done
    printf '\nconfiguration layer: %s\n' "$OUTDIR/apk-config-layer.txt"
} >> "$summary_file"

log "APKs      : $OUTDIR/apk"
log "install   : adb install -r $(apk_for universal)"
log "total wall clock: $((end_all - start_all))s"
echo
cat "$summary_file"
