#!/usr/bin/env python3
"""Transfer explicitly selected public build inputs into a new isolated guest workspace.

No build is started. The existing VM SSH administrative channel is the only
transport. Host source/APKs are read-only inputs. Never transfer a home directory,
container store, .git credentials, SDK dot-android identity, or Gradle user config.
The Firefox source includes upstream public certificate/test-key fixtures.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time

REPO = Path(__file__).resolve().parents[5]
EVIDENCE = Path(__file__).resolve().parent
SSH = REPO / 'scripts/ci-vm/ssh.sh'
WORK = '/home/runner/work/feature-parity-20260908'
SOURCE = REPO / 'librewolf-153.0esr-1-beta-20260908'
OUTPUT = REPO / 'librewolf-android-apk-153.0esr-1-beta-20260908'
SDK = Path.home() / 'redoubt-artifacts/android-sdk'
ABIS = ['armeabi-v7a', 'arm64-v8a', 'x86_64']
logfile = EVIDENCE / 'preparation.log'
records = []


def log(message):
    line = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) + ' ' + message
    print(line, flush=True)
    with logfile.open('a') as stream:
        stream.write(line + '\n')


def guest(command, **kwargs):
    remote = shlex.join(['sudo', '-iu', 'runner', 'env',
                        'XDG_RUNTIME_DIR=/run/user/1001', 'bash', '-c', command])
    return subprocess.run([str(SSH), remote], check=True, **kwargs)


def transfer(label, base, members, destination, excludes=(), filelist=None):
    archive = WORK + '/incoming/' + label + '.tar.zst'
    tar = ['tar', '--sort=name', '--sparse', '--no-acls', '--no-xattrs',
           '-C', str(base), '-cf', '-']
    tar += ['--exclude=' + pattern for pattern in excludes]
    if filelist:
        tar += ['--null', '--verbatim-files-from', '--no-recursion',
                '--files-from=' + str(filelist)]
    else:
        tar += list(members)
    remote = shlex.join(['sudo', '-iu', 'runner', 'bash', '-c',
                        'cat > ' + shlex.quote(archive)])
    command = [str(SSH), remote]
    record = {'label': label, 'base': str(base), 'members': list(members),
              'excludes': list(excludes), 'destination': destination,
              'tar_command': tar, 'compress_command': ['zstd', '-T2', '-3', '-q'],
              'transport_command': command,
              'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    log('START ' + label)
    started = time.monotonic()
    total = 0
    digest = hashlib.sha256()
    with (EVIDENCE / (label + '.stderr.txt')).open('wb') as errors:
        producer = subprocess.Popen(tar, stdout=subprocess.PIPE, stderr=errors)
        compressor = subprocess.Popen(['zstd', '-T2', '-3', '-q'],
                                      stdin=producer.stdout, stdout=subprocess.PIPE,
                                      stderr=errors)
        producer.stdout.close()
        transport = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=errors)
        updated = time.monotonic()
        try:
            while block := compressor.stdout.read(1024 * 1024):
                digest.update(block)
                transport.stdin.write(block)
                total += len(block)
                if time.monotonic() - updated > 25:
                    log(f'{label}: {total / 1024**3:.2f} GiB compressed transferred')
                    updated = time.monotonic()
            transport.stdin.close()
            statuses = [producer.wait(), compressor.wait(), transport.wait()]
            if statuses != [0, 0, 0]:
                raise RuntimeError(f'{label}: tar/zstd/SSH statuses {statuses}')
        except BaseException:
            for process in (producer, compressor, transport):
                if process.poll() is None:
                    process.terminate()
            for process in (producer, compressor, transport):
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            raise
    received = guest('sha256sum ' + shlex.quote(archive), capture_output=True,
                     text=True).stdout.split()[0]
    assert received == digest.hexdigest(), (label, received, digest.hexdigest())
    inventory = WORK + '/incoming/' + label + '.files.txt.gz'
    guest('set -euo pipefail; mkdir -p ' + shlex.quote(destination) +
          '; tar --zstd -tf ' + shlex.quote(archive) + ' | gzip -n > ' +
          shlex.quote(inventory) + '; tar --zstd --no-same-owner -xf ' +
          shlex.quote(archive) + ' -C ' + shlex.quote(destination))
    with (EVIDENCE / (label + '.files.txt.gz')).open('wb') as target:
        guest('cat ' + shlex.quote(inventory), stdout=target)
    guest('rm -- ' + shlex.quote(archive))
    record.update(sha256=received, compressed_bytes=total,
                  seconds=round(time.monotonic() - started, 2), verified=True,
                  guest_compressed_archive_removed=True)
    records.append(record)
    (EVIDENCE / 'transfers.json').write_text(json.dumps(records, indent=2) + '\n')
    log(f'PASS {label}: sha256={received}, bytes={total}, seconds={record["seconds"]}')


assert SOURCE.is_dir() and OUTPUT.is_dir() and SDK.is_dir()
assert os.statvfs(REPO).f_bavail * os.statvfs(REPO).f_frsize > 80 * 1024**3
preflight = subprocess.run(
    ['gh', 'api', 'repos/CPlusPlus17/Redoubt/actions/runners', '--jq',
     '.runners[]|{id,name,status,busy}'], check=True, capture_output=True, text=True)
(EVIDENCE / 'runner-before.json').write_text(preflight.stdout)
runner = json.loads(preflight.stdout)
assert runner['id'] == 22 and runner['status'] == 'online' and not runner['busy']
guest('set -e; test ! -e ' + shlex.quote(WORK) +
      '; test "$(df -BG --output=avail /home | tail -1 | tr -dc 0-9)" -ge 100')
guest('mkdir -p ' + shlex.quote(WORK + '/incoming') + ' ' + shlex.quote(WORK + '/evidence'))

tracked = subprocess.run(['git', 'ls-files', '--recurse-submodules', '-z'],
                         cwd=REPO, check=True, capture_output=True).stdout
filelist = EVIDENCE / 'repository-input-files.nul'
filelist.write_bytes(tracked)
(EVIDENCE / 'repository-input-files.txt').write_text(tracked.decode().replace('\0', '\n'))
(EVIDENCE / 'repository-head.txt').write_text(subprocess.run(
    ['git', 'rev-parse', 'HEAD'], cwd=REPO, check=True, capture_output=True,
    text=True).stdout)
transfer('repository', REPO, [], WORK + '/repo', filelist=filelist)
filelist.unlink()
transfer('source-native-obj', SOURCE, ['.'], WORK + '/src',
         excludes=('./obj-x86_64/gradle', '*/.gradle'))
transfer('native-aar-inputs', REPO / 'librewolf-android-aar-153.0esr-1',
         ['build-times.txt'] + [abi + '/target.maven.zip' for abi in ABIS], WORK + '/aar')
transfer('compiler-state', OUTPUT, ['mozconfig.x86_64', 'mozbuild-srcdirs'], WORK + '/out')
transfer('gradle-dependencies', OUTPUT / 'gradle-home',
         ['caches/modules-2', 'wrapper/dists'], WORK + '/out/gradle-home',
         excludes=('*/init.d', '*.lock', '*.lck'))
transfer('emulator-sdk', SDK,
         ['emulator', 'platform-tools', 'system-images/android-30/default/x86_64'], WORK + '/sdk')
guest('set -e; ' + '; '.join(
    'mkdir -p ' + shlex.quote(WORK + '/out/input/' + abi) +
    '; cp ' + shlex.quote(WORK + '/aar/' + abi + '/target.maven.zip') + ' ' +
    shlex.quote(WORK + '/out/input/' + abi + '/target.maven.zip') for abi in ABIS))
log('TRANSFER PREPARATION COMPLETE. No candidate build or emulator boot started.')
