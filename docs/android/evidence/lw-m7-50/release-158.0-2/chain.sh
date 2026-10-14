#!/bin/bash
# chain.sh NAME OVERLAYS BUILD_DATE ABI : one Redoubt 158.0-2 APK (unsigned) from
# release/158.0-2-isolation, C/C++ warnings as errors (Rust lints capped).
set -u
NAME=$1; OVL=$2; BD=$3; ABI=$4
I=/home/mgysin/redoubt-artifacts/iso-158-2/builds
B=$I/build-$NAME; R=$B/repo; T=$R/librewolf-158.0-2
IMG=localhost/librewolf-android-build:fx158
log(){ echo "$(date -u +%FT%TZ) $*" >> $B/commands.log; }
mkdir -p $B; rm -rf $R
git clone -q -b release/158.0-2-isolation /home/mgysin/redoubt-artifacts/iso-158-2/repo $R || exit 1
cd $R
git -c protocol.file.allow=always submodule update --init -q || exit 1
echo 158.0 > version; echo 158.0 > version.android; echo 2 > release.android
ln -s /home/mgysin/redoubt-artifacts/iso-proto/r2/src/firefox-158.0.source.tar.xz .
ln -s /home/mgysin/redoubt-artifacts/iso-proto/r2/src/firefox-158.0.source.tar.xz.asc .
# -Werror for C/C++ (WARNINGS_AS_ERRORS). --enable-warnings-as-errors also makes
# rustc -Dwarnings and the in-tree app-services remote_settings crate has dead
# code (not ours), so Rust lints are capped back to warnings via RUSTFLAGS.
cp assets/mozconfig.android mozconfig.werror && printf '%s\n' 'ac_add_options --enable-warnings-as-errors' 'export RUSTFLAGS="--cap-lints warn"' >> mozconfig.werror
log "START make android-dir NAME=$NAME OVERLAYS='$OVL' HEAD=$(git rev-parse HEAD) dirty=[$(git status --short | tr '\n' ' ')] tarball=$(sha256sum firefox-158.0.source.tar.xz | cut -d' ' -f1)"
make android-dir TARGETS=android ${OVL:+OVERLAYS=$OVL} > $B/make-dir.log 2>&1; rc=$?
log "END make android-dir exit=$rc marker=[$(cat $T/redoubt-overlays.txt 2>/dev/null | tr '\n' ' ')]"; [ $rc -eq 0 ] || exit $rc
log "START fat-aar $ABI bd=$BD werror [image $(podman image inspect --format '{{.Id}}' $IMG | cut -c1-12)]"
./scripts/android-fat-aar.sh --srcdir $T --outdir $B/aar --abis $ABI --fat-host-abi $ABI \
  --mozconfig mozconfig.werror --jobs 10 --build-date $BD --engine podman --image $IMG > $B/fat-aar.log 2>&1; rc=$?
log "END fat-aar exit=$rc"; [ $rc -eq 0 ] || exit $rc
AO=""; [ -n "$OVL" ] && AO="--allow-overlays"
log "START apk $ABI release $AO"
env -u LW_UPDATE_CHECK_URL -u LW_UPDATE_CHECK_ENABLED -u LW_UPDATE_CHECK_PUBKEY -u LW_UPDATE_CHECK_ENDPOINT \
  ./scripts/android-apk.sh --srcdir $T --aar-dir $B/aar --outdir $B/apk \
  --abis $ABI --fat-host-abi $ABI --mozconfig mozconfig.werror --variant release --disable-debug-signing $AO \
  --jobs 10 --build-date $BD --gradle-home $B/aar/gradle-home --engine podman --image $IMG > $B/apk.log 2>&1; rc=$?
log "END apk exit=$rc (single-ABI universal check may exit 1)"
ls $B/apk/apk/*.apk >> $B/commands.log 2>&1
sha256sum $B/apk/apk/*.apk >> $B/SHA256SUMS 2>/dev/null
log "DONE"
