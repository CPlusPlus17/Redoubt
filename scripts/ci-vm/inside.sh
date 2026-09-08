#!/usr/bin/env bash
set -euo pipefail
umask 077
rm -f /vm/network.sock /vm/qmp.sock
passt --foreground --socket /vm/network.sock --ipv4-only \
  --address 10.77.0.2 --netmask 255.255.255.0 --gateway 10.77.0.1 \
  --dns 1.1.1.1 --map-host-loopback none \
  --tcp-ports 127.0.0.1/2222:22 --udp-ports none &
network_pid=$!
qemu_pid=
cleanup() {
  kill "$network_pid" ${qemu_pid:+"$qemu_pid"} 2>/dev/null || true
  wait "$network_pid" ${qemu_pid:+"$qemu_pid"} 2>/dev/null || true
}
trap cleanup EXIT
for ((attempt=0; attempt<100; attempt++)); do
  [[ -S /vm/network.sock ]] && break
  kill -0 "$network_pid"
  sleep 0.1
done
[[ -S /vm/network.sock ]]
# QEMU itself has no host IP network. Only passt owns host network sockets;
# their pathname Unix socket crosses this additional network namespace.
bwrap --unshare-net --bind / / --dev-bind /dev /dev --die-with-parent \
  qemu-system-x86_64 -name redoubt-ci -machine q35,accel=kvm \
  -cpu host -smp 8 -m 24576 -display none -nodefaults \
  -drive if=pflash,format=raw,unit=0,readonly=on,file=/usr/share/edk2/ovmf/OVMF_CODE.fd \
  -drive if=pflash,format=raw,unit=1,file=/vm/OVMF_VARS.fd \
  -drive file=/vm/system.qcow2,if=virtio,format=qcow2,discard=unmap \
  -drive file=/vm/seed.iso,media=cdrom,readonly=on \
  -netdev stream,id=net0,addr.type=unix,addr.path=/vm/network.sock \
  -device virtio-net-pci,netdev=net0,mac=52:54:00:77:00:02 \
  -device virtio-rng-pci \
  -serial file:/vm/serial.log -monitor none \
  -qmp unix:/vm/qmp.sock,server=on,wait=off &
qemu_pid=$!
set +e
wait -n -p finished "$network_pid" "$qemu_pid"
status=$?
set -e
if [[ $finished == "$network_pid" ]]; then
  echo 'passt exited; stopping the disconnected VM so systemd can restart both' >&2
  exit 1
fi
exit "$status"
