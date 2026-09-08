#!/usr/bin/env bash
# Run as root INSIDE the dedicated Fedora 44 KVM/QEMU guest, never on the host.
# Cloud-init must have created ciadmin (administration) and runner (unprivileged).
# This script does not download or register an Actions runner.
set -euo pipefail
umask 022

die() { printf 'guest-provision: %s\n' "$*" >&2; exit 1; }
usage() {
    printf 'Usage: %s [--deny-ipv4 PUBLIC-HOST-LAN-CIDR ...]\n' "$0"
}
deny_extra=()
while (($#)); do
    case "$1" in
        --deny-ipv4)
            (($# >= 2)) || die '--deny-ipv4 requires an IPv4 CIDR'
            deny_extra+=("$2"); shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "unknown argument: $1" ;;
    esac
done
[[ $EUID == 0 ]] || die 'run as root inside the guest'
[[ -r /etc/os-release ]] || die 'missing /etc/os-release'
# shellcheck source=/dev/null
source /etc/os-release
[[ ${ID:-} == fedora && ${VERSION_ID:-} == 44 ]] || die 'requires Fedora 44'
virt=$(systemd-detect-virt --vm) || die 'requires a KVM/QEMU virtual machine'
[[ $virt == kvm || $virt == qemu ]] || die "refusing virtualization type: $virt"
for account in ciadmin runner; do
    id "$account" >/dev/null 2>&1 || die "cloud-init must create $account first"
done
runner_uid=$(id -u runner)
((runner_uid >= 1000)) || die 'runner must be an ordinary, non-root account'
runner_home=$(getent passwd runner | cut -d: -f6)
[[ $runner_home == /home/runner ]] || die 'expected runner home /home/runner'

# Public host-LAN ranges must be supplied explicitly; private ranges are built in.
# Parse before package installation or any configuration changes.
command -v python3 >/dev/null || die 'Fedora cloud image must provide python3'
extra_cidrs=$(python3 - "${deny_extra[@]}" <<'PY'
import ipaddress
import sys
try:
    networks = sorted({str(ipaddress.IPv4Network(value, strict=True))
                       for value in sys.argv[1:]})
except ValueError as error:
    raise SystemExit(f'invalid --deny-ipv4: {error}')
print(''.join(', ' + value for value in networks))
PY
)

if rpm -q curl-minimal >/dev/null 2>&1; then
    dnf -y swap curl-minimal curl
fi
dnf -y install git make python3-pyyaml curl gnupg2 tar xz patch unzip \
    java-25-openjdk-devel android-tools podman nftables util-linux \
    libicu openssl-libs krb5-libs zlib libstdc++ \
    passt fuse-overlayfs btrfs-progs shadow-utils sudo openssh-server

# Keep the administrator's cloud-init access, while removing runner's group-based
# escalation paths. The final explicit denial also overrides a cloud-init grant.
usermod -aG wheel ciadmin
usermod -G '' runner
usermod -L runner
install -d -o root -g root -m 0750 /etc/sudoers.d
cat > /etc/sudoers.d/zz-redoubt-runner-deny <<'EOF'
runner ALL=(ALL:ALL) !ALL
EOF
chown root:root /etc/sudoers.d/zz-redoubt-runner-deny
chmod 0440 /etc/sudoers.d/zz-redoubt-runner-deny
visudo -c
# Check policy as root, including password-required grants, without executing any
# command as runner. A fresh guest must have no allow entry remaining for runner.
if sudo_policy=$(LC_ALL=C sudo -l -U runner 2>&1); then
    :
elif [[ $sudo_policy != *'is not allowed to run sudo'* ]]; then
    die "could not inspect runner sudo policy: $sudo_policy"
fi
if printf '%s\n' "$sudo_policy" | grep -E '^[[:space:]]+\(' | grep -vE '\)[[:space:]]+!ALL[[:space:]]*$'; then
    die 'runner still has a sudo grant; remove it before registering the runner'
fi

# Allocate at least 65,536 subordinate IDs without stealing another user's range.
# Existing adequate mappings stay unchanged, preserving rootless container data.
python3 - "$runner_uid" <<'PY'
from pathlib import Path
import subprocess
import sys

owners = {'runner', sys.argv[1]}
for filename, option in (('/etc/subuid', '--add-subuids'),
                         ('/etc/subgid', '--add-subgids')):
    path = Path(filename)
    path.touch(exist_ok=True)
    ranges = []
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        owner, first, count = line.split(':')
        first, count = int(first), int(count)
        if first < 1 or count < 1:
            raise SystemExit(f'invalid subordinate ID range in {filename}')
        ranges.append((owner, first, first + count))
    own = [(first, end) for owner, first, end in ranges if owner in owners]
    others = [(first, end) for owner, first, end in ranges if owner not in owners]
    if any(a < d and c < b for a, b in own for c, d in others):
        raise SystemExit(f'runner overlaps another subordinate ID range: {filename}')
    if not any(end - first >= 65536 for first, end in own):
        first = max([100000] + [end for _, _, end in ranges])
        if first + 65536 >= 2**32:
            raise SystemExit(f'no subordinate ID range available: {filename}')
        subprocess.run(['usermod', option, f'{first}-{first + 65535}', 'runner'],
                       check=True)
PY

# Pin DNS in resolved and the active NetworkManager profile so it survives boot.
# A global-dns-domain-only NM override did not reach resolved on Fedora 44.
install -d -o root -g root -m 0755 /etc/systemd/resolved.conf.d /etc/sysctl.d
rm -f /etc/NetworkManager/conf.d/90-redoubt-public-dns.conf
cat > /etc/systemd/resolved.conf.d/90-redoubt-public-dns.conf <<'EOF'
[Resolve]
DNS=1.1.1.1
FallbackDNS=1.0.0.1
EOF
cat > /etc/sysctl.d/90-redoubt-ipv6.conf <<'EOF'
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1
EOF
chown root:root /etc/systemd/resolved.conf.d/90-redoubt-public-dns.conf \
    /etc/sysctl.d/90-redoubt-ipv6.conf
chmod 0644 /etc/systemd/resolved.conf.d/90-redoubt-public-dns.conf \
    /etc/sysctl.d/90-redoubt-ipv6.conf
sysctl -p /etc/sysctl.d/90-redoubt-ipv6.conf
nmcli general reload conf
while IFS=: read -r connection_uuid device; do
    [[ -n $device && $device != lo ]] || continue
    nmcli connection modify "$connection_uuid" ipv6.method disabled \
        ipv4.ignore-auto-dns yes ipv4.dns 1.1.1.1
    nmcli device reapply "$device"
done < <(nmcli -t -f UUID,DEVICE connection show --active)
systemctl restart systemd-resolved.service

# Only our table is replaced, atomically; other guest firewall tables are kept.
# Established replies come first so host-forwarded inbound SSH remains usable.
# DHCP is limited to root-owned client packets; runner cannot use the exception.
install -d -o root -g root -m 0755 /etc/nftables /etc/systemd/system
cat > /etc/nftables/redoubt-guest.nft <<EOF
destroy table inet redoubt_guest
table inet redoubt_guest {
    chain output {
        type filter hook output priority -10; policy accept;
        oifname "lo" accept
        ct state established,related accept
        meta skuid 0 udp sport 68 udp dport 67 accept
        ct state new ip daddr { 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16, 100.64.0.0/10${extra_cidrs} } reject with icmp type admin-prohibited
        meta nfproto ipv6 reject with icmpv6 type admin-prohibited
    }
}
EOF
cat > /etc/systemd/system/redoubt-guest-firewall.service <<'EOF'
[Unit]
Description=Redoubt CI guest private-network egress restriction
DefaultDependencies=no
After=local-fs.target
Before=network-pre.target shutdown.target
Wants=network-pre.target
Conflicts=shutdown.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/nft -f /etc/nftables/redoubt-guest.nft
ExecReload=/usr/sbin/nft -f /etc/nftables/redoubt-guest.nft

[Install]
WantedBy=multi-user.target
EOF
install -d -o root -g root -m 0755 "/etc/systemd/system/user@${runner_uid}.service.d"
cat > "/etc/systemd/system/user@${runner_uid}.service.d/20-redoubt-firewall.conf" <<'EOF'
[Unit]
Requires=redoubt-guest-firewall.service
After=redoubt-guest-firewall.service
EOF
chown root:root /etc/nftables/redoubt-guest.nft \
    /etc/systemd/system/redoubt-guest-firewall.service \
    "/etc/systemd/system/user@${runner_uid}.service.d/20-redoubt-firewall.conf"
chmod 0644 /etc/nftables/redoubt-guest.nft \
    /etc/systemd/system/redoubt-guest-firewall.service \
    "/etc/systemd/system/user@${runner_uid}.service.d/20-redoubt-firewall.conf"
nft --check --file /etc/nftables/redoubt-guest.nft
systemctl daemon-reload
systemctl enable redoubt-guest-firewall.service
systemctl restart redoubt-guest-firewall.service

# A separate btrfs subvolume avoids preventing snapshots of the root subvolume.
# mkswapfile disables CoW and compression and allocates the supported extents.
swap_dir=/var/lib/redoubt-swap
swap_file=$swap_dir/swapfile
swap_bytes=$((16 * 1024 * 1024 * 1024))
if [[ ! -e $swap_dir ]]; then
    case $(findmnt -n -o FSTYPE -T /var/lib) in
        btrfs) btrfs subvolume create "$swap_dir" ;;
        ext4) install -d -o root -g root -m 0700 "$swap_dir" ;;
        *) die 'swap creation supports btrfs or ext4 only' ;;
    esac
fi
[[ -d $swap_dir && ! -L $swap_dir ]] || die 'unexpected swap directory'
chown root:root "$swap_dir"
chmod 0700 "$swap_dir"
if [[ ! -e $swap_file ]]; then
    case $(findmnt -n -o FSTYPE -T "$swap_dir") in
        btrfs) btrfs filesystem mkswapfile --size 16G "$swap_file" ;;
        ext4)
            # Writing blocks, rather than a sparse truncate, is required for swap.
            (umask 077; dd if=/dev/zero of="$swap_file" bs=1M count=16384 status=progress)
            mkswap "$swap_file" ;;
        *) die 'swap creation supports btrfs or ext4 only' ;;
    esac
fi
[[ -f $swap_file && ! -L $swap_file ]] || die 'unexpected swap file'
[[ $(stat -c %s "$swap_file") == "$swap_bytes" ]] || die 'existing swap file is not 16 GiB'
[[ $(blkid -p -s TYPE -o value "$swap_file") == swap ]] || die 'existing file is not formatted swap'
chown root:root "$swap_file"
chmod 0600 "$swap_file"
if ! swapon --show=NAME --noheadings | grep -Fxq "$swap_file"; then
    swapon "$swap_file"
fi
if ! awk -v path="$swap_file" '$1 == path {found=1} END {exit !found}' /etc/fstab; then
    printf '%s none swap defaults 0 0\n' "$swap_file" >> /etc/fstab
fi
systemctl daemon-reload

# The packaged user socket and linger persist rootless Podman across SSH logout
# and reboots. Storage remains on the guest disk; no host mounts are configured.
install -d -o runner -g "$(id -gn runner)" -m 0700 \
    "$runner_home/.local" "$runner_home/.local/share" \
    "$runner_home/.local/share/containers"
loginctl enable-linger runner
systemctl start "user@${runner_uid}.service"
runuser -u runner -- env XDG_RUNTIME_DIR="/run/user/$runner_uid" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$runner_uid/bus" \
    systemctl --user enable --now podman.socket

# The first matching SSH setting wins; load before cloud-init's usual 50-* file.
install -d -o root -g root -m 0755 /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/00-redoubt-ci.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
AllowUsers ciadmin
AllowAgentForwarding no
AllowTcpForwarding no
X11Forwarding no
PermitTunnel no
EOF
chown root:root /etc/ssh/sshd_config.d/00-redoubt-ci.conf
chmod 0644 /etc/ssh/sshd_config.d/00-redoubt-ci.conf
sshd -t
ssh_policy=$(sshd -T)
for required in 'passwordauthentication no' 'kbdinteractiveauthentication no' \
    'permitrootlogin no' 'allowusers ciadmin'; do
    grep -Fxq "$required" <<< "$ssh_policy" || die "SSH policy not effective: $required"
done
systemctl enable sshd.service
systemctl reload-or-restart sshd.service

printf 'Guest provisioning complete: runner UID %s, rootless Podman socket, 16 GiB swap, private-network egress restrictions.\n' "$runner_uid"
printf 'Register the Actions runner separately; its root-owned service must Require/After redoubt-guest-firewall.service.\n'
