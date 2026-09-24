#!/usr/bin/env bash
# Check all four account-settings navigation cases after the reviewed fixture correction.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
work=/home/runner/work/feature-parity-20260908
export XDG_RUNTIME_DIR=/run/user/1001
[[ -z $(podman --remote=false ps -q) ]]
evidence="$work/evidence/fenix-navigation-diagnostic-20260909"
python3 "$work/repo/docs/android/evidence/lw-m7-21/stage-fenix-navigation-fixture.py" --check
mkdir "$evidence"
manifest="$work/evidence/fenix-navigation-fixture-source/source-sha256.txt"
[[ $(sha256sum "$manifest" | cut -d' ' -f1) == 501d04614edbc847b416cd5b6f1dac42dd0728a63125a3d9902c90d07a579c8b ]]
cp "$manifest" "$evidence/source-sha256.txt"
cd "$work/src"
sha256sum -c "$manifest" > "$evidence/source-before.txt"
results="$work/src/obj-x86_64/gradle/build/mobile/android/fenix/app/test-results/testDebugUnitTest"
[[ -d "$results" && ! -e "$results-fourth-current-20260909" ]]
mv "$results" "$results-fourth-current-20260909"
date -u --iso-8601=seconds > "$evidence/started.txt"
set +e
podman --remote=false run --rm --name fenix-navigation-diagnostic-20260909 \
  --memory=14g --memory-swap=22g --cpus=6 \
  -v "$work/src:/work/src:z" -v "$work/out:/work/out:z" \
  -v "$work/out/mozbuild-srcdirs:/root/.mozbuild/srcdirs:z" -w /work/src \
  -e MOZCONFIG=/work/out/mozconfig.x86_64 -e MOZ_BUILD_DATE=20260906190000 \
  -e GRADLE_USER_HOME=/work/out/gradle-home \
  -e MOZ_ANDROID_FAT_AAR_ARCHITECTURES=armeabi-v7a,arm64-v8a,x86_64 \
  -e MOZ_ANDROID_FAT_AAR_ARMEABI_V7A=/work/out/input/armeabi-v7a/target.maven.zip \
  -e MOZ_ANDROID_FAT_AAR_ARM64_V8A=/work/out/input/arm64-v8a/target.maven.zip \
  -e MOZ_ANDROID_FAT_AAR_X86_64=/work/out/input/x86_64/target.maven.zip \
  sha256:c5b57d94cf9e0ed1de7061cee9e0dbfde19d5651e3e2f3824b0e1466116fd687 ./mach gradle :fenix:testDebugUnitTest \
  --tests org.mozilla.fenix.HomeActivityAccountSettingsTest \
  --no-daemon --no-build-cache --max-workers=4 -PgleanBuildDate=2026-09-06T19:00:00 \
  > "$evidence/target.log" 2>&1
result=$?
printf '%s\n' "$result" > "$evidence/build-exit.txt"
set -e
sha256sum -c "$manifest" > "$evidence/source-after.txt"
tar -czf "$evidence/junit-xml.tar.gz" -C "$results" .
date -u --iso-8601=seconds > "$evidence/finished.txt"
exit "$result"
