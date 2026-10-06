#!/bin/bash
# LW-M7-45 multi-task follow-up: Fenix assembleRelease (-Werror) on the patched 157.0-3 tree (fast loop on the
# x86_64 fat AAR), throwaway signing, JVM unit tests. The keystore password is read from a file
# outside the repository (DOQ_KS_PASS_FILE), never written here.
set -u
V=/home/mgysin/redoubt-artifacts/delete-on-quit
R=$V/repo; T=$R/librewolf-157.0-3; B=$V/build3
BD=20261006150000
IMG=localhost/librewolf-android-build:fx157
AS=/home/mgysin/.local/state/codex-desktop/tmp/fivur-android-sdk36/build-tools/36.0.0/apksigner
KS=/home/mgysin/redoubt-artifacts/keep/throwaway-keys/throwaway.p12
KSPASS=${DOQ_KS_PASS_FILE:-/home/mgysin/redoubt-artifacts/keep/throwaway-keys/throwaway.pass}
TAG=${1:-doq4}
log(){ echo "$(date -u +%FT%TZ) $*" >> $B/commands.log; }
until [ -f $B/aar.rc ]; do sleep 20; done
[ "$(cat $B/aar.rc)" = 0 ] || { log "aar failed; apk not started"; exit 1; }
cd $R
rm -f $B/apk/apk/fenix-x86_64-release-unsigned.apk
log "START apk $TAG x86_64 release [patch sha256 $(sha256sum patches/android/delete-on-quit-swipe.patch | cut -c1-16)]"
env -u LW_UPDATE_CHECK_URL -u LW_UPDATE_CHECK_ENABLED ./scripts/android-apk.sh --srcdir $T --aar-dir $B/aar --outdir $B/apk \
  --abis x86_64 --fat-host-abi x86_64 --mozconfig assets/mozconfig.android --variant release --disable-debug-signing \
  --jobs 10 --build-date $BD --gradle-home $B/aar/gradle-home --engine podman --image $IMG > $B/apk-$TAG.log 2>&1; rc=$?
log "END apk $TAG exit=$rc (single-ABI universal check exits 1)"
U=$B/apk/apk/fenix-x86_64-release-unsigned.apk
if [ -f $U ]; then
  mkdir -p $V/apk
  "$AS" sign --ks $KS --ks-key-alias throwaway --ks-pass file:$KSPASS --out $V/apk/redoubt-$TAG-x86_64-throwaway.apk $U; log "signed exit=$?"
  sha256sum $U $V/apk/redoubt-$TAG-x86_64-throwaway.apk >> $B/SHA256SUMS
else log "no unsigned x86_64 apk"; fi
log "START unit tests $TAG"
O=$B/apk
podman run --rm --name lw-doq-unittest-$$ \
  -v "$T:/work/src" -v "$O:/work/out" -v "$O/mozbuild-srcdirs:/root/.mozbuild/srcdirs" -w /work/src \
  -e MOZCONFIG=/work/out/mozconfig.x86_64 -e MOZ_BUILD_DATE=$BD \
  -e GRADLE_USER_HOME=/work/out/gradle-home -e MOZ_ANDROID_FAT_AAR_ARCHITECTURES=x86_64 \
  -e MOZ_ANDROID_FAT_AAR_X86_64=/work/out/input/x86_64/target.maven.zip \
  $IMG bash -c './mach gradle fenix:testDebugUnitTest --tests "org.mozilla.fenix.lw.*"; echo MACH_EXIT=$?' > $B/unittest-$TAG.log 2>&1
log "END unit tests $TAG $(grep MACH_EXIT $B/unittest-$TAG.log)"
log DONE $TAG
