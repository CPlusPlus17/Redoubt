#!/usr/bin/env bash
# Development signing happens inside the guest with its disposable debug key.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
work=/home/runner/work/feature-parity-20260908
evidence="$work/evidence/parity-feature-apk"
mkdir -p "$evidence"
cd "$work/repo"
date -u --iso-8601=seconds > "$evidence/started.txt"
cat /proc/sys/kernel/random/boot_id > "$evidence/boot-id.txt"
free -b > "$evidence/memory-before.txt"
chmod 700 docs/android/evidence/lw-m7-15/podman-bounded.sh
set +e
./scripts/android-apk.sh --srcdir "$work/src" --aar-dir "$work/aar" \
  --outdir "$work/out" --engine "$work/repo/docs/android/evidence/lw-m7-15/podman-bounded.sh" \
  --variant release --jobs 4 --build-date 20260906190000 --skip-gecko \
  > "$evidence/apk-build.log" 2>&1
build_rc=$?
printf '%s\n' "$build_rc" > "$evidence/build-exit.txt"
date -u --iso-8601=seconds > "$evidence/finished.txt"
free -b > "$evidence/memory-after.txt"
tail -50 "$evidence/apk-build.log"
exit "$build_rc"
