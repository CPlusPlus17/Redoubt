#!/bin/bash
# LW-M7-44 follow-up: x86_64 fat AAR (GeckoView) for the Fenix JVM unit tests only.
set -u
V=/home/mgysin/redoubt-artifacts/ubo-disable
R=$V/repo
T=$R/librewolf-157.0-3
B=$V/build2
IMG=localhost/librewolf-android-build:fx157
log(){ echo "$(date -u +%FT%TZ) $*" >> $B/commands.log; }
cd $R
log "START fat-aar x86_64 [image $(podman image inspect --format '{{.Id}}' $IMG | cut -c1-12)]"
./scripts/android-fat-aar.sh --srcdir $T --outdir $B/aar --abis x86_64 --fat-host-abi x86_64 \
  --mozconfig assets/mozconfig.android --jobs 10 --build-date 20261006140000 --engine podman --image $IMG > $B/fat-aar.log 2>&1; rc=$?
log "END fat-aar exit=$rc"
exit $rc
