#!/usr/bin/env bash
# Runtime checks of the unchanged APKs after a separately bound test-only overlay.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
work=/home/runner/work/feature-parity-20260908
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
[[ -z $(podman --remote=false ps --format '{{.Names}}') ]]
apk_evidence="$work/evidence/parity-extended-apk"
[[ $(cat "$apk_evidence/build-exit.txt") == 0 && -s "$apk_evidence/finished.txt" ]]
[[ -s "$apk_evidence/shortcut-resource-check.txt" ]]
python3 "$work/repo/docs/android/evidence/lw-m7-21/stage-test-fixtures.py" --check
fixture="$work/evidence/test-fixture-source"
evidence="$work/evidence/parity-candidate-smoke"
if [[ -d "$evidence" ]]; then
  mv "$evidence" "$evidence-previous-$(date -u +%Y%m%dT%H%M%S)-$$"
fi
mkdir -p "$evidence"
cd "$work/repo"
apk="$work/out/apk/fenix-x86_64-release.apk"
[[ -s "$apk" ]]
cd "$work/out/apk"
sha256sum -c "$apk_evidence/SHA256SUMS.development" > "$evidence/apk-input-check.txt"
cd "$work/src"
sha256sum -c "$fixture/source-sha256.txt" > "$evidence/source-input-check.txt"
cp "$fixture/source-sha256.txt" "$evidence/source-sha256.txt"
cp "$fixture/receipt.json" "$evidence/test-fixture-staging.json"
cp "$apk_evidence/source-sha256.txt" "$evidence/compiled-apk-source-sha256.txt"
cd "$work/repo"
runtime="$work/runtime-native4-$(date -u +%Y%m%dT%H%M%S)-$$"
mkdir -m 700 "$runtime"
printf '%s\n' "$runtime" > "$evidence/runtime-workspace.txt"
export ANDROID_SDK_ROOT="$work/sdk" LW_SMOKE_APK="$apk" LW_SMOKE_DNS=9.9.9.9
adb="$ANDROID_SDK_ROOT/platform-tools/adb"
date -u --iso-8601=seconds > "$evidence/started.txt"
cat /proc/sys/kernel/random/boot_id > "$evidence/boot-id.txt"
sha256sum "$apk" scripts/android-smoke.sh scripts/android-graphics-smoke.py \
  scripts/android-pref-audit.sh docs/android/evidence/lw-m7-12/run-fixture-smoke.sh \
  docs/android/expected-prefs.txt docs/android/must-lock.txt > "$evidence/input-sha256.txt"
free -b > "$evidence/memory-before.txt"
"$adb" devices > "$evidence/devices-before.txt"
if awk 'NR>1 && $2 == "device" { found=1 } END { exit !found }' "$evidence/devices-before.txt"; then
  echo 'An existing device is attached; this isolated run requires its own emulator.' >&2
  exit 2
fi
serial=""
cleanup() {
  if [[ -n "$serial" ]]; then "$adb" -s "$serial" emu kill || true; fi
  date -u --iso-8601=seconds > "$evidence/finished.txt"
  free -b > "$evidence/memory-after.txt"
}
trap cleanup EXIT
set +e
./scripts/android-smoke.sh --emulator --keep-emulator --sdk "$ANDROID_SDK_ROOT" \
  --apk "$apk" --work "$runtime/smoke-first-navigation" --check-ubo-lifecycle \
  --json "$evidence/ubo-lifecycle.json" > "$evidence/ubo-lifecycle.log" 2>&1
ubo_rc=$?
printf '%s\n' "$ubo_rc" > "$evidence/ubo-lifecycle-exit.txt"
set -e
"$adb" devices > "$evidence/devices-after-ubo.txt"
serial=$(awk 'NR>1 && $2 == "device" { print $1 }' "$evidence/devices-after-ubo.txt")
if [[ ! "$serial" =~ ^emulator-[0-9]+$ ]]; then
  echo 'The emulator did not become available; no browser checks can run.' >&2
  exit 2
fi
export ANDROID_SERIAL="$serial"
export LW_SMOKE_PCAP="$runtime/smoke-first-navigation/capture.pcap"
set +e
./scripts/android-smoke.sh --serial "$serial" --sdk "$ANDROID_SDK_ROOT" \
  --apk "$apk" --work "$runtime/smoke-baseline" \
  --json "$evidence/baseline.json" > "$evidence/baseline.log" 2>&1
baseline_rc=$?
printf '%s\n' "$baseline_rc" > "$evidence/baseline-exit.txt"
LW_SMOKE_WORK="$runtime/smoke-pref-audit" ./scripts/android-pref-audit.sh \
  > "$evidence/pref-audit.log" 2>&1
pref_rc=$?
printf '%s\n' "$pref_rc" > "$evidence/pref-audit-exit.txt"
set -e
for log in ubo-lifecycle baseline pref-audit; do tail -25 "$evidence/$log.log"; done
[[ "$ubo_rc" == 0 && "$baseline_rc" == 0 && "$pref_rc" == 0 ]]
