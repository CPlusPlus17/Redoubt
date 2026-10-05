#!/usr/bin/env bash
# install-boxb.sh: idempotent host setup for Redoubt's CI VM on box B (host "llm", account "user").
#
# Run ON box B as "user", from a copy of the reviewed checkout's scripts/ci-vm and scripts/ci-vm-boxb
# (deploy-boxb.sh copies them to ~/.local/src/redoubt-ci and runs this). Safe to re-run:
#   - verifies host prerequisites (Fedora 44, /dev/kvm) and installs only missing packages;
#   - fetches the pinned Fedora Cloud 44 image once and checks its pinned SHA-256;
#   - creates the VM once (initialize.py: 16 vCPUs, 24 GiB, 250 GiB thin disk); on later runs only
#     refreshes the launcher (install-host.sh), and only while the VM is stopped;
#   - installs the box B drop-in (OOM order, memory ceiling, CPU/IO weight) and boxb-ctl.sh;
#   - binds box A's on-demand key to boxb-ctl.sh in ~/.ssh/authorized_keys (restrict,command=);
#   - enables lingering so the user manager runs without a login; never enables the VM unit itself
#     (it starts on demand only).
# It never reads, stops or edits the other project's units, accounts or files, nor llama-server's.
set -euo pipefail
umask 077

die() { printf 'install-boxb: %s\n' "$*" >&2; exit 1; }
say() { printf 'install-boxb: %s\n' "$*"; }

poller_key=""
while (($#)); do
  case $1 in
    --poller-key-file) (($# >= 2)) || die '--poller-key-file needs a path'; poller_key=$2; shift 2 ;;
    *) die "usage: install-boxb.sh [--poller-key-file FILE.pub]" ;;
  esac
done

src=$(cd -- "$(dirname -- "$0")/.." && pwd)
civm=$src/ci-vm
boxb=$src/ci-vm-boxb
[[ -f $civm/initialize.py && -f $boxb/boxb-ctl.sh ]] || die "expected scripts/ci-vm and scripts/ci-vm-boxb under $src"
(( EUID != 0 )) || die 'run as the unprivileged owner account, not root'
# shellcheck source=/dev/null
source /etc/os-release
[[ ${ID:-} == fedora && ${VERSION_ID:-} == 44 ]] || die 'expected Fedora 44'
[[ -r /dev/kvm && -w /dev/kvm ]] || die '/dev/kvm is not usable by this account'
[[ $(systemd-detect-virt --vm || true) == none ]] || die 'this is the host installer; refusing to run inside a VM'

# --- packages (the host needs no Python beyond PyYAML; no runner, no gh) --------------------------
pkgs=(qemu-system-x86-core qemu-img bubblewrap passt edk2-ovmf genisoimage python3-pyyaml util-linux openssh-clients curl)
missing=()
for p in "${pkgs[@]}"; do rpm -q "$p" >/dev/null 2>&1 || missing+=("$p"); done
if ((${#missing[@]})); then
  say "installing missing packages: ${missing[*]}"
  sudo -n dnf -y install "${missing[@]}"
else
  say "packages present: ${pkgs[*]}"
fi

# --- verified base image ----------------------------------------------------------------------------
state=$HOME/.local/share/redoubt-ci-vm
image=Fedora-Cloud-Base-Generic-44-1.7.x86_64.qcow2
sha=28680fe5b371a5a82ebf43a31926e086a168e59949d03969c5093e7071f90b7f
install -d -m 700 "$state"
if [[ ! -f $state/$image ]]; then
  say "downloading $image"
  curl --fail --location --silent --show-error --output "$state/$image.part" \
    "https://dl.fedoraproject.org/pub/fedora/linux/releases/44/Cloud/x86_64/images/$image"
  printf '%s  %s\n' "$sha" "$state/$image.part" | sha256sum -c --quiet - || { rm -f "$state/$image.part"; die 'image checksum mismatch'; }
  mv "$state/$image.part" "$state/$image"
fi
printf '%s  %s\n' "$sha" "$state/$image" | sha256sum -c --quiet - || die "$image does not match the pinned SHA-256"
say "base image verified: sha256 $sha"

# --- the VM -------------------------------------------------------------------------------------------
unit=redoubt-ci-vm.service
if [[ ! -f $state/system.qcow2 ]]; then
  say 'creating the VM (initialize.py)'
  python3 "$civm/initialize.py" --name redoubt-ci-boxb --cpus 16 --mem-mib 24576 --disk 250G \
    --instance-date 20261004
elif systemctl --user is-active --quiet "$unit"; then
  say "VM exists and $unit is active: launcher not refreshed (stop it first to update)"
else
  say 'VM exists: refreshing the launcher only (install-host.sh)'
  bash "$civm/install-host.sh"
fi
grep -qx 'VM_NAME=redoubt-ci-boxb' "$state/vm.conf" || die "$state/vm.conf does not describe the box B VM"

dropin=$HOME/.config/systemd/user/$unit.d
install -d -m 755 "$dropin"
install -m 644 "$boxb/redoubt-ci-vm-boxb.conf" "$dropin/10-boxb.conf"
systemctl --user daemon-reload
if systemctl --user is-enabled --quiet "$unit" 2>/dev/null; then
  say "$unit was enabled; disabling autostart (on demand only)"
  systemctl --user disable "$unit"
fi

# --- user manager without a login session -------------------------------------------------------
if [[ $(loginctl show-user "$USER" -p Linger --value 2>/dev/null) != yes ]]; then
  say "enabling lingering for $USER"
  loginctl enable-linger "$USER" 2>/dev/null || sudo -n loginctl enable-linger "$USER"
fi
[[ $(loginctl show-user "$USER" -p Linger --value) == yes ]] || die 'lingering is not enabled'

# --- control script and the restricted poller key --------------------------------------------------
lib=$HOME/.local/lib/redoubt-boxb
install -d -m 700 "$lib"
install -m 700 "$boxb/boxb-ctl.sh" "$lib/boxb-ctl.sh"
if [[ -n $poller_key ]]; then
  key=$(<"$poller_key")
  [[ $key =~ ^ssh-ed25519\ [A-Za-z0-9+/=]{68}(\ [^\"]*)?$ && $key != *$'\n'* ]] || die "$poller_key is not one ssh-ed25519 public key"
  read -r ktype kblob _ <<<"$key"
  install -d -m 700 "$HOME/.ssh"
  touch "$HOME/.ssh/authorized_keys"
  chmod 600 "$HOME/.ssh/authorized_keys"
  # Rewrite in place (keeps the SELinux label); every other line is preserved byte for byte.
  python3 - "$HOME/.ssh/authorized_keys" "restrict,command=\"$lib/boxb-ctl.sh\" $ktype $kblob redoubt-boxb-ondemand" <<'PY'
import sys
path, entry = sys.argv[1], sys.argv[2]
with open(path) as f:
    lines = [l for l in f.read().splitlines() if not l.endswith(' redoubt-boxb-ondemand')]
with open(path, 'w') as f:
    f.write('\n'.join(lines + [entry]) + '\n')
PY
  say 'poller key bound to boxb-ctl.sh (restrict,command=) in ~/.ssh/authorized_keys'
fi

say "done: $(cat "$state/vm.conf" | tr '\n' ' '); unit $(systemctl --user is-active "$unit" || true), enabled=$(systemctl --user is-enabled "$unit" 2>/dev/null || true)"
"$lib/boxb-ctl.sh" gate || true
