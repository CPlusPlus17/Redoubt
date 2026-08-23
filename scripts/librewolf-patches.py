#!/usr/bin/env python3

#
# The script that patches the firefox source into the librewolf source.
#


import hashlib
import os
import re
import shutil
import sys
import optparse
import time
from pathlib import Path
from tempfile import TemporaryDirectory


#
# general functions, skip these, they are not that interesting
#

# Everything this script reads out of the repository is resolved from the
# script's own location, never from the current directory. librewolf_patches()
# chdir's into the source tree, and under --no-execute it deliberately does
# not, so a cwd-relative path is read from a different place depending on the
# flag - which is how `-n` came to be neither dry nor runnable from anywhere.
REPO_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = REPO_DIR / "assets"
PATCH_LIST_DIR = ASSETS_DIR / "patches"

# Platform patch sets. 'common' is not a target: it is applied unconditionally,
# before whichever of these are selected, in the order listed here.
KNOWN_TARGETS = ("desktop", "android")

start_time = time.time()
parser = optparse.OptionParser()
parser.add_option('-n', '--no-execute', dest='no_execute', default=False, action="store_true")
# There used to be a '-P' / '--no-settings-pane' here, parsed into
# options.settings_pane. Nothing in this script ever read it: it was inert from
# the commit that introduced it (58e6d09, Dec 2021) until LW-M1-13 removed it,
# so no build can have been relying on it, and a flag that silently does nothing
# is worse than no flag. What it was meant to control - whether a build gets the
# desktop pref pane - is now a consequence of --targets: the pane's patch is an
# ordinary entry in assets/patches/desktop.txt and the four files it needs are
# copied in only for that target. A desktop build that does not want the pane
# drops the entry from that list (scripts/disable-patch.sh does it); see the
# note on the copies further down for what that leaves behind.
parser.add_option('-t', '--targets', dest='targets', default='desktop',
                  help="comma separated platforms to patch for, from {} "
                       "(default: desktop). assets/patches/common.txt is always "
                       "applied, then one list per target.".format(
                           ", ".join(sorted(KNOWN_TARGETS))))
options, args = parser.parse_args()


def script_exit(statuscode):
    if (time.time() - start_time) > 60:
        # print elapsed time
        elapsed = time.strftime("%H:%M:%S", time.gmtime(time.time() - start_time))
        print("\n\aElapsed time: {elapsed}")
        sys.stdout.flush()

    sys.exit(statuscode)

def exec(cmd, exit_on_fail = True, do_print = True):
    if cmd != '':
        if do_print:
            print(cmd)
            sys.stdout.flush()
        if not options.no_execute:
            retval = os.system(cmd)
            if retval != 0 and exit_on_fail:
                print("fatal error: command '{}' failed".format(cmd))
                sys.stdout.flush()
                script_exit(1)
            return retval
        return None


#
# Which patch lists to apply, and in what order.
#
# One file per platform under assets/patches/, plus common.txt which every
# target gets. The lists are concatenated, not merged: common.txt first, then
# the selected target lists in KNOWN_TARGETS order, so the result is
# deterministic regardless of how --targets was spelled. Relative order inside
# each file is preserved, which is what the ordering constraints in
# docs/android/AGENTS.md are expressed against.
#

def selected_targets():
    targets = [t.strip() for t in options.targets.split(",") if t.strip()]
    if not targets:
        print("fatal error: --targets is empty; expected one or more of {}".format(
            ", ".join(KNOWN_TARGETS)))
        sys.stdout.flush()
        script_exit(1)
    unknown = [t for t in targets if t not in KNOWN_TARGETS]
    if unknown:
        print("fatal error: unknown target(s) {} in --targets={}".format(
            ", ".join("'{}'".format(t) for t in unknown), options.targets))
        print("  known targets: {}".format(", ".join(KNOWN_TARGETS)))
        print("  'common' is not a target - assets/patches/common.txt is always applied.")
        sys.stdout.flush()
        script_exit(1)
    # KNOWN_TARGETS order, deduplicated.
    return [t for t in KNOWN_TARGETS if t in targets]

def read_patch_list(name):
    path = PATCH_LIST_DIR / "{}.txt".format(name)
    entries = []
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if line:
                    entries.append(line)
    except OSError as e:
        print("fatal error: can't read patch list '{}': {}".format(path, e))
        sys.stdout.flush()
        script_exit(1)
    return entries

def patches_to_apply(targets):
    lists = ["common"] + targets
    patches = []
    for name in lists:
        entries = read_patch_list(name)
        print("# {}.txt: {} patch(es)".format(name, len(entries)))
        patches += entries
    sys.stdout.flush()
    return patches

# assets/patches.txt - the generated common+desktop compatibility shim kept
# after LW-M0-02 split the monolith - is gone, and with it check_compat_shim(),
# which warned when the shim's membership drifted from the real lists. The
# lists in assets/patches/ are now the only patch inputs anything reads; there
# is nothing left to keep in sync. See docs/android/REBASE.md, appendix C.


#
# l10n pinning: assets/l10n-pin.txt records the mozilla-l10n/firefox-l10n commit
# we ship and the sha256 of its codeload zip. Both are mandatory; see the
# comments in that file for how to bump the pin.
#

L10N_PIN_FILE = Path(__file__).resolve().parent.parent / "assets" / "l10n-pin.txt"

def read_l10n_pin():
    values = {}
    try:
        with open(L10N_PIN_FILE, "r") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if not line or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    except OSError as e:
        print("fatal error: can't read l10n pin file '{}': {}".format(L10N_PIN_FILE, e))
        sys.stdout.flush()
        script_exit(1)

    commit = values.get("commit", "")
    sha256 = values.get("sha256", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        print("fatal error: '{}' has no valid 'commit = <40 hex chars>' line (got '{}')".format(
            L10N_PIN_FILE, commit))
        sys.stdout.flush()
        script_exit(1)
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        print("fatal error: '{}' has no valid 'sha256 = <64 hex chars>' line (got '{}')".format(
            L10N_PIN_FILE, sha256))
        sys.stdout.flush()
        script_exit(1)
    return commit, sha256

def verify_sha256(path, expected, description):
    # Under -n nothing was downloaded, so there is nothing to hash.
    if options.no_execute:
        print("# skipped under --no-execute: sha256 check of {} against {}".format(path, expected))
        sys.stdout.flush()
        return
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as e:
        print("fatal error: can't hash {} ({}): {}".format(path, description, e))
        sys.stdout.flush()
        script_exit(1)
    actual = digest.hexdigest()
    if actual != expected:
        print("fatal error: sha256 mismatch for {} ({})".format(path, description))
        print("  expected: {}".format(expected))
        print("  actual:   {}".format(actual))
        print("  refusing to use an unverified download; see {}".format(L10N_PIN_FILE))
        sys.stdout.flush()
        script_exit(1)
    print("sha256 ok: {}  ({})".format(actual, description))
    sys.stdout.flush()


#
# Tree deletions that a patch file cannot usefully express.
#
# A unified diff has to carry every byte of whatever it removes, so folding
# toolkit/components/ml/vendor/openai into patches/remove-openai.patch would
# paste ~340KB of the vendored OpenAI SDK into this repository - the very code
# the patch exists to get rid of. That size argument is the reason the
# deletions live here.
#
# (It used to have a second reason: a deletion hunk whose target is missing
# makes patch print "Skipping patch", write no .rej file and exit 1, and
# scripts/check-patchfail.sh decided success by grepping for .rej files, so
# expressing the deletions as diff hunks would have bought coverage that did
# not exist. LW-M0-11 made patch's exit status authoritative there, so that
# reason is gone - check-patchfail.sh would now catch it. scripts/fuzzfail.sh
# still has the .rej-only blind spot; LW-M1-11 owns it.)
#
# The deletions assert either way. A bare `rm -rf` against a path upstream has
# renamed succeeds and removes nothing, the build stays green, and the code we
# meant to drop ships anyway - that is landmine L4 in docs/android/AGENTS.md,
# and it fails open. This fails closed.
#
# The other half of the removal - every *reference* to these paths - lives in
# patches/remove-openai.patch, whose toolkit/components/ml/jar.mn and
# toolkit/content/license.html hunks quote both paths verbatim. Those hunks do
# reject when upstream moves the paths, so `make check-patchfail` is what
# catches a rename ahead of a build; the assert below catches it again at patch
# time and refuses to produce a tree that still contains the backend.
#

def delete_from_tree(path, description):
    if options.no_execute:
        # -n never entered the source directory, so there is nothing to look at.
        print("# skipped under --no-execute: existence check for {}".format(path))
        sys.stdout.flush()
    elif not os.path.lexists(path):
        print("fatal error: {} ('{}') is not in the Firefox tree at {}".format(
            description, path, os.getcwd()))
        print("  Nothing was deleted. Upstream has renamed, moved or dropped this path,")
        print("  so the code is still in the tree under some other name. Find where it")
        print("  went and fix this call and patches/remove-openai.patch together - do")
        print("  not just delete the check. See landmine L4 in docs/android/AGENTS.md.")
        sys.stdout.flush()
        script_exit(1)
    # No -f: the path was just asserted to exist, so any failure here is real.
    exec('rm -vr {}'.format(path))


PATCH_BIN = shutil.which("gpatch") or "patch"

def patch(patchfile):
    cmd = "{} -p1 -i {}".format(PATCH_BIN, patchfile)
    print("\n*** -> {}".format(cmd))
    sys.stdout.flush()
    if not options.no_execute:
        retval = os.system(cmd)
        if retval != 0:
            print("fatal error: patch '{}' failed".format(patchfile))
            sys.stdout.flush()
            script_exit(1)

def enter_srcdir(_dir = None):
    if _dir == None:
        dir = "librewolf-{}-{}".format(version, release)
    else:
        dir = _dir
    print("cd {}".format(dir))
    sys.stdout.flush()
    if not options.no_execute:
        try:
            os.chdir(dir)
        except:
            print("fatal error: can't change to '{}' folder.".format(dir))
            sys.stdout.flush()
            script_exit(1)

def leave_srcdir():
    print("cd ..")
    sys.stdout.flush()
    if not options.no_execute:
        os.chdir("..")



#
# This is the only interesting function in this script
#


def librewolf_patches():

    # Resolved before entering the tree, so an unknown target or an unreadable
    # list fails before anything has been touched. `targets` is kept because a
    # few tree mutations below are not patches and cannot live in a list, and
    # they have to be gated on the same selection the lists are.
    targets = selected_targets()
    patches = patches_to_apply(targets)

    enter_srcdir()

    # remove OpenAI integration. patches/remove-openai.patch removes every
    # reference to these two paths; the patch and these deletions are one
    # change, so keep them in sync. See delete_from_tree() above.
    delete_from_tree('toolkit/components/ml/content/backends/OpenAIPipeline.mjs',
                     'the OpenAI ML backend')
    delete_from_tree('toolkit/components/ml/vendor/openai',
                     'the vendored OpenAI SDK')

    # create the right mozconfig file..
    exec('cp -v ../assets/mozconfig.new mozconfig')

    # copy branding files..
    #
    # Desktop only, for the same reason as the pref-pane copies further down (see
    # the long comment there): ../themes/browser is 70 files of DESKTOP branding
    # -- .ico/.icns, VisualElementsManifest, NSIS installer scaffolding -- landing
    # in browser/, which the Android build never traverses. It was unconditional
    # until now, so an --targets=android run copied all 70 in; that is landmine
    # L4's shape, invisible to both lint-patch-scope.py and check-patchfail.sh
    # because neither reads this call site.
    #
    # Found by the skeptical verification of LW-M1-13, which also observed that
    # LW-M1-13 is the last task on the board owning this file -- so leaving the
    # gate undone would have orphaned it with no future owner.
    #
    # Android branding is a separate tree (mobile/android/branding/*) and belongs
    # to LW-M4-07; assets/mozconfig.android currently points at the upstream
    # unofficial branding with a TODO naming that task. When LW-M4-07 adds
    # themes/android/, it copies it in under an "android" in targets gate here.
    if "desktop" in targets:
        exec("cp -r ../themes/browser .")
    if "android" in targets:
        # The 44 launcher-icon rasters (ic_launcher*.webp/png) are binary and
        # cannot live in a text patch, so they are staged in themes/android/
        # (mirroring the src/<variant>/... layout) and copied in here. The
        # vector drawables and build.gradle/manifest identity changes are in
        # patches/android/branding.patch; this supplies the raster halves.
        exec("cp -rv ../themes/android/. mobile/android/fenix/app/src/")

    # copy the right search-config.json-v2 file and search-config-icons file
    exec('cp -v ../assets/search-config-v2.json services/settings/dumps/main/search-config-v2.json')
    exec('cp -v ../assets/search-config-icons.json services/settings/dumps/main/search-config-icons.json')

    # add mojeek
    exec('cp -v ../assets/2c4b8834-030c-4097-a887-c7506689095c services/settings/dumps/main/search-config-icons')
    exec('cp -v ../assets/2c4b8834-030c-4097-a887-c7506689095c.meta.json services/settings/dumps/main/search-config-icons')

    # apply common.txt, then one list per --targets. The lists are read from
    # PATCH_LIST_DIR (absolute), the patches themselves are applied from '../'
    # because we are inside the source tree - under -n we are not, but nothing
    # is executed there either.
    for entry in patches:
        patch('../' + entry)

    # xmas.patch used to be applied here, from its own call site, "because not
    # all builders use this repo the same way, and we don't want to disturb
    # those workflows". LW-M1-09 split it and folded both halves into the lists
    # above: patches/xmas-common.patch (common.txt) carries the root moz.build
    # `DIRS += ["lw"]` and lw/moz.build, patches/xmas-desktop.patch
    # (last in desktop.txt, where the old call site put it in the sequence)
    # carries the browser/installer/package-manifest.in hunk. Applying it
    # outside the lists meant the Android target could not get the half it
    # needs - and that half is what puts lw/ into the build at all.
    # The out-of-tree builders the old comment was written for read
    # assets/patches/{common,desktop}.txt directly - the generated
    # assets/patches.txt shim they used to be pointed at is gone (LW-M7-01).
    # Both halves are in the lists above; patches/xmas.patch itself is gone.

    # vs_pack.py issue... should be temporary
    exec('cp -v ../patches/pack_vs.py build/vs/')

    #
    # Apply most recent `settings` repository files.
    #

    exec('mkdir -p lw')
    enter_srcdir('lw')
    # The pref composition is per target (LW-M3-10): common.cfg plus the
    # target's fragment, in that order. The leading `null;` comes from
    # common.cfg and autoconfig's skipFirstLine eats it; neither fragment
    # carries one, so the concatenation yields exactly one at the top and none
    # in the middle (board.py --check-cfg-split rule E checks the fragments for
    # this, not the generated output). A desktop build's composition
    # (common.cfg + desktop.cfg) is byte-identical to the checked-in
    # settings/librewolf.cfg, so it stays a plain copy. An android build swaps
    # in android.cfg: before this it got the desktop composition, which is why
    # every M3 android.cfg decision (LW-M3-09's L2b lockPref overrides,
    # LW-M3-06's policy translations) was absent from the build and the
    # desktop-only ones (e.g. privacy.resistFingerprinting.letterboxing) were
    # present. A desktop+android run keeps the desktop composition - the
    # existing behaviour for a shared tree, which desktop and android never are
    # (they are separate tarballs, each built for a single target).
    if "android" in targets and "desktop" not in targets:
        exec('cat ../../settings/common.cfg ../../settings/android.cfg > librewolf.cfg')
    else:
        exec('cp -v ../../settings/librewolf.cfg .')
    exec('cp -v ../../settings/distribution/policies.json .')
    exec('cp -v ../../settings/defaults/pref/local-settings.js .')
    leave_srcdir();



    #
    # pref-pane: the four new files the patch cannot carry.
    #
    # patches/pref-pane/pref-pane-small.patch is NOT applied here any more.
    # LW-M1-13 moved it into assets/patches/desktop.txt, last, which is exactly
    # where this call site sat in the apply sequence - after every list entry -
    # so the desktop tree is byte-for-byte what it was. Until then it was the
    # last patch applied from its own call site, and it was applied on EVERY
    # target: an --targets=android run pushed five browser/ files (preferences/
    # {jar.mn,preferences.js,preferences.xhtml,main.js} and browser/themes/
    # shared/jar.inc.mn) into a tree where nothing under browser/ is built.
    # Neither scripts/lint-patch-scope.py nor scripts/check-patchfail.sh could
    # see it, because both of them read the lists - that is landmine L4 in
    # docs/android/AGENTS.md, and the patch is now inside the mechanism that
    # would have caught it.
    #
    # These four copies are the other half of the same change: the files the
    # jar.mn and preferences.xhtml hunks above reference but that the patch does
    # not contain. They are 348 lines of text in total and a unified diff could
    # perfectly well carry them as create hunks - that is worth doing one day,
    # and it would put them under `make check-patchfail` too - but folding them
    # in means rewriting patches/pref-pane/pref-pane-small.patch, which is not
    # this change. So they stay copies, gated on the same target the list entry
    # is, which is all that was needed to keep them off Android.
    #
    # They fail closed, which is what L4 asks of an out-of-patch mutation: every
    # destination directory here is desktop chrome that the pane patch has
    # already edited, so if upstream renames one, `cp` cannot create the file,
    # exec() sees the non-zero status and script_exit(1)s. (The patch would have
    # rejected first, in the loop above.)
    #
    # Note the gate is the target, not the list entry: commenting the patch out
    # of desktop.txt still copies these four files in. They are unreferenced
    # then - nothing packages them, because the jar.mn entries that would have
    # come from the patch are absent - so it is four dead files in the tree, not
    # a broken build. Tying the copies to the entry instead would make a
    # mis-filed list entry able to put browser/ files on Android again, which is
    # the failure this task exists to close.
    #
    if "desktop" in targets:
        exec('cp -v ../patches/pref-pane/category-librewolf.svg browser/themes/shared/preferences/category-librewolf.svg')
        exec('cp -v ../patches/pref-pane/librewolf.css browser/themes/shared/preferences/librewolf.css')
        exec('cp -v ../patches/pref-pane/librewolf.inc.xhtml browser/components/preferences/librewolf.inc.xhtml')
        exec('cp -v ../patches/pref-pane/librewolf.js browser/components/preferences/librewolf.js')

    # provide a script that fetches and bootstraps Nightly and some mozconfigs
    exec('cp -v ../scripts/mozfetch.sh lw/')
    exec('cp -v ../assets/mozconfig.new lw/')

    # override the firefox version. Not via exec(), so it needs its own
    # --no-execute guard: without one, `-n` wrote these two files for real,
    # relative to whatever directory it was run from.
    for file in ["browser/config/version.txt", "browser/config/version_display.txt"]:
        print("write {} <- {}-{}".format(file, version, release))
        sys.stdout.flush()
        if not options.no_execute:
            with open(file, "w") as f:
                f.write("{}-{}".format(version,release))

    l10n_commit, l10n_sha256 = read_l10n_pin()
    print(f"-> Downloading locales from https://github.com/mozilla-l10n/firefox-l10n at {l10n_commit}")
    with TemporaryDirectory() as tmpdir:
        zip_path = f"{tmpdir}/l10n.zip"
        # -f so an HTTP error is an error instead of a saved error page.
        exec(f"curl -sfL -o {zip_path} 'https://codeload.github.com/mozilla-l10n/firefox-l10n/zip/{l10n_commit}'")
        # Verify before unzipping: an unverified archive never gets unpacked.
        verify_sha256(zip_path, l10n_sha256, f"firefox-l10n zip @ {l10n_commit}")
        exec(f"unzip -qo {zip_path} -d {tmpdir}/l10n")
        # codeload names the top-level directory after the ref it was asked for,
        # so fetching by sha gives firefox-l10n-<full sha>, not firefox-l10n-main.
        extracted = f"{tmpdir}/l10n/firefox-l10n-{l10n_commit}"
        if not options.no_execute and not os.path.isdir(extracted):
            print(f"fatal error: '{extracted}' is missing from the l10n archive; codeload changed its layout")
            sys.stdout.flush()
            script_exit(1)
        exec(f"mv {extracted} lw/l10n")

    print("-> Patching appstrings.properties")
    # Why is "Firefox" hardcoded there???
    exec("find . -path '*/appstrings.properties' -exec sed -i s/Firefox/LibreWolf/ {} \\;")

    print("-> Applying LibreWolf locales")
    l10n_dir = Path("..", "l10n")
    # Same reason as the version.txt write above: this loop copies files
    # directly rather than through exec(), so it needs its own guard. Under -n
    # we never entered the tree, so '../l10n' points at whatever happens to sit
    # next to the current directory - it must not be walked, let alone written.
    for source_path in [] if options.no_execute else l10n_dir.rglob("*"):
        if source_path.is_dir() or source_path.name.endswith(".md"):
            continue

        rel_path = source_path.relative_to(l10n_dir)
        if rel_path.parts[0] == "en-US":
            target_path = Path(
                rel_path.parts[1],
                "locales", "en-US",
                *rel_path.parts[2:]
            )
        else:
            target_path = Path(
                "lw", "l10n",
                *rel_path.parts
            )

        target_path.parent.mkdir(parents=True, exist_ok=True)

        write_mode = "w"
        if ".inc" in target_path.name:
            target_path = target_path.with_name(target_path.name.replace(".inc", ""))
            write_mode = "a"

        print(f"{source_path} {'>' if write_mode == 'w' else '>>'} {target_path}")

        if not target_path.exists() and write_mode == "a":
            print(f"warning: target file {target_path} doesn't exist")
        with open(target_path, write_mode) as target_file:
            with open(source_path, "r") as source_file:
                target_file.write(("\n\n" if write_mode == "a" else "") + source_file.read())

    leave_srcdir()



#
# Main functionality in this script.. which is to call librewolf_patches()
#

if len(args) != 2:
    sys.stderr.write('error: please specify version and release of librewolf source')
    sys.exit(1)
version = args[0]
release = args[1]
srcdir = "librewolf-{}-{}".format(version, release)
# --no-execute never enters the tree and never touches it, so requiring the
# tree to exist would make a dry run impossible anywhere but on a machine that
# has already extracted 10GB of Firefox.
if not options.no_execute and not os.path.exists(srcdir + '/configure.py'):
    sys.stderr.write('error: folder doesn\'t look like a Firefox folder.')
    sys.exit(1)

librewolf_patches()

sys.exit(0) # ensure 0 exit code
