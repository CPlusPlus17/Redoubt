#!/usr/bin/env bash
# Run the VM in a mount/PID namespace containing no host home or credentials.
set -euo pipefail
vm_state=${REDOUBT_VM_STATE:-$HOME/.local/share/redoubt-ci-vm}
[[ -d "$vm_state" && -f "$vm_state/system.qcow2" && -f "$vm_state/seed.iso" ]]
exec flock --nonblock "$vm_state/launcher.lock" \
  bwrap --unshare-user --unshare-pid --unshare-uts --unshare-ipc \
  --die-with-parent --new-session --clearenv \
  --setenv PATH /usr/bin:/usr/sbin --setenv HOME /tmp \
  --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/sbin /sbin \
  --symlink usr/lib /lib --symlink usr/lib64 /lib64 \
  --dir /etc --ro-bind /etc/passwd /etc/passwd --ro-bind /etc/group /etc/group \
  --ro-bind /etc/resolv.conf /etc/resolv.conf \
  --ro-bind /etc/nsswitch.conf /etc/nsswitch.conf \
  --proc /proc --dev /dev --dev-bind /dev/kvm /dev/kvm \
  --tmpfs /tmp --tmpfs /run --dir /var --bind "$vm_state" /vm \
  --chdir /vm -- /usr/bin/bash /vm/inside.sh
