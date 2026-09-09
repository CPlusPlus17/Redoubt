#!/usr/bin/env bash
# Preserve the failed collection, rebuild only x86 publication, then real merge.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
work=/home/runner/work/feature-parity-20260908
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
cd "$work/repo"
[[ -z $(podman --remote=false ps --format '{{.Names}}') ]]
native="$work/evidence/parity-extended-native"
parent="$work/evidence/native4-before-packaging-recovery"
[[ $(cat "$native/build-exit.txt") == 1 && -s "$native/finished.txt" && ! -e "$parent" ]]
sha256sum -c docs/android/evidence/lw-m7-21/native4-packaging-failure/recovery-inputs.sha256
cd "$work/src"
sha256sum -c "$native/source-sha256.txt" > /dev/null
cd "$work/repo"
mv "$native" "$parent"
mkdir "$native"
cp "$parent/source-sha256.txt" "$native/source-sha256.txt"
cp docs/android/evidence/lw-m7-21/native4-packaging-failure/result.json "$native/compilation-parent.json"
date -u --iso-8601=seconds > "$native/started.txt"
cat /proc/sys/kernel/random/boot_id > "$native/boot-id.txt"
free -b > "$native/memory-before.txt"
sha256sum scripts/android-fat-aar.sh assets/mozconfig.android \
  docs/android/evidence/lw-m7-25/podman-native-bounded.sh \
  docs/android/evidence/lw-m7-21/run-native4-packaging-recovery.sh > "$native/driver-sha256.txt"
cd "$work/src"
sha256sum -c "$native/source-sha256.txt" > "$native/source-before.txt"
cd "$work/repo"
[[ ! -e "$work/aar/x86_64/target.maven.native4-mixed.zip" ]]
mv "$work/aar/x86_64/target.maven.zip" "$work/aar/x86_64/target.maven.native4-mixed.zip"
set +e
./scripts/android-fat-aar.sh --srcdir "$work/src" --outdir "$work/aar" \
  --engine "$work/repo/docs/android/evidence/lw-m7-25/podman-native-bounded.sh" \
  --abis armeabi-v7a,arm64-v8a,x86_64 --fat-host-abi x86_64 \
  --jobs 4 --build-date 20260906190000 --skip-existing > "$native/native-build.log" 2>&1
result=$?
printf '%s\n' "$result" > "$native/build-exit.txt"
set -e
cd "$work/src"
sha256sum -c "$native/source-sha256.txt" > "$native/source-after.txt"
date -u --iso-8601=seconds > "$native/finished.txt"
free -b > "$native/memory-after.txt"
tail -35 "$native/native-build.log"
exit "$result"
