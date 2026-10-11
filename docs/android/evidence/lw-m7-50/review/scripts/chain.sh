#!/bin/bash
# chain.sh NAME BUILD_DATE ABI : one ON (isolation-media,dev-app) dev APK from
# ~/redoubt-artifacts/iso-proto/fix/build-NAME/repo, warnings as errors.
set -u
NAME=$1; BD=$2; ABI=$3
F=/home/mgysin/redoubt-artifacts/iso-proto/fix
B=$F/build-$NAME; R=$B/repo; T=$R/librewolf-158.0-1
IMG=localhost/librewolf-android-build:fx158
OVL=isolation-media,dev-app
log(){ echo "$(date -u +%FT%TZ) $*" >> $B/commands.log; }
cd $R
# -Werror for C/C++ (WARNINGS_AS_ERRORS; dom/media has no AllowCompilerWarnings).
# --enable-warnings-as-errors also makes rustc -Dwarnings, and the in-tree
# app-services remote_settings crate has dead code here (10 errors, not ours), so
# Rust lints are capped back to warnings via the RUSTFLAGS rust.mk appends.
cp assets/mozconfig.android mozconfig.werror && printf '%s\n' 'ac_add_options --enable-warnings-as-errors' 'export RUSTFLAGS="--cap-lints warn"' >> mozconfig.werror
log "START make android-dir NAME=$NAME OVERLAYS=$OVL HEAD=$(git rev-parse HEAD) diff=$(git diff | sha256sum | cut -c1-16) tarball=$(sha256sum firefox-158.0.source.tar.xz | cut -c1-16)"
if [ "${SKIPDIR:-0}" = 1 ]; then rc=0; log "SKIPDIR: reusing tree and objdir"; else
rm -rf librewolf-158.0-1 librewolf-targets-*
make android-dir TARGETS=android OVERLAYS=$OVL > $B/make-dir.log 2>&1; rc=$?; fi
log "END make android-dir exit=$rc marker=[$(cat $T/redoubt-overlays.txt 2>/dev/null | tr '\n' ' ')]"; [ $rc -eq 0 ] || exit $rc
log "START fat-aar $ABI bd=$BD werror [image $(podman image inspect --format '{{.Id}}' $IMG | cut -c1-12)]"
./scripts/android-fat-aar.sh --srcdir $T --outdir $B/aar --abis $ABI --fat-host-abi $ABI \
  --mozconfig mozconfig.werror --jobs 10 --build-date $BD --engine podman --image $IMG > $B/fat-aar.log 2>&1; rc=$?
log "END fat-aar exit=$rc"; [ $rc -eq 0 ] || exit $rc
log "START apk $ABI release --allow-overlays"
env -u LW_UPDATE_CHECK_URL -u LW_UPDATE_CHECK_ENABLED -u LW_UPDATE_CHECK_PUBKEY -u LW_UPDATE_CHECK_ENDPOINT \
  ./scripts/android-apk.sh --srcdir $T --aar-dir $B/aar --outdir $B/apk \
  --abis $ABI --fat-host-abi $ABI --mozconfig mozconfig.werror --variant release --disable-debug-signing --allow-overlays \
  --jobs 10 --build-date $BD --gradle-home $B/aar/gradle-home --engine podman --image $IMG > $B/apk.log 2>&1; rc=$?
log "END apk exit=$rc (single-ABI universal check may exit 1)"
ls $B/apk/apk/*.apk >> $B/commands.log 2>&1
sha256sum $B/apk/apk/*.apk >> $B/SHA256SUMS 2>/dev/null
log "DONE"
