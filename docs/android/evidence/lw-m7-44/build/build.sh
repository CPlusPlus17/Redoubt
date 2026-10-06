#!/bin/bash
# LW-M7-44 proof build: x86_64 GeckoView + fenix assembleRelease on the 157.0-3 tree with the fix.
set -u
V=/home/mgysin/redoubt-artifacts/ubo-disable
R=$V/repo
T=$R/librewolf-157.0-3
B=$V/build
BD=20261006140000
IMG=localhost/librewolf-android-build:fx157
log(){ echo "$(date -u +%FT%TZ) $*" >> $B/commands.log; }
cd $R
log "START fat-aar x86_64 [image $(podman image inspect --format '{{.Id}}' $IMG | cut -c1-12)]"
./scripts/android-fat-aar.sh --srcdir $T --outdir $B/aar --abis x86_64 --fat-host-abi x86_64 \
  --mozconfig assets/mozconfig.android --jobs 10 --build-date $BD --engine podman --image $IMG > $B/fat-aar.log 2>&1; rc=$?
log "END fat-aar exit=$rc"
[ $rc -eq 0 ] || exit $rc
log "START apk x86_64 release"
env -u LW_UPDATE_CHECK_URL -u LW_UPDATE_CHECK_ENABLED ./scripts/android-apk.sh --srcdir $T --aar-dir $B/aar --outdir $B/apk \
  --abis x86_64 --fat-host-abi x86_64 --mozconfig assets/mozconfig.android --variant release --disable-debug-signing \
  --jobs 10 --build-date $BD --gradle-home $B/aar/gradle-home --engine podman --image $IMG > $B/apk.log 2>&1; rc=$?
log "END apk exit=$rc"
exit $rc
