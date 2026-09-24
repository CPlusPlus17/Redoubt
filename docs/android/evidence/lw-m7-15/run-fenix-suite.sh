#!/usr/bin/env bash
# Run only as runner inside the isolated guest, from a transient user service.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
work=/home/runner/work/feature-parity-20260908
evidence="$work/evidence/parity-third-combined"
mkdir -p "$evidence"
date -u --iso-8601=seconds > "$evidence/started.txt"
cat /proc/sys/kernel/random/boot_id > "$evidence/boot-id.txt"
free -b > "$evidence/memory-before.txt"
cd "$work/repo"
set +e
podman run --rm --name parity-fenix-suite \
  --memory=14g --memory-swap=22g --cpus=6 \
  -v "$work/src:/work/src:z" -v "$work/out:/work/out:z" \
  -v "$work/out/mozbuild-srcdirs:/root/.mozbuild/srcdirs:z" -w /work/src \
  -e MOZCONFIG=/work/out/mozconfig.x86_64 -e MOZ_BUILD_DATE=20260906190000 \
  -e GRADLE_USER_HOME=/work/out/gradle-home \
  -e MOZ_ANDROID_FAT_AAR_ARCHITECTURES=armeabi-v7a,arm64-v8a,x86_64 \
  -e MOZ_ANDROID_FAT_AAR_ARMEABI_V7A=/work/out/input/armeabi-v7a/target.maven.zip \
  -e MOZ_ANDROID_FAT_AAR_ARM64_V8A=/work/out/input/arm64-v8a/target.maven.zip \
  -e MOZ_ANDROID_FAT_AAR_X86_64=/work/out/input/x86_64/target.maven.zip \
  librewolf-android-build bash -c '
    ./mach gradle fenix:testDebugUnitTest components:support-webextensions:testDebugUnitTest --continue --no-daemon --max-workers=4 -PgleanBuildDate=2026-09-06T19:00:00
    task_rc=$?
    cat /sys/fs/cgroup/memory.peak > /work/out/fenix-memory.peak
    cat /sys/fs/cgroup/memory.events > /work/out/fenix-memory.events
    exit "$task_rc"
  ' > "$evidence/fenix-and-webextensions-tests.log" 2>&1
gradle_rc=$?
printf '%s\n' "$gradle_rc" > "$evidence/gradle-exit.txt"
results="$work/src/obj-x86_64/gradle/build/mobile/android/fenix/app/test-results/testDebugUnitTest"
python3 docs/android/board.py --check-fenix-tests --results "$results" > "$evidence/fenix-gate.txt" 2>&1
gate_rc=$?
printf '%s\n' "$gate_rc" > "$evidence/gate-exit.txt"
if [[ -d "$results" ]]; then
  (
    cd "$results"
    tar --sort=name -czf "$evidence/fenix-junit-xml.tar.gz" TEST-*.xml
  )
fi
cp "$work/out/fenix-memory.peak" "$work/out/fenix-memory.events" "$evidence/" 2>/dev/null
free -b > "$evidence/memory-after.txt"
date -u --iso-8601=seconds > "$evidence/finished.txt"
cat "$evidence/fenix-gate.txt"
exit "$gate_rc"
