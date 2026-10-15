#!/bin/bash
# chain.sh NAME COMMIT BUILD_DATE : x86_64 release-variant Redoubt APK from port/sept24-gaps at COMMIT,
# C/C++ warnings as errors (Rust lints capped), signed with the throwaway key, then the Fenix unit tests
# this port touches. Pattern of iso-158-2/builds/chain2.sh and evidence/lw-m7-46/build/chain.sh.
set -u
NAME=$1; COMMIT=$2; BD=$3; ABI=x86_64
I=~/redoubt-artifacts/port-sept24/builds
B=$I/build-$NAME; R=$B/repo; T=$R/librewolf-158.0-2
IMG=localhost/librewolf-android-build:fx158
AS=~/.local/state/codex-desktop/tmp/fivur-android-sdk36/build-tools/36.0.0/apksigner
KSPASS=~/redoubt-artifacts/keep/throwaway-keys/throwaway.pass
log(){ echo "$(date -u +%FT%TZ) $*" >> $B/commands.log; }
mkdir -p $B; rm -rf $R
git clone -q ~/redoubt-artifacts/port-sept24/repo $R || exit 1
cd $R; git checkout -q $COMMIT || exit 1
git -c protocol.file.allow=always -c submodule.settings.url=~/redoubt-artifacts/port-sept24/repo/settings submodule update --init -q || exit 1
ln -s ~/redoubt-artifacts/ff158/final/firefox-158.0.source.tar.xz .
ln -s ~/redoubt-artifacts/ff158/final/firefox-158.0.source.tar.xz.asc .
# -Werror for C/C++ (WARNINGS_AS_ERRORS). --enable-warnings-as-errors also makes rustc -Dwarnings and the
# in-tree app-services remote_settings crate has dead code (not ours), so Rust lints are capped to warnings.
cp assets/mozconfig.android mozconfig.werror && printf '%s\n' 'ac_add_options --enable-warnings-as-errors' 'export RUSTFLAGS="--cap-lints warn"' >> mozconfig.werror
log "START make android-dir HEAD=$(git rev-parse HEAD) settings=$(git -C settings rev-parse HEAD) dirty=[$(git status --short | tr '\n' ' ')] tarball=$(sha256sum firefox-158.0.source.tar.xz | cut -d' ' -f1)"
make android-dir TARGETS=android > $B/make-dir.log 2>&1; rc=$?
log "END make android-dir exit=$rc"; [ $rc -eq 0 ] || exit $rc
log "START fat-aar $ABI bd=$BD werror [image $(podman image inspect --format '{{.Id}}' $IMG | cut -c1-12)]"
./scripts/android-fat-aar.sh --srcdir $T --outdir $B/aar --abis $ABI --fat-host-abi $ABI \
  --mozconfig mozconfig.werror --jobs 12 --build-date $BD --engine podman --image $IMG > $B/fat-aar.log 2>&1; rc=$?
log "END fat-aar exit=$rc"; [ $rc -eq 0 ] || exit $rc
log "START apk $ABI release"
env -u LW_UPDATE_CHECK_URL -u LW_UPDATE_CHECK_ENABLED -u LW_UPDATE_CHECK_PUBKEY -u LW_UPDATE_CHECK_ENDPOINT \
  ./scripts/android-apk.sh --srcdir $T --aar-dir $B/aar --outdir $B/apk \
  --abis $ABI --fat-host-abi $ABI --mozconfig mozconfig.werror --variant release --disable-debug-signing \
  --jobs 12 --build-date $BD --gradle-home $B/aar/gradle-home --engine podman --image $IMG > $B/apk.log 2>&1; rc=$?
log "END apk exit=$rc (single-ABI universal check may exit 1)"
U=$B/apk/apk/fenix-x86_64-release-unsigned.apk
[ -f $U ] || { log "no unsigned x86_64 apk"; exit 1; }
"$AS" sign --ks ~/redoubt-artifacts/keep/throwaway-keys/throwaway.p12 --ks-key-alias throwaway \
  --ks-pass file:$KSPASS --out $B/redoubt-158.0-2-port-$NAME-x86_64-throwaway.apk $U; rc=$?
log "signed exit=$rc"
sha256sum $U $B/redoubt-158.0-2-port-$NAME-x86_64-throwaway.apk >> $B/SHA256SUMS
log "START unit tests"
O=$B/apk
podman run --rm --name lw-port-unittest-$$ \
  -v "$T:/work/src" -v "$O:/work/out" -v "$O/mozbuild-srcdirs:/root/.mozbuild/srcdirs" -w /work/src \
  -e MOZCONFIG=/work/out/mozconfig.x86_64 -e MOZ_BUILD_DATE=$BD \
  -e GRADLE_USER_HOME=/work/out/gradle-home -e MOZ_ANDROID_FAT_AAR_ARCHITECTURES=x86_64 \
  -e MOZ_ANDROID_FAT_AAR_X86_64=/work/out/input/x86_64/target.maven.zip \
  $IMG bash -c './mach gradle fenix:testDebugUnitTest --tests "org.mozilla.fenix.settings.PhoneFeatureTest" --tests "org.mozilla.fenix.utils.SettingsTest" --tests "org.mozilla.fenix.components.menu.BrowserMenuBuilderTest" --tests "org.mozilla.fenix.components.menu.compose.MoreSettingsSubmenuTest"; echo MACH_EXIT=$?' > $B/unittest.log 2>&1
log "END unit tests $(grep MACH_EXIT $B/unittest.log)"
log "DONE"
