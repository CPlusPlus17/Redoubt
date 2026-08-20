#!/bin/sh
#
# Regenerate the patches that only apply *with fuzz*.
#
# usage: ./scripts/fuzzfail.sh [--targets=<list>] [--use-desktop-tarball]
#
# For every patch in the selected lists this applies it to a pristine Firefox
# tree with --fuzz=0. A patch that needs fuzz rejects there; that patch is then
# rebuilt at zero fuzz through scripts/git-patchtree.sh and the result written
# next to it as <patch>.nofuzz. `make fixfuzz` runs this.
#
# Fuzz is NOT a failure. On the current desktop set - 24 common + 36 desktop
# patches - 31 hunks apply with fuzz and 23 distinct patches reject at
# --fuzz=0, and that is normal: it is the reason this script exists rather than
# a sign that something is broken. What this script reports as an error is the
# other thing --fuzz=0 turns up, below.
#
# (Those two numbers were measured by LW-M1-16, not copied: 31 is
# `grep -c 'with fuzz'` over a real ./scripts/check-patchfail.sh run, 23 is the
# patch list this script printed on a full run. The header used to say 29 and
# docs/android/AGENTS.md still says 30 hunks / 22 patches / 59 patches, which
# were true before the patch set changed. Re-measure rather than trust any of
# them.)
#
# Landmine L5 (docs/android/AGENTS.md), the reason this file was rewritten
# -----------------------------------------------------------------------
#
# This used to decide "did the patch apply" by grepping patch's *stdout* for
# .rej files, exactly as scripts/check-patchfail.sh did before LW-M0-11. That
# fails open. When a hunk's target file is missing - the shape of an upstream
# rename - patch writes no .rej file at all: it prints "can't find file to
# patch" on *stderr*, then "Skipping patch. / 1 out of 1 hunk ignored", and
# exits 1. The .rej grep saw nothing, so the patch was silently treated as
# clean: no regeneration, no report, no non-zero exit.
#
# The same three fixes LW-M0-11 made in check-patchfail.sh are carried over:
#
#   * patch's exit status is the authoritative signal;
#   * 2>&1, so the stderr line that explains the failure is actually captured;
#   * < /dev/null, so a missing target file cannot hang the run on patch's
#     "File to patch:" prompt - which is invisible here, because patch's output
#     is redirected to a temp file.
#
# The .rej scan is kept as a second signal, and it is what tells the two cases
# apart:
#
#   exit 0                  clean at zero fuzz, nothing to do.
#   .rej files written      fuzz or a real reject - regenerate the patch.
#   exit != 0 and no .rej   the L5 shape. Regeneration cannot fix it (there is
#                           nothing to apply against), so it is reported and
#                           the script exits non-zero.
#
# Exit status is 0 when nothing needed attention beyond fuzz, and 1 when any
# patch failed in a way regeneration does not address.
#
# LW-M1-16, two fixes
# -------------------
#
# 1. `make fixfuzz` had stopped regenerating anything at all. LW-M1-15 rewrote
#    scripts/git-patchtree.sh: the bare `git-patchtree.sh <patch>` form, which
#    left a tree in ./firefox-$(cat version) for the caller to diff and delete,
#    is gone and now exits 2 with an explanation. This script still called it
#    that way inside a subshell ending in `|| exit 1`, so every fuzzy patch -
#    all 23 of them - came back under "patches that need a human, not a fuzz
#    rebuild", and the run exited 1 having written no .nofuzz. The whole
#    subshell (call, cd, git diff, rm -rf) is now the single -o call
#    git-patchtree.sh documents, with this script's own --targets and
#    --use-desktop-tarball forwarded so an android run regenerates correctly
#    instead of being refused.
#
#    It slipped because the two files were owned by different tasks, and
#    because `make -n fixfuzz` - the verify that was supposed to catch it -
#    prints commands without running any of them, so it cannot see a runtime
#    failure. Verify this by running a regeneration and looking for the file.
#
# 2. This script used to write commit.gpgsign into the maintainer's *global*
#    git configuration - false before the regeneration, true after it - to stop
#    git-patchtree.sh's commits prompting for a signature. Three things wrong
#    with that: a repo script must not write the user's global git settings at
#    all; the restore was a hardcoded `true`, so anyone who had the setting
#    unset or false got commit signing switched on for every repository they
#    own; and ^C between the two calls left signing globally off. Both lines
#    are gone. git-patchtree.sh passes `-c commit.gpgsign=false` (plus an
#    identity, core.hooksPath and the diff settings) on each git command it
#    runs, which is per-invocation and cannot leak or be interrupted half way.
#
#    Nothing in this file writes git configuration on any path, including the
#    error paths and the cleanup traps.
#

KNOWN_TARGETS="desktop android"

targets="desktop"
use_desktop_tarball=0

while [ $# -gt 0 ]; do
    case "$1" in
        --targets=*)
            targets=${1#--targets=}
            ;;
        --targets)
            shift
            [ $# -gt 0 ] || { echo "error: --targets needs a value, e.g. --targets=android" >&2; exit 2; }
            targets=$1
            ;;
        --use-desktop-tarball)
            use_desktop_tarball=1
            ;;
        -h|--help)
            echo "usage: $0 [--targets=<list>] [--use-desktop-tarball]"
            echo ""
            echo "  --targets=<list>       comma separated, from: $KNOWN_TARGETS"
            echo "                         (default: desktop). assets/patches/common.txt"
            echo "                         is always walked first."
            echo "  --use-desktop-tarball  use the desktop tarball for an android run when"
            echo "                         the ESR one is not downloaded."
            exit 0
            ;;
        *)
            # Unlike check-patchfail.sh this does NOT forward unknown options to
            # patch: --fuzz=0 is the whole premise of the tool and letting it be
            # overridden from the command line would make the output meaningless.
            echo "error: unknown option '$1'" >&2
            echo "usage: $0 [--targets=<list>] [--use-desktop-tarball]" >&2
            exit 2
            ;;
    esac
    shift
done

#
# Targets, resolved before anything is touched. Same rules as
# selected_targets() in scripts/librewolf-patches.py and the identical block in
# scripts/check-patchfail.sh: common.txt first, then the selected lists in a
# fixed order (desktop before android), deduplicated.
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
desktop_version=$(cat version)

# Release track, same rule as the Makefile: android without desktop is Firefox
# ESR (./version.android), everything else is Firefox release (./version).
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
        echo "  in one tree. Run them one at a time; see docs/android/TRACK.md."
        exit 1
    fi
fi

firefox=firefox-$ffversion.source.tar.xz
tarball_warning=""
if [ ! -f "$firefox" ]; then
    # The ESR tarball is a separate ~766MB download and this script will not
    # start one. Same policy as scripts/check-patchfail.sh.
    if [ "$has_android" -eq 1 ] && [ "$has_desktop" -eq 0 ] && [ "$use_desktop_tarball" -eq 1 ] \
       && [ -f "firefox-$desktop_version.source.tar.xz" ]; then
        tarball_warning="WARNING: using firefox-$desktop_version.source.tar.xz (desktop) instead of the android base $firefox ($ffversion). Any .nofuzz produced is against the wrong Firefox."
        firefox="firefox-$desktop_version.source.tar.xz"
        ffversion=$desktop_version
    else
        echo "error: '$firefox' does not exist."
        if [ "$has_android" -eq 1 ] && [ "$has_desktop" -eq 0 ]; then
            echo ""
            echo "  --targets=android needs the Firefox ESR tarball named by"
            echo "  ./version.android ($ffversion), a separate ~766MB download."
            echo ""
            echo "  Fetch it:  make fetch TARGETS=android"
            echo "  or:        ./scripts/fuzzfail.sh --targets=android --use-desktop-tarball"
            echo "             (desktop base - indicative only)"
        fi
        exit 1
    fi
fi

read_patch_list() {
    _file="$repo_root/assets/patches/$1.txt"
    if [ ! -f "$_file" ]; then
        echo "error: patch list '$_file' does not exist." >&2
        exit 1
    fi
    # Same rules as read_patch_list() in scripts/librewolf-patches.py: strip
    # from the first '#' (inline comments included), strip whitespace, drop
    # what is left empty.
    sed -e 's/#.*//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "$_file" | grep .
}

patch_list=$(read_patch_list common)
for t in $selected; do
    patch_list="$patch_list
$(read_patch_list "$t")"
done
if [ -z "$(echo "$patch_list" | grep .)" ]; then
    echo "error: no patches selected by --targets=$targets."
    exit 1
fi

# The target list, in the spelling scripts/git-patchtree.sh wants: the same
# normalised, deduplicated set resolved above, comma separated. Forwarding it
# is what makes an android regeneration correct rather than refused - see the
# LW-M1-16 note in the header.
patchtree_targets=$(echo "$selected" | sed -e 's/^ *//' -e 's/ *$//' -e 's/  */,/g')

if [ -n "$tarball_warning" ]; then
    echo "!!! $tarball_warning" >&2
fi

#
# A unique scratch directory, cleaned up on every exit path - it used to be a
# hardcoded 'tmpdir92' that was rm -rf'd on start, so two concurrent runs (of
# this script, or of scripts/check-patchfail.sh, which used the same name)
# deleted each other's tree mid-run.
#
# The traps below cover ^C, TERM and HUP, but not SIGKILL or a power cut, and
# the tree inside is ~4.7GB. Neither `make clean` nor .gitignore knows the
# tmpdir92.* prefix - three scripts create it now (this one,
# check-patchfail.sh, git-patchtree.sh) - so a killed run leaves multi-GB
# untracked directories at the repo root for everyone. Reported by LW-M1-16,
# which owns neither of those two files; until they are fixed, `rm -rf
# tmpdir92.*` at the repo root is the cleanup.
#
tmpdir=$(mktemp -d "$repo_root/tmpdir92.XXXXXX") || {
    echo "error: cannot create a scratch directory under '$repo_root'."
    exit 1
}
cleanup() {
    [ -n "$tmpdir" ] && [ -d "$tmpdir" ] && rm -rf "$tmpdir"
}
trap 'cleanup' EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM
trap 'cleanup; exit 129' HUP

cd "$tmpdir" || exit 1
tar xf "$repo_root/$firefox" || { echo "error: extracting '$firefox' failed."; exit 1; }

# The directory inside the tarball is not firefox-$ffversion in general: the ESR
# artifact firefox-153.0esr.source.tar.xz unpacks to firefox-153.0/. Derive it
# from the tarball, the same way scripts/check-patchfail.sh and the Makefile do
# since LW-M0-14. The first member of both tarballs is "./", so "", "." and ".."
# are skipped explicitly; awk exits at the first usable member so tar and xz are
# stopped after a few MB.
ffdir=$(tar tf "$repo_root/$firefox" | awk '{ sub(/^\.\//, ""); sub(/\/.*/, ""); if ($0 != "" && $0 != "." && $0 != "..") { print; exit } }')
if [ -z "$ffdir" ]; then
    echo "error: cannot determine the directory inside '$firefox'."
    exit 1
fi
cd "$ffdir" || { echo "error: '$ffdir' is not in '$firefox'."; exit 1; }

patch_out="$tmpdir/patch.tmp"
regen_log="$tmpdir/patchtree.log"
hard_failures=

#
# The regeneration, as one call into scripts/git-patchtree.sh.
#
# $1 is the patch, repo-relative; $2 is where the rebuilt patch goes, also
# repo-relative. Run from the repo root, because git-patchtree.sh resolves both
# of those and its own ./version against $PWD.
#
# --expect-tarball is the interlock: this script has already picked a tarball
# and applied the patch against it, git-patchtree.sh picks one again from a
# *copy* of the same version-resolution block, and if the two ever disagree the
# rebuild is against the wrong Firefox. It refuses rather than writing one.
#
# No git configuration is touched here, globally or otherwise.
# git-patchtree.sh runs every git command through `git -c commit.gpgsign=false
# -c user.name=... -c core.hooksPath=/dev/null ...`, which is the per-invocation
# form of what this function's ancestor did by writing the maintainer's
# ~/.gitconfig - see the LW-M1-16 note in the header.
#
run_patchtree() {
    if [ "$use_desktop_tarball" -eq 1 ]; then
        scripts/git-patchtree.sh --targets="$patchtree_targets" --use-desktop-tarball \
            --expect-tarball="$firefox" -o "$2" "$1"
    else
        scripts/git-patchtree.sh --targets="$patchtree_targets" \
            --expect-tarball="$firefox" -o "$2" "$1"
    fi
}

for curpatch in $patch_list; do
    # 2>&1 and </dev/null: see the L5 note in the header. Without them the
    # explanation goes to a terminal nobody is reading and a missing target
    # file blocks on an invisible "File to patch:" prompt.
    patch --fuzz=0 -p1 -i "$repo_root/$curpatch" < /dev/null > "$patch_out" 2>&1
    patch_status=$?

    rejects=""
    for j in $(grep -n 'rej$' "$patch_out" | awk '{ print $(NF); }'); do
        rejects="$rejects $j"
    done

    if [ "$patch_status" -eq 0 ]; then
        rm -f "$patch_out"
        continue
    fi

    if [ -z "$rejects" ]; then
        # Landmine L5: patch refused and wrote no .rej. Almost always a missing
        # target file, i.e. upstream renamed or removed it. Regenerating cannot
        # help - there is nothing to apply against - so say so and fail.
        echo "error: $curpatch did not apply and produced no .rej (patch exited $patch_status)" >&2
        sed -e 's/^/    /' "$patch_out" >&2
        hard_failures="$hard_failures [$curpatch]"
        rm -f "$patch_out"
        continue
    fi

    # Ordinary fuzz/reject: rebuild the patch at zero fuzz.
    echo "$curpatch"
    echo "  regenerating $curpatch.nofuzz from $firefox (a few minutes)..." >&2

    # Any .nofuzz left by an earlier run goes first. git-patchtree.sh writes
    # nothing when it fails, so a stale file would otherwise sit there looking
    # like the output of this run - and it is stale by definition, because the
    # patch is fuzzy again.
    rm -f "$repo_root/$curpatch.nofuzz"

    # git-patchtree.sh is chatty (extract progress, patch output, the line it
    # prints on success). Keep it out of the fuzzy-patch list on stdout and show
    # it only when something went wrong, which is when it is worth reading.
    (
        cd "$repo_root" || exit 1
        run_patchtree "$curpatch" "$curpatch.nofuzz"
    ) > "$regen_log" 2>&1
    regen_status=$?

    # The regeneration used to be fire and forget: its exit status was dropped
    # and nobody looked at whether a .nofuzz had appeared, which is the same
    # fail-open shape as the .rej-only detection above. Both are checked, and
    # neither alone is enough - a script can exit 0 having written nothing, and
    # a non-empty file can be left over from something else.
    if [ "$regen_status" -ne 0 ]; then
        echo "error: regenerating $curpatch.nofuzz failed (git-patchtree.sh exited $regen_status)" >&2
        sed -e 's/^/    /' "$regen_log" >&2
        hard_failures="$hard_failures [$curpatch]"
    elif [ ! -s "$repo_root/$curpatch.nofuzz" ]; then
        echo "error: git-patchtree.sh exited 0 but wrote no $curpatch.nofuzz" >&2
        sed -e 's/^/    /' "$regen_log" >&2
        hard_failures="$hard_failures [$curpatch]"
    fi

    rm -f "$patch_out" "$regen_log"
done

cd "$repo_root"
cleanup

if [ -n "$tarball_warning" ]; then
    echo "!!! $tarball_warning" >&2
fi

if [ -n "$hard_failures" ]; then
    echo "" >&2
    echo "error: patches that need a human, not a fuzz rebuild:$hard_failures" >&2
    exit 1
fi
exit 0
