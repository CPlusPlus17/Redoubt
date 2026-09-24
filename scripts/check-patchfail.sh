#!/bin/sh
#
# Apply every patch LibreWolf applies to a pristine Firefox tree and report the
# ones that do not apply cleanly.
#
# usage: ./scripts/check-patchfail.sh [--targets=<list>] [--use-desktop-tarball]
#                                     [patch options...]
#
#   --targets=<list>       comma separated platforms, from 'desktop' and
#                          'android' (default: desktop). assets/patches/
#                          common.txt is always walked first, then one list per
#                          target, which is exactly what
#                          scripts/librewolf-patches.py applies.
#   --use-desktop-tarball  test the android list against the desktop Firefox
#                          tarball when the ESR one is not downloaded. Loudly
#                          warns; the result is indicative, not authoritative.
#
# Anything this script does not recognise is forwarded verbatim to `patch`,
# which is how `make check-fuzz` passes --fuzz=0. Our own options are shifted
# off the argument list before the loop; leaving --targets= in "$@" made patch
# choke on it (LW-M0-11 flagged this).
#
# Which lists are walked
# ----------------------
#
# assets/patches/common.txt, then the selected target lists in a fixed order
# (desktop before android), deduplicated - mirroring selected_targets() and
# patches_to_apply() in scripts/librewolf-patches.py, so that this reports on
# the same sequence a build would apply. Blank lines and '#' comments are
# skipped, inline comments included, same as read_patch_list() there.
#
# This used to walk assets/patches.txt, the generated common+desktop shim. The
# two are sequence-identical today, so the no-argument run is unchanged; the
# shim is compared as a set below and a mismatch warns, because the shim is
# still what the enable/disable helpers edit and a drift there would silently
# mean this script and a real build no longer test the same thing.
#
# Which Firefox tarball
# ---------------------
#
# The tracks differ: ./version is desktop (Firefox release), ./version.android
# is android (Firefox ESR). Same rule as the Makefile - android without desktop
# uses ./version.android, anything else uses ./version, and asking for both at
# once when the two have diverged is refused rather than silently tested
# against one of them.
#
# The ESR tarball is a 766MB download this script will never perform on its
# own: `make check-patchfail` is run casually and must not start one. When it
# is missing the run fails with the fetch command to run; --use-desktop-tarball
# is the deliberate escape hatch for checking the android list before the real
# base is on disk.
#
# Failure detection uses two signals, in this order:
#
#   1. patch's exit status. This is the authoritative one. GNU patch exits 0
#      only when every hunk applied (fuzz and offsets are still a success),
#      1 when some hunk did not apply, and 2 on serious trouble.
#   2. the .rej files named in patch's output. Kept as a second signal because
#      it is what prints the rejected hunks for a human to fix.
#
# Signal 2 alone used to be the whole test, and it fails open: when a hunk's
# target file is missing - the shape of an upstream rename - patch writes no
# .rej file at all. It prints "can't find file to patch" on *stderr*, then
# "Skipping patch. / 1 out of 1 hunk ignored", and exits 1. Grepping stdout for
# .rej files therefore reported success for a patch that applied nothing. That
# is landmine L5 in docs/android/AGENTS.md; both halves of it (the ignored exit
# status and the uncaptured stderr) are fixed below.
#
# stdout is the report: `make check-patchfail` redirects it into patchfail.out.
# The exit status is 0 when every patch applied and 1 when any did not.
#

KNOWN_TARGETS="desktop android"

targets="desktop"
use_desktop_tarball=0

# Split our own options out of "$@" and leave the rest in place for patch.
# The rotate trick: take the head, and either consume it or push it back onto
# the tail. After $argc iterations every original argument has been looked at
# exactly once and the survivors are back in their original order, with no
# word splitting anywhere - so a patch option containing a space still works.
argc=$#
while [ "$argc" -gt 0 ]; do
    arg=$1
    shift
    argc=$((argc - 1))
    case "$arg" in
        --targets=*)
            targets=${arg#--targets=}
            ;;
        --targets)
            if [ "$argc" -eq 0 ]; then
                echo "error: --targets needs a value, e.g. --targets=android" >&2
                exit 2
            fi
            targets=$1
            shift
            argc=$((argc - 1))
            ;;
        --use-desktop-tarball)
            use_desktop_tarball=1
            ;;
        -h|--help)
            echo "usage: $0 [--targets=<list>] [--use-desktop-tarball] [patch options...]"
            echo ""
            echo "  --targets=<list>       comma separated, from: $KNOWN_TARGETS"
            echo "                         (default: desktop). assets/patches/common.txt"
            echo "                         is always walked first."
            echo "  --use-desktop-tarball  check the android list against the desktop"
            echo "                         tarball when the ESR one is not downloaded."
            echo ""
            echo "Unrecognised options are forwarded to patch, e.g. --fuzz=0."
            exit 0
            ;;
        *)
            set -- "$@" "$arg"
            ;;
    esac
done

#
# Resolve the targets before touching anything, so a typo costs nothing.
#

selected=
for t in $(echo "$targets" | tr ',' ' '); do
    known=0
    for k in $KNOWN_TARGETS; do
        [ "$t" = "$k" ] && known=1
    done
    if [ "$known" -eq 0 ]; then
        echo "error: unknown target '$t' in --targets=$targets" >&2
        echo "  known targets: $KNOWN_TARGETS" >&2
        echo "  'common' is not a target - assets/patches/common.txt is always walked." >&2
        exit 2
    fi
done
# KNOWN_TARGETS order, deduplicated, so --targets=android,desktop and
# --targets=desktop,android walk the same sequence.
for k in $KNOWN_TARGETS; do
    for t in $(echo "$targets" | tr ',' ' '); do
        if [ "$t" = "$k" ]; then
            selected="$selected $k"
            break
        fi
    done
done
if [ -z "$selected" ]; then
    echo "error: --targets is empty; expected one or more of: $KNOWN_TARGETS" >&2
    exit 2
fi

has_desktop=0
has_android=0
for t in $selected; do
    [ "$t" = "desktop" ] && has_desktop=1
    [ "$t" = "android" ] && has_android=1
done

if [ ! -f version ]; then
    echo "error: 'version' does not exist. Are you in the right folder?"
    exit 1
fi
repo_root=$PWD

#
# Pick the release track. See the Makefile's "Release track" block: one
# extracted tree cannot be two Firefox versions at once.
#
version_file="version"
if [ "$has_android" -eq 1 ] && [ "$has_desktop" -eq 0 ]; then
    version_file="version.android"
    if [ ! -f "$version_file" ]; then
        echo "error: '--targets=android' needs './version.android' - see docs/android/TRACK.md"
        exit 1
    fi
fi
ffversion=$(cat "$version_file")
if [ -z "$ffversion" ]; then
    echo "error: '$version_file' is empty."
    exit 1
fi

if [ "$has_android" -eq 1 ] && [ "$has_desktop" -eq 1 ] && [ -f version.android ]; then
    android_version=$(cat version.android)
    if [ "$ffversion" != "$android_version" ]; then
        echo "error: --targets=$targets wants desktop $ffversion and android $android_version"
        echo "  in one tree. There is no single Firefox tarball to test both lists"
        echo "  against - check them one at a time:"
        echo "    ./scripts/check-patchfail.sh"
        echo "    ./scripts/check-patchfail.sh --targets=android"
        echo "  See docs/android/TRACK.md."
        exit 1
    fi
fi

firefox=firefox-$ffversion.source.tar.xz
tarball_warning=""
if [ ! -f "$firefox" ]; then
    if [ "$has_android" -eq 1 ] && [ "$has_desktop" -eq 0 ] && [ "$use_desktop_tarball" -eq 1 ] \
       && [ -f "firefox-$(cat version).source.tar.xz" ]; then
        # Deliberate, opt-in, and never quiet about it. The android list is
        # written against ESR; testing it against the release tarball catches
        # the gross failures (missing target file, drifted context in code both
        # tracks share) and cannot prove the real thing.
        tarball_warning="WARNING: tested against firefox-$(cat version).source.tar.xz (desktop, $(cat version)), NOT the android base $firefox ($ffversion). Result is indicative only."
        firefox="firefox-$(cat version).source.tar.xz"
        ffversion=$(cat version)
    else
        echo "error: '$firefox' does not exist."
        if [ "$has_android" -eq 1 ] && [ "$has_desktop" -eq 0 ]; then
            echo ""
            echo "  --targets=android tests against the Firefox ESR tarball named by"
            echo "  ./version.android ($ffversion), which is a separate ~766MB download"
            echo "  from the desktop one. This script will not start it for you."
            echo ""
            echo "  Fetch it:      make fetch TARGETS=android"
            echo "  or check the android list against the desktop tarball anyway:"
            echo "                 ./scripts/check-patchfail.sh --targets=android --use-desktop-tarball"
            echo "                 (indicative only - it is not the android base)"
        fi
        exit 1
    fi
fi

#
# The patch lists, resolved before extracting anything.
#

read_patch_list() {
    _file="$repo_root/assets/patches/$1.txt"
    if [ ! -f "$_file" ]; then
        echo "error: patch list '$_file' does not exist." >&2
        exit 1
    fi
    # Same rules as read_patch_list() in scripts/librewolf-patches.py:
    # everything from the first '#' goes (so inline comments go too), then
    # surrounding whitespace, then whatever is left empty is dropped.
    sed -e 's/#.*//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "$_file" | grep .
}

patch_list=$(read_patch_list common)
for t in $selected; do
    patch_list="$patch_list
$(read_patch_list "$t")"
done
patch_count=$(echo "$patch_list" | grep -c .)
if [ "$patch_count" -eq 0 ]; then
    echo "error: no patches selected by --targets=$targets."
    exit 1
fi

# The assets/patches.txt shim this used to cross-check is gone (LW-M7-01). The
# enable/disable helpers now edit assets/patches/*.txt directly, which is what
# this script reads, so there is no longer a second copy that can drift.

echo "Targets: $(echo $selected | tr ' ' ',') (assets/patches/common.txt first)"
echo "Firefox: $firefox"
if [ -n "$tarball_warning" ]; then
    echo ""
    echo "!!! $tarball_warning"
    echo ""
fi
echo "Patches: $patch_count"

failed_patches=

#
# A unique scratch directory, cleaned up on every exit path.
#
# It used to be a hardcoded 'tmpdir92' that was rm -rf'd on start, so two
# concurrent runs deleted each other's tree mid-run. It stays under the repo
# root rather than in $TMPDIR because the extract is ~5GB and /tmp is often a
# tmpfs, and because the report is about this checkout.
#
tmpdir=$(mktemp -d "$repo_root/tmpdir92.XXXXXX") || {
    echo "error: cannot create a scratch directory under '$repo_root'."
    exit 1
}
# Removal on the normal path, on a failure exit, and on ^C - the old script
# only removed it at the end, so an interrupted run left ~5GB behind and the
# next run's `rm -rf tmpdir92` was what eventually collected it.
cleanup() {
    [ -n "$tmpdir" ] && [ -d "$tmpdir" ] && rm -rf "$tmpdir"
}
trap 'cleanup' EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM
trap 'cleanup; exit 129' HUP

echo "Using scratch directory '$tmpdir'..."
cd "$tmpdir" || exit 1
echo "Extracting '$firefox'..."
tar xf "$repo_root/$firefox" || { echo "error: extracting '$firefox' failed."; exit 1; }

# The directory inside the tarball is not firefox-$(cat ../version) in general.
# Mozilla names the ESR *artifact* firefox-153.0esr.source.tar.xz and the
# *directory* inside it firefox-153.0, so the version string is the wrong thing
# to compute this from - and deriving it from the tarball, rather than stripping
# a literal "esr" suffix, also survives whatever Mozilla renames next. It is
# also what makes --targets=android work at all: nothing here has to know how
# the ESR artifact name maps onto the directory it unpacks to.
#
# The first member of both the release and the ESR tarball is "./", not the top
# level directory, so `tar tf | head -1` is not enough: it yields ".", and `cd .`
# succeeds and would then test every patch against the extract root instead of
# the source tree. Hence the explicit skip of "", "." and "..".
#
# awk exits at the first usable member, which closes the pipe and stops tar and
# xz after a few MB instead of listing the whole ~10GB archive a second time.
ffdir=$(tar tf "$repo_root/$firefox" | awk '{ sub(/^\.\//, ""); sub(/\/.*/, ""); if ($0 != "" && $0 != "." && $0 != "..") { print; exit } }')
if [ -z "$ffdir" ]; then
    echo "error: cannot determine the directory inside '$firefox'."
    exit 1
fi
# Without this guard a failed extract leaves us in $tmpdir and every patch below
# would be tested against an empty directory.
cd "$ffdir" || { echo "error: '$ffdir' is not in '$firefox'."; exit 1; }

patch_out="$tmpdir/patch.tmp"

echo ""
echo "Testing patches..."

for curpatch in $patch_list; do
    echo ""
    echo "==> $curpatch:"
    echo ""
    # 2>&1: a missing target file is reported on stderr, and stderr is not part
    # of the report unless it is captured here.
    # </dev/null: with a missing target file patch asks "File to patch:" on the
    # terminal, and stdout is redirected to patchfail.out, so an interactive run
    # would hang on a prompt nobody can see. At EOF patch skips and exits 1.
    patch "$@" -p1 -i "$repo_root/$curpatch" < /dev/null > "$patch_out" 2>&1
    patch_status=$?
    cat "$patch_out"

    ######################
    s=""

    # Signal 1: patch's own verdict.
    if [ "$patch_status" -ne 0 ]; then
	s="$s exit=$patch_status"
	echo "---> patch exited $patch_status"
    fi

    # Signal 2: rejected hunks, printed so they can be read here.
    for j in $(grep -n 'rej$' "$patch_out" | awk '{ print $(NF); }'); do
	s="$s $j"
	echo "---[snip]---------- --> $j:"
	if [ -f "$j" ]; then
	    cat "$j"
	else
	    echo "(missing: $j)"
	fi
	echo "---[snip]----------"
    done

    if [ ! -z "$s" ]; then
	failed_patches="$failed_patches [$curpatch]"
    fi
    #######################

    rm -f "$patch_out"
    #patch -R -p1 -i ../../$i
done

cd "$repo_root"
echo ""
echo "Removing '$tmpdir'..."
cleanup
echo ""


if [ -n "$tarball_warning" ]; then
    echo "!!! $tarball_warning"
    echo ""
fi

if [ ! -z "$failed_patches" ]; then
    echo $failed_patches
    echo ""
    echo "error: Some patches failed!"
    exit 1
else
    echo "success: All patches where applied successfully."
    exit 0
fi
