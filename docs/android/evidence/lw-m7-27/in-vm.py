#!/usr/bin/env python3
"""Guest-only bounded Podman wrapper; --preflight-only performs read-only checks."""
import argparse
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import subprocess
import sys
import uuid

import driver
from grade import InvalidResult, require


def excluded_source_entry(path):
    return path.name in {'.git', '.hg', '.gradle'} or (path.is_dir() and path.name.startswith('obj-'))


def private_source_paths(workspace):
    return (workspace.with_name(workspace.name + '-source'),
            workspace.with_name(workspace.name + '-source-copy.json'))


def prepare_source_copy(source, copied, receipt_path, manifest, binding):
    """Copy source bytes, never production objdirs, hardlinks or external links."""
    require(not copied.exists() and not receipt_path.exists(), 'private source already exists; preserve it and choose a new workspace')
    entries = sorted(source.iterdir())
    omitted = [p.name for p in entries if excluded_source_entry(p)]
    require(not any(name.split('/')[0] in omitted for name in binding['product_files']),
            'reviewed source inventory includes an excluded cache/object directory')
    # Dereference input symlinks only after proving they remain inside source.
    # This avoids writable copied links pointing back into the product tree.
    for entry in entries:
        if entry.name in omitted:
            continue
        paths = [entry]
        if entry.is_dir() and not entry.is_symlink():
            paths += [Path(root) / name for root, dirs, files in os.walk(entry, followlinks=False)
                      for name in dirs + files]
        for path in paths:
            if path.is_symlink():
                require(path.resolve().is_relative_to(source), 'source symlink escapes product tree: ' + str(path))
                require(not path.is_dir(), 'source directory symlink needs an explicit copy review: ' + str(path))
    receipt = {'status': 'COPYING', 'production_source': str(source), 'private_source': str(copied),
               'source_manifest_sha256': binding['manifest_sha256'],
               'source_count': len(binding['product_files']), 'omitted_top_level_entries': omitted,
               'copy_command': ['cp', '-aL', '--reflink=auto'],
               'scope': 'Isolated source copy; generated files writable, reviewed source bytes must remain unchanged'}
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    try:
        copied.mkdir()
        for entry in entries:
            if entry.name not in omitted:
                subprocess.run(['cp', '-aL', '--reflink=auto', '--', str(entry), str(copied / entry.name)], check=True)
        require(driver.source_binding(source, manifest) == binding, 'production source changed during private copy')
        require(driver.source_binding(copied, manifest) == binding, 'private copy differs from reviewed source')
        receipt['status'] = 'PREPARED'
    except BaseException as error:
        receipt['status'] = 'FAIL'
        receipt['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def verify_source_copy(source, copied, receipt_path, manifest, binding):
    receipt = json.loads(receipt_path.read_text())
    require(receipt.get('status') == 'PREPARED' and receipt.get('production_source') == str(source)
            and receipt.get('private_source') == str(copied)
            and receipt.get('source_manifest_sha256') == binding['manifest_sha256']
            and receipt.get('source_count') == len(binding['product_files']), 'private source copy receipt differs')
    require(driver.source_binding(source, manifest) == binding, 'production source changed')
    require(driver.source_binding(copied, manifest) == binding, 'private source changed')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--preflight-only', action='store_true')
    wrapper, arguments = parser.parse_known_args()
    args = driver.parse_args(arguments)
    require(args.action in {'build','run'}, 'wrapper accepts explicit build/run action; use --preflight-only to inspect it')
    require(wrapper.preflight_only or args.execute, 'container mutations require --execute')
    require(driver.query(['systemd-detect-virt','--vm']).strip() == 'kvm', 'must run in the KVM CI guest')
    require(pwd.getpwuid(os.getuid()).pw_name == 'runner' and os.getuid() != 0, 'must run as the unprivileged guest runner')
    os.chdir(wrapper.repo.resolve())
    runtime = Path('/run/user') / str(os.getuid())
    require(runtime.is_dir() and runtime.stat().st_uid == os.getuid(), 'missing runner runtime directory')
    os.environ['XDG_RUNTIME_DIR'] = str(runtime)
    require(not Path('/home/mgysin').exists(), 'host home must be absent (stat only)')
    require(not os.environ.get('CONTAINER_HOST') and not os.environ.get('DOCKER_HOST'), 'remote container engines are not allowed')
    require(driver.query(['systemctl','is-active','redoubt-guest-firewall.service']).strip() == 'active', 'guest firewall unit not active')
    require(not any(line.split()[2] in {'9p','virtiofs'} for line in Path('/proc/mounts').read_text().splitlines()), 'host directory sharing is not allowed')
    memory = next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:'))
    require(memory >= 19 * 1024**3, 'guest allocation must provide at least 19 GiB usable RAM')
    podman = ['podman','--remote=false']
    info = json.loads(driver.query(podman+['info','--format','json']))
    require(info.get('host',{}).get('security',{}).get('rootless') is True, 'Podman is not rootless')
    running = driver.query(podman+['ps','--format','{{.Names}}']).strip()
    require(not running, 'another container is running; reserve the native build slot first')
    image = json.loads(driver.REQUIREMENTS.read_text())['build_image_sha256']
    inspected = json.loads(driver.query(podman+['image','inspect','sha256:'+image]))
    require(len(inspected)==1 and inspected[0]['Id'].removeprefix('sha256:')==image, 'pinned Android image not present')
    repo, source = wrapper.repo.resolve(), args.source.resolve()
    workspace = args.workspace.resolve()
    parent = workspace.parent
    require(str(parent).startswith('/home/runner/') and parent.name.startswith('native-tests-'), 'use a dedicated /home/runner/.../native-tests-* parent')
    require(not parent.is_relative_to(source) and not source.is_relative_to(parent) and not parent.is_relative_to(repo) and not repo.is_relative_to(parent), 'writable workspace parent must be separate from source and repository')
    require((repo/'docs/android/evidence/lw-m7-27/driver.py').read_bytes()==Path(driver.__file__).read_bytes(), 'wrapper repository and imported driver differ')
    manifest, config = args.source_manifest.resolve(), args.product_mozconfig.resolve()
    binding = driver.source_binding(source, manifest)
    copied, copy_receipt = private_source_paths(workspace)
    if args.action == 'build':
        require(not workspace.exists() and not copied.exists() and not copy_receipt.exists(),
                'build requires new workspace and private source paths')
    else:
        verify_source_copy(source, copied, copy_receipt, manifest, binding)
    driver.derive_config(config.read_text(), workspace/'obj-x86_64-tests')
    existing = parent
    while not existing.exists():existing=existing.parent
    free = shutil.disk_usage(existing).free
    require(free >= 100 * 1024**3, 'less than 100 GiB free for the separate native test build')
    name = 'redoubt-native-tests-'+uuid.uuid4().hex
    command=podman+['run','--rm','--name',name,'--pull=never','--memory=17g','--memory-swap=23g','--cpus=6',
                    '--pids-limit=2048','--cap-drop=all','--security-opt=no-new-privileges','--network=host',
                    '-e','REDOUBT_NATIVE_TEST_IMAGE='+image,'-e','ADB_SERVER_SOCKET=tcp:127.0.0.1:5037']
    # Preserve absolute paths used by the binding/receipts; no host home, credentials
    # or build-engine sockets are exposed. Network=host is the isolated VM network.
    mounts={repo:'ro',source:'ro',manifest:'ro',config:'ro',parent:'rw'}
    for path,mode in mounts.items():
        require(':' not in str(path) and '\n' not in str(path), 'unsafe mount path')
        command+=['-v',f'{path}:{path}:{mode},z']
    command+=['-w',str(copied),'sha256:'+image,'python3',str(repo/'docs/android/evidence/lw-m7-27/driver.py')]
    # Resolve path-valued options before entering the container's source cwd.
    rewritten=list(arguments)
    for option,value in [('--source',copied),('--source-manifest',manifest),('--product-mozconfig',config),('--workspace',workspace)]:
        index=rewritten.index(option);rewritten[index+1]=str(value)
    if '--apksigner' not in rewritten:
        rewritten+=['--apksigner','/root/.mozbuild/android-sdk-linux/build-tools/37.0.0/apksigner']
    command+=rewritten
    receipt={'status':'PREFLIGHT ONLY' if wrapper.preflight_only else 'STARTING', 'guest_memory_bytes':memory,
             'guest_uid':os.getuid(),'virtualization':'kvm','rootless_podman':True,'firewall_unit':'active',
             'guest_boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
             'free_bytes':free,'image_sha256':image,'source_manifest_sha256':binding['manifest_sha256'],
             'source_mount':'production read-only; verified private copy writable under dedicated workspace parent',
             'private_source':str(copied),'source_copy_receipt':str(copy_receipt),
             'command':command}
    print(json.dumps(receipt,indent=2),flush=True)
    if wrapper.preflight_only:return
    parent.mkdir(parents=True,exist_ok=True)
    if args.action == 'build':
        prepare_source_copy(source, copied, copy_receipt, manifest, binding)
    verify_source_copy(source, copied, copy_receipt, manifest, binding)
    # A signal/SSH wrapper termination must remove the named container; killing
    # only the Podman client can leave a native build running otherwise.
    def interrupted(signum, frame):
        raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    proc=None
    try:
        proc=subprocess.Popen(command)
        rc=proc.wait(timeout=2*args.build_timeout+600 if args.action=='build' else 6*args.test_timeout+600)
        require(rc==0, 'container build/tests failed')
    finally:
        subprocess.run(podman+['rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30,check=False)
        if proc is not None and proc.poll() is None:proc.wait(timeout=30)
        # Generated cache/build files may appear; every reviewed source body and
        # the protected production tree must still match, even after failure.
        verify_source_copy(source, copied, copy_receipt, manifest, binding)


if __name__=='__main__':
    try:main()
    except (InvalidResult,OSError,ValueError,subprocess.SubprocessError) as error:
        print('FAIL / NOT ACCEPTED:',error,file=sys.stderr)
        sys.exit(1)
