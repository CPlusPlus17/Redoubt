#!/bin/bash
set -u
W=/home/mgysin/redoubt-artifacts/beta5/work
R=/home/mgysin/redoubt-artifacts/beta5/repo
BD=20261003200000
cd $R
log(){ echo "$(date -u +%FT%TZ) $*" >> $W/commands.log; }
AARCMD=(make android-build TARGETS=android CONTAINER_ENGINE=podman android_build_image=localhost/librewolf-android-build:fx157 LW_ANDROID_SRCDIR=$W/librewolf-157.0-1 ANDROID_AAR_OUTDIR=$W/librewolf-android-aar-157.0-1 "ANDROID_AAR_FLAGS=--jobs=8 --build-date=$BD")
printf '%q ' "${AARCMD[@]}" > $W/aar-cmd.txt
log "START (cwd repo) $(cat $W/aar-cmd.txt) [image $(podman image inspect --format '{{.Id}}' localhost/librewolf-android-build:fx157 | cut -c1-12)]"
"${AARCMD[@]}" > $W/fat-aar.log 2>&1; rc=$?
log "END fat-aar exit=$rc"
[ $rc -eq 0 ] || exit $rc
for d in armeabi-v7a arm64-v8a x86_64; do printf '%-12s %s\n' $d "$(grep -o '[0-9]\{14\}' $W/librewolf-157.0-1/obj-$d/buildid.h)"; done > $W/buildid-objdirs.txt
log "buildid.h: $(tr '\n' ' ' < $W/buildid-objdirs.txt)"
APKCMD=(make android-package TARGETS=android CONTAINER_ENGINE=podman android_build_image=localhost/librewolf-android-build:fx157 LW_ANDROID_SRCDIR=$W/librewolf-157.0-1 ANDROID_AAR_OUTDIR=$W/librewolf-android-aar-157.0-1 ANDROID_APK_OUTDIR=$W/librewolf-android-apk-157.0-1 "ANDROID_APK_FLAGS=--jobs=8 --variant=release --disable-debug-signing --build-date=$BD --gradle-home=$W/librewolf-android-aar-157.0-1/gradle-home")
printf '%q ' "${APKCMD[@]}" > $W/apk-cmd.txt
log "START (cwd repo, LW_UPDATE_CHECK_* unset) $(cat $W/apk-cmd.txt)"
env -u LW_UPDATE_CHECK_URL -u LW_UPDATE_CHECK_ENABLED "${APKCMD[@]}" > $W/apk.log 2>&1; rc=$?
log "END android-package exit=$rc"
exit $rc
