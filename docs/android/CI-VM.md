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
virtual CPUs, 20 GiB RAM, and a 400 GiB thin qcow2 disk. The guest has a 16 GiB
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

The later native graphics rebuild exhausted useful memory in that 16 GiB guest:
Rust held about 12 GiB resident, swap exceeded 8 GiB and full memory pressure was
over 20 percent. SSH status commands then timed out. LW-M7-25 changes the
allocation to 20 GiB and gives native containers a 17 GiB memory / 23 GiB combined
memory-and-swap limit. The entire runner user slice is capped at 18 GiB RAM and
6 GiB swap: rootless Podman creates sibling scopes, so limiting only the driver
service does not enclose its containers. The prior Fenix container limits remain
separate, beneath this shared user ceiling. Restart verification and the new native build outcome must be
recorded under `evidence/lw-m7-25/`; changing a limit does not establish success.

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

## Box B: the on-demand build VM

Owner decision, 2026-10-04: the heavy Android jobs move to box B, host `llm`
(Fedora 44, 24 threads, 62 GiB RAM, 1.8 TB free disk). Box B also runs the
owner's llama-server (`llama-qwen38.service`, RTX 5090) and three ephemeral-VM
GitHub runners of another project (`gh-runner-slot@{1,2,3}.service` in
`machine-ghci.slice`, plus two hasteheart slot accounts `fivur-ci-2/3` under
`ci-capacity`). Redoubt yields to all of them and never touches their units,
accounts or files. Box A's `redoubt-ci-qemu` (ID 22) is unchanged and keeps the
`librewolf-android` jobs (test-android).

| | Box A `redoubt-ci-qemu` | Box B `redoubt-ci-boxb` |
|---|---|---|
| Jobs | `runs-on: librewolf-android` (test-android) | `runs-on: [self-hosted, redoubt-boxb]` (build-android, android-release) |
| VM | 8 vCPUs, 20 GiB, 400 GiB thin | 16 vCPUs, 24 GiB, 250 GiB thin (`vm.conf`) |
| Guest runner slice | 18 GiB RAM / 6 GiB swap | 22 GiB RAM / 8 GiB swap |
| Started by | `redoubt-ondemand.timer` on box A | `redoubt-boxb-ondemand.timer` on box A, through `boxb-ctl.sh` on box B |

The VM, guest provisioning, firewall and runner service are the same scripts as
above ([scripts/ci-vm](../../scripts/ci-vm/)), parameterised; the defaults are box
A's, so box A's installed copies behave as before. Box B adds
[scripts/ci-vm-boxb](../../scripts/ci-vm-boxb/). Everything runs as box B's
unprivileged account `user` (user units, lingering on); `sudo -n` is only a
fallback for `loginctl enable-linger` and for missing packages (none were missing
on 2026-10-04).

State on 2026-10-04: the VM is provisioned and stopped, runner `redoubt-ci-boxb`
is GitHub runner **ID 23** (`self-hosted, Linux, X64, redoubt-boxb`, seen online),
the isolation acceptance passed on box B, and box A's poller timer is enabled. No
job has run on box B yet; build time, memory peak and APK output there are
unverified. Evidence: [evidence/lw-m6-09/boxb](evidence/lw-m6-09/boxb/README.md).

### Who decides what

Box B holds no GitHub credential. The poller runs on box A, where `gh` is
logged in, and only reads GitHub (the same queue reads and label rule as
`redoubt-ondemand.sh`). Box B decides about its own memory:

1. **Box A, every 60 s** (`redoubt-boxb-ondemand.timer`): if a queued job's labels
   are all among `redoubt-ci-boxb`'s labels, or the keepalive is due (7 days;
   GitHub drops a runner offline for 14), it asks box B to start. When nothing
   matching is queued or in progress and the runner is not busy for 15 min (and
   the VM has been up 10 min), it re-checks GitHub and asks box B to stop.
   `~/.local/state/redoubt-boxb-ondemand/hold` on box A keeps the VM up.
2. **Box B** ([boxb-ctl.sh](../../scripts/ci-vm-boxb/boxb-ctl.sh)): the poller's key
   (`~/.local/state/redoubt-boxb-control/ondemand_ed25519` on box A) is bound in box
   B's `authorized_keys` with `restrict,command=` to this script, which accepts only
   `status`, `gate`, `start REASON` and `stop`. `start` runs the gate first and
   refuses (exit 3) with the numbers in box B's journal when there is no room:

   ```
   room = MemAvailable − spherene growth − hasteheart growth − host margin 2 GiB
   start only if room ≥ 26112 MiB (VM 24 GiB + QEMU) and memory PSI some avg60 ≤ 10
   ```

   - *spherene growth*: every VM scope in `machine-ghci.slice` may still grow to
     8.5 GiB (a busy slot VM; an idle one holds ~1.1 GiB), and every active
     `gh-runner-slot@` without a VM may boot one; capped by the slice's
     `MemoryMax − MemoryCurrent` (30 GiB cap today).
   - *hasteheart growth*: a `ci-capacity` member account running a job scope
     (`fivur-slot-*.scope`) may still grow to 10 GiB (anon + shmem of its user
     slice). Box A's script counts ci-capacity grants through `/run/ci-capacity`;
     on box B that directory is mode 2770, not searchable by `user`, so box B uses
     the job scopes instead. An idle slot counts 0: ci-capacity grants only above
     its own `MemAvailable` floor (14 GiB), which a running Redoubt VM lowers.
   - *host margin*: llama-server's anonymous memory (9.2 GiB measured) can grow;
     its model file is a reclaimable mapping already outside `MemAvailable`'s
     used side, and its weights sit on the GPU.

   Knobs (parsed, never sourced) live in box B's `~/.config/redoubt-boxb.env`:
   `NEED_MIB`, `SPHERENE_VM_MIB`, `HH_JOB_MIB`, `HOST_MARGIN_MIB`, `MAX_PSI`.

In practice the gate opens when both hasteheart jobs are idle and the spherene
VMs are not all busy. With both hasteheart jobs running it defers (measured
2026-10-04: room about 3 GiB). A deferred Redoubt job waits in GitHub's queue
(up to 24 h) and the poller asks again every minute; box B logs a deferral at
most once per 10 min.

**Overcommit is structural.** At their caps, llama-server, the spherene slice
(30 GiB), hasteheart (2 × 10 GiB) and the host already exceed box B's 62 GiB
(`/etc/ci-capacity.conf` says so). The gate protects the start, not the next
hour. The box B drop-in
([redoubt-ci-vm-boxb.conf](../../scripts/ci-vm-boxb/redoubt-ci-vm-boxb.conf)) therefore
makes Redoubt the first victim: `OOMScoreAdjust=700` (Redoubt QEMU ≈ 390 + 700 against
spherene ≈ 130 + 500 and llama-server ≈ 0), `MemoryMax=26G` for the QEMU unit, and
`CPUWeight=50`/`IOWeight=50`. A killed QEMU fails the running build; nothing else
is disturbed. The other direction (a hasteheart grant just after a Redoubt start)
is the same open point as box A's (`impl/boxa/REVIEW.md` O1).

### Install and register (idempotent; run from box A in the repository root)

```sh
bash scripts/ci-vm-boxb/deploy-boxb.sh host       # copy scripts, poller files on box A, install-boxb.sh on box B
bash scripts/ci-vm-boxb/deploy-boxb.sh guest      # start (only if the gate agrees), provision 22G/8G, install runner 2.337.0
bash scripts/ci-vm-boxb/deploy-boxb.sh register   # redoubt-ci-boxb, label redoubt-boxb; token via SSH stdin only
bash scripts/ci-vm-boxb/deploy-boxb.sh verify     # verify-host.py on box B with box B's parameters
bash scripts/ci-vm-boxb/install-poller.sh --enable  # enable redoubt-boxb-ondemand.timer on box A
```

Administration uses the owner's key `~/.ssh/id_boxb` (`user@10.0.0.154`). Set
`BOXB_LOG=FILE` to append every remote command to an evidence log. `deploy-boxb.sh
host` copies `scripts/ci-vm` and `scripts/ci-vm-boxb` to box B's
`~/.local/src/redoubt-ci` and runs
[install-boxb.sh](../../scripts/ci-vm-boxb/install-boxb.sh) there, which fetches the
pinned Fedora image (SHA-256 above), runs `initialize.py --name redoubt-ci-boxb
--cpus 16 --mem-mib 24576 --disk 250G` once, and on later runs only refreshes the
launcher while the VM is stopped. It never enables `redoubt-ci-vm.service`.
`guest --force` overrides the memory gate for provisioning; use it only as an owner
decision. The registration token is fetched on box A with `gh api` and sent through
SSH stdin through box B's `ssh.sh` into `config.sh`; it is never written on box B
or in the guest outside the runner's own configuration. The android build image is
not transferred: box A's archived image predates `assets/Dockerfile.android`'s
SDK pins (bd3cb07e), so the workflows build it in the guest from the commit's
Dockerfile and label it with its hash (`org.redoubt.dockerfile-sha256`); a later
Dockerfile change rebuilds it.

Box B paths: VM state `~/.local/share/redoubt-ci-vm/` (with `vm.conf`), host
control `~/.local/state/redoubt-ci-vm-control/`, launcher `~/.local/lib/redoubt-ci-vm/`,
`~/.local/lib/redoubt-boxb/boxb-ctl.sh`, units `~/.config/systemd/user/redoubt-ci-vm.service`
and `redoubt-ci-vm.service.d/10-boxb.conf`. Guest SSH is box B's `127.0.0.1:2222`.
The guest's private-network rejection covers box B's LAN (10.0.0.0/24) and libvirt
bridges (192.168.122.0/24, 192.168.150.0/24).

### Daily operation

```sh
# box A
systemctl --user list-timers redoubt-boxb-ondemand.timer
journalctl --user -u redoubt-boxb-ondemand -n 40 --no-pager
REDOUBT_DRY_RUN=1 ~/.local/lib/redoubt-boxb-ondemand/redoubt-boxb-ondemand.sh
# box B (owner key)
ssh -i ~/.ssh/id_boxb -o IdentitiesOnly=yes user@10.0.0.154 \
  '.local/lib/redoubt-boxb/boxb-ctl.sh gate; journalctl -t redoubt-boxb-ctl -n 20 --no-pager'
ssh -i ~/.ssh/id_boxb -o IdentitiesOnly=yes user@10.0.0.154 \
  'systemctl --user status redoubt-ci-vm.service --no-pager'
ssh -i ~/.ssh/id_boxb -o IdentitiesOnly=yes user@10.0.0.154 \
  ".local/lib/redoubt-ci-vm/ssh.sh 'free -h; df -h /home; sudo systemctl status redoubt-actions-runner.service --no-pager'"
```

Limits: the poller lives on box A, so box B's VM is not started while box A is
off (queued jobs wait). Both pollers share box A's `gh` rate limit (about 20
requests per minute each while 19 box A jobs are queued). The VM is persistent
between jobs like box A's; the build caches under `/home/runner/redoubt-ci` are
the point. Roll back by pointing the two workflows' `runs-on` back to
`librewolf-android`, `systemctl --user disable --now redoubt-boxb-ondemand.timer`
on box A, stopping the VM on box B, and removing the `redoubt-boxb-ondemand` line
from box B's `authorized_keys`; retire `redoubt-ci-boxb`'s registration before
deleting its disk.
