#!/bin/bash
# Fenix JVM unit tests for the preinstaller, in the same container/objdir as the proof build.
set -u
V=/home/mgysin/redoubt-artifacts/ubo-disable
T=$V/repo/librewolf-157.0-3
O=$V/build/apk
podman run --rm --name lw-ubo-unittest-$$ \
  -v "$T:/work/src" -v "$O:/work/out" -v "$O/mozbuild-srcdirs:/root/.mozbuild/srcdirs" -w /work/src \
  -e MOZCONFIG=/work/out/mozconfig.x86_64 -e MOZ_BUILD_DATE=20261006140000 \
  -e GRADLE_USER_HOME=/work/out/gradle-home -e MOZ_ANDROID_FAT_AAR_ARCHITECTURES=x86_64 \
  -e MOZ_ANDROID_FAT_AAR_X86_64=/work/out/input/x86_64/target.maven.zip \
  localhost/librewolf-android-build:fx157 \
  bash -c './mach gradle fenix:testDebugUnitTest --tests "org.mozilla.fenix.components.LibreWolfUboPreinstallerTest" --tests "org.mozilla.fenix.components.LibreWolfUboPreinstallMiddlewareTest"; echo MACH_EXIT=$?'
