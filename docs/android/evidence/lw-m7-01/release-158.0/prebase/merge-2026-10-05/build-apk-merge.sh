#!/bin/bash
# Gradle-only re-run (--skip-gecko) after merging main, fix/harness-sni, fix/update-accept-language; update check compiled in with the committed public key.
set -u
W=/home/mgysin/redoubt-artifacts/ff158/work
R=$W/buildrepo
T=$R/librewolf-158.0-1
B=$W/build
BD=20261004120000
IMG=localhost/librewolf-android-build:fx158
log(){ echo "$(date -u +%FT%TZ) $*" >> $B/commands.log; }
cd $R
N=${1:-2}
log "START apk x86_64 release --skip-gecko --update-check (run $N, merged main + fix branches)"
env -u LW_UPDATE_CHECK_URL -u LW_UPDATE_CHECK_ENABLED ./scripts/android-apk.sh --srcdir $T --aar-dir $B/aar --outdir $B/apk$N \
  --abis x86_64 --fat-host-abi x86_64 --mozconfig assets/mozconfig.android --variant release --disable-debug-signing \
  --jobs 8 --build-date $BD --gradle-home $B/aar/gradle-home --engine podman --image $IMG --skip-gecko --update-check > $B/apk$N.log 2>&1; rc=$?
log "END apk (run $N) exit=$rc"
exit $rc
