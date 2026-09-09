#!/usr/bin/env bash
# Rerun complete target suites after fixture corrections, then unchanged-APK runtime.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
work=/home/runner/work/feature-parity-20260908
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
cd "$work/repo"
evidence="$work/evidence/test-fixture-recovery-checkpoint"
mkdir "$evidence"
date -u --iso-8601=seconds > "$evidence/started.txt"
trap 'date -u --iso-8601=seconds > "$evidence/finished.txt"' EXIT
for stage in tests runtime; do
  case "$stage" in
    tests) script=docs/android/evidence/lw-m7-12/run-fixture-tests.sh ;;
    runtime) script=docs/android/evidence/lw-m7-12/run-fixture-smoke.sh ;;
  esac
  set +e
  bash "$script" > "$evidence/$stage.log" 2>&1
  result=$?
  set -e
  printf '%s\n' "$result" > "$evidence/$stage-exit.txt"
  [[ "$result" == 0 ]]
done
