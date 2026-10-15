#!/bin/bash
# Negative control (run 2026-10-14 in the build-apk tree of c414e7b6): the four test classes with the
# src/main hunks of no-webcompat-reporter.patch and drm-permission-default.patch reverse-applied
#   (filterdiff -i '*/src/main/*' <patch> | patch -p1 -R), then re-applied afterwards.
# The new tests must fail. Output: unittest-mutant.log and the results-mutant/ JUnit XMLs.
B=~/redoubt-artifacts/port-sept24/builds/build-apk; T=$B/repo/librewolf-158.0-2; O=$B/apk; BD=20261014180000
IMG=localhost/librewolf-android-build:fx158
podman run --rm --name lw-port-mutant-$$ \
  -v "$T:/work/src" -v "$O:/work/out" -v "$O/mozbuild-srcdirs:/root/.mozbuild/srcdirs" -w /work/src \
  -e MOZCONFIG=/work/out/mozconfig.x86_64 -e MOZ_BUILD_DATE=$BD \
  -e GRADLE_USER_HOME=/work/out/gradle-home -e MOZ_ANDROID_FAT_AAR_ARCHITECTURES=x86_64 \
  -e MOZ_ANDROID_FAT_AAR_X86_64=/work/out/input/x86_64/target.maven.zip \
  $IMG bash -c './mach gradle fenix:testDebugUnitTest --tests "org.mozilla.fenix.settings.PhoneFeatureTest" --tests "org.mozilla.fenix.utils.SettingsTest" --tests "org.mozilla.fenix.components.menu.BrowserMenuBuilderTest" --tests "org.mozilla.fenix.components.menu.compose.MoreSettingsSubmenuTest"; echo MACH_EXIT=$?' > $B/unittest-mutant.log 2>&1
