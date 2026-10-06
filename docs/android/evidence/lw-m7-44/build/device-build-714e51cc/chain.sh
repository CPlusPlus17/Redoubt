#!/bin/bash
# LW-M7-44 device proof of 714e51cc (+ header-only owner-decision note): fresh
# make android-dir of the patched 157.0-3 tree, x86_64 fat AAR, Fenix assembleRelease
# (-Werror), throwaway signing.
set -u
V=/home/mgysin/redoubt-artifacts/ubo-disable
R=$V/repo
T=$R/librewolf-157.0-3
B=$V/build3
BD=20261006180000
IMG=localhost/librewolf-android-build:fx157
AS=/home/mgysin/.local/state/codex-desktop/tmp/fivur-android-sdk36/build-tools/36.0.0/apksigner
# The keystore password is read from a file outside the repository (scrubbed
# 2026-10-06: an earlier copy of this script passed it inline).
KSPASS=${KS_PASS_FILE:-/home/mgysin/redoubt-artifacts/keep/throwaway-keys/throwaway.pass}
log(){ echo "$(date -u +%FT%TZ) $*" >> $B/commands.log; }
cd $R
log "START make android-dir [HEAD $(git rev-parse HEAD), worktree diff sha256 $(git diff | sha256sum | cut -c1-16)]"
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
  --ks-pass file:$KSPASS --out $V/apk/redoubt-714e51cc-x86_64-throwaway.apk $U; rc=$?
log "signed exit=$rc"
sha256sum $U $V/apk/redoubt-714e51cc-x86_64-throwaway.apk >> $B/SHA256SUMS
log "DONE"
