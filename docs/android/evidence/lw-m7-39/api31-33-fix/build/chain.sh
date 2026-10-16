#!/bin/bash
# chain.sh NAME OVERLAYS BUILD_DATE ABI : one unsigned Redoubt 158.0-3 APK from fix/drm-api31-33's
# WORKTREE state (HEAD + uncommitted diff + untracked files + settings HEAD), C/C++ -Werror
# (Rust lints capped). Gradle steps serialised with builds/apk.lock.
set -u
NAME=$1; OVL=$2; BD=$3; ABI=$4
I=/home/mgysin/redoubt-artifacts/drm-a12/builds; W=/home/mgysin/redoubt-artifacts/drm-a12/repo
B=$I/build-$NAME; R=$B/repo; T=$R/librewolf-158.0-3
IMG=localhost/librewolf-android-build:fx158
log(){ echo "$(date -u +%FT%TZ) $*" >> $B/commands.log; }
mkdir -p $B; rm -rf $R
git clone -q /home/mgysin/Documents/librewolf $R || exit 1
cd $R; git fetch -q $W HEAD && git checkout -q $(git -C $W rev-parse HEAD) || exit 1
git -C $W diff --binary HEAD -- . ':!settings' | git apply || exit 1
for f in $(git -C $W ls-files --others --exclude-standard); do mkdir -p $(dirname $f); cp $W/$f $f; done
SET=$(git -C $W ls-tree HEAD settings | awk '{print $3}')
git -c protocol.file.allow=always -c submodule.settings.url=/home/mgysin/Documents/librewolf/settings submodule update --init -q || exit 1
[ "$(git -C settings rev-parse HEAD)" = "$SET" ] || { log "settings mismatch"; exit 1; }
ln -s /home/mgysin/redoubt-artifacts/ff158/final/firefox-158.0.source.tar.xz .
ln -s /home/mgysin/redoubt-artifacts/ff158/final/firefox-158.0.source.tar.xz.asc .
cp assets/mozconfig.android mozconfig.werror && printf '%s\n' 'ac_add_options --enable-warnings-as-errors' 'export RUSTFLAGS="--cap-lints warn"' >> mozconfig.werror
log "START make android-dir NAME=$NAME OVERLAYS='$OVL' HEAD=$(git rev-parse HEAD) settings=$SET worktree-diff-sha256=$(git diff --binary HEAD -- . ':!settings' | sha256sum | cut -c1-16) isolation-eme.patch=$(sha256sum patches/android/isolation-eme.patch | cut -c1-16) tarball=$(sha256sum firefox-158.0.source.tar.xz | cut -d' ' -f1)"
make android-dir TARGETS=android ${OVL:+OVERLAYS=$OVL} > $B/make-dir.log 2>&1; rc=$?
log "END make android-dir exit=$rc marker=[$(cat $T/redoubt-overlays.txt 2>/dev/null | tr '\n' ' ')]"; [ $rc -eq 0 ] || exit $rc
log "START fat-aar $ABI bd=$BD werror [image $(podman image inspect --format '{{.Id}}' $IMG | cut -c1-12)]"
./scripts/android-fat-aar.sh --srcdir $T --outdir $B/aar --abis $ABI --fat-host-abi $ABI \
  --mozconfig mozconfig.werror --jobs 12 --build-date $BD --engine podman --image $IMG > $B/fat-aar.log 2>&1; rc=$?
log "END fat-aar exit=$rc"; [ $rc -eq 0 ] || exit $rc
AO=""; [ -n "$OVL" ] && AO="--allow-overlays"
exec 9>$I/apk.lock; flock 9
log "START apk $ABI release $AO (apk lock held)"
env -u LW_UPDATE_CHECK_URL -u LW_UPDATE_CHECK_ENABLED -u LW_UPDATE_CHECK_PUBKEY -u LW_UPDATE_CHECK_ENDPOINT \
  ./scripts/android-apk.sh --srcdir $T --aar-dir $B/aar --outdir $B/apk \
  --abis $ABI --fat-host-abi $ABI --mozconfig mozconfig.werror --variant release --disable-debug-signing $AO \
  --jobs 12 --build-date $BD --gradle-home $B/aar/gradle-home --engine podman --image $IMG > $B/apk.log 2>&1; rc=$?
log "END apk exit=$rc (single-ABI universal check may exit 1)"; flock -u 9
ls $B/apk/apk/*.apk >> $B/commands.log 2>&1
sha256sum $B/apk/apk/*.apk >> $B/SHA256SUMS 2>/dev/null
log "DONE"
