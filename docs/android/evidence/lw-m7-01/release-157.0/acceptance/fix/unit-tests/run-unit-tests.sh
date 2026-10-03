#!/bin/bash
# Targeted Fenix unit tests for the canvas-webgl-permissions dialog fix, in the rc APK build's container env
# (mirrors android-apk.sh container_run; same image, mozconfig, build date and gradle home as the rc APK build).
podman run --rm --name lw157-acc-ut-$$ \
  -v "/home/mgysin/redoubt-artifacts/release-157/rc/librewolf-157.0-1:/work/src:z" -v "/home/mgysin/redoubt-artifacts/release-157/rc/librewolf-android-apk-157.0-1:/work/out:z" \
  -v "/home/mgysin/redoubt-artifacts/release-157/rc/librewolf-android-aar-157.0-1/gradle-home:/work/gh:z" \
  -v "/home/mgysin/redoubt-artifacts/release-157/rc/librewolf-android-apk-157.0-1/mozbuild-srcdirs:/root/.mozbuild/srcdirs:z" -w /work/src \
  -e MOZCONFIG=/work/out/mozconfig.x86_64 -e MOZ_BUILD_DATE=20261002210000 -e GRADLE_USER_HOME=/work/gh \
  -e MOZ_ANDROID_FAT_AAR_ARCHITECTURES=armeabi-v7a,arm64-v8a,x86_64 \
  -e MOZ_ANDROID_FAT_AAR_ARMEABI_V7A=/work/out/input/armeabi-v7a/target.maven.zip \
  -e MOZ_ANDROID_FAT_AAR_ARM64_V8A=/work/out/input/arm64-v8a/target.maven.zip \
  -e MOZ_ANDROID_FAT_AAR_X86_64=/work/out/input/x86_64/target.maven.zip \
  localhost/librewolf-android-build:fx157 \
  bash -c "./mach gradle fenix:testDebugUnitTest --tests '*OriginBoundPermissionsDialogFragmentTest' --tests '*OriginBoundPermissionsFeatureTest'"
echo EXIT=$?
