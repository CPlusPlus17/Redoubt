#!/bin/bash
# Optional 158 x86_64 build on the merged android/firefox-158 (890043b4), release-day
# layout (version 158.0, release.android 1) with 158.0b4's bytes, for --check-video and
# --check-ubo-user-disable. Not a release build.
set -u
W=/home/mgysin/redoubt-artifacts/ff158/work
R=$W/b4build
T=$R/librewolf-158.0-1
B=$W/build-b4
BD=20261006200000
IMG=localhost/librewolf-android-build:fx158
AS=/home/mgysin/.local/state/codex-desktop/tmp/fivur-android-sdk36/build-tools/36.0.0/apksigner
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
  --ks-pass pass:throwaway --out $B/redoubt-158b4-x86_64-throwaway.apk $U; rc=$?
log "signed exit=$rc"
sha256sum $U $B/redoubt-158b4-x86_64-throwaway.apk >> $B/SHA256SUMS
log "DONE"
