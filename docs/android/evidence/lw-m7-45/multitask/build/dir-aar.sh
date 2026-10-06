#!/bin/bash
# LW-M7-45 multi-task follow-up: extract 157.0-3 tree and build x86_64 fat AAR (Gecko unchanged by the patch).
set -u
V=/home/mgysin/redoubt-artifacts/delete-on-quit
R=$V/repo; T=$R/librewolf-157.0-3; B=$V/build3
BD=20261006150000
IMG=localhost/librewolf-android-build:fx157
log(){ echo "$(date -u +%FT%TZ) $*" >> $B/commands.log; }
cd $R
rm -f $B/aar.rc
log "START make android-dir [HEAD $(git rev-parse HEAD)]"
make android-dir > $B/make-dir.log 2>&1; rc=$?
log "END make android-dir exit=$rc"
[ $rc = 0 ] || { echo $rc > $B/aar.rc; exit 1; }
log "START fat-aar x86_64 [image $(podman image inspect --format '{{.Id}}' $IMG | cut -c1-12)]"
./scripts/android-fat-aar.sh --srcdir $T --outdir $B/aar --abis x86_64 --fat-host-abi x86_64 \
  --mozconfig assets/mozconfig.android --jobs 10 --build-date $BD --engine podman --image $IMG > $B/fat-aar.log 2>&1; rc=$?
log "END fat-aar exit=$rc"
echo $rc > $B/aar.rc
