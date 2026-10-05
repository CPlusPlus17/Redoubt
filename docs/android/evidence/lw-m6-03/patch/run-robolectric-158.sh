#!/bin/bash
# Robolectric run of the installer-check change (LW-M6-03) on the Firefox 158 working tree,
# the only tree on this host with a built GeckoView AAR. Both the tree and the build dir are
# mounted as overlays (:O): nothing in them is modified. The three changed files are copied in.
W=/home/mgysin/redoubt-artifacts/ff158/work; B=$W/build
podman run --rm --name lw-fdroid-robolectric-$$ --security-opt label=disable \
  -v $W/buildrepo/librewolf-158.0-1:/work/src:O -v $B/apk3:/work/out:O -v $B/apk3/mozbuild-srcdirs:/root/.mozbuild/srcdirs:O \
  -v <the three files, extracted from update-check.patch>:/changed:ro -w /work/src \
  -e MOZCONFIG=/work/out/mozconfig.x86_64 -e MOZ_BUILD_DATE=20261004120000 -e GRADLE_USER_HOME=/work/out/gradle-home \
  -e MOZ_ANDROID_FAT_AAR_ARCHITECTURES=x86_64 -e MOZ_ANDROID_FAT_AAR_X86_64=/work/out/input/x86_64/target.maven.zip \
  localhost/librewolf-android-build:fx158 bash -c '
    for f in main/java/org/mozilla/fenix/lw/UpdateCheck.kt test/java/org/mozilla/fenix/lw/UpdateCheckSwitchTest.kt test/java/org/mozilla/fenix/lw/UpdateCheckerTest.kt; do
      cp /changed/$f mobile/android/fenix/app/src/$f && sha256sum mobile/android/fenix/app/src/$f; done
    ./mach gradle fenix:testDebugUnitTest --tests "org.mozilla.fenix.lw.*" --tests org.mozilla.fenix.settings.SettingsFragmentTest; echo MACH_EXIT=$?'
