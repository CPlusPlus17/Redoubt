docker_targets = docker-build-image docker-run-build-job docker-remove-image
android_image_targets = android-build-image android-run-build-job android-remove-image

# The Android build targets, in one list because three separate things need it:
# .PHONY below, the android-goal track selection further down, and `make help`.
# android-aar and android-apk are the artifact-named spellings of android-build
# and android-package and are aliases for them - see the Android section near
# the bottom of this file.
android_targets = android-dir android-build android-package android-clean android-aar android-apk

woodpecker_targets = fetch-upstream-woodpecker check-patchfail-woodpecker
testing_targets = full-test test test-linux test-macos test-windows
.PHONY : help moztree check all clean veryclean distclean patches dir bootstrap fetch build package run update setup-wasi check-patchfail check-fuzz fixfuzz $(android_targets) $(docker_targets) $(android_image_targets) $(woodpecker_targets) $(testing_targets)

version := $(shell cat ./version)
release := $(shell cat ./release)

# Which platform patch sets scripts/librewolf-patches.py applies, as a comma
# separated list, passed through to its --targets. "desktop" is the historical
# behaviour and the default. Recognised values are desktop and android;
# assets/patches/common.txt is applied whatever this says. The patcher rejects
# anything else, so a typo is a build failure rather than a silently smaller
# patch set.
TARGETS ?= desktop

comma := ,

# --- Android goals select the android track ---------------------------------
#
# $(version)/$(release) - and therefore the tree name, the tarball, the stamp
# and the patcher's --targets - are chosen from TARGETS by the release-track
# block below. TARGETS is a variable, so without this block a bare
# `make android-package` would extract and patch a *desktop* tree at the
# desktop version and then build an Android APK out of it. That is a
# mislabelled artifact of exactly the kind android-aar's guard exists to
# prevent, and telling every caller to type TARGETS=android for a target whose
# name already says android is a guard where a default belongs.
#
# So: when every goal on the command line is one of the android build goals and
# the caller did not set TARGETS themselves, select the android track. Both
# halves of that condition are load bearing:
#
#   - $(origin TARGETS) is "file" only when nothing but the `?=` above set it.
#     An explicit `make android-aar TARGETS=desktop` is still honoured, and
#     still refused by $(call android_guard,...) - saying it out loud keeps
#     beating the default, which is the rule the CONTAINER_ENGINE comment
#     further down argues for at length.
#   - the goal list must contain nothing else. `make dir android-dir` cannot be
#     served by one tree, so it is left alone and the guard tells the caller so.
#     A bare `make` (no goals at all) is untouched: MAKECMDGOALS is empty then,
#     which is why the emptiness test is there and not folded into the filter.
#
# This is parse-time, pure make, and reads only make's own goal list: no
# $(shell), no probing of the environment, so `make -n` stays a real dry run.
# android-run-build-job is not in the list because it passes TARGETS=android to
# its own sub-make instead.
ifeq ($(origin TARGETS),file)
ifneq ($(strip $(MAKECMDGOALS)),)
ifeq ($(filter-out $(android_targets),$(MAKECMDGOALS)),)
TARGETS := android
endif
endif
endif

# --- Release track ----------------------------------------------------------
#
# Desktop tracks Firefox release; Android tracks Firefox ESR. The decision, the
# numbers behind it, and the divergence model are in docs/android/TRACK.md.
#
# ./version + ./release name the desktop tree, ./version.android +
# ./release.android name the Android one. A single extracted tree cannot be two
# Firefox versions at once, so exactly one pair is in effect per invocation and
# TARGETS chooses it:
#
#   TARGETS=desktop (default) -> ./version, ./release                unchanged
#   android without desktop   -> ./version.android, ./release.android
#   both                      -> ./version, ./release, plus $(lw_tree_guard),
#                                which refuses to build when the two pairs
#                                have actually diverged.
#
# Everything downstream is already written in terms of $(version)/$(release),
# so overriding them here is the whole mechanism: $(lw_source_dir) becomes
# librewolf-153.0esr-1, the android tree gets its own directory, its own
# tarball and its own $(ff_source_url), and the desktop tree is never touched
# by an android build. The ESR tarball lives under the same
# .../releases/<version>/source/firefox-<version>.source.tar.xz layout as a
# release build - "153.0esr" is just a version string to archive.mozilla.org -
# so FF_CHANNEL needs no new case.
target_list := $(subst $(comma), ,$(TARGETS))
has_desktop := $(filter desktop,$(target_list))
has_android := $(filter android,$(target_list))

android_version := $(shell cat ./version.android 2>/dev/null)
android_release := $(shell cat ./release.android 2>/dev/null)

# Which files the extracted tree is invalidated by. Only the pair actually in
# effect, so a desktop version bump does not force the android tree to
# re-extract, or the other way round.
version_files := ./version ./release

ifneq ($(has_android),)
ifeq ($(has_desktop),)
ifeq ($(and $(strip $(android_version)),$(strip $(android_release))),)
$(error TARGETS=$(TARGETS) needs ./version.android and ./release.android - see docs/android/TRACK.md)
endif
version := $(android_version)
release := $(android_release)
version_files := ./version.android ./release.android
endif
endif

# One tree, one Firefox version. If both platform patch sets are asked for
# while the two tracks point at different versions there is no single tree to
# apply them to, so refuse - but at recipe time, not with $(error), so that
# `make -n` stays a real dry run and LW-M0-01's plumbing check
# (`make -n dir TARGETS=desktop,android`) keeps working. The variable is empty
# in every other case, and make drops a recipe line that expands to nothing
# entirely, which is what keeps the default `make dir` unchanged.
lw_tree_guard =
ifneq ($(has_android),)
ifneq ($(has_desktop),)
ifneq ($(version)-$(release),$(android_version)-$(android_release))
lw_tree_guard = echo "TARGETS=$(TARGETS) wants desktop $(version)-$(release) and android $(android_version)-$(android_release) in one tree - build them one at a time, see docs/android/TRACK.md" >&2; exit 1
endif
endif
endif

# The TARGETS value the extracted tree was built with is recorded in the *name*
# of a stamp file, which is a prerequisite of $(lw_source_dir) below. A
# different TARGETS therefore selects a stamp that does not exist yet; making
# it removes the stale stamp and touches the new one, which is then newer than
# the tree and forces the re-extract. Encoding the value in the name rather
# than the contents keeps this ordinary make: no $(shell) side effects at parse
# time, so `make -n` stays a real dry run. The librewolf- prefix is deliberate,
# .gitignore already ignores /librewolf-*.
#
# The version and release are part of the name, and this definition has to come
# *after* the release-track block above that may have overridden them - a := is
# expanded on the spot. Without them the stamp is shared between the two tracks
# while the trees are not: `make dir` and `make dir TARGETS=android` produce
# librewolf-153.0.4-1 and librewolf-153.0esr-1 side by side, and a
# version-agnostic stamp made each switch delete the other's stamp and
# re-extract a tree that was already correct - about 10GB per switch. See
# "Known defect: targets_stamp thrashes between tracks" in docs/android/TRACK.md.
#
# NOTE: this rename means the first `make dir` after this change re-extracts
# once on every existing builder, because no stamp under the new name exists
# yet. That is a one-time cost, not a recurring one.
targets_stamp := librewolf-targets-$(version)-$(release)-$(subst $(comma),-,$(TARGETS))

# The patch lists the patcher actually reads. Only the ones in effect: editing
# android.txt must not re-extract a desktop tree. assets/patches.txt is a
# generated shim (see assets/patches/common.txt) that nothing in this recipe
# reads any more, so it is deliberately not a prerequisite.
patch_lists := assets/patches/common.txt $(foreach t,$(target_list),assets/patches/$(t).txt)

patcher_cmd := python3 scripts/librewolf-patches.py $(version) $(release) --targets=$(TARGETS)

FF_BASE_URL ?= https://archive.mozilla.org/pub/firefox/releases
FF_CHANNEL ?= releases
FF_BUILD ?= build1

# Beta minor suffix (e.g "b9")
FF_BETA_SUFFIX ?=

ff_source_tarball := firefox-$(version)$(FF_BETA_SUFFIX).source.tar.xz

ifeq ($(FF_CHANNEL),candidates)
ff_source_url := https://archive.mozilla.org/pub/firefox/candidates/$(version)-candidates/$(FF_BUILD)/source/$(ff_source_tarball)
else ifeq ($(FF_CHANNEL),beta)
ff_source_url := https://archive.mozilla.org/pub/firefox/candidates/$(version)$(FF_BETA_SUFFIX)-candidates/$(FF_BUILD)/source/$(ff_source_tarball)
else
ff_source_url := $(FF_BASE_URL)/$(version)/source/$(ff_source_tarball)
endif

## Simplistic archive format selection

# archive_create=tar cfJ
# ext=.tar.xz
archive_create := tar cfz
ext := .tar.gz

# ff_source_tarball is defined once, above, next to $(ff_source_url) that uses
# it. It used to be assigned a second time here, without $(FF_BETA_SUFFIX), and
# the second assignment won - so `make test-beta FF_BETA_SUFFIX=b9` downloaded
# firefox-153.0.source.tar.xz from a beta candidates URL that does not serve
# it. FF_BETA_SUFFIX is empty by default, so restoring it changes nothing for a
# release build.
#
# $(ff_source_dir) is the name the tarball is *expected* to unpack to. It is a
# guess derived from the artifact name, and after LW-M0-14 the only thing that
# still trusts it is `clean`, which has to work when the tarball has already
# been deleted by `distclean` and there is nothing left to ask. Everything that
# actually touches the tree asks the tarball - see $(ff_tarball_dir).
ff_source_dir := firefox-$(version)$(FF_BETA_SUFFIX)

# The directory the tarball *actually* unpacks to, derived from the tarball.
#
# The name of the artifact and the name of the directory inside it are two
# different things, and Mozilla does not keep them in step:
# firefox-153.0esr.source.tar.xz unpacks to firefox-153.0/, not to
# firefox-153.0esr/. Computing the directory as firefox-$(version) therefore
# made `make dir TARGETS=android` die on
# `mv firefox-153.0esr librewolf-153.0esr-1` - after a 766MB download and a
# ~10GB extract, which is the expensive place to find out. Deriving the name
# also survives the next rename; stripping a literal "esr" suffix would only
# survive this one.
#
# This is a *shell* snippet - $$( ), expanded by the recipe's shell - and
# deliberately not a $(shell tar tf ...). A $(shell ...) here would run at
# parse time on every single make invocation, including `make help` and every
# `make -n`, and on a fresh checkout it would run before `make fetch` has
# downloaded anything and quietly evaluate to nothing. Same reasoning as the
# $(targets_stamp) comment above and the CONTAINER_ENGINE one below: this
# Makefile does not do parse time shell side effects. At recipe time the
# tarball is guaranteed to be present, because it is a prerequisite of the rule
# that expands this.
#
# The awk, rather than the obvious `tar tf | head -1 | cut -d/ -f1`:
#
#   - the first member of both tarballs is "./", not the top level directory.
#     head -1 yields "." - and this expansion is used as an `rm -rf` operand,
#     so that shortcut is `rm -rf .` in the source root. Checked against the
#     real firefox-153.0.4 and firefox-153.0esr tarballs, not assumed.
#   - so it skips "", "." and ".." explicitly and only ever prints a real
#     name. `rm -rf $(ff_tarball_dir)` cannot degenerate into `rm -rf .`.
#   - awk exits at the first usable member, which closes the pipe and kills tar
#     and xz off after a few MB rather than streaming the whole ~10GB. Measured
#     at 3ms on the 766MB tarball, so calling it more than once is free.
#   - if it finds nothing it prints nothing, and every use below is quoted:
#     `rm -rf ""` is a silent no-op (exit 0) and `mv "" <dir>` fails loudly, so
#     the empty case cannot do damage and cannot pass silently either.
#
# For a release tarball the derived name is exactly firefox-$(version), so the
# desktop recipe runs the same two commands it ran before this existed.
ff_tarball_dir = $$(tar tf $(ff_source_tarball) 2>/dev/null | awk '{ sub(/^\.\//, ""); sub(/\/.*/, ""); if ($$0 != "" && $$0 != "." && $$0 != "..") { print; exit } }')

lw_source_dir := librewolf-$(version)-$(release)
lw_source_tarball := librewolf-$(version)-$(release).source$(ext)

help:

	@echo "use: $(MAKE) [all] [check] [clean] [veryclean] [bootstrap] [build] [package] [run]"
	@echo ""
	@echo "  all         - Make LibreWolf source archive ${version}-${release}."
	@echo ""
	@echo "  check       - Check if there is a new version of Firefox."
	@echo "  update      - Update the git submodules."
	@echo ""
	@echo "  clean       - Clean everything except the upstream firefox tarball."
	@echo "  veryclean   - Clean everything including the firefox tarball."
	@echo ""
	@echo "  bootstrap   - Bootstrap the build environment."
	@echo "  setup-wasi  - Setup WASM sandbox libraries (required on Linux)."
	@echo ""
	@echo "  fetch       - fetch Firefox source archive."
	@echo "  dir         - extract Firefox and apply the patches, creating a"
	@echo "                ready to build librewolf folder."
	@echo "  build       - Build LibreWolf (requires bootstrapped build environment)."
	@echo "  package     - Package LibreWolf (requires build)."
	@echo "  run         - Run LibreWolf (requires build)."
	@echo ""
	@echo "Android (docs/android/BUILD.md, docs/android/TRACK.md). These four"
	@echo "mirror dir/build/package/clean and are independent of them: a machine"
	@echo "can run either set without ever running the other. TARGETS=android is"
	@echo "selected automatically when every goal on the command line is one of"
	@echo "them, so it only has to be typed when it is not."
	@echo ""
	@echo "  android-dir     - extract Firefox and apply common+android patches,"
	@echo "                    creating a ready to build librewolf folder, plus the"
	@echo "                    lw/l10n directory --with-l10n-base needs. ('dir')"
	@echo "                    Tree: librewolf-$(android_version)-$(android_release)"
	@echo ""
	@echo "  android-build   - Build the shipped Android ABIs and merge them into"
	@echo "                    one fat GeckoView AAR. ('build')"
	@echo "                    Output: librewolf-android-aar-$(android_version)-$(android_release)"
	@echo "                    Measured: 59 min and ~65GB of objdir for three ABIs"
	@echo "                    at -j16, sequential (memory bound, ~31GB per pass)."
	@echo "                    ANDROID_AAR_FLAGS=... goes to scripts/android-fat-aar.sh,"
	@echo "                    ANDROID_AAR_OUTDIR=<dir> moves the output."
	@echo ""
	@echo "  android-package - Feed that fat AAR into the in-tree Fenix Gradle build"
	@echo "                    and produce one APK per ABI plus a universal one, in"
	@echo "                    <output>/apk/. ('package')"
	@echo "                    Output: librewolf-android-apk-$(android_version)-$(android_release)"
	@echo "                    Builds the fat AAR first if it is not there yet."
	@echo "                    Debug-signed, NOT release-signed - see LW-M6-01."
	@echo "                    Needs a mozconfig with --enable-android-subproject=fenix;"
	@echo "                    ANDROID_MOZCONFIG=<file> currently '$(ANDROID_MOZCONFIG)'."
	@echo "                    ANDROID_APK_FLAGS=... goes to scripts/android-apk.sh,"
	@echo "                    ANDROID_APK_OUTDIR=<dir> moves the output."
	@echo ""
	@echo "  android-clean   - Remove the android tree, its targets stamp and the"
	@echo "                    two default output directories above. Keeps the"
	@echo "                    downloaded Firefox tarball, and never touches the"
	@echo "                    desktop track. ('clean' + 'veryclean')"
	@echo ""
	@echo "  android-aar and android-apk are artifact-named aliases for"
	@echo "  android-build and android-package."
	@echo ""
	@echo "  All four honour CONTAINER_ENGINE and LW_ANDROID_SRCDIR=<tree>, e.g."
	@echo "    make android-package CONTAINER_ENGINE=podman"
	@echo "    make android-build LW_ANDROID_SRCDIR=/scratch/lw-tree"
	@echo ""
	@echo "  check-patchfail - check patches for errors."
	@echo "  check-fuzz      - check patches for fuzz."
	@echo "  fixfuz          - fix the fuzz."
	@echo ""
	@echo ""
	@echo "Variables:"
	@echo ""
	@echo "  TARGETS   - comma separated platforms to patch for, currently"
	@echo "              '$(TARGETS)' (default: desktop). Changing it forces"
	@echo "              'dir' to re-extract, e.g. make dir TARGETS=desktop,android"
	@echo ""
	@echo "  CONTAINER_ENGINE - engine the image targets below drive, currently"
	@echo "              '$(CONTAINER_ENGINE)' (default: docker). Not auto-detected,"
	@echo "              e.g. make android-build-image CONTAINER_ENGINE=podman"
	@echo ""
	@echo "Release track (docs/android/TRACK.md):"
	@echo ""
	@echo "  desktop tracks Firefox release : ./version ./release"
	@echo "  android tracks Firefox ESR     : ./version.android ./release.android"
	@echo "                                   ($(android_version)-$(android_release))"
	@echo "  in effect for this invocation  : $(version)-$(release)"
	@echo ""
	@echo ""
	@echo "Container images (all honour CONTAINER_ENGINE, currently '$(CONTAINER_ENGINE)'):"
	@echo ""
	@echo "docker:" $(docker_targets)
	@echo "           assets/Dockerfile -> $(build_image)"
	@echo ""
	@echo "android:" $(android_image_targets)
	@echo "           assets/Dockerfile.android -> $(android_build_image)"
	@echo "           (android-run-build-job is still a stub: run the android"
	@echo "            targets above from the host instead - see its recipe)"
	@echo ""
	@echo ""
	@echo "Maintainer commands:"
	@echo ""
	@echo "  patches   - Just make the LibreWolf source directory (download, extract, patch)"
	@echo "  all       - build LW tarball"
	@echo ""
	@echo "  clean     - remove all cruft except LW source tree"
	@echo "  veryclean - remove all except download FF tarball"
	@echo "  distclean - remove all including downloads"
	@echo ""
	@echo "  moztree   - show LW source tree"
	@echo "  check     - checking for new versions of FF"
	@echo "  update    - update settings submodule"
	@echo ""

moztree:

	(cd $(lw_source_dir) && ../scripts/moztree )

patches:

	make veryclean
	make dir

# Build

all: $(lw_source_tarball)

# Clean up

# "$(ff_tarball_dir)" is listed next to $(ff_source_dir) rather than instead of
# it: the derived name is the correct one but it can only be asked for while
# the tarball is still here, and `clean` has to keep working after `distclean`
# has removed it. With the tarball present the two agree on every release
# tarball, so the desktop operand list is unchanged bar a duplicate; with it
# absent the expansion is "" and `rm -rf ""` is a silent no-op. On the android
# track they disagree - firefox-153.0 against firefox-153.0esr - and without
# this the ~10GB extract survived `make clean`.
#
# The android-aar output is listed by its *default* name, deliberately not as
# $(ANDROID_AAR_OUTDIR): that variable is an override a builder may point at a
# directory of their own outside the checkout, and `make clean` has no business
# rm -rf-ing a path the caller supplied for something else. Like the rest of
# this file it is version scoped, so `make clean TARGETS=android` removes the
# android one and a desktop clean leaves it alone. The android-apk output is
# listed on the same terms and for the same reasons.
clean:
	rm -rf *~ public_key.asc $(ff_source_dir) "$(ff_tarball_dir)" $(lw_source_tarball) $(lw_source_tarball).sha256sum $(lw_source_tarball).sha512sum firefox-$(version) patchfail.out patchfail-fuzz.out librewolf-android-aar-$(version)-$(release) librewolf-android-apk-$(version)-$(release)

veryclean: clean
	rm -rf $(lw_source_dir) librewolf-targets-$(version)-$(release)-*

distclean: veryclean
	rm -f $(ff_source_tarball) $(ff_source_tarball).asc

# Check for new versions

check:
	-bash -c ./scripts/update-settings-module.sh
	python3 scripts/update-version.py
	cut -f1 version > version.tmp
	mv -vf version.tmp version
	@echo ""
	@echo "Firefox version   : " $$(cat version)
	@echo "LibreWolf release : " $$(cat release)
	@echo ""

# Update settings submodule

update:
	-bash -c ./scripts/update-settings-module.sh

# The actual build stuff

fetch: $(ff_source_tarball)

$(ff_source_tarball):
	curl -so public_key.asc "https://keys.openpgp.org/vks/v1/by-fingerprint/14F26682D0916CDD81E37B6D61B7B526D98F0353"
	gpg --import public_key.asc
	rm -f public_key.asc
	curl -so $(ff_source_tarball).asc "$(ff_source_url).asc"
	curl -so $(ff_source_tarball) "$(ff_source_url)"
	gpg --verify $(ff_source_tarball).asc $(ff_source_tarball)

$(targets_stamp):
	@rm -f librewolf-targets-$(version)-$(release)-*
	@touch $@

# Android translation pins participate in extraction; desktop inputs stay identical.
android_translation_inputs := $(if $(filter android,$(target_list)),scripts/package-translation-assets.py assets/translations/catalog.json assets/translations/bergamot-translator.wasm.zst assets/translations/provenance.json)

$(lw_source_dir): $(ff_source_tarball) $(version_files) scripts/librewolf-patches.py assets/mozconfig assets/l10n-pin.txt $(patch_lists) $(targets_stamp) $(android_translation_inputs)
	$(lw_tree_guard)
	rm -rf "$(ff_tarball_dir)" $(lw_source_dir)
	tar xf $(ff_source_tarball)
	mv "$(ff_tarball_dir)" $(lw_source_dir)
	$(patcher_cmd)

$(lw_source_tarball): $(lw_source_dir)
	rm -f $(lw_source_tarball)
	tar cf librewolf-$(version)-$(release).source.tar $(lw_source_dir)
	pigz -6 librewolf-$(version)-$(release).source.tar
	touch $(lw_source_dir)
	sha256sum $(lw_source_tarball) > $(lw_source_tarball).sha256sum
	cat $(lw_source_tarball).sha256sum
	sha256sum -c $(lw_source_tarball).sha256sum
	sha512sum $(lw_source_tarball) > $(lw_source_tarball).sha512sum
	cat $(lw_source_tarball).sha512sum
	sha512sum -c $(lw_source_tarball).sha512sum
	if [ -n "$${SIGNING_KEY}" ]; then printf '%s\n' "$${SIGNING_KEY}" | gpg --import && gpg --detach-sign $(lw_source_tarball) && ls -lh $(lw_source_tarball).sig; fi
	ls -lh $(lw_source_tarball)*

debs = python3 python3-dev python3-pip
rpms = python3 python3-devel
bootstrap: $(lw_source_dir)
	(sudo apt-get -y install $(debs); true)
	(sudo rpm -y install $(rpms); true)
	(cd $(lw_source_dir) && MOZBUILD_STATE_PATH=$$HOME/.mozbuild ./mach --no-interactive bootstrap --application-choice=browser)

setup-wasi:
	./scripts/setup-wasi-linux.sh

dir: $(lw_source_dir)

build: $(lw_source_dir)
	(cd $(lw_source_dir) && ./mach build)

package:
	(cd $(lw_source_dir) && cat browser/locales/shipped-locales | xargs ./mach package-multi-locale --locales)
	cp -v $(lw_source_dir)/obj-*/dist/librewolf-$(version)-$(release).en-US.*.tar.xz .

run:
	(cd $(lw_source_dir) && ./mach run)

# --- Android fat AAR --------------------------------------------------------
#
# `make android-aar TARGETS=android` builds one GeckoView AAR per shipped ABI
# (armeabi-v7a, arm64-v8a, x86_64) and merges them into a single fat AAR, using
# the tree's own fat-AAR support. scripts/android-fat-aar.sh does the work and
# documents the mechanism, the per-ABI cost and why 32-bit x86 is not built.
#
# This composes with the machinery above rather than around it:
#
#   - the tree it builds is $(lw_source_dir) - the same tree `make dir`
#     produces, with the same $(targets_stamp) prerequisite, so a TARGETS change
#     re-extracts here exactly as it does for `dir`;
#   - $(lw_tree_guard) refuses desktop+android in one tree for the same reason
#     it refuses it everywhere else;
#   - $(CONTAINER_ENGINE) is passed through and still not auto-detected. On a
#     machine without docker: make android-aar TARGETS=android CONTAINER_ENGINE=podman
#
# TARGETS must include android. An AAR built from a tree carrying only the
# desktop patch set would be a mislabelled artifact, and the release track
# block above has already picked ./version.android for us in that case, which
# is where the output directory name comes from. Like $(lw_tree_guard), the
# check runs at recipe time rather than as an $(error) so that `make -n` stays
# a real dry run.
#
# LW_ANDROID_SRCDIR points the build at an already extracted tree somewhere
# else, and drops the $(lw_source_dir) prerequisite with it. That is the
# supported way to build outside the repository - the objdirs are ~21GB each
# and three ABIs plus the merge want ~90GB - and it is how a second builder can
# work on a tree that `make dir` did not create.
#
# ANDROID_AAR_FLAGS is passed straight through to the script, e.g.
#   make android-aar TARGETS=android ANDROID_AAR_FLAGS="--abis=arm64-v8a --jobs=8"
LW_ANDROID_SRCDIR ?=
ANDROID_AAR_FLAGS ?=

# Ignored by .gitignore's /librewolf-* rule, like every other generated tree.
# Overridable because the per-ABI maven zips and the merged AAR are around a
# gigabyte, and on a builder that keeps its trees outside the checkout they
# belong next to those trees.
ANDROID_AAR_OUTDIR ?= $(CURDIR)/librewolf-android-aar-$(version)-$(release)

android_aar_srcdir := $(CURDIR)/$(lw_source_dir)
android_aar_prereq := $(lw_source_dir)

ifneq ($(strip $(LW_ANDROID_SRCDIR)),)
android_aar_srcdir := $(LW_ANDROID_SRCDIR)
android_aar_prereq :=
endif

# One guard for every android target, called with the name of the target it is
# guarding. It was two near-identical variables (android_aar_guard,
# android_apk_guard) before android-dir/android-build/android-package/
# android-clean needed four more; $(call ...) is the same text with the name
# substituted.
#
# It names the target whose *recipe* is running, which for the two artifact
# named aliases is not the name the caller typed: `make android-aar
# TARGETS=desktop` is refused by android-build's copy of the guard and `make
# android-apk TARGETS=desktop` by android-package's. The advice in the message
# is still correct and still fixes the caller's command line, and one guard
# with one message beats six copies that drift; but do not read the message as
# a claim about what was typed.
#
# An ifeq block rather than $(if $(has_android),,...): the message contains a
# comma, and $(if)'s arguments are split on commas, so the obvious one-liner
# hands make a fourth argument and fails to parse.
#
# Recipe time rather than $(error), for the reason $(lw_tree_guard) gives: a
# `make -n` must stay a real dry run. Since the android-goal selection at the
# top of this file now picks TARGETS=android for these goals, this fires only
# when a caller has *said* TARGETS=desktop (or set it in the environment), or
# has asked for a desktop goal and an android goal in one command line. Saying
# it out loud still beats the default - it just no longer has to be said.
android_guard =
ifeq ($(has_android),)
android_guard = echo "$(1) needs TARGETS to include android, e.g. make $(1) TARGETS=android - see docs/android/TRACK.md" >&2; exit 1
# Drop the prerequisite as well as failing the recipe. Leaving it in place
# would extract and patch a whole desktop tree first and only then tell the
# caller that TARGETS is wrong, which is a ~10GB way to deliver an error
# message.
android_aar_prereq :=
endif

# --- Android source tree ----------------------------------------------------
#
# `make android-dir` is the android counterpart of `dir`: extract the Firefox
# tarball and apply assets/patches/common.txt + assets/patches/android.txt to
# it, leaving a tree that ./mach can build. It is the same $(lw_source_dir)
# rule `dir` uses - the release-track block at the top of this file has already
# pointed $(version)/$(release) at ./version.android + ./release.android, so
# the tree it creates is librewolf-$(android_version)-$(android_release) and a
# desktop tree of the same repository is never touched. That independence is
# the point: a machine can run the android targets without ever having run the
# desktop ones, and the other way round.
#
# The one thing it does that `dir` does not is create lw/l10n.
# assets/mozconfig.android passes --with-l10n-base="$$topsrcdir/lw/l10n" and
# toolkit/moz.configure:500-504 *dies* - "Invalid value --with-l10n-base, ...
# doesn't exist" - when that path is not a directory. On a fully patched tree
# scripts/librewolf-patches.py has already created it (it is where the l10n
# archive is unpacked), so this is belt and braces rather than the normal path;
# it costs one mkdir and it turns a configure hard stop three minutes into a
# build into nothing at all on a tree that was extracted by hand, patched with
# an older patcher, or pointed at by LW_ANDROID_SRCDIR. LW-M0-15 identified
# this as belonging here rather than in assets/Dockerfile.android, which has no
# Firefox tree to create it in.
#
# The `test -d` in front of it is not decoration: with LW_ANDROID_SRCDIR set
# there is no prerequisite that guarantees the tree exists, and `mkdir -p`
# would happily create the whole path out of a typo and report success. Landmine
# L4 in docs/android/AGENTS.md is exactly this failure mode - a mutation outside
# the patch set that fails open.
android_l10n_base = test -d "$(android_aar_srcdir)" || { echo "no such directory: $(android_aar_srcdir) - extract it with 'make android-dir', or point LW_ANDROID_SRCDIR at a tree that exists" >&2; exit 1; }; mkdir -p "$(android_aar_srcdir)/lw/l10n"

android-dir: $(android_aar_prereq)
	$(call android_guard,android-dir)
	$(lw_tree_guard)
	$(android_l10n_base)

# The command, in one variable, because three rules run it: the .PHONY
# android-build below (which still rebuilds unconditionally, exactly as the
# desktop `build` re-runs ./mach build every time), the android-aar alias, and
# the file rule further down that android-package depends on. Duplicating seven
# lines that must not drift apart is worse than one variable.
android_fat_aar_cmd = ./scripts/android-fat-aar.sh \
		--srcdir "$(android_aar_srcdir)" \
		--outdir "$(ANDROID_AAR_OUTDIR)" \
		--mozconfig "$(CURDIR)/assets/mozconfig.android" \
		--engine "$(CONTAINER_ENGINE)" \
		--image "$(android_build_image)" \
		$(ANDROID_AAR_FLAGS)

# `make android-build` is the android counterpart of `build`: one ./mach build
# per shipped ABI, merged into the fat GeckoView AAR. Unconditional, like
# `build` - the per-ABI objdirs survive between runs, so a second run is an
# incremental mach build and not another 59 minutes.
android-build: $(android_aar_prereq)
	$(call android_guard,android-build)
	$(lw_tree_guard)
	$(android_l10n_base)
	$(android_fat_aar_cmd)

# android-aar is the artifact-named spelling and stays as an alias rather than
# a second copy of the recipe: it is the name docs/android/ and every earlier
# task used, and two recipes that must produce the same artifact are two
# recipes that will eventually not.
android-aar: android-build

# --- Android APK ------------------------------------------------------------
#
# `make android-apk TARGETS=android` feeds the fat GeckoView AAR into the
# in-tree mobile/android/fenix Gradle build and produces a debug-signed APK per
# ABI plus a universal one. scripts/android-apk.sh does the work and documents
# the mechanism; the short version is that it builds Gecko once for
# --fat-host-abi with --enable-android-subproject=fenix and the three per-ABI
# maven zips in the environment, then runs `mach gradle fenix:assembleDebug` in
# that objdir - the same two steps upstream's fenix-debug job takes
# (taskcluster/kinds/build/fenix.yml, mozharness 64_aarch64_fenix_debug.py).
#
# It composes with the block above exactly like android-aar does: same tree,
# same TARGETS guard, same $(lw_tree_guard), same $(CONTAINER_ENGINE), and
# LW_ANDROID_SRCDIR points it at a tree outside the checkout.
#
# ANDROID_MOZCONFIG exists because the mozconfig this target needs is not
# necessarily the one in assets/: the APK build requires
# `ac_add_options --enable-android-subproject=fenix`, and until that line is in
# assets/mozconfig.android (LW-M5-03 owns that file) a builder points this at
# their own copy. The script refuses to start without the option rather than
# appending it silently - building from a mozconfig that is not the one in the
# repository is exactly the ambiguity this project cannot afford.
#
# ANDROID_APK_FLAGS is passed straight through, e.g.
#   make android-apk TARGETS=android ANDROID_APK_FLAGS="--fat-host-abi=arm64-v8a"
ANDROID_APK_FLAGS ?=
ANDROID_MOZCONFIG ?= $(CURDIR)/assets/mozconfig.android
ANDROID_APK_OUTDIR ?= $(CURDIR)/librewolf-android-apk-$(version)-$(release)

# The APK needs the fat AAR, and gets it by depending on a *file* the AAR run
# writes rather than on the .PHONY android-aar target. A phony prerequisite
# would rebuild all three ABIs - measured at 59 minutes - on every single
# `make android-apk`, including the ones where the AAR is already sitting
# there. With the file dependency, a first `make android-apk TARGETS=android`
# on a machine with no AAR really does go from an extracted tree to an APK, and
# the second one only rebuilds the APK.
#
# build-times.txt is named because it is the one file with a fixed path that an
# AAR run always produces - the merged AAR's own name embeds MOZ_BUILD_DATE, so
# it cannot be written down here. Be precise about what its existence proves:
# scripts/android-fat-aar.sh *creates* it before the first pass and appends the
# "total" line only after every artifact check has passed, so a failed AAR run
# leaves the file behind and make will consider this prerequisite satisfied.
# That is deliberate rather than overlooked: scripts/android-apk.sh's preflight
# requires <abi>/target.maven.zip for every ABI and dies in seconds with
# "Build it first: make android-aar" when the AAR run did not get that far, so
# the second line of defence is the one that actually validates the input.
#
# $(call android_guard,android-build) and not a bare $(android_aar_guard):
# that variable was deleted when the guard became a $(call ...) and nothing
# noticed, so this recipe carried an *empty* first line and the rule was
# fail-open. Measured on the working tree before this task:
# `make -n android-apk TARGETS=desktop` printed
# `./scripts/android-fat-aar.sh --srcdir .../librewolf-153.0.4-1` - i.e. a
# 59 minute three-ABI Android AAR built out of the DESKTOP tree - and only
# then the "needs TARGETS to include android" line from the target below.
# An undefined make variable expands to the empty string in silence, which is
# landmine L4's shape in a Makefile: a check that fails open.
#
# It names android-build because that is the target whose work this rule does;
# both android-package and android-apk reach it as a prerequisite.
$(ANDROID_AAR_OUTDIR)/build-times.txt: $(android_aar_prereq)
	$(call android_guard,android-build)
	$(lw_tree_guard)
	$(android_l10n_base)
	$(android_fat_aar_cmd)

# `make android-package` is the android counterpart of `package`, and it carries
# its own guard rather than relying on the AAR rule's: when the AAR is already
# built the rule above does not run at all, so its guard is not a guard for this
# one.
#
# Where the desktop `package` ends in `cp -v ./*.xz .`, this one ends in a
# directory of APKs. scripts/android-apk.sh collects them into
# $(ANDROID_APK_OUTDIR)/apk/ itself - one per ABI plus a universal one, plus the
# Gradle output-metadata.json - so there is nothing for the Makefile to copy and
# no `cp` line here. Note "unsigned" in the task brief means *not release
# signed*: `mach gradle fenix:assembleDebug` signs with the Android debug
# keystore, so these APKs are debug-signed and installable, and a release
# signing key is LW-M6-01's problem and deliberately not this file's.
android-package: $(ANDROID_AAR_OUTDIR)/build-times.txt
	$(call android_guard,android-package)
	$(lw_tree_guard)
	$(android_l10n_base)
	./scripts/android-apk.sh \
		--srcdir "$(android_aar_srcdir)" \
		--aar-dir "$(ANDROID_AAR_OUTDIR)" \
		--outdir "$(ANDROID_APK_OUTDIR)" \
		--mozconfig "$(ANDROID_MOZCONFIG)" \
		--engine "$(CONTAINER_ENGINE)" \
		--image "$(android_build_image)" \
		$(ANDROID_APK_FLAGS)

# android-apk is the artifact-named spelling, an alias for the same reason
# android-aar is one: two recipes that must produce the same artifact are two
# recipes that will eventually not.
android-apk: android-package

# --- Android clean ----------------------------------------------------------
#
# The android counterpart of `clean` + `veryclean` in one target, because the
# board asks for one and because the thing worth reclaiming is the tree: the
# per-ABI objdirs live *inside* it (obj-*), so three ABIs plus the APK pass is
# ~65GB that only `rm -rf $(lw_source_dir)` gets back. It keeps the downloaded
# Firefox tarball, like `clean` and unlike `distclean`.
#
# Everything it removes is named with $(version)-$(release), which the release
# track block at the top of this file has already pointed at ./version.android
# and ./release.android - so a desktop tree, a desktop stamp and a desktop
# tarball of the same checkout are never operands. That independence is the
# whole point of the android targets and it is the one property of this recipe
# worth testing, so it was: in a scratch checkout carrying a full set of both
# tracks' artifacts, `make android-clean` removed firefox-153.0,
# librewolf-153.0esr-1, librewolf-targets-153.0esr-1-android,
# librewolf-android-{aar,apk}-153.0esr-1 and librewolf-153.0esr-1.source.tar.gz
# and left every 153.0.4 name and both tarballs standing; `make veryclean` and
# `make distclean` in the same checkout left every 153.0esr name standing.
#
# Two things it deliberately does NOT remove, both for the reason `clean`'s
# comment gives about $(ANDROID_AAR_OUTDIR):
#
#   - $(LW_ANDROID_SRCDIR). That is a tree the caller supplied and pointed the
#     build at; `make android-clean` has no business rm -rf-ing a path that was
#     handed to it for something else. $(lw_source_dir) - the tree `make
#     android-dir` itself creates in this checkout - is the only tree here.
#   - $(ANDROID_AAR_OUTDIR)/$(ANDROID_APK_OUTDIR) as *variables*. The default
#     names are listed literally, exactly as `clean` lists them, so an override
#     pointing outside the checkout survives.
#
# And one thing `clean` lists that this does not: $(ff_source_dir). That name is
# a *guess* derived from the artifact name, which `clean` keeps only because it
# has to work after `distclean` has removed the tarball it would otherwise ask.
# On the android track the guess is wrong - firefox-153.0esr.source.tar.xz
# unpacks to firefox-153.0 - so it would remove nothing on a good day, and on a
# machine where the two tracks happened to collide it is a hardcoded directory
# name pointed at the repository root next to a tree other agents read.
# "$(ff_tarball_dir)" is derived from the tarball, is the only name an
# interrupted `tar xf` can have left behind, and expands to "" (a silent no-op
# for rm -rf) when the tarball is not there.
#
# $(lw_tree_guard) is not decoration either: with TARGETS=desktop,android the
# release track block leaves $(version)/$(release) on the DESKTOP pair, so
# $(lw_source_dir) would be the desktop tree. The guard refuses that
# combination whenever the two tracks disagree, which is every case in which
# the operands would be ambiguous - and when they agree the two tracks name the
# same tree anyway, so removing it is unambiguous.
android-clean:
	$(call android_guard,android-clean)
	$(lw_tree_guard)
	rm -rf "$(ff_tarball_dir)" $(lw_source_dir) librewolf-targets-$(version)-$(release)-* librewolf-android-aar-$(version)-$(release) librewolf-android-apk-$(version)-$(release) $(lw_source_tarball) $(lw_source_tarball).sha256sum $(lw_source_tarball).sha512sum

check-patchfail:
	sh -c "./scripts/check-patchfail.sh" > patchfail.out

check-fuzz:
	-sh -c "./scripts/check-patchfail.sh --fuzz=0" > patchfail-fuzz.out
fixfuzz:
	sh -c "./scripts/fuzzfail.sh"

# Container images

# Which container engine the image targets drive. docker stays the default, so
# an existing `make docker-build-image` runs byte for byte the command it ran
# before this variable existed. Maintainers without docker say so explicitly:
#
#   make docker-build-image  CONTAINER_ENGINE=podman
#   make android-build-image CONTAINER_ENGINE=podman
#
# podman is command line compatible with docker for build/run/rmi, which is why
# a plain variable is enough and no per-engine argument translation is needed.
#
# Deliberately NOT auto-detected, i.e. not
# `CONTAINER_ENGINE ?= $(shell command -v docker || command -v podman)`:
#
#   - it makes the build environment implicit. A log line reading "docker build"
#     while podman actually ran is exactly the ambiguity a reproducibility
#     focused project should not introduce, and the two engines are not
#     interchangeable where it matters: podman resolves the short name in
#     `FROM ubuntu:jammy` through registries.conf, so the same Dockerfile can
#     pull a different base image on two machines.
#   - it costs a $(shell) at parse time on every single make invocation,
#     including `make help` and every `make -n`, which this Makefile otherwise
#     avoids on purpose (see the $(targets_stamp) comment).
#   - the failure mode it removes is a one-line error message; the failure mode
#     it adds is a build that silently used the other engine.
#
# Naming the engine is one word on the command line and it ends up in the shell
# history and the CI file, where it belongs.
CONTAINER_ENGINE ?= docker

build_image = librewolf-build-image
android_build_image = librewolf-android-build

# Both build targets pipe the Dockerfile on stdin with no build context at all
# ("- <"), which is why neither assets/Dockerfile nor assets/Dockerfile.android
# may ever COPY or ADD from the context. Neither does today; keep it that way,
# or these two lines have to grow a context argument and start uploading the
# whole source tree to the engine.
docker-build-image:
	$(CONTAINER_ENGINE) build --no-cache -t $(build_image) - < assets/Dockerfile

docker-run-build-job:
	$(CONTAINER_ENGINE) run -v $$(pwd):/output --rm $(build_image) sh -c "git pull && make fetch && make build package && cp -v ./*.xz /output"

docker-remove-image:
	$(CONTAINER_ENGINE) rmi $(build_image)

android-build-image:
	$(CONTAINER_ENGINE) build --no-cache -t $(android_build_image) - < assets/Dockerfile.android

# Still no android counterpart of docker-run-build-job, and LW-M2-06 - which
# added the targets it would have called - is the task that measured why. The
# two blockers below were checked against the running image and the running
# upstream repository, not predicted:
#
#   1. `podman run --rm librewolf-android-build git -C /source remote -v`
#      is https://codeberg.org/librewolf/source.git (HEAD 8232da0 when this was
#      written) and `grep -c android /source/Makefile` there is 0 - as is
#      `grep -c android` on the 225 line Makefile codeberg serves today. So
#      `git pull && make android-dir` inside the image is "No rule to make
#      target", after several GB of pull, until this branch lands upstream.
#      That one is only a matter of time.
#
#   2. The one that is not a matter of time. The image ships no container
#      engine (`command -v docker podman` finds neither inside it), and
#      scripts/android-fat-aar.sh and scripts/android-apk.sh are container
#      *drivers*: run inside the image, both die in preflight with
#      "container engine 'podman' not found in PATH", whatever --engine says.
#      Measured by running each of them in there. So even with the targets
#      present, an in-image `make android-build` stops before it compiles
#      anything. Making this real needs a no-container mode in those two
#      scripts - neither of which LW-M2-06 owns - or nested containers. Writing
#      a second, simpler, in-image build path here instead would be a build
#      path nothing has ever verified, producing a single-ABI artifact of a
#      different shape from the one we ship: exactly the plausible looking
#      thing this comment has refused to ship since LW-M0-12.
#
# The artifact shape point from LW-M0-12 still stands and is now concrete: the
# desktop job ends in `cp -v ./*.xz /output`, while an android run produces
# librewolf-android-aar-<v>-<r>/ (per-ABI maven zips + the merged AAR) and
# librewolf-android-apk-<v>-<r>/apk/*.apk. Both are already written straight to
# host directories by the scripts, so there is no artifact left to copy out.
#
# And the label, since that is where a :z would have gone. The scripts mount
# with ":z" already - MOUNT_OPT defaults to z in both, overridable with
# --mount-opt / LW_MOUNT_OPT - which is what makes `make android-package` work
# on this host at all. Measured here, SELinux Enforcing, podman rootless:
# `-v "$$PWD:/out"` answers `touch: cannot touch '/out/nolabel': Permission
# denied`; `-v "$$PWD:/out:z"` writes and leaves the path
# system_u:object_r:container_file_t:s0. ":z" is shared and ":Z" is exclusive,
# and a ~10GB tree that several agents and several passes read is exactly the
# case ":Z" breaks. The desktop docker-run-build-job above is still deliberately
# label-free, so existing docker users get the byte-identical command.
#
# So this target exists, is .PHONY, is documented, and fails loudly.
android-run-build-job:
	@echo "android-run-build-job: still not implemented - and no longer for want of make targets." >&2
	@echo "android-dir / android-build / android-package exist now. Two things stop this job from" >&2
	@echo "running them INSIDE $(android_build_image):" >&2
	@echo "  1. the image's /source is a clone of upstream codeberg, whose Makefile has no" >&2
	@echo "     android-* target, so 'git pull && make android-dir' finds nothing to make until" >&2
	@echo "     this branch has landed there;" >&2
	@echo "  2. the image ships no container engine, and scripts/android-fat-aar.sh and" >&2
	@echo "     scripts/android-apk.sh are container drivers - run inside it they both die with" >&2
	@echo "     \"container engine 'podman' not found in PATH\" before compiling anything." >&2
	@echo "" >&2
	@echo "Run it from the host instead. The scripts start the containers themselves and already" >&2
	@echo "mount with :z, which an SELinux Enforcing host requires:" >&2
	@echo "  make android-package CONTAINER_ENGINE=$(CONTAINER_ENGINE)" >&2
	@echo "Artifacts land in librewolf-android-aar-$(android_version)-$(android_release)/ and" >&2
	@echo "librewolf-android-apk-$(android_version)-$(android_release)/apk/*.apk - already on the host," >&2
	@echo "so there is nothing to copy out of a container." >&2
	@exit 1

android-remove-image:
	$(CONTAINER_ENGINE) rmi $(android_build_image)

setup-debian:
	apt-get -y install mercurial python3 python3-dev python3-pip curl wget dpkg-sig  libssl-dev zstd libxml2-dev

setup-fedora:
	dnf -y install python3 curl wget zstd python3-devel python3-pip mercurial openssl-devel libxml2-devel

# Testing_targets=full-test test

test: full-test

# full-test: produce the xz artifact using bsys6 from scratch
full-test: $(lw_source_tarball)
	${MAKE} -f assets/testing.mk bsys6_x86_64_linux_xz_artifact

test-linux: full-test

test-candidate:
	$(MAKE) FF_CHANNEL=candidates FF_BUILD=$(FF_BUILD) test-linux

test-beta:
	$(MAKE) FF_CHANNEL=beta FF_BUILD=$(FF_BUILD) FF_BETA_SUFFIX=$(FF_BETA_SUFFIX) test-linux

test-macos: $(lw_source_tarball)
	${MAKE} -f assets/testing.mk bsys6_x86_64_macos_dmg_artifact

test-windows: $(lw_source_tarball)
	${MAKE} -f assets/testing.mk bsys6_x86_64_windows_zip_artifact
