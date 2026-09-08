#!/usr/bin/env bash
# Manual feature-candidate checks inside the isolated guest, serial with builds.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
work=/home/runner/work/feature-parity-20260908
evidence="$work/evidence/parity-candidate-smoke"
mkdir -p "$evidence"
cd "$work/repo"
[[ $(cat "$work/evidence/parity-feature-apk/build-exit.txt") == 0 ]]
apk="$work/out/apk/fenix-x86_64-release.apk"
[[ -s "$apk" ]]
export ANDROID_SDK_ROOT="$work/sdk" LW_SMOKE_APK="$apk" LW_SMOKE_DNS=9.9.9.9
adb="$ANDROID_SDK_ROOT/platform-tools/adb"
date -u --iso-8601=seconds > "$evidence/started.txt"
cat /proc/sys/kernel/random/boot_id > "$evidence/boot-id.txt"
sha256sum "$apk" scripts/android-smoke.sh scripts/android-pref-audit.sh \
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
  --apk "$apk" --work "$work/smoke-first-navigation" --check-ubo-lifecycle \
  --json "$evidence/ubo-lifecycle.json" > "$evidence/ubo-lifecycle.log" 2>&1
ubo_rc=$?
printf '%s\n' "$ubo_rc" > "$evidence/ubo-lifecycle-exit.txt"
set -e
"$adb" devices > "$evidence/devices-after-ubo.txt"
serial=$(awk 'NR>1 && $2 == "device" { print $1 }' "$evidence/devices-after-ubo.txt")
[[ "$serial" =~ ^emulator-[0-9]+$ ]]
export ANDROID_SERIAL="$serial"
export LW_SMOKE_PCAP="$work/smoke-first-navigation/capture.pcap"
set +e
./scripts/android-smoke.sh --serial "$serial" --sdk "$ANDROID_SDK_ROOT" \
  --apk "$apk" --work "$work/smoke-baseline" \
  --json "$evidence/baseline.json" > "$evidence/baseline.log" 2>&1
baseline_rc=$?
printf '%s\n' "$baseline_rc" > "$evidence/baseline-exit.txt"
LW_SMOKE_WORK="$work/smoke-pref-audit" ./scripts/android-pref-audit.sh \
  > "$evidence/pref-audit.log" 2>&1
pref_rc=$?
printf '%s\n' "$pref_rc" > "$evidence/pref-audit-exit.txt"
set -e
for log in ubo-lifecycle baseline pref-audit; do tail -25 "$evidence/$log.log"; done
[[ "$ubo_rc" == 0 && "$baseline_rc" == 0 && "$pref_rc" == 0 ]]
