#!/usr/bin/env python3
#
# check-patch-order.py - assert the patch lists apply in a working order.
#
# LW-M1-10. Run it with no arguments; it exits 0 when the lists are fine and 1
# with an explanation when they are not. It reads only this repository - no
# Firefox tree, no network - so it is cheap enough to run before `make fetch`,
# which is where .forgejo/workflows/android-test.yaml calls it.
#
#
# WHAT IT CHECKS
#
# 1. The declared ordering constraints (docs/android/AGENTS.md, "Patch ordering
#    constraints") hold in the sequence the patcher actually applies.
# 2. Every *other* pair of co-applied patches that touch the same tree file is
#    one this repository has already looked at. A new one is a hard failure that
#    asks a human to classify it, because "these two patches edit the same file"
#    is where an ordering constraint comes from.
#
# Check 2 is the derivation: the pairs come from the `--- a/x` / `+++ b/x`
# headers of the patch files themselves, so a patch that grows a new hunk in a
# file another patch touches is caught without anyone updating a list of names.
#
#
# THE APPLY SEQUENCE IS NOT ONE LIST
#
# scripts/librewolf-patches.py:116-124 applies assets/patches/common.txt first,
# then one list per --targets in KNOWN_TARGETS order. So there is no single
# ordering to check: there is one sequence per target, and common.txt is a
# prefix of all of them.
#
# This matters. Since LW-M1-01 the mozilla_dirs/xdg-dir pair is CROSS-LIST -
# mozilla_dirs is in common.txt, xdg-dir in desktop.txt. Both patches edit
# toolkit/xre/nsXREDirProvider.cpp and only apply in that order. A checker that
# compared positions within a single list would not see the pair at all - after
# a swap, common.txt holds only xdg-dir and desktop.txt holds only mozilla_dirs,
# so there is nothing left to compare - and it would pass a genuinely broken
# ordering. scripts/enable-patch.sh models the
# same thing in applies_before(); this script models it by building the whole
# sequence.
#
#
# WHY THE DIRECTIONS ARE DECLARED AND NOT DERIVED
#
# Deriving *which* pairs share a file is easy and exact. Deriving which way
# round a sharing pair has to go is not, and the honest answer after measuring
# it on this tree is that no content heuristic is usable as a rule:
#
#   * "the hunks overlap or abut" gets 1 of the 5 real constraints -
#     firefox-in-ua/moz-configure, which abuts at toolkit/moz.configure:27|28
#     and :34|35 - and misses the other 4. autoconfig-setEnv/profile-directory,
#     fpp-canvas-fix/webgl-permission-common, mozilla_dirs/xdg-dir and
#     webgl-permission-common/webgl-prompt-default all edit far-apart regions
#     of a shared file. It also fires on 6 of the 31 pairs that are known to be
#     fine, nearly all of them under browser/components/preferences/, where a
#     dozen patches have shipped in their current order for years.
#
#   * "the later patch's context contains lines the earlier one adds" also gets
#     1 of the 5 - and a different one: the webgl pref block, where the quoted
#     lines ('- name: librewolf.webgl.prompt') are unique identifiers. It fires
#     on 6 order-free pairs, because JS boilerplate like
#     `Preferences.addSetting({`, `headingLevel: 2,` and `mirror: always`
#     appears verbatim in both halves of a pair by coincidence, and it
#     disagrees with itself, reporting some pairs as dependent in both
#     directions at once.
#
# Both are therefore printed as *evidence* when a new pair shows up, clearly
# labelled as weak, and neither decides anything. The direction of a constraint
# is a human finding, recorded in CONSTRAINTS below with the evidence that
# established it. LW-M1-09 is the reason this care is taken: three patches touch
# browser/installer/package-manifest.in at lines ~42, ~251 and ~397 and their
# order genuinely does not matter, so a checker that treated every shared file
# as a constraint would be wrong about most of this tree and would get switched
# off.
#
#
# HOW TO SATISFY IT WHEN IT FAILS ON A NEW PAIR
#
# Open both patches, look at what they do to the shared file, and then either
#   - add a (first, then, file, why) row to CONSTRAINTS if one order is
#     required, or
#   - add the pair to REVIEWED_ORDER_FREE with a one-line reason.
# The failure message prints the row to paste in either case. Do not "fix" a
# failure by deleting a row.
#

import itertools
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
PATCH_LIST_DIR = REPO_DIR / "assets" / "patches"

# Mirrors scripts/librewolf-patches.py:34. 'common' is not a target: it is
# applied unconditionally, before whichever of these are selected, in the order
# listed here.
KNOWN_TARGETS = ("desktop", "android")

# Patches the patcher applies from its own call site rather than from a list.
# scripts/librewolf-patches.py:385 applies this one after every list entry, on
# every target, and it shares four files with list entries - so it is part of
# the sequence and has to be modelled. LW-M1-09 folded xmas.patch into the
# lists; this is the only one left. If it ever moves into a list, delete it
# here: the duplicate check below will say so.
# Patches applied from their own call site in scripts/librewolf-patches.py rather
# than from a list, and therefore invisible to the list-order model unless named
# here. LW-M1-13 moved pref-pane-small into assets/patches/desktop.txt, so this is
# now empty — keep it that way unless someone adds a new out-of-list call site.
OUT_OF_LIST_TAIL = ()


# --------------------------------------------------------------------------
# The declared constraints.
#
# The declarations below are the authority the CI gate runs. LW-M3-07 added
# no-adjust -> ubo-preinstall because the HomeActivity startup gate requires
# no-adjust's parameterless splash-screen method. The older AGENTS.md table
# omits that row; each declaration here carries its own source/replay evidence.
#
# 'first' must apply before 'then'. 'file' is the tree file they share and is
# re-checked against the patch contents on every run, so a split or a rebase
# that moves the hunks out of that file fails loudly instead of leaving a row
# that quietly checks nothing.
#
# 'file' may also be a TUPLE of files, and must be when the pair shares more
# than one. Before LW-M4-01 it was always a single string and a constrained pair
# that shared a second file was reported as an error with no way to record the
# review - which is a hole, not a safety property: no-adjust -> no-glean shares
# five files, ordering is mandatory because of two of them, and the other three
# only shift by an offset. Every file the pair shares must be listed here or the
# run still fails; that is what keeps a NEW shared file from appearing silently.
# --------------------------------------------------------------------------

CONSTRAINTS = (
    ('patches/android/firefox-suggest-policy.patch', 'patches/android/firefox-suggest-data.patch', ('mobile/android/android-components/components/feature/fxsuggest/src/main/java/mozilla/components/feature/fxsuggest/FxSuggestStorage.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/search/SearchEngineFragment.kt', 'mobile/android/fenix/app/src/main/res/values/firefox_suggest_policy_strings.xml', 'mobile/android/fenix/app/src/main/res/xml/search_settings_preferences.xml'), 'The explicit data installer extends Task26 admission and settings controls; inverse replay fails on all four shared paths (LW-M7-29 ordering-review.json).'),
    ('patches/android/ubo-preinstall.patch', 'patches/android/cookie-banner-controls.patch', ('mobile/android/fenix/app/src/main/res/values/strings.xml',), 'Retain uBO before graphics before cookie controls; the alternate attempt fails first in graphics, not in the cookie candidate (LW-M7-21 cookie-controls-order.json).'),
    ('patches/android/canvas-webgl-permissions.patch', 'patches/android/cookie-banner-controls.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/quicksettings/QuickSettingsSheetDialogFragment.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/trustpanel/TrustPanelFragment.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/trustpanel/ui/ProtectionPanel.kt', 'mobile/android/fenix/app/src/main/res/values/strings.xml', 'mobile/android/geckoview/api.txt', 'mobile/android/geckoview/src/main/java/org/mozilla/geckoview/StorageController.java', 'mobile/shared/components/geckoview/GeckoViewStartup.sys.mjs', 'mobile/shared/modules/geckoview/GeckoViewStorageController.sys.mjs'), 'The expanded native cookie candidate requires the preceding graphics UI/context; its alternate order fails at cookie application. All eight shared files were replayed (LW-M7-21 cookie-controls-order.json).'),
    # LW-M7-26: measured Suggest composition.
    ('patches/android/no-adjust.patch', 'patches/android/firefox-suggest-policy.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt'), 'Keep the existing predecessor chain before this candidate; inverse attempt failed before the candidate and is not an isolated pair conflict (LW-M7-26 ordering-review.json).'),
    ('patches/android/no-gms.patch', 'patches/android/firefox-suggest-policy.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt'), 'Candidate requires this predecessor in the tested full composition (LW-M7-26 ordering-review.json).'),
    ('patches/android/sync-opt-in.patch', 'patches/android/firefox-suggest-policy.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt', 'mobile/android/fenix/app/src/test/java/org/mozilla/fenix/helpers/FenixRobolectricTestApplication.kt'), 'Candidate requires this predecessor in the tested full composition (LW-M7-26 ordering-review.json).'),
    # LW-M7-21: scoped cookie-controls/Sync composition replay.
    # LW-M7-20: retained scoped alternate-order replay, including explicit composition constraint.
    ('patches/android/no-nimbus.patch', 'patches/android/sync-opt-in.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/HomeActivity.kt',), 'The scoped candidate is authored after this predecessor; moving it earlier fails the measured complete scoped replay (LW-M7-20 ordering-review.json).'),
    ('patches/android/no-adjust.patch', 'patches/android/sync-opt-in.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/HomeActivity.kt'), 'Keep the existing no-adjust -> no-gms predecessor chain ahead of the selected Sync integration order. The inverse attempt failed in no-gms before Sync; this is a chosen composition constraint, not an isolated intrinsic pair conflict (LW-M7-20 ordering-review.json).'),
    ('patches/android/ubo-preinstall.patch', 'patches/android/sync-opt-in.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/HomeActivity.kt'), 'The scoped candidate is authored after this predecessor; moving it earlier fails the measured complete scoped replay (LW-M7-20 ordering-review.json).'),
    (
        "patches/android/webgl-prompt-default.patch",
        "patches/android/canvas-webgl-permissions.patch",
        "modules/libpref/init/StaticPrefList.yaml",
        "LW-M7-14 removes the predecessor's Android false block together with the complete native/GV/Fenix bridge.",
    ),
    (
        "patches/webgl-permission-common.patch",
        "patches/android/canvas-webgl-permissions.patch",
        ("dom/canvas/ClientWebGLContext.cpp", "modules/libpref/init/StaticPrefList.yaml"),
        "LW-M7-14 wraps the common GetWebGLPermission/IsWebGLAllowed helpers and its context-creation call; "
        "the pref hunk also requires the common definition and the later Android default override.",
    ),
    (
        "patches/android/ubo-preinstall.patch",
        "patches/android/canvas-webgl-permissions.patch",
        "mobile/android/fenix/app/src/main/res/values/strings.xml",
        "LW-M7-14's terminal resource hunk uses the new librewolf_ubo_setup_* strings as context.",
    ),
    (
        "patches/android/no-adjust.patch",
        "patches/android/ubo-preinstall.patch",
        (
            "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt",
            "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/HomeActivity.kt",
            "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Components.kt",
        ),
        "ubo error UI requires no-adjust's parameterless createSplashScreenOperation in HomeActivity; "
        "the other shared files are disjoint; pristine forward replay passes and reverse fails at fuzz=0; "
        "docs/android/evidence/lw-m3-07/completion-20260908/order-replay-pristine.json",
    ),
    (
        "patches/autoconfig-setEnv.patch",
        "patches/profile-directory.patch",
        "extensions/pref/autoconfig/src/prefcalls.js",
        "docs/android/AGENTS.md ordering table; both in common.txt, and the "
        "comment on the profile-directory entry says 'must apply AFTER it'",
    ),
    (
        "patches/firefox-in-ua.patch",
        "patches/moz-configure.patch",
        "toolkit/moz.configure",
        "docs/android/AGENTS.md ordering table; the hunks abut - firefox-in-ua "
        "holds :28-34 and moz-configure holds :22-27 and :35-40",
    ),
    (
        "patches/fpp-canvas-fix.patch",
        "patches/webgl-permission-common.patch",
        "dom/canvas/ClientWebGLContext.cpp",
        "docs/android/AGENTS.md ordering table; LW-M1-08 kept the split half in "
        "the monolith's position and both list comments record the direction",
    ),
    (
        "patches/mozilla_dirs.patch",
        "patches/xdg-dir.patch",
        "toolkit/xre/nsXREDirProvider.cpp",
        "docs/android/AGENTS.md ordering table. CROSS-LIST since LW-M1-01: "
        "mozilla_dirs is common, xdg-dir is desktop. xdg-dir's hunk headers are "
        "already in post-mozilla_dirs coordinates (:1333 is :1327 in the "
        "pristine tree, the +6 lines mozilla_dirs adds above it), which is what "
        "makes the direction mandatory",
    ),
    (
        "patches/webgl-permission-common.patch",
        "patches/android/webgl-prompt-default.patch",
        "modules/libpref/init/StaticPrefList.yaml",
        "also in the AGENTS.md table - see the note above. The Android patch's "
        "context quotes the pref block the common half adds "
        "('# Prefs starting with \"librewolf.\"', '- name: "
        "librewolf.webgl.prompt'), so it cannot apply first. Satisfied for free "
        "today because common.txt precedes android.txt, and that is exactly the "
        "reasoning assets/patches/android.txt records for this entry",
    ),
    (
        "patches/xmas-common.patch",
        "patches/android/autoconfig-resource-fallback.patch",
        "lw/moz.build",
        "LW-M3-02, landing the LW-M3-08 autoconfig spike. NOT in the AGENTS.md "
        "table - see the note above. xmas-common CREATES lw/moz.build (its hunk "
        "is @@ -0,0 +1,12 @@ against an empty file); the android patch appends "
        "FINAL_TARGET_FILES.defaults.autoconfig to it with @@ -10,3 +10,12 @@, "
        "i.e. its context is the three local-settings.js lines xmas-common adds, "
        "so it cannot apply first - there is no file for it to apply to. Third "
        "CROSS-LIST pair (common.txt -> android.txt), satisfied for free because "
        "common.txt precedes every target list, which is why this row is a "
        "declaration rather than a reordering",
    ),
    (
        "patches/android/no-adjust.patch",
        "patches/android/no-glean.patch",
        (
            "mobile/android/fenix/app/build.gradle",
            "mobile/android/fenix/app/src/main/AndroidManifest.xml",
            "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt",
            "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Analytics.kt",
            "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/onboarding/OnboardingFragment.kt",
        ),
        "LW-M4-01. MEASURED, not derived from the overlap hint. no-adjust removes "
        "the AdjustMetricsService and InstallReferrerMetricsService imports and "
        "list entries that sit immediately around the Glean ones, and in "
        "OnboardingFragment.kt it removes the rtamoAttributionHandler line that "
        "was no-glean's trailing context. Generated against the pristine tree, "
        "no-glean's three Analytics.kt hunks and one OnboardingFragment.kt hunk "
        "are REJECTED after no-adjust, and fuzz does not rescue them because the "
        "missing lines are context on both sides. no-glean's hunks are therefore "
        "in post-no-adjust coordinates, which is the list order. The pair also "
        "shares app/build.gradle, AndroidManifest.xml and FenixApplication.kt, "
        "where the regions are disjoint and the order only shifts offsets",
    ),
    (
        "patches/android/no-adjust.patch",
        "patches/android/no-gms.patch",
        (
            "gradle/libs.versions.toml",
            "mobile/android/fenix/app/build.gradle",
            "mobile/android/fenix/app/src/main/AndroidManifest.xml",
            "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt",
            "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Components.kt",
            "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt",
            "mobile/android/fenix/config/detekt-baseline.xml",
            "mobile/android/fenix/docs/index.rst",
        ),
        "LW-M4-05. MEASURED per shared file, not derived from the overlap hint: "
        "each file was replayed on its own through the whole apply sequence in "
        "list order and with this pair swapped. SEVEN of the eight files are "
        "order-free (byte-identical either way). gradle/libs.versions.toml is "
        "not: no-gms's two hunks are @@ -55,16 @@ and @@ -221,20 @@, i.e. in "
        "post-no-adjust coordinates, and their context no longer contains the "
        "'installreferrer = \"2.2\"' and 'adjust = \"5.7.0\"' lines no-adjust "
        "deletes, so with no-gms first both hunks REJECT (patch exits 1, one "
        ".rej). That single file makes the direction mandatory",
    ),
    (
        "patches/android/no-glean.patch",
        "patches/android/no-gms.patch",
        (
            "mobile/android/fenix/app/build.gradle",
            "mobile/android/fenix/app/src/main/AndroidManifest.xml",
            "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt",
        ),
        "LW-M4-05. MEASURED the same way. app/build.gradle and "
        "FenixApplication.kt are order-free (byte-identical either way); "
        "AndroidManifest.xml is not. no-gms removes the three firebase_* "
        "<meta-data> flags, and the TRAILING CONTEXT of that hunk is the "
        "'<!-- LibreWolf: GleanDebugActivity is declared exported and "
        "singleInstance ... -->' comment block that NO-GLEAN ADDS. Running "
        "no-gms first rejects that hunk (patch exits 1, one .rej), so the "
        "direction is mandatory",
    ),
    (
        "patches/android/no-adjust.patch",
        "patches/android/no-crashreporter.patch",
        (
            "mobile/android/fenix/app/build.gradle",
            "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Analytics.kt",
            "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Components.kt",
        ),
        "LW-M4-04. MEASURED the same way as the two rows above - each shared "
        "file replayed on its own through the whole android sequence in list "
        "order and with this pair swapped. The overlap hint called "
        "app/build.gradle and Analytics.kt 'overlap or abut' and Components.kt "
        "'disjoint', and it is right about the direction here only by accident: "
        "what makes the order mandatory is that no-crashreporter's hunks are in "
        "post-no-adjust coordinates in TWO files. In app/build.gradle, "
        "no-crashreporter's hunk 2 (@@ -391,7 +391,6 @@, deleting "
        "buildConfigField 'String', 'SENTRY_TOKEN', 'null' from "
        "android.buildTypes.debug) has trailing context that no longer contains "
        "the ADJUST_TOKEN line immediately below it - the line no-adjust's "
        "@@ -406,7 +399,6 @@ deletes - so with no-crashreporter first that hunk "
        "REJECTS (patch exits 1, one .rej). In Analytics.kt, no-crashreporter's "
        "hunk 1 (@@ -13,21 +13,9 @@) spans the import block from "
        "runtimetagproviders.BuildRuntimeTagProvider to "
        "components.metrics.MetricController, a range that in the pristine file "
        "still holds the AdjustMetricsService and InstallReferrerMetricsService "
        "imports no-adjust removes; it REJECTS too, and fuzz does not rescue it "
        "because the extra lines sit in the middle of the context. Components.kt "
        "is order-free (byte-identical either way, sha256 c41c47a2d34ac740...), "
        "but one mandatory file is enough to fix the pair",
    ),
    (
        "patches/android/no-gms.patch",
        "patches/android/no-crashreporter.patch",
        (
            "mobile/android/fenix/app/build.gradle",
            "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Components.kt",
            "mobile/android/focus-android/app/build.gradle",
        ),
        "LW-M4-04. MEASURED the same way. TWO of the three shared files are "
        "order-free - fenix app/build.gradle and Components.kt come out "
        "byte-identical either way (sha256 1fd0d1b9149c3e06... and "
        "c41c47a2d34ac740...), which is worth stating because the overlap hint "
        "flags fenix app/build.gradle as 'overlap or abut' and it is wrong. The "
        "file that fixes the direction is mobile/android/focus-android/app/"
        "build.gradle: no-crashreporter's hunk 2 (@@ -315,7 +318,8 @@, deleting "
        "implementation libs.sentry) has leading context "
        "libs.google.material / libs.kotlinx.coroutines / libs.mozilla.glean, "
        "and in the pristine file the two lines no-gms deletes - "
        "implementation libs.play.review and libs.play.review.ktx - sit between "
        "libs.mozilla.glean and libs.sentry. Run no-crashreporter first and that "
        "hunk REJECTS (patch exits 1, one .rej). focus-android is not in the "
        "LibreWolf build (settings.gradle includes :focus-android only when "
        "MOZ_ANDROID_SUBPROJECT is unset or 'focus'), so this constraint never "
        "changes a shipped byte - it keeps `make check-patchfail` green, which "
        "patches the whole tree regardless of subproject",
    ),
)


# --------------------------------------------------------------------------
# Pairs that share a tree file with no mandatory order.
#
# This is a baseline, not a set of proofs. Every entry below was co-applied, in
# the order recorded in the lists, by the patch set that shipped when LW-M1-10
# landed - that order is what `make check-patchfail` is green on, so it is known
# to work. What the table buys is not confidence in these pairs: it is that a
# *new* pair, or an existing pair that grows a new shared file, cannot appear
# without someone deciding which of the two tables it belongs in.
#
# Entries are unordered - "order-free" means either way round is fine - and each
# records the exact set of shared files, so a rebase that makes two of these
# patches meet in a new file is reported.
# --------------------------------------------------------------------------

REVIEWED_ORDER_FREE = (
    ('patches/android/rs-blocker-android.patch', 'patches/android/firefox-suggest-data.patch', ('third_party/application-services/components/remote_settings/src/client.rs',), 'Both scoped orders produce the same 17 code files; explicit local import retains the generic remote network blocker (LW-M7-29 ordering-review.json).'),
    ('patches/android/search-config.patch', 'patches/android/firefox-suggest-data.patch', ('third_party/application-services/components/remote_settings/src/client.rs',), 'Both scoped orders produce the same 17 code files; search packaged attachment lookup and explicit Suggest import remain separate (LW-M7-29 ordering-review.json).'),
    (
        "patches/android/ubo-readiness.patch",
        "patches/android/extension-permission-durability.patch",
        ("mobile/shared/modules/geckoview/GeckoViewWebExtension.sys.mjs",),
        "LW-M7-31 root replay: readiness and uninstall persistence edit separate "
        "methods. Both orders applied to the recovered pre-readiness source and "
        "produced identical bytes. See lw-m7-21/extension-permission-order.json.",
    ),
    ('patches/android/no-adjust.patch', 'patches/android/cookie-banner-controls.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt',), 'Both scoped orders, including the archived-baseline uBO-readiness overlay, yield identical bytes in all 37 inputs (LW-M7-21 cookie-controls-order.json).'),
    ('patches/android/no-onboarding.patch', 'patches/android/cookie-banner-controls.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt',), 'Both scoped orders, including the archived-baseline uBO-readiness overlay, yield identical bytes in all 37 inputs (LW-M7-21 cookie-controls-order.json).'),
    ('patches/android/no-gms.patch', 'patches/android/cookie-banner-controls.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt', 'mobile/android/fenix/app/src/main/res/values/preference_keys.xml'), 'Both scoped orders, including the archived-baseline uBO-readiness overlay, yield identical bytes in all 37 inputs (LW-M7-21 cookie-controls-order.json).'),
    ('patches/android/no-crashreporter.patch', 'patches/android/cookie-banner-controls.patch', ('mobile/android/fenix/app/src/main/res/values/strings.xml',), 'Both scoped orders, including the archived-baseline uBO-readiness overlay, yield identical bytes in all 37 inputs (LW-M7-21 cookie-controls-order.json).'),
    ('patches/android/no-suggest.patch', 'patches/android/cookie-banner-controls.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt',), 'Both scoped orders, including the archived-baseline uBO-readiness overlay, yield identical bytes in all 37 inputs (LW-M7-21 cookie-controls-order.json).'),
    ('patches/android/search-config.patch', 'patches/android/cookie-banner-controls.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt',), 'Both scoped orders, including the archived-baseline uBO-readiness overlay, yield identical bytes in all 37 inputs (LW-M7-21 cookie-controls-order.json).'),
    ('patches/android/update-check.patch', 'patches/android/cookie-banner-controls.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/SettingsFragment.kt', 'mobile/android/fenix/app/src/main/res/xml/preferences.xml'), 'Both scoped orders, including the archived-baseline uBO-readiness overlay, yield identical bytes in all 37 inputs (LW-M7-21 cookie-controls-order.json).'),
    ('patches/android/ubo-readiness.patch', 'patches/android/cookie-banner-controls.patch', ('mobile/android/geckoview/api.txt', 'mobile/shared/components/geckoview/GeckoViewStartup.sys.mjs'), 'Both scoped orders, including the archived-baseline uBO-readiness overlay, yield identical bytes in all 37 inputs (LW-M7-21 cookie-controls-order.json).'),
    ('patches/android/privacy-defaults.patch', 'patches/android/cookie-banner-controls.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt',), 'Both scoped orders, including the archived-baseline uBO-readiness overlay, yield identical bytes in all 37 inputs (LW-M7-21 cookie-controls-order.json).'),
    ('patches/android/sync-opt-in.patch', 'patches/android/cookie-banner-controls.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/SettingsFragment.kt',), 'Both scoped orders, including the archived-baseline uBO-readiness overlay, yield identical bytes in all 37 inputs (LW-M7-21 cookie-controls-order.json).'),
    # LW-M7-26: measured Suggest composition.
    ('patches/android/no-onboarding.patch', 'patches/android/firefox-suggest-policy.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt',), 'Both tested orders apply and yield identical bytes in all 20 scoped files (LW-M7-26 ordering-review.json).'),
    ('patches/android/no-glean.patch', 'patches/android/firefox-suggest-policy.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/SecretSettingsFragment.kt'), 'Both tested orders apply and yield identical bytes in all 20 scoped files (LW-M7-26 ordering-review.json).'),
    ('patches/android/no-suggest.patch', 'patches/android/firefox-suggest-policy.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt',), 'Both tested orders apply and yield identical bytes in all 20 scoped files (LW-M7-26 ordering-review.json).'),
    ('patches/android/search-config.patch', 'patches/android/firefox-suggest-policy.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/SecretSettingsFragment.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt'), 'Both tested orders apply and yield identical bytes in all 20 scoped files (LW-M7-26 ordering-review.json).'),
    ('patches/android/ubo-preinstall.patch', 'patches/android/firefox-suggest-policy.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt',), 'Both tested orders apply and yield identical bytes in all 20 scoped files (LW-M7-26 ordering-review.json).'),
    ('patches/android/privacy-defaults.patch', 'patches/android/firefox-suggest-policy.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt',), 'Both tested orders apply and yield identical bytes in all 20 scoped files (LW-M7-26 ordering-review.json).'),
    ('patches/android/cookie-banner-controls.patch', 'patches/android/firefox-suggest-policy.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt',), 'Both orders apply against the archived Settings input with identical final bytes (LW-M7-21 suggest-cookie-order.json).'),
    # LW-M7-21: scoped cookie-controls/Sync composition replay.
    # LW-M7-20: retained scoped alternate-order replay, including explicit composition constraint.
    ('patches/android/no-glean.patch', 'patches/android/sync-opt-in.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt',), 'Both orders apply with all other scoped predecessors retained and yield identical bytes in all 23 files (LW-M7-20 ordering-review.json).'),
    ('patches/android/no-gms.patch', 'patches/android/sync-opt-in.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/BackgroundServices.kt'), 'Both orders apply with all other scoped predecessors retained and yield identical bytes in all 23 files (LW-M7-20 ordering-review.json).'),
    ('patches/android/no-suggest.patch', 'patches/android/sync-opt-in.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/HomeActivity.kt',), 'Both orders apply with all other scoped predecessors retained and yield identical bytes in all 23 files (LW-M7-20 ordering-review.json).'),
    ('patches/android/update-check.patch', 'patches/android/sync-opt-in.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/HomeActivity.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/SettingsFragment.kt'), 'Both orders apply with all other scoped predecessors retained and yield identical bytes in all 23 files (LW-M7-20 ordering-review.json).'),
    ('patches/android/canvas-webgl-permissions.patch', 'patches/android/sync-opt-in.patch', ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/browser/BaseBrowserFragment.kt',), 'Both orders apply with all other scoped predecessors retained and yield identical bytes in all 23 files (LW-M7-20 ordering-review.json).'),
    ("patches/android/no-nimbus.patch", "patches/android/home-section-defaults.patch",
     ("mobile/android/fenix/app/nimbus.fml.yaml",),
     "LW-M7-24 edits only the home defaults near the start; no-nimbus edits fission around line 510. "
     "Both orders replay with zero fuzz to the same final hash; home-first shifts later hunks by two lines. "
     "docs/android/evidence/lw-m7-24/replay.log"),
    ("patches/android/no-crashreporter.patch", "patches/android/canvas-webgl-permissions.patch",
     ("mobile/android/fenix/app/src/main/res/values/strings.xml",),
     "LW-M7-14: crash body at the existing startup strings and new terminal permission strings are disjoint."),
    ("patches/android/ubo-readiness.patch", "patches/android/canvas-webgl-permissions.patch",
     ("mobile/android/geckoview/api.txt", "mobile/shared/components/geckoview/GeckoViewStartup.sys.mjs"),
     "LW-M7-14: ContentPermission/StorageController API and permission actor/storage registration "
     "are separate from WebExtensionController API and uBO events; existing apply order retained."),
    ("patches/fpp-canvas-fix.patch", "patches/android/canvas-webgl-permissions.patch",
     ("dom/canvas/ClientWebGLContext.cpp",),
     "LW-M7-14: extraction randomization hunks are separate from includes and WebGL creation helpers."),
    # LW-M4-12. l10n-strings and no-onboarding share exactly one tree file,
    # ContinuousOnboardingFeatureTest.kt, and nothing else. no-onboarding
    # inverts three day-2/3/7 gating assertions at :80-108; l10n-strings
    # replaces two hardcoded English brand strings in
    # getNotificationOnboardingPageState at ~:240 with getString() calls,
    # because mobile/android/lw-brand rewrites the brand out of the resources
    # those assertions compare against. ~130 lines apart, neither quotes a line
    # the other writes. MEASURED, not eyeballed: both orders applied to the
    # pristine file exit 0 with no .rej and give a byte-identical result
    # (sha256 1f7c913bc77ec1dc0a38b64bebf1e1f2263d3b833c737fa8a2ed632c1145556b);
    # in the swapped order l10n-strings' single hunk lands at offset -6.
    ("patches/android/no-onboarding.patch", "patches/android/l10n-strings.patch",
     ("mobile/android/fenix/app/src/test/java/org/mozilla/fenix/onboarding/"
      "continuous/ContinuousOnboardingFeatureTest.kt",),
     "disjoint regions of ContinuousOnboardingFeatureTest.kt (:80-108 vs ~:240); "
     "measured byte-identical both ways, offset -6 when swapped (LW-M4-12)"),

    # LW-M4-04's no-crashreporter lands in GeckoProvider.kt alongside two patches
    # that were already there. Reviewed by reading the hunks rather than trusting
    # the overlap hint: no-crashreporter edits the import block (lines 7-25) and
    # the runtime-settings builder around :71-84, while about-config edits
    # :120-127 and isolated-process :131-139. Three disjoint regions of one file;
    # order only shifts offsets. Recorded so a NEW hunk that does collide is still
    # caught, which is the point of classifying rather than exempting the file.
    ("patches/android/about-config.patch", "patches/android/no-crashreporter.patch",
     ("mobile/android/fenix/app/src/main/java/org/mozilla/fenix/gecko/GeckoProvider.kt",),
     "disjoint regions of GeckoProvider.kt: :120-127 vs :7-25 and :71-84 (LW-M4-04)"),
    ("patches/android/isolated-process.patch", "patches/android/no-crashreporter.patch",
     ("mobile/android/fenix/app/src/main/java/org/mozilla/fenix/gecko/GeckoProvider.kt",),
     "disjoint regions of GeckoProvider.kt: :131-139 vs :7-25 and :71-84 (LW-M4-04)"),
    # LW-M4-04. no-glean and no-crashreporter share fenix app/build.gradle and
    # Analytics.kt, and unlike the no-adjust and no-gms pairs above this one is
    # genuinely order-free: MEASURED by replaying each shared file through the
    # whole android sequence in list order and with the pair swapped. Both files
    # come out byte-identical (app/build.gradle sha256 1fd0d1b9149c3e06...,
    # Analytics.kt sha256 eab5e34448c7fc8f...), patch exits 0 and writes no .rej
    # either way. Stated honestly, because the overlap hint calls Analytics.kt
    # "overlap or abut" and it is half right: with no-crashreporter first, its
    # import hunk lands "with fuzz 1" (no-glean's GleanMetricsService /
    # GleanUsageReportingMetricsService imports are still in the middle of its
    # context) and no-glean's own hunk then lands with fuzz 1 too. Fuzz rescues
    # it, the result is identical, and `make check-patchfail` does not treat
    # fuzz as failure - but this is the one row here that leans on fuzz, so a
    # future rebase that tightens fuzz has to look at it again. The list order
    # (no-glean before no-crashreporter) applies both hunks at fuzz 0.
    ("patches/android/no-glean.patch", "patches/android/no-crashreporter.patch",
     ("mobile/android/fenix/app/build.gradle",
      "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Analytics.kt"),
     "measured order-free (LW-M4-04): both orders exit 0 with no .rej and give "
     "byte-identical files; the swapped order needs fuzz 1 on Analytics.kt"),

    # LW-M1-09's finding, and the reason this script does not treat a shared
    # file as a constraint: three patches edit browser/installer/
    # package-manifest.in at ~42, ~251 and ~397 and order only shifts offsets.
    ("patches/remove-pingsender-desktop.patch", "patches/temp-macos-fix.patch",
     ("browser/installer/package-manifest.in",),
     "disjoint regions of the installer manifest (LW-M1-09)"),
    ("patches/remove-pingsender-desktop.patch", "patches/xmas-desktop.patch",
     ("browser/installer/package-manifest.in",),
     "disjoint regions of the installer manifest (LW-M1-09)"),
    ("patches/temp-macos-fix.patch", "patches/xmas-desktop.patch",
     ("browser/installer/package-manifest.in",),
     "disjoint regions of the installer manifest (LW-M1-09)"),

    # LW-M4-10. Both patches edit mobile/android/fenix/.../utils/Settings.kt and
    # nothing else in common: no-adjust flips shouldShowMarketingOnboarding's
    # default at ~2280, no-onboarding replaces shouldShowOnboarding's body at
    # ~2203-2222. ~60 lines apart, neither quotes a line the other touches, so
    # the only effect of the order is an offset on no-adjust's single hunk when
    # no-onboarding (a net -9 lines) goes first.
    ("patches/android/no-adjust.patch", "patches/android/no-onboarding.patch",
     ("mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt",),
     "disjoint regions of Settings.kt (~2280 vs ~2203); order only shifts an offset (LW-M4-10)"),

    # LW-M4-05, both measured by replaying the shared file through the whole
    # apply sequence in list order and with the pair swapped: patch exits 0 with
    # no .rej both ways and the resulting file is byte-identical (sha256).
    #
    # no-onboarding rewrites shouldShowOnboarding in Settings.kt at ~2203;
    # no-gms deletes the overridePushServer property at ~1954. Different
    # regions, neither quotes a line the other touches.
    ("patches/android/no-onboarding.patch", "patches/android/no-gms.patch",
     ("mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt",),
     "disjoint regions of Settings.kt (~1954 vs ~2203); measured identical both ways (LW-M4-05)"),
    #
    # The TOPSRCDIR build.gradle: no-gms drops `classpath libs.osslicenses.plugin`
    # from the buildscript block at ~line 25, build-fixes rewrites
    # computeVersionCode() at ~line 168. In list order build-fixes' single hunk
    # applies at offset -1; that is the whole effect of the ordering.
    ("patches/android/no-gms.patch", "patches/android/build-fixes.patch",
     ("build.gradle",),
     "disjoint regions of the root build.gradle (~25 vs ~168); measured identical both ways (LW-M4-05)"),

    # LW-M4-09. Both patches edit GeckoProvider.kt's GeckoRuntimeSettings.Builder
    # chain and nothing else in common: about-config replaces
    # .aboutConfigEnabled(...) at 123, isolated-process replaces
    # .isolatedProcessEnabled/.appZygoteProcessEnabled at 134-135. The hunks are
    # disjoint and separated by four unmodified lines (120-126 vs 131-138 in
    # pristine coordinates), so neither quotes a line the other writes.
    # MEASURED, not eyeballed: both orders applied to the pristine file exit 0
    # with no .rej and produce a byte-identical result (md5
    # 63ca3b0e4ff183edf256f6ebbbd7a278 both ways). The only effect of the order
    # is a 10-line offset on isolated-process's hunk when about-config (net +10
    # lines) goes first.
    ("patches/android/isolated-process.patch", "patches/android/about-config.patch",
     ("mobile/android/fenix/app/src/main/java/org/mozilla/fenix/gecko/GeckoProvider.kt",),
     "disjoint regions of GeckoProvider.kt (123 vs 134-135); measured identical both ways (LW-M4-09)"),

    # LW-M6-07 loose end. fenix-abi-split edits the fenix app/build.gradle splits
    # block (~:239-256), which no other patch touches, so it is order-free
    # against the four patches that share that file: no-adjust (:350+),
    # no-glean (:512), no-gms (:32/:366+) and no-crashreporter (:334+). Disjoint
    # regions of one file; order only shifts offsets.
    ("patches/android/no-adjust.patch", "patches/android/fenix-abi-split.patch",
     ("mobile/android/fenix/app/build.gradle",),
     "disjoint regions of fenix app/build.gradle: splits block (~:239-256) vs no-adjust's region (:350+); order only shifts offsets (LW-M6-07)"),
    ("patches/android/no-glean.patch", "patches/android/fenix-abi-split.patch",
     ("mobile/android/fenix/app/build.gradle",),
     "disjoint regions of fenix app/build.gradle: splits block (~:239-256) vs no-glean's region (:512); order only shifts offsets (LW-M6-07)"),
    ("patches/android/no-gms.patch", "patches/android/fenix-abi-split.patch",
     ("mobile/android/fenix/app/build.gradle",),
     "disjoint regions of fenix app/build.gradle: splits block (~:239-256) vs no-gms's regions (:32, :366+); order only shifts offsets (LW-M6-07)"),
    ("patches/android/no-crashreporter.patch", "patches/android/fenix-abi-split.patch",
     ("mobile/android/fenix/app/build.gradle",),
     "disjoint regions of fenix app/build.gradle: splits block (~:239-256) vs no-crashreporter's region (:334+); order only shifts offsets (LW-M6-07)"),

    # LW-M4-07. branding edits fenix app/build.gradle's defaultConfig +
    # buildTypes (roughly lines 55-175): applicationId org.mozilla ->
    # org.redoubtbrowser, the per-variant suffixes, a single deepLinkScheme
    # redoubt, and the removal of the Mozilla sharedUserId on beta+release.
    # That region is disjoint from every other toucher of the file (no-adjust
    # :350+, no-glean :512, no-gms :32/:366+, no-crashreporter :334+,
    # fenix-abi-split's splits block ~:239-256); branding's other three files
    # (values/colors.xml, ic_launcher_foreground.xml,
    # ic_launcher_monochrome.xml) are touched by no other patch in either
    # list, so each pair shares exactly this one file. Order only shifts
    # offsets.
    ("patches/android/no-adjust.patch", "patches/android/branding.patch",
     ("mobile/android/fenix/app/build.gradle",),
     "disjoint regions of fenix app/build.gradle: branding's defaultConfig+buildTypes (~:55-175) vs no-adjust's region (:350+); order only shifts offsets (LW-M4-07)"),
    ("patches/android/no-glean.patch", "patches/android/branding.patch",
     ("mobile/android/fenix/app/build.gradle",),
     "disjoint regions of fenix app/build.gradle: branding's defaultConfig+buildTypes (~:55-175) vs no-glean's region (:512); order only shifts offsets (LW-M4-07)"),
    ("patches/android/no-gms.patch", "patches/android/branding.patch",
     ("mobile/android/fenix/app/build.gradle",),
     "disjoint regions of fenix app/build.gradle: branding's defaultConfig+buildTypes (~:55-175) vs no-gms's regions (:32, :366+); order only shifts offsets (LW-M4-07)"),
    ("patches/android/no-crashreporter.patch", "patches/android/branding.patch",
     ("mobile/android/fenix/app/build.gradle",),
     "disjoint regions of fenix app/build.gradle: branding's defaultConfig+buildTypes (~:55-175) vs no-crashreporter's region (:334+); order only shifts offsets (LW-M4-07)"),
    ("patches/android/fenix-abi-split.patch", "patches/android/branding.patch",
     ("mobile/android/fenix/app/build.gradle",),
     "disjoint regions of fenix app/build.gradle: branding's defaultConfig+buildTypes (~:55-175) vs fenix-abi-split's splits block (~:239-256); order only shifts offsets (LW-M4-07)"),

    # LW-M3-07 replacement: seven shared-file pairs replayed at fuzz=0 in both
    # orders, byte-identical; the old fabricated-provider measurements are retired.
    ('patches/android/fission-isolation.patch', "patches/android/ubo-preinstall.patch",
     ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Core.kt',),
     "measured order-free 2026-09-08, byte-identical at fuzz=0; "
     "docs/android/evidence/lw-m3-07/completion-20260908/order-replay.json (LW-M3-07)"),
    ('patches/android/no-crashreporter.patch', "patches/android/ubo-preinstall.patch",
     ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Components.kt', 'mobile/android/fenix/app/src/main/res/values/strings.xml'),
     "measured order-free 2026-09-08, byte-identical at fuzz=0; "
     "docs/android/evidence/lw-m3-07/completion-20260908/order-replay.json (LW-M3-07)"),
    ('patches/android/no-glean.patch', "patches/android/ubo-preinstall.patch",
     ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt',),
     "measured order-free 2026-09-08, byte-identical at fuzz=0; "
     "docs/android/evidence/lw-m3-07/completion-20260908/order-replay.json (LW-M3-07)"),
    ('patches/android/no-gms.patch', "patches/android/ubo-preinstall.patch",
     ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/Components.kt'),
     "measured order-free 2026-09-08, byte-identical at fuzz=0; "
     "docs/android/evidence/lw-m3-07/completion-20260908/order-replay.json (LW-M3-07)"),
    ('patches/android/no-nimbus.patch', "patches/android/ubo-preinstall.patch",
     ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/HomeActivity.kt',),
     "measured order-free 2026-09-08, byte-identical at fuzz=0; "
     "docs/android/evidence/lw-m3-07/completion-20260908/order-replay.json (LW-M3-07)"),
    ('patches/android/no-suggest.patch', "patches/android/ubo-preinstall.patch",
     ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/HomeActivity.kt',),
     "measured order-free 2026-09-08, byte-identical at fuzz=0; "
     "docs/android/evidence/lw-m3-07/completion-20260908/order-replay.json (LW-M3-07)"),
    ('patches/android/update-check.patch', "patches/android/ubo-preinstall.patch",
     ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/HomeActivity.kt',),
     "measured order-free 2026-09-08, byte-identical at fuzz=0; "
     "docs/android/evidence/lw-m3-07/completion-20260908/order-replay.json (LW-M3-07)"),

    # LW-M7-12: each shared file replayed from the pristine Android archive,
    # with all other enabled edits held constant. Both orders apply at fuzz=0
    # and produce identical SHA256 values; the overlap hint does not decide.
    ("patches/android/no-adjust.patch", "patches/android/privacy-defaults.patch",
     ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt',),
     "marketing-onboarding default vs HTTPS, tracking, cleanup, autofill and DoH defaults; measured both orders byte-identical at fuzz=0; "
     "docs/android/evidence/lw-m7-12/patch-integration/privacy-pair-replay.json"),
    ("patches/android/no-gms.patch", "patches/android/privacy-defaults.patch",
     ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt',),
     "push-server preference removal vs privacy defaults in different Settings properties; measured both orders byte-identical at fuzz=0; "
     "docs/android/evidence/lw-m7-12/patch-integration/privacy-pair-replay.json"),
    ("patches/android/no-onboarding.patch", "patches/android/privacy-defaults.patch",
     ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt', 'mobile/android/fenix/app/src/test/java/org/mozilla/fenix/utils/SettingsTest.kt'),
     "onboarding function/flag and assertions vs privacy defaults and their assertions; measured both orders byte-identical at fuzz=0; "
     "docs/android/evidence/lw-m7-12/patch-integration/privacy-pair-replay.json"),
    ("patches/android/no-suggest.patch", "patches/android/privacy-defaults.patch",
     ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt', 'mobile/android/fenix/app/src/test/java/org/mozilla/fenix/utils/SettingsTest.kt'),
     "suggestion/trending/Contile defaults and suggestion assertion vs privacy settings and assertions; neighboring hunks still commute; measured both orders byte-identical at fuzz=0; "
     "docs/android/evidence/lw-m7-12/patch-integration/privacy-pair-replay.json"),
    ("patches/android/search-config.patch", "patches/android/privacy-defaults.patch",
     ('mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt',),
     "remote-search-configuration constant vs privacy defaults in different Settings properties; measured both orders byte-identical at fuzz=0; "
     "docs/android/evidence/lw-m7-12/patch-integration/privacy-pair-replay.json"),

    # Recorded in assets/patches/desktop.txt on the moz-official-desktop entry:
    # "different region, ~line 300 vs ~504".
    ("patches/hide-passwordmgr.patch", "patches/moz-official-desktop.patch",
     ("browser/base/content/browser-init.js",),
     "different regions of browser-init.js (~300 vs ~500), noted in desktop.txt"),

    # Everything below is the pre-existing patch set, grandfathered in the
    # order it ships. Most of it is browser/components/preferences/, where a
    # dozen patches have edited the same handful of files for years.
    ("patches/extensions-setUninstallURL.patch", "patches/vendor-name.patch",
     ("toolkit/components/extensions/parent/ext-runtime.js",),
     "grandfathered: shipping order, both in common.txt"),
    ("patches/fullpage-translations-customization.patch",
     "patches/pref-pane/pref-pane-small.patch",
     ("browser/components/preferences/main.js",),
     "grandfathered: shipping order"),
    ("patches/fullpage-translations-customization.patch",
     "patches/ui-patches/hide-default-browser.patch",
     ("browser/components/preferences/main.inc.xhtml",
      "browser/components/preferences/main.js"),
     "grandfathered: shipping order"),
    ("patches/fullpage-translations-customization.patch",
     "patches/ui-patches/settings-redesign.patch",
     ("browser/components/preferences/config/languages.mjs",
      "browser/components/preferences/main.js"),
     "grandfathered: shipping order"),
    ("patches/hide-passwordmgr.patch",
     "patches/ui-patches/privacy-preferences.patch",
     ("browser/components/preferences/privacy.js",),
     "grandfathered: shipping order"),
    ("patches/hide-passwordmgr.patch",
     "patches/ui-patches/settings-redesign.patch",
     ("browser/components/preferences/privacy.js",),
     "grandfathered: shipping order"),
    ("patches/link-preview.patch", "patches/ui-patches/remove-cfrprefs.patch",
     ("browser/components/preferences/config/tabs-browsing.mjs",),
     "grandfathered: shipping order"),
    ("patches/link-preview.patch", "patches/ui-patches/settings-redesign.patch",
     ("browser/components/preferences/config/tabs-browsing.mjs",),
     "grandfathered: shipping order"),
    ("patches/lw-permissions.patch", "patches/ui-patches/firefox-view.patch",
     ("browser/base/content/navigator-toolbox.inc.xhtml",),
     "grandfathered: shipping order"),
    ("patches/lw-permissions.patch",
     "patches/ui-patches/privacy-preferences.patch",
     ("browser/components/preferences/config/permissions-data.mjs",
      "browser/themes/shared/preferences/privacy.css"),
     "grandfathered: shipping order"),
    ("patches/ui-patches/allow_cookies_for_site.patch",
     "patches/ui-patches/settings-redesign.patch",
     ("browser/components/controlcenter/content/trustPanel.inc.xhtml",),
     "grandfathered: shipping order"),
    ("patches/ui-patches/hide-default-browser.patch",
     "patches/pref-pane/pref-pane-small.patch",
     ("browser/components/preferences/main.js",),
     "grandfathered: shipping order"),
    ("patches/ui-patches/hide-default-browser.patch",
     "patches/ui-patches/settings-redesign.patch",
     ("browser/components/preferences/main.js",),
     "grandfathered: shipping order"),
    ("patches/ui-patches/pref-naming.patch",
     "patches/ui-patches/privacy-preferences.patch",
     ("browser/locales/en-US/browser/preferences/preferences.ftl",),
     "grandfathered: shipping order"),
    ("patches/ui-patches/privacy-preferences.patch",
     "patches/pref-pane/pref-pane-small.patch",
     ("browser/components/preferences/preferences.js",),
     "grandfathered: shipping order"),
    ("patches/ui-patches/privacy-preferences.patch",
     "patches/ui-patches/remove-cfrprefs.patch",
     ("browser/components/preferences/preferences.js",),
     "grandfathered: shipping order"),
    ("patches/ui-patches/privacy-preferences.patch",
     "patches/ui-patches/remove-organization-policy-banner.patch",
     ("browser/components/preferences/preferences.js",),
     "grandfathered: shipping order"),
    ("patches/ui-patches/privacy-preferences.patch",
     "patches/ui-patches/settings-redesign.patch",
     ("browser/components/preferences/config/privacy.mjs",
      "browser/components/preferences/preferences.js",
      "browser/components/preferences/privacy.inc.xhtml",
      "browser/components/preferences/privacy.js"),
     "grandfathered: shipping order"),
    ("patches/ui-patches/remove-cfrprefs.patch",
     "patches/pref-pane/pref-pane-small.patch",
     ("browser/components/preferences/preferences.js",),
     "grandfathered: shipping order"),
    ("patches/ui-patches/remove-cfrprefs.patch",
     "patches/ui-patches/remove-organization-policy-banner.patch",
     ("browser/components/preferences/preferences.js",),
     "grandfathered: shipping order"),
    ("patches/ui-patches/remove-cfrprefs.patch",
     "patches/ui-patches/settings-redesign.patch",
     ("browser/components/preferences/config/tabs-browsing.mjs",
      "browser/components/preferences/preferences.js"),
     "grandfathered: shipping order"),
    ("patches/ui-patches/remove-organization-policy-banner.patch",
     "patches/pref-pane/pref-pane-small.patch",
     ("browser/components/preferences/preferences.js",),
     "grandfathered: shipping order"),
    ("patches/ui-patches/remove-organization-policy-banner.patch",
     "patches/ui-patches/settings-redesign.patch",
     ("browser/components/preferences/preferences.js",),
     "grandfathered: shipping order"),
    ("patches/ui-patches/settings-redesign.patch",
     "patches/pref-pane/pref-pane-small.patch",
     ("browser/components/preferences/main.js",
      "browser/components/preferences/preferences.js",
      "browser/components/preferences/preferences.xhtml",
      "browser/themes/shared/jar.inc.mn"),
     "grandfathered: shipping order; pref-pane-small is applied last by the "
     "patcher, so this pair cannot be reordered from a list anyway"),
    ("patches/ui-patches/settings-redesign.patch",
     "patches/ui-patches/website-appearance-ui-rfp.patch",
     ("browser/components/preferences/config/appearance.mjs",),
     "grandfathered: shipping order"),
    ("patches/ui-patches/settings-redesign.patch",
     "patches/webgl-permission-desktop.patch",
     ("browser/themes/shared/jar.inc.mn",),
     "grandfathered: LW-M1-08 kept the desktop half in the monolith's position"),
    ("patches/webgl-permission-desktop.patch",
     "patches/pref-pane/pref-pane-small.patch",
     ("browser/themes/shared/jar.inc.mn",),
     "grandfathered: three separate jar.inc.mn regions"),
    # LW-M4-02. Unlike the grandfathered rows above, this one was MEASURED
    # rather than inherited, and it had to be: in pre-patch coordinates the
    # hunk regions in HomeActivity.kt are no-nimbus [87..93] and [419..426]
    # against no-adjust [112..118], [462..468], [1262..1268] and [1275..1284],
    # so the closest pair is only 36 lines apart (426 -> 462) and the next 19
    # (93 -> 112). "Far apart" is therefore NOT the argument. The argument is
    # that both patches were applied to a mini tree holding the union of the 36
    # files they touch, in both orders; both orders exited 0, left zero .rej
    # files, and `diff -r` found the two result trees byte-identical. Neither
    # patch quotes a line the other adds.
    ("patches/android/no-nimbus.patch",
     "patches/android/no-adjust.patch",
     ("mobile/android/fenix/app/src/main/java/org/mozilla/fenix/HomeActivity.kt",),
     "measured order-free (LW-M4-02): both orders applied with zero rejects "
     "and produced byte-identical trees; disjoint but only 19-36 lines apart, "
     "so this is a measurement and not an eyeball"),

    # LW-M4-11 (no-suggest) and LW-M4-06 (search-config), 2026-09-02. Every row
    # below is a MEASUREMENT, not an eyeball: each shared file was extracted
    # pristine from firefox-153.0esr.source.tar.xz and replayed through the
    # android.txt sequence in list order, then once more per partner with the
    # new patch moved in front of that partner. In every case patch exited 0
    # both ways, wrote no .rej, and the two results were byte-identical; the
    # only effect of the order is a line offset (quoted where non-zero). The
    # script that did it is reproduced in docs/android/evidence/lw-m4-11/.
    ("patches/android/no-nimbus.patch", "patches/android/no-suggest.patch",
     ("mobile/android/fenix/app/src/main/java/org/mozilla/fenix/HomeActivity.kt",),
     "no-nimbus edits messaging/onboarding call sites; no-suggest deletes the "
     "TopSitesRefresher observer (:595-603), the contile startPeriodicWork block "
     "(:638-640) and stopPeriodicWork (:916). Byte-identical both ways "
     "(sha256 cf447dd9...), no-suggest lands at offset -10 when first (LW-M4-11)"),
    ("patches/android/no-adjust.patch", "patches/android/no-suggest.patch",
     ("mobile/android/fenix/app/src/main/java/org/mozilla/fenix/HomeActivity.kt", "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt"),
     "disjoint regions of both files; byte-identical both ways (HomeActivity.kt "
     "sha256 cf447dd9..., Settings.kt db719ae5...), offsets of 1 and 5 lines "
     "when swapped (LW-M4-11)"),
    ("patches/android/no-onboarding.patch", "patches/android/no-suggest.patch",
     ("mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt",
      "mobile/android/fenix/app/src/test/java/org/mozilla/fenix/utils/SettingsTest.kt"),
     "no-onboarding edits the onboarding prefs (~:2220-2241) and three "
     "SettingsTest assertions (~:850-891); no-suggest edits the search-suggestion "
     "defaults (:1628-1653), showContileFeature (:2182) and the "
     "showSearchSuggestions test (:440). Byte-identical both ways (Settings.kt "
     "db719ae5..., SettingsTest.kt 0369a329...), offsets <= 17 lines (LW-M4-11)"),
    ("patches/android/no-gms.patch", "patches/android/no-suggest.patch",
     ("mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt",),
     "no-gms edits ~:1961; no-suggest :1628-1653 and :2182. Byte-identical both "
     "ways (sha256 db719ae5...), offset 5 when swapped (LW-M4-11)"),
    ("patches/android/no-adjust.patch", "patches/android/search-config.patch",
     ("mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt",),
     "search-config's single Settings.kt hunk is useRemoteSearchConfiguration "
     "(:2280-2283); no-adjust's is at ~:2297. Byte-identical both ways (sha256 "
     "9d8ee639...), offset 14 when swapped (LW-M4-06)"),
    ("patches/android/no-onboarding.patch", "patches/android/search-config.patch",
     ("mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt",),
     "disjoint (:2280-2283 vs ~:2220-2241); byte-identical both ways (sha256 "
     "9d8ee639...), offset 14 when swapped (LW-M4-06)"),
    ("patches/android/no-gms.patch", "patches/android/search-config.patch",
     ("mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt",),
     "disjoint (:2280-2283 vs ~:1961); byte-identical both ways (sha256 "
     "9d8ee639...), offset 5 when swapped (LW-M4-06)"),
    ("patches/android/no-suggest.patch", "patches/android/search-config.patch",
     ("mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt",),
     "disjoint (:2280-2283 vs :1628-1653 and :2182); byte-identical both ways "
     "(sha256 9d8ee639...), no offset either way (LW-M4-06)"),
    ("patches/android/no-glean.patch", "patches/android/search-config.patch",
     ("mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/SecretSettingsFragment.kt",
      "mobile/android/fenix/app/src/main/res/xml/secret_settings_preferences.xml"),
     "no-glean removes the Glean debug rows; search-config removes the "
     "remote-search-configuration switch (SecretSettingsFragment.kt :319-331, "
     "secret_settings_preferences.xml :48-51). Byte-identical both ways "
     "(sha256 502a232f... / 1545b5eb...), offsets 7 and -2 when swapped (LW-M4-06)"),
    ("patches/android/rs-blocker-android.patch", "patches/android/search-config.patch",
     ("third_party/application-services/components/remote_settings/src/client.rs",),
     "rs-blocker-android edits fetch/sync/make_request (:377-, :639-); "
     "search-config adds two ids (Mojeek, Startpage) to packaged_attachments! (:129). Byte-identical "
     "both ways (sha256 918c0bd0...), rs-blocker lands at offset 12 when second "
     "(LW-M4-06)"),

    # LW-M6-06 (update-check), 2026-09-02, measured the same way as the rows above
    # (pristine replay, list order and once per partner with update-check moved in
    # front of it): exit 0 both ways, no .rej, byte-identical -- HomeActivity.kt
    # sha256 dd8a1886..., app/build.gradle sha256 2ef204e5.... update-check adds one
    # maybeRun() call in HomeActivity.onResume (~:760) and two buildConfigFields
    # at the end of defaultConfig (build.gradle :88), regions none of the partners
    # touch.
    ("patches/android/no-nimbus.patch", "patches/android/update-check.patch",
     ("mobile/android/fenix/app/src/main/java/org/mozilla/fenix/HomeActivity.kt",),
     "update-check adds one call in onResume (~:760), no-nimbus edits elsewhere; "
     "byte-identical both ways (sha256 dd8a1886...) (LW-M6-06)"),
    ("patches/android/no-adjust.patch", "patches/android/update-check.patch",
     ("mobile/android/fenix/app/build.gradle", "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/HomeActivity.kt"),
     "update-check appends two buildConfigFields to defaultConfig (build.gradle :88) "
     "and one call in HomeActivity.onResume (~:760); no-adjust edits the Adjust "
     "dependency/config lines and other HomeActivity regions. Byte-identical both "
     "ways (sha256 2ef204e5... / dd8a1886...) (LW-M6-06)"),
    ("patches/android/no-suggest.patch", "patches/android/update-check.patch",
     ("mobile/android/fenix/app/src/main/java/org/mozilla/fenix/HomeActivity.kt",),
     "update-check adds one call in onResume (~:760), no-suggest edits elsewhere; "
     "byte-identical both ways (sha256 dd8a1886...) (LW-M6-06)"),
    ("patches/android/no-glean.patch", "patches/android/update-check.patch",
     ("mobile/android/fenix/app/build.gradle",),
     "update-check appends two buildConfigFields to defaultConfig (:88); no-glean edits the Glean dependency/config lines; "
     "byte-identical both ways (sha256 2ef204e5...) (LW-M6-06)"),
    ("patches/android/no-gms.patch", "patches/android/update-check.patch",
     ("mobile/android/fenix/app/build.gradle",),
     "update-check appends two buildConfigFields to defaultConfig (:88); no-gms edits the GMS dependency/config lines; "
     "byte-identical both ways (sha256 2ef204e5...) (LW-M6-06)"),
    ("patches/android/no-crashreporter.patch", "patches/android/update-check.patch",
     ("mobile/android/fenix/app/build.gradle",),
     "update-check appends two buildConfigFields to defaultConfig (:88); no-crashreporter edits the crash-reporter dependency lines; "
     "byte-identical both ways (sha256 2ef204e5...) (LW-M6-06)"),
    ("patches/android/fenix-abi-split.patch", "patches/android/update-check.patch",
     ("mobile/android/fenix/app/build.gradle",),
     "update-check appends two buildConfigFields to defaultConfig (:88); fenix-abi-split edits the splits block; "
     "byte-identical both ways (sha256 2ef204e5...) (LW-M6-06)"),
    ("patches/android/branding.patch", "patches/android/update-check.patch",
     ("mobile/android/fenix/app/build.gradle",),
     "update-check appends two buildConfigFields to defaultConfig (:88); branding edits applicationId / identity lines; "
     "byte-identical both ways (sha256 2ef204e5...) (LW-M6-06)"),
)


# --------------------------------------------------------------------------
# Reading the lists and the patches.
# --------------------------------------------------------------------------

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class Problem(Exception):
    """A precondition failure - not an ordering result."""


def read_patch_list(name):
    """The entries of a list, in file order.

    Identical rules to read_patch_list() in scripts/librewolf-patches.py: a
    '#' starts a comment anywhere on the line, and blank lines are dropped.
    The three lists carry a lot of inline commentary, so this is not optional.
    """
    path = PATCH_LIST_DIR / "{}.txt".format(name)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise Problem("can't read patch list '{}': {}".format(path, e))
    entries = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            entries.append(line)
    return entries


def header_path(raw):
    """The tree path named by a '--- ' / '+++ ' header, or None.

    Returns None for the /dev/null that marks a creation or a deletion. A naive
    strip of the two leading characters turns '/dev/null' into 'ev/null' and a
    naive strip of 'a/' turns it into 'dev/null', either of which becomes a
    file that every creating patch appears to share.
    """
    path = raw.split("\t", 1)[0].strip()
    if path in ("/dev/null", "a/dev/null", "b/dev/null"):
        return None
    if path.startswith(("a/", "b/")):
        path = path[2:]
    return path or None


def parse_patch(path):
    """{tree file: [(old_start, old_count), ...]} for one patch file.

    A '--- ' line only counts as a file header when the next line is a '+++ '
    line. Both halves of that rule earn their keep:

      * a removed body line whose content begins with '-- ' is spelled exactly
        like a '--- ' header once patch's '-' prefix is on it, so a patch that
        edits a diff, a changelog or a Markdown file would otherwise invent a
        tree file out of a hunk body;
      * counting hunk bodies out from the @@ line instead would be worse here,
        because some of these patches are hand-edited and their counts are
        wrong. patches/always-fetch-latest-toolchain-artifact.patch declares
        '@@ -452,28 +452,30 @@' over a 15-line body and GNU patch applies it
        anyway, so a parser that trusted the counts would reject the tree.

    A '@@ -a,b +c,d @@' line needs no such care: every body line carries a
    ' ', '-', '+' or '\\' prefix, so column 0 is unambiguous.
    """
    try:
        text = (REPO_DIR / path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise Problem("can't read patch '{}': {}".format(path, e))

    hunks = defaultdict(list)
    current = []
    lines = text.splitlines()

    for i, line in enumerate(lines):
        if line.startswith("--- "):
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if not nxt.startswith("+++ "):
                continue
            # A rename or a create/delete names two paths; count both as
            # touched, minus the /dev/null header_path() drops.
            current = [p for p in (header_path(line[4:]),
                                   header_path(nxt[4:])) if p]
            for p in current:
                hunks[p]                    # register even a zero-hunk file
            continue

        m = HUNK_RE.match(line)
        if m and current:
            old_start = int(m.group(1))
            old_count = int(m.group(2) or 1)
            for p in current:
                hunks[p].append((old_start, old_count))

    if not hunks:
        raise Problem("{}: no '--- a/x' / '+++ b/x' file headers found; this "
                      "does not look like a unified diff".format(path))
    return dict(hunks)


def apply_sequences(lists):
    """{target: [patch, ...]} - the real order, per target.

    scripts/librewolf-patches.py:116-124 reads common.txt first and then one
    list per --targets, in KNOWN_TARGETS order; :385 applies the pref-pane
    patch after all of them. Two different target lists never apply together,
    so nothing can be ordered across desktop.txt and android.txt - which is
    why this returns one sequence per target rather than one flat list.
    """
    return {
        target: lists["common"] + lists[target] + list(OUT_OF_LIST_TAIL)
        for target in KNOWN_TARGETS
    }


# --------------------------------------------------------------------------
# Evidence. Printed when a new pair turns up; never used as a decision.
# --------------------------------------------------------------------------

ABUT_SLACK = 3

EVIDENCE_CAVEAT = (
    "The overlap note is a hint, not a verdict. On this tree it flags 1 of the "
    "5\n    known constraints and 6 pairs that are fine, and hunk headers of a "
    "later\n    patch are in post-earlier-patch coordinates anyway. Read the "
    "patches.")


def hunk_evidence(a_hunks, b_hunks):
    """A deliberately non-authoritative note about two hunk sets on one file."""
    for a_start, a_count in a_hunks:
        a_end = a_start + max(a_count, 1) - 1
        for b_start, b_count in b_hunks:
            b_end = b_start + max(b_count, 1) - 1
            if not (a_end + ABUT_SLACK < b_start or b_end + ABUT_SLACK < a_start):
                return "hunks overlap or abut"
    return "hunks are in disjoint regions"


# --------------------------------------------------------------------------
# The checks.
# --------------------------------------------------------------------------

def check(verbose=False):
    errors = []
    warnings = []

    lists = {name: read_patch_list(name) for name in ("common",) + KNOWN_TARGETS}

    # Preconditions. A patch named by a list but absent from disk is a build
    # failure later on and makes everything below meaningless.
    seen_in = {}
    for name, entries in lists.items():
        for entry in entries:
            if not (REPO_DIR / entry).is_file():
                errors.append(
                    "assets/patches/{}.txt names '{}', which is not a file"
                    .format(name, entry))
            if entry in seen_in:
                errors.append(
                    "'{}' is in both {}.txt and {}.txt, so any build reading "
                    "both applies it twice".format(entry, seen_in[entry], name))
            seen_in[entry] = name
    for entry in OUT_OF_LIST_TAIL:
        if not (REPO_DIR / entry).is_file():
            errors.append("'{}' is applied by scripts/librewolf-patches.py but "
                          "is not a file".format(entry))
        if entry in seen_in:
            errors.append(
                "'{}' is now in assets/patches/{}.txt as well as being applied "
                "from its own call site in scripts/librewolf-patches.py. Drop "
                "it from OUT_OF_LIST_TAIL in this script if the call site is "
                "gone.".format(entry, seen_in[entry]))
    if errors:
        # Must match the 3-tuple returned below: main() unpacks three values, and
        # this early path is only reached when something is already wrong, so a
        # 2-tuple here turns a clear diagnostic into a ValueError traceback.
        return errors, warnings, {"constraints": len(CONSTRAINTS), "enforced": 0,
                                  "targets": len(KNOWN_TARGETS), "pairs": 0}

    sequences = apply_sequences(lists)
    patches = {}
    for entry in set(itertools.chain.from_iterable(sequences.values())):
        patches[entry] = parse_patch(entry)

    position = {t: {p: i for i, p in enumerate(seq)} for t, seq in sequences.items()}

    def where(entry):
        return seen_in.get(entry, "<applied from librewolf-patches.py>")

    # ---- 1. the declared constraints ------------------------------------
    declared = {}
    enforced = 0
    for first, then, shared_file, why in CONSTRAINTS:
        declared[frozenset((first, then))] = (first, then, shared_file, why)

        present = [p for p in (first, then) if p in seen_in or p in OUT_OF_LIST_TAIL]
        if not present:
            continue                                # both disabled: vacuous
        if len(present) == 1:
            missing = then if present[0] == first else first
            warnings.append(
                "ordering constraint {} -> {}: '{}' is not in any list, so the "
                "constraint is not being checked".format(first, then, missing))
            continue

        # The row must still describe the tree. A split or a rebase that moves
        # the hunks elsewhere would otherwise leave a row checking nothing.
        for entry in (first, then):
            for f in ((shared_file,) if isinstance(shared_file, str)
                      else tuple(shared_file)):
                if f not in patches[entry]:
                    errors.append(
                        "declared constraint {} -> {} says they share '{}', but "
                        "'{}' does not touch that file any more. The constraint "
                        "may have moved with the hunks - re-derive it, do not "
                        "just delete the row.".format(first, then, f, entry))

        co_applied = [t for t in KNOWN_TARGETS
                      if first in position[t] and then in position[t]]
        if not co_applied:
            warnings.append(
                "ordering constraint {} -> {} can never be enforced: they are "
                "in {}.txt and {}.txt, which never apply together"
                .format(first, then, where(first), where(then)))
            continue

        enforced += 1
        for target in co_applied:
            if position[target][first] >= position[target][then]:
                errors.append(
                    "ORDERING VIOLATION on target '{}':\n"
                    "    {} must apply BEFORE {}\n"
                    "    they share {}\n"
                    "    but the apply sequence has it the other way round:\n"
                    "      #{:<3} {}   ({}.txt)\n"
                    "      #{:<3} {}   ({}.txt)\n"
                    "    why: {}".format(
                        target, first, then,
                        shared_file if isinstance(shared_file, str)
                        else ", ".join(shared_file),
                        position[target][then], then, where(then),
                        position[target][first], first, where(first),
                        why))

    # ---- 2. every other shared-file pair must be classified --------------
    reviewed = {}
    for a, b, files, reason in REVIEWED_ORDER_FREE:
        reviewed[frozenset((a, b))] = (tuple(sorted(files)), reason)

    found = {}
    for target, seq in sequences.items():
        for a, b in itertools.combinations(seq, 2):
            shared = set(patches[a]) & set(patches[b])
            if not shared:
                continue
            key = frozenset((a, b))
            entry = found.setdefault(key, {"a": a, "b": b, "files": set(),
                                           "targets": []})
            entry["files"] |= shared
            entry["targets"].append(target)

    for key, info in sorted(found.items(), key=lambda kv: (kv[1]["a"], kv[1]["b"])):
        a, b, files = info["a"], info["b"], tuple(sorted(info["files"]))
        if key in declared:
            first, then, shared_file, _ = declared[key]
            declared_files = ((shared_file,) if isinstance(shared_file, str)
                              else tuple(shared_file))
            extra = [f for f in files if f not in declared_files]
            if extra:
                errors.append(
                    "{} and {} are a declared ordering constraint over {}, but "
                    "they now also share {}. Re-review the pair: the recorded "
                    "direction was derived from the listed file(s)."
                    .format(first, then, ", ".join("'%s'" % f for f in declared_files),
                            ", ".join(extra)))
            continue
        if key in reviewed:
            recorded, _ = reviewed[key]
            if recorded != files:
                errors.append(
                    "the shared files of a reviewed order-free pair changed:\n"
                    "      {}\n      {}\n"
                    "    recorded: {}\n    now:      {}\n"
                    "    Re-review: a new shared file is a new chance for an "
                    "ordering constraint.".format(
                        a, b, ", ".join(recorded) or "(none)", ", ".join(files)))
            continue

        ev = []
        for f in files:
            ev.append("      {}: {}".format(
                f, hunk_evidence(patches[a][f], patches[b][f])))
        errors.append(
            ("UNCLASSIFIED shared-file pair - a human has to look at this:\n"
             "      {a}   ({wa}.txt)\n      {b}   ({wb}.txt)\n"
             "    co-applied on: {targets}\n"
             "    shared files:\n{ev}\n"
             "    {caveat}\n"
             "    Two patches editing the same tree file must be ordered, not\n"
             "    parallel (docs/android/AGENTS.md, \"Ownership\"). Decide which\n"
             "    it is and record it in scripts/check-patch-order.py:\n"
             "      - one order required -> add to CONSTRAINTS:\n"
             "          ({a!r},\n           {b!r},\n           {one!r},\n"
             "           \"<evidence>\"),\n"
             "      - either order fine   -> add to REVIEWED_ORDER_FREE:\n"
             "          ({a!r},\n           {b!r},\n           {files!r},\n"
             "           \"<reason>\"),").format(
                a=a, b=b, wa=where(a), wb=where(b),
                targets=", ".join(sorted(set(info["targets"]))),
                ev="\n".join(ev), caveat=EVIDENCE_CAVEAT,
                one=files[0], files=files))

    # ---- 3. rows that no longer describe anything ------------------------
    for key, (recorded, _) in reviewed.items():
        a, b = sorted(key)
        if key in found:
            continue
        if not all(p in seen_in or p in OUT_OF_LIST_TAIL for p in (a, b)):
            continue                                # one of them was disabled
        co_applied = any(a in position[t] and b in position[t] for t in KNOWN_TARGETS)
        if co_applied:
            errors.append(
                "stale REVIEWED_ORDER_FREE row: {} and {} are both enabled and "
                "co-applied but no longer share any file (recorded: {}). Drop "
                "the row.".format(a, b, ", ".join(recorded) or "(none)"))

    if verbose:
        print("# apply sequences")
        for target in KNOWN_TARGETS:
            print("#   {:<8} {} patch(es): common.txt({}) + {}.txt({}) + {}"
                  .format(target, len(sequences[target]), len(lists["common"]),
                          target, len(lists[target]), ", ".join(OUT_OF_LIST_TAIL)))
        print("# shared-file pairs. " + EVIDENCE_CAVEAT.replace("\n    ", "\n#   "))
        for key, info in sorted(found.items(),
                                key=lambda kv: (kv[1]["a"], kv[1]["b"])):
            kind = ("constraint" if key in declared
                    else "order-free" if key in reviewed else "UNCLASSIFIED")
            print("#   [{}] {} + {}".format(kind, info["a"], info["b"]))
            for f in sorted(info["files"]):
                print("#        {}  ({})".format(
                    f, hunk_evidence(patches[info["a"]][f], patches[info["b"]][f])))

    stats = {
        "constraints": len(CONSTRAINTS),
        "enforced": enforced,
        "targets": len(KNOWN_TARGETS),
        "pairs": len(found),
    }
    return errors, warnings, stats


def main(argv):
    verbose = False
    for arg in argv[1:]:
        if arg in ("-v", "--verbose", "--pairs"):
            verbose = True
        elif arg in ("-h", "--help"):
            print("Usage: {} [-v|--pairs]".format(Path(argv[0]).name))
            print("\nChecks that assets/patches/{common,desktop,android}.txt "
                  "apply in a working order.\nSee the comment at the top of "
                  "this file, and docs/android/AGENTS.md.")
            return 0
        else:
            sys.stderr.write("error: unknown argument '{}' (try --help)\n".format(arg))
            return 2

    try:
        errors, warnings, stats = check(verbose=verbose)
    except Problem as e:
        sys.stderr.write("error: {}\n".format(e))
        return 1

    for w in warnings:
        sys.stderr.write("warning: {}\n".format(w))
    if errors:
        for e in errors:
            sys.stderr.write("error: {}\n".format(e))
        sys.stderr.write(
            "\n{} problem(s). See \"Patch ordering constraints\" in "
            "docs/android/AGENTS.md.\n".format(len(errors)))
        return 1

    print("patch order ok: {}/{} declared constraint(s) enforced across {} "
          "target sequence(s); {} shared-file pair(s) derived and classified."
          .format(stats["enforced"], stats["constraints"], stats["targets"],
                  stats["pairs"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
