#!/usr/bin/env bash
# Check application admission, parent choices and worker regression cases after the combined process correction.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
work=/home/runner/work/feature-parity-20260908
export XDG_RUNTIME_DIR=/run/user/1001
[[ -z $(podman --remote=false ps -q) ]]
evidence="$work/evidence/account-process-diagnostic-20260909"
python3 "$work/repo/docs/android/evidence/lw-m7-21/stage-account-process-fixes.py" --check
mkdir "$evidence"
manifest="$work/evidence/account-process-source/source-sha256.txt"
[[ $(sha256sum "$manifest" | cut -d' ' -f1) == 4ff8b61617049c56710a406c1ff30ab73b370dd0e614b97aba5f038b0eb89739 ]]
cp "$manifest" "$evidence/source-sha256.txt"
cd "$work/src"
sha256sum -c "$manifest" > "$evidence/source-before.txt"
results="$work/src/obj-x86_64/gradle/build/mobile/android/fenix/app/test-results/testDebugUnitTest"
[[ -d "$results" && ! -e "$results-navigation-current-20260909" ]]
mv "$results" "$results-navigation-current-20260909"
for pair in "accounts:service/firefox-accounts" "syncedtabs:feature/syncedtabs"; do
  name=${pair%%:*}; relative=${pair#*:}
  xml="$work/src/obj-x86_64/gradle/build/mobile/android/android-components/components/$relative/test-results/testDebugUnitTest"
  if [[ -d "$xml" ]]; then mv "$xml" "$evidence/prior-$name-results"; fi
done
date -u --iso-8601=seconds > "$evidence/started.txt"
date +%s > "$evidence/started-epoch.txt"
set +e
podman --remote=false run --rm --name account-process-diagnostic-20260909 \
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
  --tests org.mozilla.fenix.FenixApplicationTest \
  --tests org.mozilla.fenix.settings.AccountServicesPreferenceTest \
  --tests org.mozilla.fenix.settings.search.FirefoxSuggestPolicyTest \
  :components:service-firefox-accounts:testDebugUnitTest \
  --tests mozilla.components.service.fxa.AccountServicesTest \
  --tests mozilla.components.service.fxa.AccountServicesDisabledTest \
  --tests mozilla.components.service.fxa.sync.AccountServicesWorkerTest \
  :components:feature-syncedtabs:testDebugUnitTest \
  --tests mozilla.components.feature.syncedtabs.commands.AccountServicesFlushWorkerTest \
  --continue \
  --no-daemon --no-build-cache --max-workers=4 -PgleanBuildDate=2026-09-06T19:00:00 \
  > "$evidence/target.log" 2>&1
result=$?
printf '%s\n' "$result" > "$evidence/build-exit.txt"
set -e
sha256sum -c "$manifest" > "$evidence/source-after.txt"
tar -czf "$evidence/fenix-junit-xml.tar.gz" -C "$results" .
for pair in "accounts:service/firefox-accounts" "syncedtabs:feature/syncedtabs"; do
  name=${pair%%:*}; relative=${pair#*:}
  xml="$work/src/obj-x86_64/gradle/build/mobile/android/android-components/components/$relative/test-results/testDebugUnitTest"
  tar -czf "$evidence/$name-junit-xml.tar.gz" -C "$xml" .
done
date -u --iso-8601=seconds > "$evidence/finished.txt"
exit "$result"
