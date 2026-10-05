#!/usr/bin/env bash
# install-poller.sh: idempotent install of box B's on-demand poller on box A (the workstation).
#
#   bash scripts/ci-vm-boxb/install-poller.sh            # key, pinned host key, script, units; one dry-run pass
#   bash scripts/ci-vm-boxb/install-poller.sh --enable   # and enable the 60 s timer
#
# Creates ~/.local/state/redoubt-boxb-control/ondemand_ed25519 (only once). Its public half is bound
# on box B to boxb-ctl.sh by install-boxb.sh, so this key can run status|gate|start|stop there and
# nothing else. Box B's host key is copied from ~/.ssh/known_hosts and pinned (never scanned).
# Needs no root. gh must be logged in on this host with read access to the repository's runs and
# runners; no GitHub credential is copied anywhere.
set -euo pipefail
umask 077
die() { printf 'install-poller: %s\n' "$*" >&2; exit 1; }

enable=0
case ${1:-} in
  --enable) enable=1 ;;
  '') ;;
  *) die 'usage: install-poller.sh [--enable]' ;;
esac
src=$(cd -- "$(dirname -- "$0")" && pwd)
host=${REDOUBT_BOXB_ADDR:-10.0.0.154}
control=$HOME/.local/state/redoubt-boxb-control
lib=$HOME/.local/lib/redoubt-boxb-ondemand
units=$HOME/.config/systemd/user
{ command -v gh && command -v jq; } >/dev/null || die 'gh and jq are required'

install -d -m 700 "$control" "$lib"
if [[ ! -f $control/ondemand_ed25519 ]]; then
  ssh-keygen -q -t ed25519 -N '' -C "redoubt-boxb-ondemand@$(hostname -s)" -f "$control/ondemand_ed25519"
fi
pinned=$(ssh-keygen -F "$host" -f "$HOME/.ssh/known_hosts" | grep -v '^#' | grep ' ssh-ed25519 ' || true)
[[ -n $pinned ]] || die "no ssh-ed25519 host key for $host in ~/.ssh/known_hosts; connect once with the owner's key and verify it first"
printf '%s\n' "$pinned" > "$control/known_hosts"

install -m 700 "$src/redoubt-boxb-ondemand.sh" "$lib/redoubt-boxb-ondemand.sh"
install -d -m 755 "$units"
install -m 644 "$src/redoubt-boxb-ondemand.service" "$src/redoubt-boxb-ondemand.timer" "$units/"
systemctl --user daemon-reload
printf 'install-poller: public key for install-boxb.sh --poller-key-file: %s\n' "$control/ondemand_ed25519.pub"
printf 'install-poller: dry-run pass:\n'
REDOUBT_DRY_RUN=1 "$lib/redoubt-boxb-ondemand.sh" || true
if ((enable)); then
  systemctl --user enable --now redoubt-boxb-ondemand.timer
  systemctl --user list-timers redoubt-boxb-ondemand.timer --no-pager
fi
