#!/bin/bash
# LW-M7-44 follow-up: Fenix release compile (-Werror) on the patched tree, then the
# preinstaller JVM unit tests in the same container/objdir, exactly as build/unittest.sh.
set -u
V=/home/mgysin/redoubt-artifacts/ubo-disable
R=$V/repo
T=$R/librewolf-157.0-3
B=$V/build2
O=$B/apk
IMG=localhost/librewolf-android-build:fx157
log(){ echo "$(date -u +%FT%TZ) $*" >> $B/commands.log; }
cd $R
log "START apk x86_64 release"
env -u LW_UPDATE_CHECK_URL -u LW_UPDATE_CHECK_ENABLED ./scripts/android-apk.sh --srcdir $T --aar-dir $B/aar --outdir $O \
  --abis x86_64 --fat-host-abi x86_64 --mozconfig assets/mozconfig.android --variant release --disable-debug-signing \
  --jobs 10 --build-date 20261006140000 --gradle-home $B/aar/gradle-home --engine podman --image $IMG > $B/apk.log 2>&1; rc=$?
log "END apk exit=$rc"
log "START unit tests"
podman run --rm --name lw-ubo-unittest-$$ \
  -v "$T:/work/src" -v "$O:/work/out" -v "$O/mozbuild-srcdirs:/root/.mozbuild/srcdirs" -w /work/src \
  -e MOZCONFIG=/work/out/mozconfig.x86_64 -e MOZ_BUILD_DATE=20261006140000 \
  -e GRADLE_USER_HOME=/work/out/gradle-home -e MOZ_ANDROID_FAT_AAR_ARCHITECTURES=x86_64 \
  -e MOZ_ANDROID_FAT_AAR_X86_64=/work/out/input/x86_64/target.maven.zip \
  $IMG \
  bash -c './mach gradle fenix:testDebugUnitTest --tests "org.mozilla.fenix.components.LibreWolfUboPreinstallerTest" --tests "org.mozilla.fenix.components.LibreWolfUboPreinstallMiddlewareTest"; echo MACH_EXIT=$?' > $B/unittest.log 2>&1
log "END unit tests $(grep MACH_EXIT $B/unittest.log)"
