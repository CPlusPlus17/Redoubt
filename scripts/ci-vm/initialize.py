#!/usr/bin/env python3
"""Initialize a new VM from the separately downloaded, verified Fedora image.

Refuses to replace an existing guest. No release keys or Actions credentials are
used. The only host private key generated here stays outside the QEMU namespace.
"""
import hashlib
from pathlib import Path
import shutil
import subprocess
import yaml

home = Path.home()
state = home / '.local/share/redoubt-ci-vm'
control = home / '.local/state/redoubt-ci-vm-control'
source = Path(__file__).resolve().parent
base = state / 'Fedora-Cloud-Base-Generic-44-1.7.x86_64.qcow2'
expected = '28680fe5b371a5a82ebf43a31926e086a168e59949d03969c5093e7071f90b7f'
for directory in (state, control):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
if (state / 'system.qcow2').exists():
    raise SystemExit('Existing system.qcow2: refusing to overwrite a guest')
with base.open('rb') as stream:
    if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
        raise SystemExit('Fedora image checksum mismatch')
for name in ('admin_ed25519', 'guest_ed25519'):
    path = control / name
    if not path.exists():
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(path)], check=True)
admin_public = (control / 'admin_ed25519.pub').read_text().strip()
guest_public = (control / 'guest_ed25519.pub').read_text().strip()
(control / 'known_hosts').write_text('[127.0.0.1]:2222 ' + guest_public + '\n')
config = {
    'hostname': 'redoubt-ci', 'manage_etc_hosts': True,
    'disable_root': True, 'ssh_pwauth': False,
    'ssh_keys': {
        'ed25519_private': (control / 'guest_ed25519').read_text(),
        'ed25519_public': guest_public,
    },
    'users': [
        {'name': 'ciadmin', 'groups': ['wheel'], 'shell': '/bin/bash',
         'lock_passwd': True, 'sudo': 'ALL=(ALL) NOPASSWD:ALL',
         'ssh_authorized_keys': [admin_public]},
        {'name': 'runner', 'shell': '/bin/bash', 'lock_passwd': True,
         'sudo': None},
    ],
    'growpart': {'mode': 'auto', 'devices': ['/']}, 'resize_rootfs': True,
}
(state / 'user-data').write_text('#cloud-config\n' + yaml.safe_dump(config))
(state / 'user-data').chmod(0o600)
(state / 'meta-data').write_text('instance-id: redoubt-ci-20260908\nlocal-hostname: redoubt-ci\n')
subprocess.run(['genisoimage', '-quiet', '-output', str(state / 'seed.iso'),
                '-volid', 'cidata', '-joliet', '-rock',
                str(state / 'user-data'), str(state / 'meta-data')], check=True)
subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2',
                '-b', base.name, str(state / 'system.qcow2'), '400G'], check=True)
shutil.copyfile('/usr/share/edk2/ovmf/OVMF_VARS.fd', state / 'OVMF_VARS.fd')
shutil.copyfile(source / 'inside.sh', state / 'inside.sh')
installed = home / '.local/lib/redoubt-ci-vm'
installed.mkdir(parents=True, exist_ok=True, mode=0o700)
for name in ('launch.sh', 'inside.sh', 'ssh.sh', 'stop.sh', 'poweroff.py'):
    shutil.copy2(source / name, installed / name)
units = home / '.config/systemd/user'
units.mkdir(parents=True, exist_ok=True)
shutil.copyfile(source / 'redoubt-ci-vm.service', units / 'redoubt-ci-vm.service')
print('Initialized Fedora44 VM; start with systemctl --user enable --now redoubt-ci-vm.service')
