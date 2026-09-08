#!/usr/bin/env bash
# Build development-signed APKs only after the matching native source passed.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
work=/home/runner/work/feature-parity-20260908
native="$work/evidence/parity-extended-native"
evidence="$work/evidence/parity-extended-apk"
[[ $(cat "$native/build-exit.txt") == 0 ]]
[[ -s "$native/finished.txt" && -s "$native/source-sha256.txt" ]]
if [[ -d "$evidence" ]]; then
  mv "$evidence" "$evidence-previous-$(date -u +%Y%m%dT%H%M%S)-$$"
fi
mkdir -p "$evidence"
cp "$native/source-sha256.txt" "$evidence/source-sha256.txt"
cd "$work/src"
sha256sum -c "$evidence/source-sha256.txt" > "$evidence/source-before.txt"
cd "$work/repo"
date -u --iso-8601=seconds > "$evidence/started.txt"
cat /proc/sys/kernel/random/boot_id > "$evidence/boot-id.txt"
free -b > "$evidence/memory-before.txt"
sha256sum scripts/android-apk.sh assets/mozconfig.android \
  docs/android/evidence/lw-m7-15/podman-bounded.sh > "$evidence/driver-sha256.txt"
sha256sum "$work/aar/armeabi-v7a/target.maven.zip" \
  "$work/aar/arm64-v8a/target.maven.zip" "$work/aar/x86_64/target.maven.zip" \
  > "$evidence/native-input-sha256.txt"
set +e
./scripts/android-apk.sh --srcdir "$work/src" --aar-dir "$work/aar" \
  --outdir "$work/out" --engine "$work/repo/docs/android/evidence/lw-m7-15/podman-bounded.sh" \
  --variant release --jobs 4 --build-date 20260906190000 --skip-gecko \
  > "$evidence/apk-build.log" 2>&1
build_rc=$?
printf '%s\n' "$build_rc" > "$evidence/build-exit.txt"
set -e
cd "$work/src"
sha256sum -c "$evidence/source-sha256.txt" > "$evidence/source-after.txt"
if [[ "$build_rc" == 0 ]]; then
  cd "$work/out/apk"
  sha256sum fenix-*-release.apk > "$evidence/SHA256SUMS.development"
fi
date -u --iso-8601=seconds > "$evidence/finished.txt"
free -b > "$evidence/memory-after.txt"
tail -45 "$evidence/apk-build.log"
exit "$build_rc"
