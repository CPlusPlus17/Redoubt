#!/bin/bash
# apkonly.sh NAME OVERLAYS BUILD_DATE ABI : re-run only the APK step of chain.sh
# (same tree, AAR and objdir), e.g. after a Gradle daemon was killed.
set -u
NAME=$1; OVL=$2; BD=$3; ABI=$4
I=/home/mgysin/redoubt-artifacts/iso-158-2/builds
B=$I/build-$NAME; R=$B/repo; T=$R/librewolf-158.0-2
IMG=localhost/librewolf-android-build:fx158
log(){ echo "$(date -u +%FT%TZ) $*" >> $B/commands.log; }
cd $R
AO=""; [ -n "$OVL" ] && AO="--allow-overlays"
log "START apk (retry) $ABI release $AO HEAD=$(git rev-parse HEAD)"
env -u LW_UPDATE_CHECK_URL -u LW_UPDATE_CHECK_ENABLED -u LW_UPDATE_CHECK_PUBKEY -u LW_UPDATE_CHECK_ENDPOINT \
  ./scripts/android-apk.sh --srcdir $T --aar-dir $B/aar --outdir $B/apk \
  --abis $ABI --fat-host-abi $ABI --mozconfig mozconfig.werror --variant release --disable-debug-signing $AO \
  --jobs 10 --build-date $BD --gradle-home $B/aar/gradle-home --engine podman --image $IMG > $B/apk-retry.log 2>&1; rc=$?
log "END apk (retry) exit=$rc (single-ABI universal check may exit 1)"
ls $B/apk/apk/*.apk >> $B/commands.log 2>&1
sha256sum $B/apk/apk/*.apk >> $B/SHA256SUMS 2>/dev/null
log "DONE"
