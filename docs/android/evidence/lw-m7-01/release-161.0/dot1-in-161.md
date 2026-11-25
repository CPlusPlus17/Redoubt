# 160.0.1 fixes in 161.0 (2026-11-25)

160.0.1 tarball sig VALIDSIG pinned primary OK. diff -rq 160.0 vs 160.0.1: 558 entries; 109 code files after excluding strings/locales/tests.
Per file: 160.0->160.0.1 diff reverse-applies on pristine 161.0 = PRESENT.

     11 DIFFERENT
     98 PRESENT

DIFFERENT (not reverse-applicable):
DIFFERENT gfx/layers/apz/src/InputQueue.cpp
DIFFERENT mobile/android/android-components/components/service/merino-manifest/src/main/assets/manifest/manifest.json
DIFFERENT mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt
DIFFERENT mobile/android/fenix/app/src/main/java/org/mozilla/fenix/onboarding/view/OnboardingScreen.kt
DIFFERENT mobile/android/version.txt
DIFFERENT services/settings/dumps/blocklists/addons-bloomfilters/addons-mlbf.bin
DIFFERENT services/settings/dumps/blocklists/addons-bloomfilters/softblocks-addons-mlbf.bin
DIFFERENT services/settings/dumps/blocklists/addons-bloomfilters.json
DIFFERENT services/settings/dumps/main/ai-window-prompts.json
DIFFERENT services/settings/dumps/security-state/intermediates.json
DIFFERENT sourcestamp.txt

InputQueue.cpp: the 160.0.1 hunk (mActivePanGestureBlock = nullptr after terminator) is at 161.0 :619-622, context drift only. The rest are data dumps / version files / Fenix files rewritten further in 161. Security files (dom/canvas/WebGL*, gfx/gl/GLContext*, dom/media/ChannelMediaDecoder.cpp) PRESENT.
