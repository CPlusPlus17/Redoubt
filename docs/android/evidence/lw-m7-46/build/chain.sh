#!/bin/bash
# LW-M7-46: x86_64 build of fix/webgl-quiet-notice on 158.0b4 bytes, release-day layout
# (version 158.0, release.android 2). Not a release build. Throwaway key; password read from a file.
set -u
W=/home/mgysin/redoubt-artifacts/webgl-notice/build
R=$W/repo; T=$R/librewolf-158.0-2; B=$W/out
BD=20261009140000
IMG=localhost/librewolf-android-build:fx158
AS=/home/mgysin/.local/state/codex-desktop/tmp/fivur-android-sdk36/build-tools/36.0.0/apksigner
KSPASS=/home/mgysin/redoubt-artifacts/keep/throwaway-keys/throwaway.pass
log(){ echo "$(date -u +%FT%TZ) $*" >> $B/commands.log; }
cd $R
log "START fat-aar x86_64 [tree from make android-dir; canvas patch sha256 $(sha256sum patches/android/canvas-webgl-permissions.patch | cut -c1-16); tarball 158.0b4 $(sha256sum firefox-158.0.source.tar.xz | cut -c1-16); image $(podman image inspect --format '{{.Id}}' $IMG | cut -c1-12)]"
./scripts/android-fat-aar.sh --srcdir $T --outdir $B/aar --abis x86_64 --fat-host-abi x86_64 \
  --mozconfig assets/mozconfig.android --jobs 8 --build-date $BD --engine podman --image $IMG > $B/fat-aar.log 2>&1; rc=$?
log "END fat-aar exit=$rc"; [ $rc -eq 0 ] || exit $rc
log "START apk x86_64 release"
env -u LW_UPDATE_CHECK_URL -u LW_UPDATE_CHECK_ENABLED ./scripts/android-apk.sh --srcdir $T --aar-dir $B/aar --outdir $B/apk \
  --abis x86_64 --fat-host-abi x86_64 --mozconfig assets/mozconfig.android --variant release --disable-debug-signing \
  --jobs 8 --build-date $BD --gradle-home $B/aar/gradle-home --engine podman --image $IMG > $B/apk.log 2>&1; rc=$?
log "END apk exit=$rc (single-ABI universal check exits 1)"
U=$B/apk/apk/fenix-x86_64-release-unsigned.apk
[ -f $U ] || { log "no unsigned x86_64 apk"; exit 1; }
"$AS" sign --ks /home/mgysin/redoubt-artifacts/keep/throwaway-keys/throwaway.p12 --ks-key-alias throwaway \
  --ks-pass file:$KSPASS --out $B/redoubt-158b4-webgl-notice-x86_64-throwaway.apk $U; rc=$?
log "signed exit=$rc"
sha256sum $U $B/redoubt-158b4-webgl-notice-x86_64-throwaway.apk >> $B/SHA256SUMS
log "START unit tests org.mozilla.fenix.browser.permissions.*"
O=$B/apk
podman run --rm --name lw-webgl-notice-unittest-$$ \
  -v "$T:/work/src" -v "$O:/work/out" -v "$O/mozbuild-srcdirs:/root/.mozbuild/srcdirs" -w /work/src \
  -e MOZCONFIG=/work/out/mozconfig.x86_64 -e MOZ_BUILD_DATE=$BD \
  -e GRADLE_USER_HOME=/work/out/gradle-home -e MOZ_ANDROID_FAT_AAR_ARCHITECTURES=x86_64 \
  -e MOZ_ANDROID_FAT_AAR_X86_64=/work/out/input/x86_64/target.maven.zip \
  $IMG bash -c './mach gradle fenix:testDebugUnitTest --tests "org.mozilla.fenix.browser.permissions.*"; echo MACH_EXIT=$?' > $B/unittest.log 2>&1
log "END unit tests $(grep MACH_EXIT $B/unittest.log)"
log "DONE"
