# Android CI virtual machine

Owner: **LW-M6-09**. Runtime scripts are in [scripts/ci-vm](../../scripts/ci-vm/).
Run host commands as `mgysin`, the owner of the user systemd service. Commands
below assume a Bash terminal in the repository root unless stated otherwise.

## Current state and limits

On 2026-09-08, CI moved to the Fedora 44 KVM guest. The fresh GitHub runner is
`redoubt-ci-qemu`, ID **22**, with production labels `librewolf-android` and
`redoubt-build`. Its root-owned service runs as guest user `runner`, which has no
sudo grant. The previous host runner, ID **2**, is unregistered and its host
service is stopped, disabled and masked. GitHub reports only the VM runner online.
An actual reboot has been checked: cloud-init completed without errors or
warnings, and the guest runner returned online. See
[registration output](evidence/lw-m6-09/runner-registration.txt) and
[completed provisioning](evidence/lw-m6-09/guest-provision-final.txt).

[Actions run 34257944277](https://github.com/CPlusPlus17/Redoubt/actions/runs/34257944277)
passed on runner **22** using the existing remote `android-port` commit
`56c5d8ed0e4f9f3be3d42f01ad6b7b6fb62ba04e` and the Android release workflow in
`preflight` mode. See [job evidence](evidence/lw-m6-09/preflight-jobs.json),
[runner inventory](evidence/lw-m6-09/runners-after-cutover.json), and
[host retirement](evidence/lw-m6-09/host-runner-retired.txt).
This migration has not changed general
CI workflows or published the local Android implementation commits. A preflight
on that older remote commit does not validate the newer local beta code.

No full Android build has been demonstrated in this VM. Its allocation is eight
virtual CPUs, 16 GiB RAM, and a 400 GiB thin qcow2 disk. The guest has a 16 GiB
disk swap file plus 8 GiB zram; zram consumes RAM and is not additional physical
memory. The imported Android image contains Clang 21 and JDK 17; the guest's
default Java outside the container reports version 25 and is used by the preflight
tool-presence check. This does not change the Android container's JDK selection.
The 400 GiB virtual capacity does not reserve 400 GiB on the host. Monitor
both filesystems' actual free space. Full-build peak RAM, elapsed time, and
performance remain unverified; the QEMU process also needs host memory overhead.

On 2026-09-08 the host kernel killed the original 24 GiB QEMU process during a
Fenix unit run; the service had reached a 28.1 GiB memory peak. The allocation
was reduced to 16 GiB, and the complete host/guest isolation check passed after
restart. The interrupted suite is not a test pass. Its logs and the kernel
evidence are retained under `evidence/lw-m7-15/`.

Long manual jobs should run under a named guest `systemd-run --user` service,
as runner with `XDG_RUNTIME_DIR=/run/user/1001`. An SSH disconnect then leaves
the job running. Keep a bounded runtime, full logs, source hashes, start/end and
boot records, and separate Gradle and board-gate exit codes. The recorded
`evidence/lw-m7-15/run-fenix-suite.sh` uses a 14 GiB container memory limit and
22 GiB combined memory/swap limit. These limits do not establish that a full
APK build fits; measure that separately before changing its build resources.

The VM is persistent across jobs. It is not recreated for every job, so workspaces
and container caches can carry state between jobs. The host kernel, KVM, QEMU,
passt, and the host administrator remain trusted. This is isolation on the same
physical host, not a separate signing machine. Keep the existing approval controls
for external-contributor workflows; do not infer permission to run unreviewed
fork code from this migration.

The returned beta APKs were signed on the Fedora build host before this migration.
Changing the runner's location cannot change that history or establish offline
signing. E7 and any owner exception remain governed by [BETA.md](BETA.md) and
[SIGNING.md](SIGNING.md). Never copy the release keystore, passphrase, host SSH
credentials, or GitHub CLI credentials into the VM, its seed, or its shared state.

## Isolation and paths

The host user service launches an unprivileged bubblewrap namespace. Host `/home`
is absent; `/usr` and a small set of system configuration files are read-only.
Only the dedicated VM state directory is bound as writable `/vm`, with `/dev/kvm`
provided for acceleration. There are no 9p or virtiofs host directory shares.

Inside that filesystem namespace, passt owns the host network sockets. QEMU runs
inside a further network namespace with no host IP connectivity and talks to
passt through a pathname Unix socket. Passt gives the guest `10.77.0.2/24`, gateway
`10.77.0.1`, public DNS `1.1.1.1`, and only the inbound mapping
`127.0.0.1:2222` → guest SSH port 22. Host-loopback mapping and UDP port forwarding
are disabled in [inside.sh](../../scripts/ci-vm/inside.sh).

DNS persistence was verified after fixing a reboot failure: NetworkManager's
global domain setting alone had not supplied systemd-resolved after boot. The
provisioner now also configures resolved with `1.1.1.1` and fallback `1.0.0.1`,
and sets the active NetworkManager profile to `ipv4.dns=1.1.1.1`,
`ipv4.ignore-auto-dns=yes`, and `ipv6.method=disabled`.

The root-owned guest nftables output chain accepts local loopback and established
or related replies, then permits root-owned DHCP client packets on UDP 68→67.
It rejects new destinations in `10/8`, `172.16/12`, `192.168/16`, `169.254/16`, and
`100.64/10`. IPv6 is disabled by sysctl and rejected by the firewall. The reply
rule preserves inbound administrative SSH. If the host LAN uses public IPv4
space, add that CIDR through `guest-provision.sh --deny-ipv4 CIDR`; it is not
discovered automatically. These controls block guest-initiated private-network
connections; they do not restrict public Internet destinations.

| Location | Contents and recovery role |
|---|---|
| `~/.local/share/redoubt-ci-vm/` | Writable VM state, visible to QEMU as `/vm`; keep it dedicated to this VM. |
| `system.qcow2` in that directory | Guest disk, including runner registration and workspace/container data. Its backing image is required. |
| `Fedora-Cloud-Base-Generic-44-1.7.x86_64.qcow2` | Verified backing image. Its relative filename is part of the disk chain. |
| `OVMF_VARS.fd` | Mutable UEFI variables; preserve with the disk. Firmware code comes from host `/usr/share/edk2/ovmf/OVMF_CODE.fd`. |
| `seed.iso`, `user-data`, `meta-data` | Initial cloud-init users and guest SSH host identity. They contain the guest SSH host key, never the host administrative private key or release key. Treat backups as private. |
| `serial.log`, `qmp.sock`, `network.sock`, `launcher.lock` | Boot diagnostics and runtime control. The launcher serializes startup and recreates its sockets. |
| `~/.local/state/redoubt-ci-vm-control/` | Host administrative SSH private key, pinned `known_hosts`, and transferred public archives. Outside the QEMU namespace. |
| `~/.local/lib/redoubt-ci-vm/` | Installed launch, stop, QMP, and SSH helpers. |
| `~/.config/systemd/user/redoubt-ci-vm.service` | Host user service; owner lingering is enabled so logout does not stop it. |
| Guest `/home/runner/actions-runner/` | Fresh runner installation and credentials, owned by guest `runner`; never copied from the old host installation. |
| Guest `/home/runner/.local/share/containers/` | Persistent rootless Podman storage. |
| Guest `/var/lib/redoubt-swap/swapfile` | 16 GiB swap in its own btrfs subvolume, enabled through `/etc/fstab`. |

## Daily operation

These commands inspect the VM and guest services without exposing credentials:

```sh
systemctl --user status redoubt-ci-vm.service --no-pager
journalctl --user -u redoubt-ci-vm.service -n 80 --no-pager
loginctl show-user "$USER" -p Linger
./scripts/ci-vm/ssh.sh 'sudo systemctl status redoubt-actions-runner.service redoubt-guest-firewall.service --no-pager'
./scripts/ci-vm/ssh.sh 'free -h; df -h /home; sudo swapon --show'
./scripts/ci-vm/ssh.sh 'sudo journalctl -u redoubt-actions-runner.service -n 80 --no-pager'
gh api repos/CPlusPlus17/Redoubt/actions/runners \
  --jq '.runners[] | {id,name,status,busy,labels:[.labels[].name]}'
```

[ssh.sh](../../scripts/ci-vm/ssh.sh) ignores host SSH configuration, uses only the
dedicated administrative key, and requires the pinned guest host key. Do not
replace that with `StrictHostKeyChecking=no`. For an interactive session, use
`./scripts/ci-vm/ssh.sh`; the login is `ciadmin`, with passwordless guest sudo.
SSH password authentication, root login, agent forwarding, and TCP forwarding are
disabled. The runner service launches `/usr/bin/bash .../run.sh`, which worked
with SELinux enforcing; disabling SELinux is not part of this setup.

Before maintenance, check the runner's `busy` field and let its job finish. Stop
the guest runner first, then the VM:

```sh
./scripts/ci-vm/ssh.sh 'sudo systemctl stop redoubt-actions-runner.service'
systemctl --user stop redoubt-ci-vm.service
```

The stop helper requests ACPI poweroff through QMP and waits up to 90 seconds.
The unit has a 100-second stop timeout and kills the process group if graceful
shutdown fails. A forced stop can interrupt writes; inspect guest logs afterwards.
An unexpected passt failure also stops QEMU and triggers a restart; that failure
path terminates the guest without ACPI shutdown. It was reviewed but not fault-injected.
Starting it again restores enabled guest services:

```sh
systemctl --user start redoubt-ci-vm.service
./scripts/ci-vm/ssh.sh 'sudo systemctl start redoubt-actions-runner.service'
```

To update launcher scripts or their service definition, stop the VM first, run
the installer from the reviewed checkout, and start it again:

```sh
./scripts/ci-vm/install-host.sh
systemctl --user start redoubt-ci-vm.service
```

`install-host.sh` refuses an active VM, takes the launcher lock, and updates runtime
files without replacing the disk, backing image, seed, SSH keys, or UEFI variables.
Editing repository scripts alone does not update their installed copies. For guest
package maintenance, stop the runner, run `sudo dnf upgrade --refresh` inside the
guest, then perform a host-service stop/start if a reboot is needed and recheck
the services. To change the pinned Fedora image or initial Actions archive,
review and update the corresponding hardcoded checksum before rebuilding.

## Repair an existing VM

Start with the host journal and `~/.local/share/redoubt-ci-vm/serial.log`. Check
host disk space, `/dev/kvm` access, and whether something else owns localhost port
2222. Do not remove a lock file to bypass a running launcher. A stopped service
plus an unavailable QMP endpoint is the expected state before disk maintenance.

Back up the stopped guest disk, its exact Fedora backing image, and `OVMF_VARS.fd`
together, preserving sparse files. Preserve the seed and host control directory
as private recovery material. Never back up only `system.qcow2`: it is an overlay,
not a self-contained image. Do not run `initialize.py` to repair an existing disk;
it deliberately refuses to replace it. Do not recreate UEFI variables during a
launcher update. Use `install-host.sh` for runtime repair and restore the complete
disk chain for storage recovery. Do not run qcow2 repair against a live disk.

If the guest is lost or suspected compromised, retire its GitHub registration and
rebuild with a fresh registration token. Do not transplant `.runner`,
`.credentials*`, or the old runner home into a replacement. Preserve needed logs
privately first. Recovery never requires putting release-signing material in the
guest. Host compromise remains outside the protection this VM provides.

## Rebuild from verified inputs

This sequence is for a **new** VM, not the existing guest. First stop the previous
instance, preserve its complete recovery set, and retire its registration before
reusing the default directories. The initializer uses the fixed paths above and
refuses an existing `system.qcow2`.

The host needs KVM access, QEMU, bubblewrap, passt, edk2 OVMF, genisoimage, Python
3.11+ with PyYAML, OpenSSH, curl, GnuPG, util-linux, and systemd user services.
Podman is needed for the optional image transfer; authenticated `gh` with repository
runner administration is needed only for fresh registration. Keep those GitHub
credentials on the host. The bootstrap uses the official
[Fedora Cloud 44 image and verification procedure](https://www.fedoraproject.org/cloud/download/).

```sh
set -euo pipefail
repo_dir=$PWD
vm_state="$HOME/.local/share/redoubt-ci-vm"
install -d -m 700 "$vm_state"
cd "$vm_state"
fedora_images=https://dl.fedoraproject.org/pub/fedora/linux/releases/44/Cloud/x86_64/images
curl --fail --location --remote-name "$fedora_images/Fedora-Cloud-Base-Generic-44-1.7.x86_64.qcow2"
curl --fail --location --remote-name "$fedora_images/Fedora-Cloud-44-1.7-x86_64-CHECKSUM"
curl --fail --location --remote-name https://fedoraproject.org/fedora.gpg
gpg --with-fingerprint --show-keys --keyid-format long fedora.gpg
```

Compare the Fedora 44 fingerprint with Fedora's
[published signing-key details](https://fedoraproject.org/security/):
`36F6 12DC F27F 7D1A 48A8 35E4 DBFC F71C 6D9F 90A6`. Continue only when it agrees:

```sh
gpgv --keyring ./fedora.gpg --output - Fedora-Cloud-44-1.7-x86_64-CHECKSUM \
  | sha256sum -c --ignore-missing
cd "$repo_dir"
python3 scripts/ci-vm/initialize.py
systemctl --user daemon-reload
loginctl enable-linger "$USER"
systemctl --user enable --now redoubt-ci-vm.service
./scripts/ci-vm/ssh.sh 'sudo cloud-init status --wait'
./scripts/ci-vm/ssh.sh 'sudo bash -s' < scripts/ci-vm/guest-provision.sh
```

The image SHA-256 is pinned in `initialize.py` as
`28680fe5b371a5a82ebf43a31926e086a168e59949d03969c5093e7071f90b7f`.
The initializer creates a new administrator key, pins the separately generated
guest SSH host key, creates the seed and 400 GiB overlay, and copies initial
runtime files. Wait for SSH to become available after first boot; do not bypass
host-key checks. Supply `sudo bash -s -- --deny-ipv4 CIDR` in the provisioning
command if a public host-LAN range also needs blocking. The provisioner requires
Fedora 44 in KVM/QEMU and must never be executed on the host.

Download the pinned official
[Actions runner v2.337.0](https://github.com/actions/runner/releases/tag/v2.337.0)
outside VM state, verify its digest, copy only that archive into the guest, and
install it before registering:

```sh
vm_control="$HOME/.local/state/redoubt-ci-vm-control"
runner_archive=actions-runner-linux-x64-2.337.0.tar.gz
curl --fail --location \
  --output "$vm_control/$runner_archive" \
  "https://github.com/actions/runner/releases/download/v2.337.0/$runner_archive"
printf '%s  %s\n' \
  70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613 \
  "$vm_control/$runner_archive" | sha256sum -c -
./scripts/ci-vm/ssh.sh 'cat > /home/ciadmin/actions-runner.tar.gz' \
  < "$vm_control/$runner_archive"
./scripts/ci-vm/ssh.sh 'sudo bash -s -- /home/ciadmin/actions-runner.tar.gz' \
  < scripts/ci-vm/install-runner.sh
python3 scripts/ci-vm/register-runner.py
```

The installer verifies the archive again, creates the root-owned guest service,
and makes it depend on `redoubt-guest-firewall.service`. Registration obtains a
fresh repository token on the host and sends it through SSH stdin without saving
or printing it. Initial registration uses the staging label. Do not copy old
runner credentials, print the token, or add the production label before validation.

## Transfer the Android container and verify readiness

The Android build container is a locally built image, not a published registry
image. Only transfer the reviewed build image's OCI archive, never the host
container store, checkout, home directory, or credential files. The intended image
ID is `c5b57d94cf9e0ed1de7061cee9e0dbfde19d5651e3e2f3824b0e1466116fd687`.

```sh
vm_control="$HOME/.local/state/redoubt-ci-vm-control"
podman save --format oci-archive --output "$vm_control/android-build.oci.tar" \
  librewolf-android-build
sha256sum "$vm_control/android-build.oci.tar"
./scripts/ci-vm/ssh.sh 'sudo -u runner sh -c "cat > /home/runner/android-build.oci.tar"' \
  < "$vm_control/android-build.oci.tar"
./scripts/ci-vm/ssh.sh 'sudo -u runner sha256sum /home/runner/android-build.oci.tar'
```

Compare both archive checksums before loading. Load the completed file as runner:

```sh
./scripts/ci-vm/ssh.sh 'sudo -iu runner env XDG_RUNTIME_DIR=/run/user/$(id -u runner) podman load --input /home/runner/android-build.oci.tar'
./scripts/ci-vm/ssh.sh 'sudo -iu runner env XDG_RUNTIME_DIR=/run/user/$(id -u runner) podman image inspect --format "{{.Id}}" librewolf-android-build'
```

Loading from the completed file succeeded; retain the file-based transfer and
checksum comparison on rebuilds. See the
[input verification](evidence/lw-m6-09/verified-inputs.json). An import or a container
tool probe is not a full Android build. Rootless Podman's lingering user socket follows its
[upstream service guidance](https://docs.podman.io/en/latest/markdown/podman-system-service.1.html).

[verify-guest.sh](../../scripts/ci-vm/verify-guest.sh) checks resources, swap,
privileges, the live firewall, IPv6, absence of host shares, rootless Podman, the
expected image and compiler/Java/HTTPS controls. Its network denial checks require
a host test listener on TCP 8765, first proven reachable on the host. The flag
`--host-canary-confirmed` records that positive control; do not pass it when the
listener is absent. The current probe targets `10.0.0.135` and guest gateway
`10.77.0.1`, so review the host address when rebuilding elsewhere. Run the guest
probe through the host orchestrator, which starts and verifies that temporary
listener, runs the guest checks and removes the listener afterwards:

```sh
python3 scripts/ci-vm/verify-host.py --require-cutover
```

## Repeat a cutover after rebuilding

After local guest acceptance, preserve the production label `librewolf-android`
when transferring scheduling to the VM. Arrange labels and stop the old runner so
the acceptance job can run only on the new VM. Dispatch the existing workflow:

```sh
gh workflow run android-release.yaml --repo CPlusPlus17/Redoubt \
  --ref android-port -f mode=preflight
```

Record the run URL, exact checked-out commit, job conclusion, and runner name/ID.
Stop and disable the old host service before transferring labels. Only after
successful guest validation and Actions preflight should its registration be
removed and the service masked. Verify the old runner is
absent from GitHub and cannot restart on the host; retain any needed historical
logs privately. Do not re-enable the old host runner as an automatic fallback.
The retired host unit is preserved outside VM state as
`~/.local/state/redoubt-ci-vm-control/actions-runner.host.service.retired`.
Its old workspace remains intact; its registration is revoked. Update the
recorded cutover result and labels here and in LW-M6-09 evidence when rebuilding.
No full build or release publication is implied by this preflight-only dispatch.
