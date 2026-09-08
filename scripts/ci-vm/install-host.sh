#!/usr/bin/env bash
# Install/update host runtime without touching the VM disk, firmware or keys.
set -euo pipefail
vm_state=${REDOUBT_VM_STATE:-$HOME/.local/share/redoubt-ci-vm}
source_dir=$(cd -- "$(dirname -- "$0")" && pwd)
if systemctl --user is-active --quiet redoubt-ci-vm.service; then
  echo 'Stop redoubt-ci-vm.service before updating its launcher' >&2
  exit 1
fi
exec 9>"$vm_state/launcher.lock"
flock --nonblock 9
install -d -m 700 "$HOME/.local/lib/redoubt-ci-vm"
install -d "$HOME/.config/systemd/user"
for name in launch.sh inside.sh ssh.sh stop.sh poweroff.py; do
  install -m 700 "$source_dir/$name" "$HOME/.local/lib/redoubt-ci-vm/$name"
done
install -m 700 "$source_dir/inside.sh" "$vm_state/inside.sh"
install -m 644 "$source_dir/redoubt-ci-vm.service" "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
