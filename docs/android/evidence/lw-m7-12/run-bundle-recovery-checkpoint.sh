#!/usr/bin/env bash
# Retry the recorded Kotlin compiler failure, then required tests and runtime.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
work=/home/runner/work/feature-parity-20260908
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
cd "$work/repo"
evidence="$work/evidence/apk-bundle-recovery-checkpoint"
mkdir "$evidence"
date -u --iso-8601=seconds > "$evidence/started.txt"
trap 'date -u --iso-8601=seconds > "$evidence/finished.txt"' EXIT
for stage in apk tests runtime; do
  case "$stage" in
    apk) script=docs/android/evidence/lw-m7-12/run-apk-bundle-recovery.sh ;;
    tests) script=docs/android/evidence/lw-m7-12/run-extended-tests.sh ;;
    runtime) script=docs/android/evidence/lw-m7-12/run-candidate-smoke.sh ;;
  esac
  set +e
  bash "$script" > "$evidence/$stage.log" 2>&1
  result=$?
  set -e
  printf '%s\n' "$result" > "$evidence/$stage-exit.txt"
  [[ "$result" == 0 ]]
done
