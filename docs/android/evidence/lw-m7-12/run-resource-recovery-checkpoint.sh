#!/usr/bin/env bash
# Finish resource verification of the compiled APKs, then run tests and runtime.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
work=/home/runner/work/feature-parity-20260908
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
cd "$work/repo"
evidence="$work/evidence/apk-resource-recovery-checkpoint"
mkdir "$evidence"
date -u --iso-8601=seconds > "$evidence/started.txt"
trap 'date -u --iso-8601=seconds > "$evidence/finished.txt"' EXIT
for stage in resources tests runtime; do
  set +e
  case "$stage" in
    resources) python3 docs/android/evidence/lw-m7-21/finalize-apk-resources.py > "$evidence/$stage.log" 2>&1 ;;
    tests) bash docs/android/evidence/lw-m7-12/run-extended-tests.sh > "$evidence/$stage.log" 2>&1 ;;
    runtime) bash docs/android/evidence/lw-m7-12/run-candidate-smoke.sh > "$evidence/$stage.log" 2>&1 ;;
  esac
  result=$?
  set -e
  printf '%s\n' "$result" > "$evidence/$stage-exit.txt"
  [[ "$result" == 0 ]]
done
