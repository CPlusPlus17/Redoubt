#!/usr/bin/env bash
# Full Fenix/AC after combined account and Suggest process guards; new APK pending.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
work=/home/runner/work/feature-parity-20260908
apk_evidence="$work/evidence/fenix-regression-apk"
evidence="$work/evidence/account-process-tests"
[[ $(cat "$apk_evidence/build-exit.txt") == 0 ]]
[[ -s "$apk_evidence/finished.txt" ]]
python3 "$work/repo/docs/android/evidence/lw-m7-21/stage-account-process-fixes.py" --check
fixture="$work/evidence/account-process-source"
[[ ! -e "$evidence" ]]
[[ $(cat "$work/evidence/account-process-diagnostic-20260909/build-exit.txt") == 0 ]]
mkdir -p "$evidence/prior-results"
cp "$fixture/source-sha256.txt" "$evidence/source-sha256.txt"
cp "$fixture/receipt.json" "$evidence/source-staging.json"
cp "$apk_evidence/source-sha256.txt" "$evidence/historical-compiled-apk-source-sha256.txt"
cd "$work/src"
sha256sum -c "$evidence/source-sha256.txt" > "$evidence/source-before.txt"
cd "$work/repo"
date -u --iso-8601=seconds > "$evidence/started.txt"
date +%s > "$evidence/started-epoch.txt"
cat /proc/sys/kernel/random/boot_id > "$evidence/boot-id.txt"
free -b > "$evidence/memory-before.txt"
sha256sum docs/android/board.py docs/android/fenix-test-allowlist.yaml \
  docs/android/evidence/lw-m7-12/run-fenix-account-process-tests.sh \
  docs/android/evidence/lw-m7-12/grade-extended-tests.py > "$evidence/driver-sha256.txt"
results_root="$work/src/obj-x86_64/gradle/build/mobile/android"
for pair in \
  'fenix:fenix/app' \
  'extensions:android-components/components/support/webextensions' \
  'gecko:android-components/components/browser/engine-gecko' \
  'state:android-components/components/browser/state' \
  'accounts:android-components/components/service/firefox-accounts' \
  'syncedtabs:android-components/components/feature/syncedtabs' \
  'suggest:android-components/components/feature/fxsuggest'; do
  name=${pair%%:*}
  relative=${pair#*:}
  path="$results_root/$relative/test-results/testDebugUnitTest"
  if [[ -d "$path" ]]; then mv "$path" "$evidence/prior-results/$name"; fi
done
set +e
podman run --rm --name parity-extended-tests \
  --memory=14g --memory-swap=22g --cpus=6 \
  -v "$work/src:/work/src:z" -v "$work/out:/work/out:z" \
  -v "$evidence:/work/test-evidence:z" \
  -v "$work/out/mozbuild-srcdirs:/root/.mozbuild/srcdirs:z" -w /work/src \
  -e MOZCONFIG=/work/out/mozconfig.x86_64 -e MOZ_BUILD_DATE=20260906190000 \
  -e GRADLE_USER_HOME=/work/out/gradle-home \
  -e MOZ_ANDROID_FAT_AAR_ARCHITECTURES=armeabi-v7a,arm64-v8a,x86_64 \
  -e MOZ_ANDROID_FAT_AAR_ARMEABI_V7A=/work/out/input/armeabi-v7a/target.maven.zip \
  -e MOZ_ANDROID_FAT_AAR_ARM64_V8A=/work/out/input/arm64-v8a/target.maven.zip \
  -e MOZ_ANDROID_FAT_AAR_X86_64=/work/out/input/x86_64/target.maven.zip \
  sha256:c5b57d94cf9e0ed1de7061cee9e0dbfde19d5651e3e2f3824b0e1466116fd687 bash -c '
    ./mach gradle :fenix:testDebugUnitTest :components:support-webextensions:testDebugUnitTest --continue --no-daemon --no-build-cache --max-workers=4 -PgleanBuildDate=2026-09-06T19:00:00
    fenix_rc=$?
    printf "%s\n" "$fenix_rc" > /work/test-evidence/fenix-gradle-exit.txt
    ./mach gradle \
      :components:browser-engine-gecko:testDebugUnitTest \
      --tests mozilla.components.browser.engine.gecko.permission.OriginBoundPermissionRequestTest \
      --tests mozilla.components.browser.engine.gecko.permission.OriginBoundPermissionsStorageTest \
      --tests mozilla.components.browser.engine.gecko.permission.GeckoSitePermissionsStorageTest \
      --tests mozilla.components.browser.engine.gecko.cookiebanners.GeckoCookieBannersStorageTest \
      :components:browser-state:testDebugUnitTest \
      --tests mozilla.components.browser.state.ext.PermissionRequestTest \
      :components:service-firefox-accounts:testDebugUnitTest \
      --tests mozilla.components.service.fxa.AccountServicesDisabledTest \
      --tests mozilla.components.service.fxa.AccountServicesTest \
      --tests mozilla.components.service.fxa.sync.AccountServicesWorkerTest \
      :components:feature-syncedtabs:testDebugUnitTest \
      --tests mozilla.components.feature.syncedtabs.commands.AccountServicesFlushWorkerTest \
      :components:feature-fxsuggest:testDebugUnitTest \
      --tests mozilla.components.feature.fxsuggest.FxSuggestAdmissionTest \
      --tests mozilla.components.feature.fxsuggest.datasource.OnlineSuggestionAdmissionTest \
      --continue --no-daemon --no-build-cache --max-workers=4 -PgleanBuildDate=2026-09-06T19:00:00
    ac_rc=$?
    printf "%s\n" "$ac_rc" > /work/test-evidence/ac-gradle-exit.txt
    cat /sys/fs/cgroup/memory.peak > /work/test-evidence/memory.peak
    cat /sys/fs/cgroup/memory.events > /work/test-evidence/memory.events
    exit "$ac_rc"
  ' > "$evidence/target-tests.log" 2>&1
container_rc=$?
printf '%s\n' "$container_rc" > "$evidence/container-exit.txt"
python3 docs/android/board.py --check-fenix-tests \
  --results "$results_root/fenix/app/test-results/testDebugUnitTest" \
  > "$evidence/fenix-gate.txt" 2>&1
gate_rc=$?
printf '%s\n' "$gate_rc" > "$evidence/fenix-gate-exit.txt"
python3 docs/android/evidence/lw-m7-12/grade-extended-tests.py \
  "$results_root" "$evidence" > "$evidence/fresh-results-gate.txt" 2>&1
fresh_rc=$?
printf '%s\n' "$fresh_rc" > "$evidence/fresh-results-gate-exit.txt"
set -e
cd "$work/src"
sha256sum -c "$evidence/source-sha256.txt" > "$evidence/source-after.txt"
free -b > "$evidence/memory-after.txt"
date -u --iso-8601=seconds > "$evidence/finished.txt"
cat "$evidence/fenix-gate.txt" "$evidence/fresh-results-gate.txt"
[[ "$container_rc" == 0 && "$gate_rc" == 0 && "$fresh_rc" == 0 ]]
