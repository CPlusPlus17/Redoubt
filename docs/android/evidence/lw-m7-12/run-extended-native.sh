#!/usr/bin/env bash
# Rebuild all native ABIs after graphics C++ and integrated asset changes.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
work=/home/runner/work/feature-parity-20260908
source_manifest=${REDOUBT_SOURCE_MANIFEST:-$work/evidence/extended-source/source-sha256.txt}
evidence="$work/evidence/parity-extended-native"
if [[ -d "$evidence" ]]; then
  mv "$evidence" "$evidence-previous-$(date -u +%Y%m%dT%H%M%S)-$$"
fi
mkdir -p "$evidence"
cp "$source_manifest" "$evidence/source-sha256.txt"
cd "$work/src"
sha256sum -c "$evidence/source-sha256.txt" > "$evidence/source-before.txt"
cd "$work/repo"
date -u --iso-8601=seconds > "$evidence/started.txt"
cat /proc/sys/kernel/random/boot_id > "$evidence/boot-id.txt"
free -b > "$evidence/memory-before.txt"
sha256sum scripts/android-fat-aar.sh assets/mozconfig.android \
  docs/android/evidence/lw-m7-15/podman-bounded.sh > "$evidence/driver-sha256.txt"
set +e
./scripts/android-fat-aar.sh --srcdir "$work/src" --outdir "$work/aar" \
  --engine "$work/repo/docs/android/evidence/lw-m7-15/podman-bounded.sh" \
  --abis armeabi-v7a,arm64-v8a,x86_64 --fat-host-abi x86_64 \
  --jobs 4 --build-date 20260906190000 > "$evidence/native-build.log" 2>&1
build_rc=$?
printf '%s\n' "$build_rc" > "$evidence/build-exit.txt"
set -e
cd "$work/src"
sha256sum -c "$evidence/source-sha256.txt" > "$evidence/source-after.txt"
date -u --iso-8601=seconds > "$evidence/finished.txt"
free -b > "$evidence/memory-after.txt"
tail -45 "$evidence/native-build.log"
exit "$build_rc"
