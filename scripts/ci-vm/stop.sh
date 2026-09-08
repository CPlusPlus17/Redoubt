#!/usr/bin/env bash
set -euo pipefail
vm_state=${REDOUBT_VM_STATE:-$HOME/.local/share/redoubt-ci-vm}
[[ -S "$vm_state/qmp.sock" ]] || exit 0
"$(dirname "$0")/poweroff.py"
for ((attempt=0; attempt<90; attempt++)); do
  [[ -S "$vm_state/qmp.sock" ]] || exit 0
  # QEMU can leave its socket inode behind after exit; the QMP connection is authoritative.
  if ! python3 - "$vm_state/qmp.sock" <<'PY'
import socket, sys
with socket.socket(socket.AF_UNIX) as client:
    client.settimeout(1)
    try:
        client.connect(sys.argv[1])
    except OSError:
        sys.exit(1)
PY
  then
    exit 0
  fi
  sleep 1
done
echo 'Guest did not shut down within 90 seconds' >&2
exit 1
