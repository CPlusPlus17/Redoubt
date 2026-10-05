#!/usr/bin/env python3
"""Register a fresh guest runner; never persist or print the GitHub token.

The token is fetched on the host that runs this script (where `gh` is logged
in) and travels only through SSH stdin into config.sh inside the guest. Box B
passes --ssh with a command that hops through box B's own ssh.sh, so the token
is never written to box B's disk either (CI-VM.md, "Box B").
"""
import argparse
import json
import re
from pathlib import Path
import shlex
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--name', default='redoubt-ci-qemu')
# The staging label prevents production jobs from being routed before cutover.
parser.add_argument('--labels', default='redoubt-vm-staging',
                    help='comma-separated custom labels (self-hosted,Linux,X64 are implicit)')
parser.add_argument('--ssh', default=str(Path(__file__).resolve().with_name('ssh.sh')),
                    help='command (shell words) that runs its argument as ciadmin in the guest')
parser.add_argument('--hop', action='store_true',
                    help='--ssh goes through one extra remote shell (box B), so quote once more')
args = parser.parse_args()
if not re.fullmatch(r'[A-Za-z0-9._-]{1,64}', args.name):
    raise SystemExit('invalid runner name')
if not re.fullmatch(r'[A-Za-z0-9._-]+(,[A-Za-z0-9._-]+)*', args.labels):
    raise SystemExit('invalid label list')
ssh = shlex.split(args.ssh)

token = json.loads(subprocess.check_output([
    'gh', 'api', '--method', 'POST',
    'repos/CPlusPlus17/Redoubt/actions/runners/registration-token',
], text=True))['token']
command = f"""sudo -u runner -H bash -c 'set -eu
cd /home/runner/actions-runner
IFS= read -r registration_token
./config.sh --unattended --url https://github.com/CPlusPlus17/Redoubt \\
  --name {args.name} --work _work --labels {args.labels} \\
  --token "$registration_token"
'"""


def guest(text):
    return [*ssh, shlex.quote(text) if args.hop else text]


subprocess.run(guest(command), input=token + '\n', text=True, check=True)
subprocess.run(guest('sudo systemctl enable --now redoubt-actions-runner.service'), check=True)
