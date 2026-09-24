#!/usr/bin/env python3
"""Register a fresh guest runner; never persist or print the GitHub token."""
import json
from pathlib import Path
import subprocess

ssh = Path(__file__).resolve().with_name('ssh.sh')
# The staging label prevents production jobs from being routed before cutover.
token = json.loads(subprocess.check_output([
    'gh', 'api', '--method', 'POST',
    'repos/CPlusPlus17/Redoubt/actions/runners/registration-token',
], text=True))['token']
command = """sudo -u runner -H bash -c 'set -eu
cd /home/runner/actions-runner
IFS= read -r registration_token
./config.sh --unattended --url https://github.com/CPlusPlus17/Redoubt \\
  --name redoubt-ci-qemu --work _work --labels redoubt-vm-staging \\
  --token "$registration_token"
'"""
subprocess.run([str(ssh), command], input=token + '\n', text=True, check=True)
subprocess.run([str(ssh), 'sudo systemctl enable --now redoubt-actions-runner.service'], check=True)
