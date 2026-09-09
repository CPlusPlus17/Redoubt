#!/usr/bin/env bash
# Check whether the failing cookie fixture contaminates the unchanged credit-card class.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
work=/home/runner/work/feature-parity-20260908
export XDG_RUNTIME_DIR=/run/user/1001
[[ -z $(podman --remote=false ps -q) ]]
evidence="$work/evidence/cookie-creditcard-diagnostic-20260909"
mkdir "$evidence"
manifest="$work/evidence/test-fixture-optin-source/source-sha256.txt"
[[ $(sha256sum "$manifest" | cut -d' ' -f1) == 659bf836ec885425b596bf077236190e8df30b2285df625ff3988c5dc93129b6 ]]
cp "$manifest" "$evidence/source-sha256.txt"
cd "$work/src"
sha256sum -c "$manifest" > "$evidence/source-before.txt"
results="$work/src/obj-x86_64/gradle/build/mobile/android/fenix/app/test-results/testDebugUnitTest"
[[ -d "$results" && ! -e "$results-creditcard-diagnostic-20260909" ]]
mv "$results" "$results-creditcard-diagnostic-20260909"
date -u --iso-8601=seconds > "$evidence/started.txt"
set +e
podman --remote=false run --rm --name cookie-creditcard-diagnostic-20260909 \
  --memory=14g --memory-swap=22g --cpus=6 \
  -v "$work/src:/work/src:z" -v "$work/out:/work/out:z" \
  -v "$work/out/mozbuild-srcdirs:/root/.mozbuild/srcdirs:z" -w /work/src \
  -e MOZCONFIG=/work/out/mozconfig.x86_64 -e MOZ_BUILD_DATE=20260906190000 \
  -e GRADLE_USER_HOME=/work/out/gradle-home \
  -e MOZ_ANDROID_FAT_AAR_ARCHITECTURES=armeabi-v7a,arm64-v8a,x86_64 \
  -e MOZ_ANDROID_FAT_AAR_ARMEABI_V7A=/work/out/input/armeabi-v7a/target.maven.zip \
  -e MOZ_ANDROID_FAT_AAR_ARM64_V8A=/work/out/input/arm64-v8a/target.maven.zip \
  -e MOZ_ANDROID_FAT_AAR_X86_64=/work/out/input/x86_64/target.maven.zip \
  librewolf-android-build ./mach gradle :fenix:testDebugUnitTest \
  --tests org.mozilla.fenix.settings.cookiebannerhandling.CookieBannerSettingsTest \
  --tests org.mozilla.fenix.settings.cookiebannerhandling.CookieBannerSiteControllerTest \
  --tests org.mozilla.fenix.settings.creditcards.CreditCardItemViewHolderTest \
  --no-daemon --no-build-cache --max-workers=4 -PgleanBuildDate=2026-09-06T19:00:00 \
  > "$evidence/target.log" 2>&1
result=$?
printf '%s\n' "$result" > "$evidence/build-exit.txt"
set -e
sha256sum -c "$manifest" > "$evidence/source-after.txt"
tar -czf "$evidence/junit-xml.tar.gz" -C "$results" .
date -u --iso-8601=seconds > "$evidence/finished.txt"
exit "$result"
