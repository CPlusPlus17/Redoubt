#!/bin/bash
# apk-stage.sh COMMIT BUILD_DATE : APK step for port/sept24-gaps at COMMIT on top of the x86_64 fat AAR that
# build-x86rel's android-fat-aar.sh produced from 6809f6b8 (same Gecko inputs: the two commits differ only in
# Fenix Kotlin under patches/android/drm-permission-default.patch, docs and an android.cfg comment).
# Fresh tree via make android-dir, C/C++ -Werror mozconfig as before, throwaway signature, then unit tests.
set -u
COMMIT=$1; BD=$2; ABI=x86_64
I=~/redoubt-artifacts/port-sept24/builds
A=$I/build-x86rel/aar
B=$I/build-apk; R=$B/repo; T=$R/librewolf-158.0-2
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
cp assets/mozconfig.android mozconfig.werror && printf '%s\n' 'ac_add_options --enable-warnings-as-errors' 'export RUSTFLAGS="--cap-lints warn"' >> mozconfig.werror
log "START make android-dir HEAD=$(git rev-parse HEAD) settings=$(git -C settings rev-parse HEAD) dirty=[$(git status --short | tr '\n' ' ')]"
make android-dir TARGETS=android > $B/make-dir.log 2>&1; rc=$?
log "END make android-dir exit=$rc"; [ $rc -eq 0 ] || exit $rc
log "Gecko-input diff 6809f6b8..$COMMIT outside Fenix sources: $(git diff --stat 6809f6b8 $COMMIT -- . ':!docs' ':!patches/android/drm-permission-default.patch' | tail -1)"
log "waiting for the fat AAR (android-fat-aar.sh of build-x86rel)"
while pgrep -f "android-fat-aar.sh --srcdir $I/build-x86rel/" > /dev/null; do sleep 30; done
log "fat-aar log tail: $(tail -1 $I/build-x86rel/fat-aar.log)"
log "START apk $ABI release (AAR $A)"
env -u LW_UPDATE_CHECK_URL -u LW_UPDATE_CHECK_ENABLED -u LW_UPDATE_CHECK_PUBKEY -u LW_UPDATE_CHECK_ENDPOINT \
  ./scripts/android-apk.sh --srcdir $T --aar-dir $A --outdir $B/apk \
  --abis $ABI --fat-host-abi $ABI --mozconfig mozconfig.werror --variant release --disable-debug-signing \
  --jobs 12 --build-date $BD --gradle-home $A/gradle-home --engine podman --image $IMG > $B/apk.log 2>&1; rc=$?
log "END apk exit=$rc (single-ABI universal check may exit 1)"
U=$B/apk/apk/fenix-x86_64-release-unsigned.apk
[ -f $U ] || { log "no unsigned x86_64 apk"; exit 1; }
"$AS" sign --ks ~/redoubt-artifacts/keep/throwaway-keys/throwaway.p12 --ks-key-alias throwaway \
  --ks-pass file:$KSPASS --out $B/redoubt-158.0-2-port-x86_64-throwaway.apk $U; rc=$?
log "signed exit=$rc"
sha256sum $U $B/redoubt-158.0-2-port-x86_64-throwaway.apk >> $B/SHA256SUMS
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
