#!/usr/bin/env bash
# Run inside the guest as runner. Inspects setup; no candidate compile or AVD boot.
set -euo pipefail
work=/home/runner/work/feature-parity-20260908
cd "$work/repo"
date -u +%FT%TZ
id
free -h
df -h "$work"
du -sh "$work"/{repo,src,aar,out,sdk}
test ! -e "$work/src/obj-x86_64/gradle"
test ! -e "$work/out/gradle-home/gradle.properties"
test ! -e "$work/out/gradle-home/init.d"
test ! -e "$work/sdk/dot-android"
test ! -e "$work/sdk/.android"
echo 'PASS prior Gradle results and user-specific Gradle/SDK identities absent'
podman image inspect librewolf-android-build --format '{{.Id}}'
sha256sum "$work/src/obj-x86_64/config.status" "$work/src/obj-x86_64/buildid.h" \
  "$work/out/mozconfig.x86_64" "$work/aar"/*/target.maven.zip
"$work/sdk/emulator/emulator" -version
"$work/sdk/emulator/emulator" -accel-check
echo 'PASS emulator launcher and nested KVM acceleration checks'
podman run --rm --name redoubt-parity-prerequisites \
  -v "$work/src:/work/src:z" -v "$work/out:/work/out:z" \
  -v "$work/out/mozbuild-srcdirs:/root/.mozbuild/srcdirs:z" \
  -w /work/src librewolf-android-build bash -euc '
    java -version
    test -x /root/.mozbuild/srcdirs/src-1507bbc88e3b/_virtualenvs/build/bin/python
    /root/.mozbuild/srcdirs/src-1507bbc88e3b/_virtualenvs/build/bin/python -c "import sys; print(sys.executable)"
    test -f /work/src/obj-x86_64/config.status
    test -f /work/out/input/arm64-v8a/target.maven.zip
    test -f /work/out/input/armeabi-v7a/target.maven.zip
    test -f /work/out/input/x86_64/target.maven.zip
    echo "PASS /work/src, /work/out and configured Glean virtualenv portability"
  '
./scripts/android-apk.sh --srcdir "$work/src" --aar-dir "$work/aar" \
  --outdir "$work/out" --engine podman --variant release --jobs 8 \
  --build-date 20260906190000 --skip-gecko --dry-run
echo 'PASS candidate driver preflight only; no candidate build started'
