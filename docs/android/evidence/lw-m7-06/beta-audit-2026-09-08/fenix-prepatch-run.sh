#!/usr/bin/env bash
# Run from the repository root. Uses the candidate's existing Gecko objdir.
set -uo pipefail
evidence=docs/android/evidence/lw-m7-06/beta-audit-2026-09-08
source_dir=$(realpath librewolf-153.0esr-1)
output_dir=$(realpath librewolf-android-apk-153.0esr-1-unsigned)
results="$source_dir/obj-x86_64/gradle/build/mobile/android/fenix/app/test-results/testDebugUnitTest"
container_name=lw-beta-fenix-20260908
date -u +'%Y-%m-%dT%H:%M:%SZ' > "$evidence/fenix-started.txt"
{
    git rev-parse HEAD
    git status --short
    podman image inspect librewolf-android-build --format '{{.Id}}'
    cat "$source_dir/obj-x86_64/buildid.h"
    sha256sum "$source_dir/obj-x86_64/config.status" "$output_dir/mozconfig.x86_64" docs/android/fenix-test-allowlist.yaml docs/android/board.py
    sha256sum "$output_dir"/apk/*-release-unsigned.apk
} > "$evidence/fenix-provenance-before.txt"
python3 - "$source_dir" "$evidence/fenix-source-sha256.json.gz" <<'PY'
import gzip, hashlib, json, pathlib, sys
source = pathlib.Path(sys.argv[1])
paths = list((source / 'mobile/android/fenix').rglob('*'))
paths += list((source / 'mobile/android/android-components').rglob('*'))
paths += list((source / 'mobile/android/gradle').rglob('*'))
paths += [source / p for p in ['build.gradle', 'settings.gradle', 'gradle.properties']]
manifest = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(set(paths)) if p.is_file() and '.gradle' not in p.relative_to(source).parts}
with gzip.GzipFile(sys.argv[2], 'wb', mtime=0) as out:
    out.write((json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode())
print(f'Captured {len(manifest)} source-file hashes')
PY
podman run --rm --name "$container_name" \
    -v "$source_dir:/work/src:z" \
    -v "$output_dir:/work/out:z" \
    -v "$output_dir/mozbuild-srcdirs:/root/.mozbuild/srcdirs:z" \
    -w /work/src \
    -e MOZCONFIG=/work/out/mozconfig.x86_64 \
    -e MOZ_BUILD_DATE=20260906190000 \
    -e GRADLE_USER_HOME=/work/out/gradle-home \
    -e MOZ_ANDROID_FAT_AAR_ARCHITECTURES=armeabi-v7a,arm64-v8a,x86_64 \
    -e MOZ_ANDROID_FAT_AAR_ARMEABI_V7A=/work/out/input/armeabi-v7a/target.maven.zip \
    -e MOZ_ANDROID_FAT_AAR_ARM64_V8A=/work/out/input/arm64-v8a/target.maven.zip \
    -e MOZ_ANDROID_FAT_AAR_X86_64=/work/out/input/x86_64/target.maven.zip \
    librewolf-android-build \
    bash -c 'test -x /root/.mozbuild/srcdirs/src-1507bbc88e3b/_virtualenvs/build/bin/python && ./mach gradle fenix:testDebugUnitTest --no-daemon' \
    > "$evidence/fenix-unit-tests.log" 2>&1
gradle_rc=$?
printf 'fenix:testDebugUnitTest exit=%s\n' "$gradle_rc" > "$evidence/fenix-exit-status.txt"
python3 docs/android/board.py --check-fenix-tests --results "$results" > "$evidence/fenix-gate.txt" 2>&1
gate_rc=$?
printf 'board.py --check-fenix-tests exit=%s\n' "$gate_rc" >> "$evidence/fenix-exit-status.txt"
if [ -d "$results" ]; then
    python3 - "$results" "$evidence/fenix-junit-xml.tar.gz" <<'PY'
import gzip, pathlib, sys, tarfile
results = pathlib.Path(sys.argv[1])
with gzip.GzipFile(sys.argv[2], 'wb', mtime=0) as out:
    with tarfile.open(fileobj=out, mode='w') as archive:
        for result in sorted(results.glob('*.xml')):
            archive.add(result, arcname=result.name)
PY
fi
{
    date -u +'%Y-%m-%dT%H:%M:%SZ'
    sha256sum "$output_dir"/apk/*-release-unsigned.apk
    sha256sum "$evidence"/fenix-source-sha256.json.gz "$evidence"/fenix-junit-xml.tar.gz "$evidence"/fenix-unit-tests.log
} > "$evidence/fenix-provenance-after.txt"
cat "$evidence/fenix-exit-status.txt" "$evidence/fenix-gate.txt"
exit "$gate_rc"
