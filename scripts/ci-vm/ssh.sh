#!/usr/bin/env bash
set -euo pipefail
vm_control=${REDOUBT_VM_CONTROL:-$HOME/.local/state/redoubt-ci-vm-control}
exec ssh -F /dev/null -i "$vm_control/admin_ed25519" \
  -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile="$vm_control/known_hosts" \
  -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=2 \
  -p 2222 ciadmin@127.0.0.1 "$@"
