#!/bin/bash
# LW-M7-45 on 158: x86_64 build of the local android/firefox-158 merge (a0c10098, multi-task fix), release-day
# layout (version 158.0, release.android 1) with 158.0b4's bytes. Not a release build. The
# throwaway keystore password is read from a file outside the repository.
set -u
W=/home/mgysin/redoubt-artifacts/delete-on-quit/build158b
R=$W/repo; T=$R/librewolf-158.0-1; B=$W
BD=20261006230000
IMG=localhost/librewolf-android-build:fx158
AS=/home/mgysin/.local/state/codex-desktop/tmp/fivur-android-sdk36/build-tools/36.0.0/apksigner
KSPASS=${DOQ_KS_PASS_FILE:-/home/mgysin/redoubt-artifacts/keep/throwaway-keys/throwaway.pass}
log(){ echo "$(date -u +%FT%TZ) $*" >> $B/commands.log; }
cd $R
log "START make android-dir [HEAD $(git rev-parse HEAD); tarball sha256 $(sha256sum firefox-158.0.source.tar.xz | cut -c1-16) = 158.0b4]"
make android-dir > $B/make-dir.log 2>&1; rc=$?
log "END make android-dir exit=$rc"; [ $rc -eq 0 ] || exit $rc
log "START fat-aar x86_64 [image $(podman image inspect --format '{{.Id}}' $IMG | cut -c1-12)]"
./scripts/android-fat-aar.sh --srcdir $T --outdir $B/aar --abis x86_64 --fat-host-abi x86_64 \
  --mozconfig assets/mozconfig.android --jobs 10 --build-date $BD --engine podman --image $IMG > $B/fat-aar.log 2>&1; rc=$?
log "END fat-aar exit=$rc"; [ $rc -eq 0 ] || exit $rc
log "START apk x86_64 release"
env -u LW_UPDATE_CHECK_URL -u LW_UPDATE_CHECK_ENABLED ./scripts/android-apk.sh --srcdir $T --aar-dir $B/aar --outdir $B/apk \
  --abis x86_64 --fat-host-abi x86_64 --mozconfig assets/mozconfig.android --variant release --disable-debug-signing \
  --jobs 10 --build-date $BD --gradle-home $B/aar/gradle-home --engine podman --image $IMG > $B/apk.log 2>&1; rc=$?
log "END apk exit=$rc (single-ABI universal check exits 1)"
U=$B/apk/apk/fenix-x86_64-release-unsigned.apk
[ -f $U ] || { log "no unsigned x86_64 apk"; exit 1; }
"$AS" sign --ks /home/mgysin/redoubt-artifacts/keep/throwaway-keys/throwaway.p12 --ks-key-alias throwaway \
  --ks-pass file:$KSPASS --out $B/redoubt-158b4-doq5-x86_64-throwaway.apk $U; rc=$?
log "signed exit=$rc"
sha256sum $U $B/redoubt-158b4-doq5-x86_64-throwaway.apk >> $B/SHA256SUMS
log "START unit tests lw.*"
O=$B/apk
podman run --rm --name lw-doq158-unittest-$$ \
  -v "$T:/work/src" -v "$O:/work/out" -v "$O/mozbuild-srcdirs:/root/.mozbuild/srcdirs" -w /work/src \
  -e MOZCONFIG=/work/out/mozconfig.x86_64 -e MOZ_BUILD_DATE=$BD \
  -e GRADLE_USER_HOME=/work/out/gradle-home -e MOZ_ANDROID_FAT_AAR_ARCHITECTURES=x86_64 \
  -e MOZ_ANDROID_FAT_AAR_X86_64=/work/out/input/x86_64/target.maven.zip \
  $IMG bash -c './mach gradle fenix:testDebugUnitTest --tests "org.mozilla.fenix.lw.*"; echo MACH_EXIT=$?' > $B/unittest.log 2>&1
log "END unit tests $(grep MACH_EXIT $B/unittest.log)"
log "DONE"
