# Feature-parity VM build workspace

Prepared 2026-09-08 at `/home/runner/work/feature-parity-20260908` inside the
existing isolated VM. This is a disposable task workspace outside the Actions
checkout. The host runner remains masked/inactive; GitHub runner 22 was online
and idle at preparation start. No candidate compilation or AVD boot was performed.

The transfer completed in session `54688`; the successful prerequisite check
completed in session `26884`. All six compressed streams were SHA-256 verified
in the guest before extraction. Their temporary compressed archives were then
removed. Exact commands, hashes, durations and file inventories are retained in
`prepare-workspace.py`, `preparation.log`, `transfers.json` and `*.files.txt.gz`.
The script intentionally refuses an existing task workspace; do not rerun it to
update this workspace.

| Guest path relative to workspace | Prepared input |
|---|---|
| `repo/` | Public tracked working-tree snapshot at the HEAD in `repository-head.txt`; no `.git` credentials. New untracked task files require a later explicit transfer. |
| `src/` | Beta source plus x86_64 native object directory, about 22 GiB. Prior `obj-x86_64/gradle` output and `.gradle` directories excluded. |
| `aar/` | Three per-ABI Maven ZIPs and their build-date record, 269 MiB. No stale merged AARs, signing bundles or APKs copied. |
| `out/` | Matching mozconfig, 48 MiB configured Python state, all three copied Maven inputs, and selected Gradle dependencies. |
| `out/gradle-home/` | Only `caches/modules-2` and wrapper distributions; no user Gradle properties, init scripts, daemon state or credential files. Distribution `init.d` and lock files excluded. |
| `sdk/` | Emulator 37.1.11, platform-tools and the API 30 AOSP/default x86_64 image, about 4 GiB. No host `dot-android`, ADB identities or preexisting AVD copied. |

Firefox's public source includes upstream NSS certificate/test-key fixtures and
Chromium's public debug test keystore. These are source fixtures, not host signing
identities. No release key, signing passphrase, host administrative key file,
GitHub credentials, host home share or container store was transferred.

`workspace-checks.txt` records successful nested KVM acceleration, container JDK
17.0.18, the configured Glean Python executable at its original container path,
and the Android APK driver's three-ABI `--dry-run --skip-gecko` preflight. The
guest initially lacked `libxkbfile`; the only package addition was
`sudo dnf install -y libxkbfile` (202 KiB installed), recorded with the initial
failure. Bare `ldd` on the QEMU sub-binaries misses bundled libraries that the
emulator launcher supplies; the actual launcher/acceleration check passes.

Host free space was 828 GiB before transfer. Guest free space is 362 GiB after
preparation, with 22 GiB available RAM and essentially unused swap. The VM still
has eight vCPUs and 24 GiB RAM. Run compilation, the full unit suite and emulator
smoke sequentially. The earlier host R8 build peaked at 23.30 GB; VM full-build
memory/time and an actual nested Android boot remain unverified.

## Update only the task's public source

These are handoff recipes, not commands executed by this readiness audit. Root
must supply the new task source before a candidate build. The transferred native
inputs use build date `20260906190000`; `input-provenance.json` records their exact
hashes. Reuse them only while native/resource inputs remain compatible. A changed
Gecko patch set, engine-packaged policy/resource, toolchain or build date requires
fresh matching native AARs; a Kotlin-only change can use the warm native objects.

To update an explicitly selected public patched source tree while preserving the
guest's native objects, run from the host repository with `NEW_PATCHED_TREE` set
to that source tree, never a home or credential directory:

```sh
vm_control="$HOME/.local/state/redoubt-ci-vm-control"
rsync -a --delete --exclude='/obj-*' --exclude='.git' --exclude='.gradle' \
  --rsync-path='sudo -iu runner rsync' \
  -e "ssh -F /dev/null -i $vm_control/admin_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$vm_control/known_hosts -o ForwardAgent=no -o ClearAllForwardings=yes -p 2222" \
  "$NEW_PATCHED_TREE/" \
  ciadmin@127.0.0.1:/home/runner/work/feature-parity-20260908/src/
```

Update the guest repository scripts/patches from an explicit tracked-file list
as in `prepare-workspace.py`; include the new task's public files explicitly if
they are not tracked yet. Do not copy `.git`, the entire host checkout with build
outputs, or any host Gradle/SDK user configuration. Keep source manifests and
patch hashes with the eventual build/test evidence.

## Compile and test after the new source arrives

Enter the runner account through the established channel; a plain
`sudo -u runner -H` can retain inaccessible `/home/ciadmin` as its current directory:

```sh
./scripts/ci-vm/ssh.sh 'sudo -iu runner env XDG_RUNTIME_DIR=/run/user/1001 bash'
```

Inside that guest shell, the following builds all four development APKs with R8
using a debug signing identity inside the guest. Add `--disable-debug-signing`
when preparing unsigned artifacts for a separate signing step; unsigned APKs
cannot be installed for smoke testing.

```sh
set -euo pipefail
work=/home/runner/work/feature-parity-20260908
cd "$work/repo"
./scripts/android-apk.sh --srcdir "$work/src" --aar-dir "$work/aar" \
  --outdir "$work/out" --engine podman --variant release --jobs 8 \
  --build-date 20260906190000 --skip-gecko \
  2>&1 | tee "$work/evidence/apk-build.log"
```

The full Fenix suite must run in the same container path layout. No test filter
is used. Gradle's exit status is preserved separately because documented failures
are subtracted by the board's XML gate, not by interpreting console counts:

```sh
set +e
podman run --rm --name parity-fenix-unit \
  -v "$work/src:/work/src:z" -v "$work/out:/work/out:z" \
  -v "$work/out/mozbuild-srcdirs:/root/.mozbuild/srcdirs:z" -w /work/src \
  -e MOZCONFIG=/work/out/mozconfig.x86_64 -e MOZ_BUILD_DATE=20260906190000 \
  -e GRADLE_USER_HOME=/work/out/gradle-home \
  -e MOZ_ANDROID_FAT_AAR_ARCHITECTURES=armeabi-v7a,arm64-v8a,x86_64 \
  -e MOZ_ANDROID_FAT_AAR_ARMEABI_V7A=/work/out/input/armeabi-v7a/target.maven.zip \
  -e MOZ_ANDROID_FAT_AAR_ARM64_V8A=/work/out/input/arm64-v8a/target.maven.zip \
  -e MOZ_ANDROID_FAT_AAR_X86_64=/work/out/input/x86_64/target.maven.zip \
  librewolf-android-build bash -c \
  './mach gradle fenix:testDebugUnitTest --no-daemon --max-workers=4 -PgleanBuildDate=2026-09-06T19:00:00' \
  > "$work/evidence/fenix-unit.log" 2>&1
gradle_rc=$?
results="$work/src/obj-x86_64/gradle/build/mobile/android/fenix/app/test-results/testDebugUnitTest"
python3 docs/android/board.py --check-fenix-tests --results "$results" \
  > "$work/evidence/fenix-gate.txt" 2>&1
gate_rc=$?
printf 'Gradle=%s\nboard=%s\n' "$gradle_rc" "$gate_rc" > "$work/evidence/fenix-status.txt"
tar --sort=name -C "$results" -cf - . | gzip -n > "$work/evidence/fenix-junit-xml.tar.gz"
gzip -n "$work/evidence/fenix-unit.log"
cat "$work/evidence/fenix-status.txt" "$work/evidence/fenix-gate.txt"
test "$gate_rc" -eq 0
```

Then run the emulator and origin server inside the VM. Here the emulator's
`10.0.2.2` refers to the VM loopback, not the physical host:

```sh
LW_SMOKE_DNS=9.9.9.9 ./scripts/android-smoke.sh --emulator \
  --sdk "$work/sdk" --apk "$work/out/apk/fenix-x86_64-release.apk" \
  --work "$work/smoke" --json "$work/evidence/baseline-smoke.json" \
  > "$work/evidence/baseline-smoke.out" 2>&1
```

The harness creates a fresh task AVD and normally stops it afterwards. Its
baseline does not prove uBlock Origin installation/filtering or other newly
implemented parity features; those need the task's explicit runtime checks.

Fetch only public results/APKs through SSH into a fresh host artifact directory:

```sh
results_dir="$HOME/redoubt-artifacts/feature-parity-20260908-results"
mkdir -p "$results_dir"
./scripts/ci-vm/ssh.sh 'sudo -iu runner tar -C /home/runner/work/feature-parity-20260908 -cf - evidence out/apk' \
  | tar -C "$results_dir" -xf -
```

Check GitHub runner 22's `busy` field before starting heavy manual work. The
task workspace does not share the Actions checkout or its caches, and none of
these operations requires re-enabling the host runner or exposing host paths.
