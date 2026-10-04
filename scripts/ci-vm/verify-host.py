#!/usr/bin/env python3
"""Probe the live QEMU boundary and run guest checks against a live TCP canary."""
import argparse
import os
from pathlib import Path
import shlex
import socket
import socketserver
import subprocess
import threading

parser = argparse.ArgumentParser()
parser.add_argument('--require-cutover', action='store_true')
# Defaults are box A's. Box B: --lan-ip 10.0.0.154 --vm-name redoubt-ci-boxb --on-demand
# --guest-arg=--cpus --guest-arg=16 ... (CI-VM.md, "Box B").
parser.add_argument('--lan-ip', default='10.0.0.135',
                    help="this host's LAN address, the private canary the guest must not reach")
parser.add_argument('--vm-name', default='redoubt-ci', help='QEMU -name of the VM')
parser.add_argument('--on-demand', action='store_true',
                    help='the VM unit is started on demand, so it is not expected to be enabled')
parser.add_argument('--guest-arg', action='append', default=[],
                    help='extra argument for verify-guest.sh (repeatable)')
args = parser.parse_args()
source = Path(__file__).resolve().parent
state = Path(os.environ.get('REDOUBT_VM_STATE', Path.home() / '.local/share/redoubt-ci-vm'))
subprocess.run(['systemctl', '--user', 'is-active', '--quiet', 'redoubt-ci-vm.service'], check=True)
if not args.on_demand:
    subprocess.run(['systemctl', '--user', 'is-enabled', '--quiet', 'redoubt-ci-vm.service'], check=True)
qemu = []
for entry in Path('/proc').iterdir():
    if not entry.name.isdigit():
        continue
    try:
        argv = (entry / 'cmdline').read_bytes().split(b'\0')
    except (OSError, ProcessLookupError):
        continue
    if argv and argv[0] == b'qemu-system-x86_64' and args.vm_name.encode() in argv:
        qemu.append(entry)
assert len(qemu) == 1, f'Expected one Redoubt QEMU process, found {len(qemu)}'
process = qemu[0]
for namespace in ('mnt', 'net', 'pid', 'user'):
    guest_ns = (process / 'ns' / namespace).readlink()
    host_ns = (Path('/proc/self/ns') / namespace).readlink()
    assert guest_ns != host_ns, f'QEMU shares host {namespace} namespace'
    print(f'PASS QEMU separate {namespace} namespace: {guest_ns}', flush=True)
assert not (process / 'root/home').exists(), 'Host home visible to QEMU'
print('PASS QEMU namespace has no /home directory', flush=True)
before = (state / 'qmp.sock').stat().st_ino
duplicate = subprocess.run([str(source / 'launch.sh')], timeout=5, capture_output=True)
assert duplicate.returncode == 1, 'Second launch was not rejected by lifecycle lock'
assert before == (state / 'qmp.sock').stat().st_ino, 'Second launch changed live QMP socket'
print('PASS duplicate launch refused without changing live QMP socket', flush=True)

if args.require_cutover:
    for query in ('is-active', 'is-enabled'):
        result = subprocess.run(['systemctl', '--user', query, 'actions-runner.service'], capture_output=True, text=True)
        assert result.returncode != 0, f'Host runner remains {query}: {result.stdout}'
    print('PASS host runner inactive and disabled', flush=True)

class Canary(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.sendall(b'redoubt-ci-isolation-canary\n')

class Server(socketserver.TCPServer):
    allow_reuse_address = True

with Server(('0.0.0.0', 8765), Canary) as server:
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        for address in ('127.0.0.1', args.lan_ip):
            with socket.create_connection((address, 8765), timeout=2) as client:
                assert client.recv(128) == b'redoubt-ci-isolation-canary\n'
            print(f'PASS host canary live at {address}:8765', flush=True)
        with (source / 'verify-guest.sh').open('rb') as script:
            guest = ['--host-canary-confirmed', '--canary-host', args.lan_ip, *args.guest_arg]
            subprocess.run([str(source / 'ssh.sh'), 'bash -s -- ' + shlex.join(guest)],
                           stdin=script, check=True, timeout=180)
    finally:
        server.shutdown()
        worker.join()
print('PASS host and guest acceptance complete; temporary canary stopped', flush=True)
