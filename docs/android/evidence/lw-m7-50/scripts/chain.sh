#!/bin/bash
# chain.sh NAME OVERLAYS BUILD_DATE ABI [UPDATECHECK=0|1]
# Builds one Redoubt APK from ~/redoubt-artifacts/iso-proto/build-NAME/repo:
# make android-dir (with OVERLAYS), fat AAR for ABI, APK release unsigned.
set -u
NAME=$1; OVL=$2; BD=$3; ABI=$4; UC=${5:-0}
I=/home/mgysin/redoubt-artifacts/iso-proto
R=$I/build-$NAME/repo
B=$I/build-$NAME
T=$R/librewolf-158.0-1
IMG=localhost/librewolf-android-build:fx158
log(){ echo "$(date -u +%FT%TZ) $*" >> $B/commands.log; }
cd $R
log "START make android-dir NAME=$NAME OVERLAYS='$OVL' HEAD=$(git rev-parse HEAD) dirty=[$(git status --short | tr '\n' ' ')] tarball=$(sha256sum firefox-158.0.source.tar.xz | cut -c1-16)"
make android-dir TARGETS=android ${OVL:+OVERLAYS=$OVL} > $B/make-dir.log 2>&1; rc=$?
log "END make android-dir exit=$rc"; [ $rc -eq 0 ] || exit $rc
log "START fat-aar $ABI bd=$BD [image $(podman image inspect --format '{{.Id}}' $IMG | cut -c1-12)]"
./scripts/android-fat-aar.sh --srcdir $T --outdir $B/aar --abis $ABI --fat-host-abi $ABI \
  --mozconfig assets/mozconfig.android --jobs 10 --build-date $BD --engine podman --image $IMG > $B/fat-aar.log 2>&1; rc=$?
log "END fat-aar exit=$rc"; [ $rc -eq 0 ] || exit $rc
UCF=""; [ "$UC" = 1 ] && UCF="--update-check"
log "START apk $ABI release update-check=$UC"
env -u LW_UPDATE_CHECK_URL -u LW_UPDATE_CHECK_ENABLED -u LW_UPDATE_CHECK_PUBKEY -u LW_UPDATE_CHECK_ENDPOINT \
  ./scripts/android-apk.sh --srcdir $T --aar-dir $B/aar --outdir $B/apk \
  --abis $ABI --fat-host-abi $ABI --mozconfig assets/mozconfig.android --variant release --disable-debug-signing \
  --jobs 10 --build-date $BD --gradle-home $B/aar/gradle-home --engine podman --image $IMG $UCF > $B/apk.log 2>&1; rc=$?
log "END apk exit=$rc (single-ABI universal check may exit 1)"
ls $B/apk/apk/*.apk >> $B/commands.log 2>&1
sha256sum $B/apk/apk/*.apk >> $B/SHA256SUMS 2>/dev/null
log "DONE"
