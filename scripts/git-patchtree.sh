#!/bin/sh
#
# Build a throwaway git repository out of a pristine Firefox tree with one
# LibreWolf patch applied, so that patch can be edited by hand or rebuilt at
# zero fuzz.
#
# usage: ./scripts/git-patchtree.sh (-o <file> | --edit) [--targets=<list>]
#                                   [--use-desktop-tarball] [--keep]
#                                   [--expect-tarball=<name>] <patch>
#
#   <patch>                the patch to apply, e.g.
#                          patches/sed-patches/disable-pocket.patch
#   -o <file>              rebuild <patch> at zero fuzz, write the result to
#                          <file>, and remove the tree.
#   --edit                 keep the tree and print where it is, to edit by hand.
#   --targets=<list>       comma separated, from 'desktop' and 'android'
#                          (default: desktop). Chooses which Firefox the tree
#                          is built from - see "Which Firefox tarball" below.
#   --keep                 keep the tree even when -o was given.
#   --use-desktop-tarball  build an android run from the desktop tarball when
#                          the ESR one is not downloaded. Loudly warns; what
#                          comes out is against the wrong Firefox.
#   --expect-tarball=<n>   refuse to run unless the tarball resolved below is
#                          exactly <n>. For callers that already picked a
#                          tarball - see "The --expect-tarball interlock".
#
# The two modes
# -------------
#
# --edit is the "make a patch" helper README.md documents: it leaves a git repo
# whose first commit is the pristine files and whose second commit is the
# patch, so you can edit the tree and `git diff` a new patch out of it. The
# path is printed at the end, together with the exact diff command.
#
# -o is the batch half scripts/fuzzfail.sh drives: apply, commit, diff, write,
# delete the tree. Nothing is left behind, and nothing is written unless every
# check below passed.
#
# The two modes also differ in how hard a failed `patch` is treated. Fixing a
# patch upstream broke is the whole point of --edit, so there a failed apply is
# a warning and the tree (with its .rej files) is kept. In -o mode there is
# nobody watching, so it is fatal and no output file is written.
#
# One of the two is required, and that is deliberate: this script used to take
# a patch and nothing else, and its caller then reached into
# ./firefox-$(cat version) itself. That directory is gone (see below), so the
# bare form has no meaning any more - and left as a silent success it would
# hand an un-updated caller a tree at a path that, in a checkout where
# ./firefox-$(cat version) happens to exist, is *inside the librewolf git
# repo*. `git diff` there describes librewolf's own history and the caller's
# `rm -rf` deletes a real 4.7GB extract. So the bare form is refused, before
# anything is extracted, with the replacement command in the message.
#
# Where the tree goes  (LW-M1-15)
# -------------------
#
# It used to be $PWD/firefox-$(cat version), which this script `rm -rf`'d on
# start. That is the same directory `make dir` extracts to and `make build`
# builds in, so `make fixfuzz` could delete a 4.7GB tree someone was mid-build
# on, with no warning and no prompt, and two concurrent runs destroyed each
# other's tree. It is now a private `mktemp -d` scratch directory removed by a
# cleanup trap, the same pattern scripts/check-patchfail.sh and
# scripts/fuzzfail.sh use since LW-M1-11.
#
# Like those two it stays *under the repo root* rather than in $TMPDIR: the
# extract is ~4.7GB and /tmp here is a 31GB tmpfs shared with everything else
# on the machine, so an extract per concurrent run is not something to put in
# RAM. Consequence worth knowing: the scratch directories are named
# tmpdir92.XXXXXX, and neither .gitignore nor `make clean` covers that prefix,
# so a run killed past its traps (SIGKILL, power cut) leaves a ~4.7GB untracked
# directory at the repo root that nothing collects. Reported by LW-M1-16, which
# owns neither of those files; `rm -rf tmpdir92.*` at the repo root until then.
#
# Which Firefox tarball  (LW-M1-15)
# ---------------------
#
# The tracks differ: ./version is desktop (Firefox release), ./version.android
# is android (Firefox ESR). This script only ever knew about ./version, so a
# patch that only exists on the android list could not be rebuilt at all - it
# would be regenerated against desktop context and the result would apply
# cleanly while being wrong. That is why scripts/fuzzfail.sh used to refuse to
# regenerate anything on an android run; since LW-M1-16 it forwards its own
# --targets here instead.
#
# Same rule as the Makefile and the two sibling scripts: android without
# desktop uses ./version.android, anything else uses ./version, and asking for
# both when the two have diverged is refused rather than silently answered with
# one of them.
#
# The ESR tarball is a separate ~766MB download and this script will never
# start one: `make fixfuzz` is run casually and must not begin a download.
# When it is missing the run fails with the fetch command to run, and
# --use-desktop-tarball is the deliberate, noisy escape hatch. Precedent is
# scripts/fuzzfail.sh, which does the same for the same reason.
#
# Because the default is desktop and getting it wrong is silent, a patch that
# appears *only* in assets/patches/android.txt is refused outright when
# --targets was not given, rather than rebuilt against the desktop tree.
#
# The --expect-tarball interlock  (LW-M1-16)
# ------------------------------
#
# The block below that turns --targets into a tarball name is a *copy* of the
# one in scripts/fuzzfail.sh, scripts/check-patchfail.sh and the Makefile. That
# is fine while the four agree, and silently catastrophic when they drift: the
# caller detects fuzz against tarball A, this script rebuilds against tarball B,
# and the result is verified at --fuzz=0 against B and written out. A patch that
# is wrong *and* applies cleanly forever is the worst artefact in this repo.
#
# So a caller that has already resolved a tarball passes its name in, and this
# script refuses to run at all if it resolved a different one. fuzzfail.sh does
# this on every regeneration. It costs one string compare and it turns a silent
# wrong-base rebuild into a loud refusal before anything is extracted.
#
# Three fail-open bugs this also closes
# -------------------------------------
#
# 1. `patch`'s exit status was thrown away. A patch that half applied was
#    diffed anyway, so the rebuilt patch silently *lost* the rejected hunks -
#    landmine L5 in docs/android/AGENTS.md, in its worst form, because the
#    output is a patch file that then applies cleanly forever. stderr is now
#    captured (2>&1) and stdin closed (< /dev/null, so a missing target file
#    cannot block on patch's "File to patch:" prompt).
#
# 2. The pre-patch commit added every path named in a `+++` line, including the
#    files the patch *creates*. Those do not exist yet, `git add` failed, and
#    the `&&` chain skipped `git commit -am original` - leaving no first commit
#    at all, so `git rev-list --max-parents=0 HEAD` resolved to the only commit
#    there was and the diff came out empty. Nine such `--- /dev/null` hunks are
#    in the current patch set. Files are now added if and only if they exist,
#    and both `---` and `+++` sides are read so a *deletion* hunk gets its file
#    tracked before it disappears (none today, but the same bug in reverse).
#
# 3. Nothing checked that the rebuilt patch was any good. It is now re-applied
#    to the restored original tree with --fuzz=0 --dry-run before it is written
#    to -o, which is exactly the property the caller wanted, so a patch that
#    does not have it never reaches disk.
#

# No globbing anywhere in this script; patch target paths are word-split on
# purpose and must not be expanded a second time.
set -f

KNOWN_TARGETS="desktop android"

targets=""
targets_given=0
use_desktop_tarball=0
outfile=""
edit=0
keep=0
patcharg=""
expect_tarball=""

usage() {
    echo "usage: $0 (-o <file> | --edit) [--targets=<list>] [--use-desktop-tarball] [--keep]"
    echo "          [--expect-tarball=<name>] <patch>"
    echo ""
    echo "  <patch>                the patch to apply, e.g. patches/sed-patches/disable-pocket.patch"
    echo "  -o <file>              rebuild <patch> at zero fuzz into <file>, remove the tree."
    echo "  --edit                 keep the tree and print where it is, to edit by hand."
    echo "  --targets=<list>       comma separated, from: $KNOWN_TARGETS (default: desktop)."
    echo "                         Picks the Firefox the tree is built from: desktop is"
    echo "                         ./version, android alone is ./version.android (ESR)."
    echo "  --keep                 keep the tree even with -o."
    echo "  --use-desktop-tarball  build an android run from the desktop tarball when the"
    echo "                         ESR one is not downloaded (wrong base - warns loudly)."
    echo "  --expect-tarball=<name>  refuse to run unless the tarball resolved from the"
    echo "                         options above is exactly <name>."
}

while [ $# -gt 0 ]; do
    case "$1" in
        --targets=*)
            targets=${1#--targets=}
            targets_given=1
            ;;
        --targets)
            shift
            [ $# -gt 0 ] || { echo "error: --targets needs a value, e.g. --targets=android" >&2; exit 2; }
            targets=$1
            targets_given=1
            ;;
        -o|--output)
            shift
            [ $# -gt 0 ] || { echo "error: -o needs a file name" >&2; exit 2; }
            outfile=$1
            ;;
        --output=*)
            outfile=${1#--output=}
            ;;
        -e|--edit)
            edit=1
            ;;
        --keep)
            keep=1
            ;;
        --use-desktop-tarball)
            use_desktop_tarball=1
            ;;
        --expect-tarball=*)
            expect_tarball=${1#--expect-tarball=}
            ;;
        --expect-tarball)
            shift
            [ $# -gt 0 ] || { echo "error: --expect-tarball needs a file name" >&2; exit 2; }
            expect_tarball=$1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            # Deliberately not forwarded to `patch`, unlike check-patchfail.sh:
            # the fuzz this applies with is the whole premise of the rebuild and
            # letting it be overridden from the command line would produce a
            # patch nobody can reason about.
            echo "error: unknown option '$1'" >&2
            usage >&2
            exit 2
            ;;
        *)
            if [ -n "$patcharg" ]; then
                echo "error: only one patch file can be given (got '$patcharg' and '$1')" >&2
                exit 2
            fi
            patcharg=$1
            ;;
    esac
    shift
done

if [ -z "$patcharg" ]; then
    echo "error: no patch file given." >&2
    usage >&2
    exit 2
fi

if [ -n "$outfile" ] && [ "$edit" -eq 1 ]; then
    echo "error: -o and --edit are the two modes; pick one." >&2
    echo "  (-o already keeps the tree if you add --keep.)" >&2
    exit 2
fi
if [ -z "$outfile" ] && [ "$edit" -eq 0 ]; then
    # Refused rather than defaulted, before anything is extracted. See "The two
    # modes" at the top: the bare form used to mean "leave a tree in
    # ./firefox-$(cat version) and let the caller deal with it", and there is no
    # such tree any more.
    echo "error: say which of the two things you want:" >&2
    echo "" >&2
    echo "  $0 --edit $patcharg" >&2
    echo "      extract a tree with the patch applied, keep it, print where it is." >&2
    echo "      This is README.md's 'Development: Existing patches' workflow." >&2
    echo "" >&2
    echo "  $0 -o $patcharg.nofuzz $patcharg" >&2
    echo "      rebuild the patch at zero fuzz into that file and remove the tree." >&2
    echo "" >&2
    echo "  The bare form used to extract into ./firefox-\$(cat version) and leave the" >&2
    echo "  tree there for the caller to diff and delete. LW-M1-15 removed that - the" >&2
    echo "  tree is a private scratch directory now - and LW-M1-16 moved the one caller" >&2
    echo "  (scripts/fuzzfail.sh) onto -o. Any other caller wants the same shape:" >&2
    echo "" >&2
    echo "      scripts/git-patchtree.sh --targets=<target> -o \"\$curpatch.nofuzz\" \"\$curpatch\"" >&2
    echo "" >&2
    exit 2
fi

if [ ! -f version ]; then
    echo "error: 'version' does not exist. Are you in the right folder?" >&2
    exit 1
fi
# -P: the physical path, so the patch argument can be canonicalised below and
# still be recognised as repo-relative when $PWD was reached through a symlink.
repo_root=$(pwd -P)
desktop_version=$(cat version)

#
# The patch, resolved and named relative to the repo root so it can be looked
# up in the patch lists.
#

case "$patcharg" in
    /*) patchpath=$patcharg ;;
    *)  patchpath=$repo_root/$patcharg ;;
esac
if [ ! -f "$patchpath" ]; then
    echo "error: '$patcharg' is not a file - the first non-option argument is the patch to apply." >&2
    exit 1
fi
# Canonicalise, so './patches/x.patch', 'patches/x.patch' and the absolute form
# all reduce to the same string. The patch lists are matched literally below and
# an unrecognised spelling would silently turn the android guard off.
patchdir=$(cd "$(dirname "$patchpath")" && pwd -P) || {
    echo "error: cannot resolve the directory of '$patcharg'." >&2
    exit 1
}
patchpath=$patchdir/$(basename "$patchpath")
patchrel=$patchpath
case "$patchrel" in
    "$repo_root"/*) patchrel=${patchrel#"$repo_root"/} ;;
esac

read_patch_list() {
    _file="$repo_root/assets/patches/$1.txt"
    # Same rules as read_patch_list() in scripts/librewolf-patches.py: strip
    # from the first '#' (inline comments included), strip whitespace, drop
    # what is left empty.
    sed -e 's/#.*//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "$_file" | grep .
}

# Which list the patch lives on. Only used to keep an android-only patch from
# being rebuilt against desktop context by accident - it is a guard, not a
# default, because a patch on no list at all (a new one) has no track to infer.
patch_track=unknown
if [ -f "$repo_root/assets/patches/common.txt" ] &&
   [ -f "$repo_root/assets/patches/desktop.txt" ] &&
   [ -f "$repo_root/assets/patches/android.txt" ]; then
    in_common=0
    in_desktop=0
    in_android=0
    read_patch_list common  | grep -Fxq "$patchrel" && in_common=1
    read_patch_list desktop | grep -Fxq "$patchrel" && in_desktop=1
    read_patch_list android | grep -Fxq "$patchrel" && in_android=1
    if [ "$in_common" -eq 1 ]; then
        patch_track=common
    elif [ "$in_android" -eq 1 ] && [ "$in_desktop" -eq 0 ]; then
        patch_track=android
    elif [ "$in_desktop" -eq 1 ] && [ "$in_android" -eq 0 ]; then
        patch_track=desktop
    fi
fi

if [ "$targets_given" -eq 0 ]; then
    if [ "$patch_track" = "android" ]; then
        echo "error: '$patchrel' is listed only in assets/patches/android.txt." >&2
        echo "  The default target is desktop, and rebuilding an android patch against the" >&2
        echo "  desktop tree produces a patch that applies cleanly and is wrong. Say which" >&2
        echo "  tree you mean:" >&2
        echo "    $0 --targets=android $patchrel" >&2
        exit 2
    fi
    targets="desktop"
fi

#
# Targets, resolved before anything is touched or extracted, so a typo costs
# nothing. Same rules as selected_targets() in scripts/librewolf-patches.py and
# the identical blocks in scripts/check-patchfail.sh and scripts/fuzzfail.sh.
#

for t in $(echo "$targets" | tr ',' ' '); do
    known=0
    for k in $KNOWN_TARGETS; do
        [ "$t" = "$k" ] && known=1
    done
    if [ "$known" -eq 0 ]; then
        echo "error: unknown target '$t' in --targets=$targets" >&2
        echo "  known targets: $KNOWN_TARGETS" >&2
        echo "  'common' is not a target - it says which lists a patch is on, not which" >&2
        echo "  Firefox to build the tree from." >&2
        exit 2
    fi
done

has_desktop=0
has_android=0
for t in $(echo "$targets" | tr ',' ' '); do
    [ "$t" = "desktop" ] && has_desktop=1
    [ "$t" = "android" ] && has_android=1
done
if [ "$has_desktop" -eq 0 ] && [ "$has_android" -eq 0 ]; then
    echo "error: --targets is empty; expected one or more of: $KNOWN_TARGETS" >&2
    exit 2
fi

# The guard above only fires when --targets was omitted. When it was given
# explicitly the maintainer may well know better - say what looks wrong and go.
if [ "$patch_track" = "android" ] && [ "$has_android" -eq 0 ]; then
    echo "warning: '$patchrel' is on the android list only, but --targets=$targets builds" >&2
    echo "warning: the desktop tree. The rebuilt patch will carry desktop context." >&2
fi
if [ "$patch_track" = "desktop" ] && [ "$has_desktop" -eq 0 ]; then
    echo "warning: '$patchrel' is on the desktop list only, but --targets=$targets builds" >&2
    echo "warning: the android tree. The rebuilt patch will carry ESR context." >&2
fi

#
# Release track, same rule as the Makefile: android without desktop is Firefox
# ESR (./version.android), everything else is Firefox release (./version).
#

version_file="version"
if [ "$has_android" -eq 1 ] && [ "$has_desktop" -eq 0 ]; then
    version_file="version.android"
    if [ ! -f "$version_file" ]; then
        echo "error: '--targets=android' needs './version.android' - see docs/android/TRACK.md" >&2
        exit 1
    fi
fi
ffversion=$(cat "$version_file")
if [ -z "$ffversion" ]; then
    echo "error: '$version_file' is empty." >&2
    exit 1
fi

if [ "$has_android" -eq 1 ] && [ "$has_desktop" -eq 1 ] && [ -f version.android ]; then
    android_version=$(cat version.android)
    if [ "$ffversion" != "$android_version" ]; then
        echo "error: --targets=$targets wants desktop $ffversion and android $android_version" >&2
        echo "  in one tree. A patch is rebuilt against one Firefox; pick it:" >&2
        echo "    $0 --targets=desktop $patchrel" >&2
        echo "    $0 --targets=android $patchrel" >&2
        echo "  See docs/android/TRACK.md." >&2
        exit 1
    fi
fi

firefox=firefox-$ffversion.source.tar.xz
tarball_warning=""
if [ ! -f "$firefox" ]; then
    if [ "$has_android" -eq 1 ] && [ "$has_desktop" -eq 0 ] && [ "$use_desktop_tarball" -eq 1 ] &&
       [ -f "firefox-$desktop_version.source.tar.xz" ]; then
        tarball_warning="WARNING: built from firefox-$desktop_version.source.tar.xz (desktop, $desktop_version), NOT the android base $firefox ($ffversion). Any patch produced is against the wrong Firefox."
        firefox="firefox-$desktop_version.source.tar.xz"
        ffversion=$desktop_version
    else
        echo "error: '$firefox' does not exist." >&2
        if [ "$has_android" -eq 1 ] && [ "$has_desktop" -eq 0 ]; then
            echo "" >&2
            echo "  --targets=android rebuilds against the Firefox ESR tarball named by" >&2
            echo "  ./version.android ($ffversion), which is a separate ~766MB download from" >&2
            echo "  the desktop one. This script will not start it for you." >&2
            echo "" >&2
            echo "  Fetch it:  make fetch TARGETS=android" >&2
            echo "  or:        $0 --targets=android --use-desktop-tarball $patchrel" >&2
            echo "             (desktop base - the result is against the wrong Firefox)" >&2
        fi
        exit 1
    fi
fi

# The interlock described at the top. Checked *after* the --use-desktop-tarball
# fallback above, because that fallback is part of what the caller has to agree
# with: a caller that fell back to desktop passes --use-desktop-tarball too, and
# then both sides land on the same name.
if [ -n "$expect_tarball" ] && [ "$expect_tarball" != "$firefox" ]; then
    echo "error: --expect-tarball=$expect_tarball, but --targets=$targets resolves to" >&2
    echo "  $firefox here." >&2
    echo "  The caller found the patch fuzzy against one Firefox and this would rebuild" >&2
    echo "  it against another, then verify the result at --fuzz=0 against that other" >&2
    echo "  one and write it out - a patch that is wrong and applies cleanly forever." >&2
    echo "  Pass the same --targets and --use-desktop-tarball to both sides." >&2
    exit 1
fi

#
# The output file, checked before the extract so a bad path costs no time.
#

outpath=""
if [ -n "$outfile" ]; then
    case "$outfile" in
        /*) outpath=$outfile ;;
        *)  outpath=$repo_root/$outfile ;;
    esac
    outdir=$(dirname "$outpath")
    if [ ! -d "$outdir" ]; then
        echo "error: output directory '$outdir' does not exist." >&2
        exit 1
    fi
fi

if [ -n "$tarball_warning" ]; then
    echo "" >&2
    echo "!!! $tarball_warning" >&2
    echo "" >&2
fi

#
# A unique scratch directory, cleaned up on every exit path including ^C.
# See "Where the tree goes" at the top for why it is here and not in $TMPDIR.
#
tmpdir=$(mktemp -d "$repo_root/tmpdir92.XXXXXX") || {
    echo "error: cannot create a scratch directory under '$repo_root'." >&2
    exit 1
}
keep_tree=$keep
cleanup() {
    if [ "$keep_tree" -eq 0 ] && [ -n "$tmpdir" ] && [ -d "$tmpdir" ]; then
        rm -rf "$tmpdir"
    fi
}
trap 'cleanup' EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM
trap 'cleanup; exit 129' HUP

# Every git command runs through this. The scratch repo is a disposable
# artefact, so it must not depend on - or disturb - the maintainer's git setup:
#
#   commit.gpgsign  a signing prompt in the middle of `make fixfuzz` is not
#                   wanted, and this is why fuzzfail.sh used to flip the
#                   *global* setting around the call (and set it to true
#                   afterwards whether or not it started that way).
#   user.name/email so this works in a container with no git identity.
#   core.hooksPath  so a global hook cannot run against this tree.
#   diff.noprefix, diff.mnemonicPrefix, core.quotepath
#                   both prefix settings and a quoted path can change `git
#                   diff` output into something GNU patch cannot apply at -p1.
#                   The diff below additionally passes --src-prefix/--dst-prefix
#                   and --no-ext-diff/--no-renames/--no-color/-U3, which is the
#                   rest of that list (an external differ, rename detection,
#                   colour, a different context size).
#   core.autocrlf   so line endings survive the round trip unchanged.
git_() {
    git -c commit.gpgsign=false \
        -c tag.gpgsign=false \
        -c user.name="LibreWolf patch tree" \
        -c user.email="patchtree@librewolf.invalid" \
        -c core.hooksPath=/dev/null \
        -c core.autocrlf=false \
        -c core.safecrlf=false \
        -c core.quotepath=false \
        -c init.defaultBranch=patchtree \
        -c advice.detachedHead=false \
        -c diff.noprefix=false \
        -c diff.mnemonicPrefix=false \
        -c diff.relative=false \
        "$@"
}

# `git diff` restricted to what GNU patch can read back at -p1.
git_diff() {
    git_ diff --no-ext-diff --no-textconv --no-color --no-renames \
        -U3 --src-prefix=a/ --dst-prefix=b/ "$@"
}

echo "git-patchtree: patch   $patchrel"
echo "git-patchtree: firefox $firefox"
echo "git-patchtree: scratch $tmpdir"

cd "$tmpdir" || exit 1
echo "git-patchtree: extracting '$firefox'..."
tar xf "$repo_root/$firefox" || { echo "error: extracting '$firefox' failed." >&2; exit 1; }

# The directory inside the tarball is not firefox-$ffversion in general: the
# ESR artifact firefox-153.0esr.source.tar.xz unpacks to firefox-153.0/. Derive
# it from the tarball, the same way scripts/check-patchfail.sh, scripts/
# fuzzfail.sh and the Makefile do since LW-M0-14. The first member of both
# tarballs is "./", so "", "." and ".." are skipped explicitly; awk exits at the
# first usable member so tar and xz stop after a few MB instead of listing the
# whole archive again.
ffdir=$(tar tf "$repo_root/$firefox" | awk '{ sub(/^\.\//, ""); sub(/\/.*/, ""); if ($0 != "" && $0 != "." && $0 != "..") { print; exit } }')
if [ -z "$ffdir" ]; then
    echo "error: cannot determine the directory inside '$firefox'." >&2
    exit 1
fi
tree=$tmpdir/$ffdir
cd "$tree" || { echo "error: '$ffdir' is not in '$firefox'." >&2; exit 1; }

# --edit exists to hand back a tree, so from here on it is kept - including
# when the patch fails, because a tree full of .rej files is exactly what
# someone fixing a broken patch came for.
if [ -z "$outpath" ]; then
    keep_tree=1
fi

#
# The files the patch touches.
#
# Read from *paired* '---'/'+++' header lines: a lone '--- ' can also be an
# ordinary removed line whose content starts with '--', and requiring the pair
# rejects almost all of those. A stray path that survives costs nothing, since
# every path below is used only if it exists.
#
# Both sides are read, not just '+++': the '---' side is the only place a
# deleted file is named, and it has to be tracked *before* the patch removes it
# or the deletion cannot appear in the rebuilt diff at all.
#
# One leading component is stripped, which is what `patch -p1` does, rather than
# assuming the git 'a/' and 'b/' prefixes.
#
patch_files=$(
    awk '
        /^--- / { minus = $0; next }
        /^\+\+\+ / { if (minus != "") { print minus; print $0 } minus = ""; next }
        { minus = "" }
    ' "$patchpath" |
    sed -e 's/^--- //' -e 's/^+++ //' -e 's/	.*//' -e 's/[[:space:]]*$//' |
    grep -v '^/dev/null$' |
    sed -e 's|^[^/]*/||' |
    grep . | sort -u
)
if [ -z "$patch_files" ]; then
    echo "error: no '--- ' / '+++ ' file headers in '$patchrel' - is it a unified diff?" >&2
    exit 1
fi

git_ init -q . || { echo "error: 'git init' failed in '$tree'." >&2; exit 1; }

# Only the files that exist. The ones the patch creates do not, and the old
# `git add` of all of them failed and took the first commit down with it.
# -f because the Firefox tree ships its own .gitignore and a target that
# matches one of its rules must still be tracked here.
present=""
for p in $patch_files; do
    [ -e "$p" ] && present="$present $p"
done
if [ -n "$present" ]; then
    git_ add -f -- $present || { echo "error: 'git add' of the original files failed." >&2; exit 1; }
fi
# --allow-empty: a patch that only adds files has no original files to commit,
# and an empty root commit is still the right base to diff against.
git_ commit -q -m "original" --allow-empty || {
    echo "error: committing the original files failed." >&2
    exit 1
}

#
# Apply. 2>&1 so the stderr line that explains a missing target file is
# captured, < /dev/null so that case cannot block on patch's invisible
# "File to patch:" prompt.
#
patch_out=$tmpdir/patch.out
patch -p1 -i "$patchpath" < /dev/null > "$patch_out" 2>&1
patch_status=$?
sed -e 's/^/    /' "$patch_out"

rejects=""
for j in $(grep -n 'rej$' "$patch_out" | awk '{ print $(NF) }'); do
    rejects="$rejects $j"
done

if [ "$patch_status" -ne 0 ] || [ -n "$rejects" ]; then
    if [ -n "$outpath" ]; then
        # Fatal here: diffing a half applied patch writes a patch file with the
        # rejected hunks quietly missing, and that artefact then applies
        # cleanly forever. Nothing is written.
        echo "" >&2
        echo "error: '$patchrel' did not apply to $firefox (patch exited $patch_status)." >&2
        [ -n "$rejects" ] && echo "  rejects:$rejects" >&2
        echo "  Nothing was written to '$outfile' - a rebuilt patch would be missing those" >&2
        echo "  hunks and would then apply cleanly forever. To get a tree with the rejects" >&2
        echo "  in it and fix the patch by hand:" >&2
        echo "    $0 --targets=$(echo "$targets" | tr -d ' ') --edit $patchrel" >&2
        exit 1
    fi
    echo "" >&2
    echo "warning: '$patchrel' did not apply cleanly (patch exited $patch_status)." >&2
    [ -n "$rejects" ] && echo "warning: rejects:$rejects" >&2
    echo "warning: the tree below has the hunks that did apply; the rest are in the .rej" >&2
    echo "warning: files. Do not diff it out until you have dealt with them." >&2
fi

#
# Commit the result. Everything that now exists is added (files the patch
# created included); `commit -a` picks up modifications and the deletions of
# tracked files the patch removed.
#
present=""
for p in $patch_files; do
    [ -e "$p" ] && present="$present $p"
done
if [ -n "$present" ]; then
    git_ add -f -- $present || { echo "error: 'git add' of the patched files failed." >&2; exit 1; }
fi
if ! git_ commit -q -a -m "patch"; then
    if [ -n "$outpath" ]; then
        echo "error: nothing to commit after applying '$patchrel' - it changed no file this" >&2
        echo "  script is tracking. Either it was already applied, or its file headers do not" >&2
        echo "  match the tree. Nothing was written to '$outfile'." >&2
        exit 1
    fi
    # --edit again: a patch that applied nothing at all is the case someone
    # reaches for this mode to fix, so hand the tree over anyway. HEAD stays on
    # the pristine commit and the diff command printed below still works once
    # there is something to diff.
    echo "" >&2
    echo "warning: the patch changed no file, so there is no second commit - the tree" >&2
    echo "warning: below is the pristine one." >&2
fi

root=$(git_ rev-list --max-parents=0 HEAD) || exit 1
patched=$(git_ rev-parse HEAD) || exit 1

#
# --edit: hand the tree back and stop.
#
if [ -z "$outpath" ]; then
    echo ""
    echo "git-patchtree: files under git control:"
    git_ ls-tree -r HEAD --name-only | sed -e 's/^/    /'
    echo ""
    echo "git-patchtree: the tree is at"
    echo "    $tree"
    echo ""
    echo "git-patchtree: edit it, then (remember to 'git add' files you create):"
    echo "    cd $tree"
    echo "    git add <any new file>"
    echo "    git commit -am edited"
    echo "    git diff --no-ext-diff --no-renames $root HEAD > $repo_root/$patchrel"
    echo ""
    echo "git-patchtree: (rebuilding it in one shot, with a --fuzz=0 check, is)"
    echo "    $0 --targets=$(echo "$targets" | tr -d ' ') -o $patchrel $patchrel"
    echo ""
    echo "git-patchtree: it is ~$(du -sh "$tmpdir" 2>/dev/null | awk '{print $1}') and nothing will remove it for you:"
    echo "    rm -rf $tmpdir"
    if [ -n "$tarball_warning" ]; then
        echo "" >&2
        echo "!!! $tarball_warning" >&2
    fi
    exit 0
fi

#
# -o mode: rebuild the patch, prove it, then write it.
#
regenerated=$tmpdir/regenerated.patch
git_diff "$root" "$patched" > "$regenerated" || {
    echo "error: 'git diff' failed." >&2
    exit 1
}
if [ ! -s "$regenerated" ]; then
    echo "error: the rebuilt patch is empty." >&2
    exit 1
fi

# The check that was missing: put the tree back the way the tarball had it and
# re-apply what we just produced at zero fuzz. `reset --hard` restores the
# tracked files and removes the ones the patch created, and touches nothing
# else in the tree because nothing else is tracked.
git_ reset --hard --quiet "$root" || { echo "error: 'git reset --hard' failed." >&2; exit 1; }
patch -p1 --fuzz=0 --dry-run -i "$regenerated" < /dev/null > "$patch_out" 2>&1
verify_status=$?
git_ reset --hard --quiet "$patched" || { echo "error: 'git reset --hard' failed." >&2; exit 1; }

if [ "$verify_status" -ne 0 ]; then
    echo "error: the rebuilt patch does not apply to $firefox at --fuzz=0 (patch exited" >&2
    echo "  $verify_status), which is the one property it was rebuilt to have. Refusing to" >&2
    echo "  write '$outfile'." >&2
    sed -e 's/^/    /' "$patch_out" >&2
    exit 1
fi

mv -f "$regenerated" "$outpath" || {
    echo "error: cannot write '$outfile'." >&2
    exit 1
}

echo "git-patchtree: wrote $outfile ($(wc -l < "$outpath" | tr -d ' ') lines, verified at --fuzz=0)"
if [ "$keep_tree" -eq 1 ]; then
    echo "git-patchtree: tree kept at $tree (rm -rf $tmpdir)"
fi
if [ -n "$tarball_warning" ]; then
    echo "" >&2
    echo "!!! $tarball_warning" >&2
fi
exit 0
