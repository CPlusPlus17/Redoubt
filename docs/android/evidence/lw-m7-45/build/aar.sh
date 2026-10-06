#!/bin/bash
# LW-M7-45: x86_64 GeckoView AAR from the unmodified origin/main 157.0-3 tree (the patch is Fenix-only).
set -u
V=/home/mgysin/redoubt-artifacts/delete-on-quit
R=$V/repo; T=$R/librewolf-157.0-3; B=$V/build
BD=20261006150000
IMG=localhost/librewolf-android-build:fx157
log(){ echo "$(date -u +%FT%TZ) $*" >> $B/commands.log; }
cd $R
log "START fat-aar x86_64 [HEAD $(git rev-parse HEAD)] [image $(podman image inspect --format '{{.Id}}' $IMG | cut -c1-12)]"
./scripts/android-fat-aar.sh --srcdir $T --outdir $B/aar --abis x86_64 --fat-host-abi x86_64 \
  --mozconfig assets/mozconfig.android --jobs 10 --build-date $BD --engine podman --image $IMG > $B/fat-aar.log 2>&1; rc=$?
log "END fat-aar exit=$rc"
echo $rc > $B/aar.rc
