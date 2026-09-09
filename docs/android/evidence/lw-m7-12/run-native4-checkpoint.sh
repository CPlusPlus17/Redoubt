#!/usr/bin/env bash
# Serialize the already authorized checkpoint after the pinned native invocation.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
work=/home/runner/work/feature-parity-20260908
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
cd "$work/repo"
evidence="$work/evidence/native4-checkpoint"
if [[ -d "$evidence" ]]; then
  [[ -s "$evidence/finished.txt" ]]
  mv "$evidence" "$evidence-previous-$(date -u +%Y%m%dT%H%M%S)-$$"
fi
mkdir "$evidence"
date -u --iso-8601=seconds > "$evidence/started.txt"
trap 'date -u --iso-8601=seconds > "$evidence/finished.txt"' EXIT
unit=${REDOUBT_NATIVE_UNIT:-redoubt-parity-native4-20260909.service}
expected_invocation=${REDOUBT_NATIVE_INVOCATION:-367f4a0c473843b4832ee42f0c9e2ff2}
expected_start=${REDOUBT_NATIVE_STARTED:-2026-09-09T00:53:49+00:00}
systemctl --user show "$unit" -p InvocationID -p ActiveState -p ExecMainStartTimestamp \
  > "$evidence/initial-service.txt"
grep -qx "InvocationID=$expected_invocation" "$evidence/initial-service.txt"
while true; do
  state=$(systemctl --user show "$unit" -p ActiveState --value)
  if [[ "$state" == inactive ]]; then break; fi
  invocation=$(systemctl --user show "$unit" -p InvocationID --value)
  [[ -z "$invocation" || "$invocation" == "$expected_invocation" ]]
  [[ "$state" == active || "$state" == activating || "$state" == deactivating ]]
  sleep 20
done
python3 docs/android/evidence/lw-m7-21/capture-native4.py --unit "$unit" \
  --invocation "$expected_invocation" --started "$expected_start" > "$evidence/native-capture.json"
for stage in apk tests; do
  set +e
  bash "docs/android/evidence/lw-m7-12/run-extended-$stage.sh" > "$evidence/$stage.log" 2>&1
  result=$?
  set -e
  printf '%s\n' "$result" > "$evidence/$stage-exit.txt"
  [[ "$result" == 0 ]]
done
set +e
bash docs/android/evidence/lw-m7-12/run-candidate-smoke.sh > "$evidence/runtime.log" 2>&1
result=$?
set -e
printf '%s\n' "$result" > "$evidence/runtime-exit.txt"
exit "$result"
