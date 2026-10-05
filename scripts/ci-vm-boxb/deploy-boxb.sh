#!/usr/bin/env bash
# deploy-boxb.sh: run from box A in the repository root. Sets up Redoubt's CI VM on box B step by
# step; every step is safe to repeat.
#
#   host      copy scripts/ci-vm{,-boxb} to box B (~/.local/src/redoubt-ci), install the poller
#             files on box A (install-poller.sh) and run install-boxb.sh on box B with its key
#   guest     start the VM (only if box B's memory gate agrees, unless --force), wait for
#             cloud-init, provision the guest (22G/8G runner slice), install the pinned runner
#   register  register runner redoubt-ci-boxb with label redoubt-boxb (skipped if GitHub has it);
#             the token is fetched here and passed through SSH stdin, never stored on box B
#   verify    host/guest isolation acceptance on box B (verify-host.py with box B's parameters)
#
# Administration uses the owner's key (BOXB_SSH_KEY, default ~/.ssh/id_boxb); the poller uses its
# own restricted key. Nothing here touches box B's other services or the existing box A runner.
set -euo pipefail
die() { printf 'deploy-boxb: %s\n' "$*" >&2; exit 1; }

repo=$(git rev-parse --show-toplevel)
key=${BOXB_SSH_KEY:-$HOME/.ssh/id_boxb}
target=${BOXB_TARGET:-user@10.0.0.154}
lan_ip=${target#*@}
boxb=(ssh -i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 "$target")
remote_src=.local/src/redoubt-ci
guest_ssh=".local/lib/redoubt-ci-vm/ssh.sh"
runner_archive=$HOME/.local/state/redoubt-ci-vm-control/actions-runner-linux-x64-2.337.0.tar.gz
runner_sha=70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613
# rb CMD: run CMD on box B. With BOXB_LOG=FILE every remote command (never stdin, so never a
# token) is appended to FILE with a UTC timestamp, for the evidence record.
rb() {
  if [[ -n ${BOXB_LOG:-} ]]; then printf '\n### %s  %s\n$ %s\n' "$(date -u +%FT%TZ)" "$target" "$1" >> "$BOXB_LOG"; fi
  "${boxb[@]}" "$1"
}
# On box B, through its own ssh.sh into the guest; the command is quoted for box B's shell.
in_guest() { rb "$guest_ssh $(printf '%q' "$1")"; }

step_host() {
  tar -C "$repo/scripts" -cf - ci-vm ci-vm-boxb |
    rb "rm -rf $remote_src && mkdir -p $remote_src && tar -C $remote_src -xf -"
  bash "$repo/scripts/ci-vm-boxb/install-poller.sh"
  rb "cat > $remote_src/poller.pub" < "$HOME/.local/state/redoubt-boxb-control/ondemand_ed25519.pub"
  rb "bash $remote_src/ci-vm-boxb/install-boxb.sh --poller-key-file $remote_src/poller.pub"
}

step_guest() {
  local force=${1:-}
  if [[ $(rb 'systemctl --user is-active redoubt-ci-vm.service' || true) != active ]]; then
    if ! rb '.local/lib/redoubt-boxb/boxb-ctl.sh gate'; then
      [[ $force == --force ]] || die 'box B memory gate says defer; retry later (or --force, owner decision)'
    fi
    rb 'systemctl --user start redoubt-ci-vm.service'
  fi
  for ((i = 0; i < 60; i++)); do
    in_guest true 2>/dev/null && break
    sleep 5
  done
  # Exit 2 = done with recoverable warnings (box B's first boot: the hostname warning); the
  # status is shown either way, and anything worse stops here.
  in_guest 'sudo cloud-init status --wait; rc=$?; [ $rc -eq 0 ] || [ $rc -eq 2 ]'
  rb "$guest_ssh 'sudo bash -s -- --runner-mem-max 22G --runner-swap-max 8G'" \
    < "$repo/scripts/ci-vm/guest-provision.sh"
  if in_guest 'test -e /home/runner/actions-runner/run.sh'; then
    echo 'deploy-boxb: runner already installed in the guest'
  else
    printf '%s  %s\n' "$runner_sha" "$runner_archive" | sha256sum -c - || die 'runner archive digest mismatch'
    rb "$guest_ssh 'cat > /home/ciadmin/actions-runner.tar.gz'" < "$runner_archive"
    rb "$guest_ssh 'sudo bash -s -- /home/ciadmin/actions-runner.tar.gz'" \
      < "$repo/scripts/ci-vm/install-runner.sh"
    in_guest 'rm -f /home/ciadmin/actions-runner.tar.gz'
  fi
}

step_register() {
  if gh api repos/CPlusPlus17/Redoubt/actions/runners --jq '.runners[].name' | grep -qx redoubt-ci-boxb; then
    echo 'deploy-boxb: redoubt-ci-boxb is already registered'
    return
  fi
  in_guest 'test ! -e /home/runner/actions-runner/.runner' ||
    die 'guest has a .runner but GitHub does not list it: rebuild per CI-VM.md, never transplant credentials'
  if [[ -n ${BOXB_LOG:-} ]]; then
    printf '\n### %s  %s\n$ %s\n' "$(date -u +%FT%TZ)" "$target" \
      "(register-runner.py) $guest_ssh <config.sh --name redoubt-ci-boxb --labels redoubt-boxb, token on stdin>; $guest_ssh 'sudo systemctl enable --now redoubt-actions-runner.service'" >> "$BOXB_LOG"
  fi
  python3 "$repo/scripts/ci-vm/register-runner.py" --name redoubt-ci-boxb --labels redoubt-boxb --hop \
    --ssh "ssh -i $key -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 $target $guest_ssh"
}

step_verify() {
  rb "cd $remote_src && python3 ci-vm/verify-host.py --on-demand --vm-name redoubt-ci-boxb \
    --lan-ip $lan_ip --guest-arg=--cpus --guest-arg=16 --guest-arg=--mem-gib --guest-arg=24 \
    --guest-arg=--runner-mem-max --guest-arg=23622320128 --guest-arg=--runner-swap-max \
    --guest-arg=8589934592 --guest-arg=--image-id --guest-arg=none"
}

case ${1:-} in
  host) step_host ;;
  guest) step_guest "${2:-}" ;;
  register) step_register ;;
  verify) step_verify ;;
  *) die 'usage: deploy-boxb.sh host | guest [--force] | register | verify' ;;
esac
