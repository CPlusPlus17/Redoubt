#!/usr/bin/env bash
# Run after the controlled reboot, before native logs can be overwritten.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
work=/home/runner/work/feature-parity-20260908
evidence="$work/evidence/native-memory-adjustment"
mkdir "$evidence"
cp -a "$work/evidence/parity-extended-native" "$evidence/native-attempt-2"
cp -a "$work/aar/logs/armeabi-v7a.log" "$evidence/armeabi-v7a.log"
cp "$work/evidence/translation-cancellation-fix/source-sha256.txt" "$evidence/source-sha256.txt"
cd "$work/src"
sha256sum -c "$evidence/source-sha256.txt" > "$evidence/source-after-reboot.txt"
cat /proc/sys/kernel/random/boot_id > "$evidence/new-boot-id.txt"
free -b > "$evidence/memory-after-reboot.txt"
podman ps --format json > "$evidence/active-containers.json"
[[ $(podman ps -q | wc -l) == 0 ]]
journalctl --no-pager _SYSTEMD_USER_UNIT=redoubt-parity-native2-20260909.service \
  > "$evidence/native-service-journal.txt"
printf '%s\n' 'INTERRUPTED: controlled VM shutdown after measured native-build memory pressure; no all-ABI success.' \
  > "$evidence/classification.txt"
date -u --iso-8601=seconds > "$evidence/captured.txt"
cd "$work/evidence"
tar -czf native-memory-adjustment.tar.gz native-memory-adjustment
sha256sum native-memory-adjustment.tar.gz
