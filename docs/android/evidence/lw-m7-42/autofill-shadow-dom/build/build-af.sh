#!/bin/bash
# LW-M7-42 (autofill-shadow-dom): incremental x86_64 Gecko pass (omni.ja carries the
# patched GeckoViewAutoFillChild.sys.mjs) + fat merge, then fenix assembleRelease.
# Same tree, objdir, image and build date as PREBASE section 4 / run 4.
set -u
W=/home/mgysin/redoubt-artifacts/ff158/work
R=$W/buildrepo
T=$R/librewolf-158.0-1
B=$W/build
BD=20261004120000
IMG=localhost/librewolf-android-build:fx158
log(){ echo "$(date -u +%FT%TZ) $*" >> $B/commands.log; }
cd $R
# obj-x86_64 was last configured by the fat merge pass; force the per-ABI pass to
# re-run configure with per-ABI substs (mach re-configures when moz.configure is
# newer than config.status). No source content changes.
touch $T/moz.configure
log "START LW-M7-42 fat-aar x86_64 incremental [image $(podman image inspect --format '{{.Id}}' $IMG | cut -c1-12)]"
./scripts/android-fat-aar.sh --srcdir $T --outdir $B/aar-af --abis x86_64 --fat-host-abi x86_64 \
  --mozconfig assets/mozconfig.android --jobs 8 --build-date $BD --engine podman --image $IMG > $B/fat-aar-af.log 2>&1; rc=$?
log "END LW-M7-42 fat-aar exit=$rc"
[ $rc -eq 0 ] || exit $rc
log "START LW-M7-42 apk x86_64 release --update-check"
env -u LW_UPDATE_CHECK_URL -u LW_UPDATE_CHECK_ENABLED ./scripts/android-apk.sh --srcdir $T --aar-dir $B/aar-af --outdir $B/apk-af \
  --abis x86_64 --fat-host-abi x86_64 --mozconfig assets/mozconfig.android --variant release --disable-debug-signing \
  --jobs 8 --build-date $BD --gradle-home $B/aar-af/gradle-home --engine podman --image $IMG --skip-gecko --update-check > $B/apk-af.log 2>&1; rc=$?
log "END LW-M7-42 apk exit=$rc"
exit $rc
