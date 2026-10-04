#!/usr/bin/env bash
# boxb-ctl.sh: the only thing box A's on-demand poller can run on box B.
#
# Installed as ~/.local/lib/redoubt-boxb/boxb-ctl.sh on box B (host "llm", account "user") and
# bound to the poller's key in ~/.ssh/authorized_keys with restrict,command="...". The verb comes
# from SSH_ORIGINAL_COMMAND (or from "$@" when run locally):
#
#   status        state=<ActiveState> entered=<unix seconds> of redoubt-ci-vm.service
#   gate          the memory decision, read-only; exit 0 = room, 3 = defer
#   start REASON  start the VM unit only if the gate says there is room (exit 3 otherwise)
#   stop          stop the VM unit (ExecStop powers the guest down over QMP)
#
# Box B decides about its own memory, whoever asks: the poller only knows GitHub's queue. Every
# start, deferral and stop is logged to box B's journal (journalctl -t redoubt-boxb-ctl).
#
# The gate (all MiB):
#   room = MemAvailable - spherene growth - hasteheart growth - host margin
#   spherene growth   machine-ghci.slice (the other project's runner VMs, gh-runner-slot@N):
#                     every running VM scope may still grow to SPHERENE_VM_MIB, and every active
#                     slot without a VM may boot one; capped by the slice's MemoryMax - MemoryCurrent.
#   hasteheart growth every ci-capacity slot account (members of group ci-capacity) that is running
#                     a job scope may still grow to HH_JOB_MIB (anon + shmem of its user slice).
#                     An idle slot account counts 0: ci-capacity grants only above its own
#                     MemAvailable floor, which a running Redoubt VM lowers.
#   host margin       llama-server's anonymous growth and the host itself (llama's model file is
#                     a reclaimable mapping and its weights sit on the 5090).
#   start when room >= NEED_MIB (VM -m 24576 + QEMU overhead) and memory PSI some avg60 <= MAX_PSI.
# Nothing here opens, locks or writes another project's files; it reads /proc, the cgroup tree and
# systemctl show/list-units.
set -euo pipefail
export LC_ALL=C

UNIT=redoubt-ci-vm.service
CONF=${XDG_CONFIG_HOME:-$HOME/.config}/redoubt-boxb.env
# Defaults; ~/.config/redoubt-boxb.env may override these keys (parsed, never sourced).
NEED_MIB=26112
SPHERENE_VM_MIB=8704
HH_JOB_MIB=10240
HOST_MARGIN_MIB=2048
MAX_PSI=10
GHCI_SLICE=machine-ghci.slice
SLOT_UNIT_GLOB='gh-runner-slot@*.service'
HH_GROUP=ci-capacity
HH_SCOPE_GLOB='fivur-slot-*.scope'
CG=${REDOUBT_CGROUP_ROOT:-/sys/fs/cgroup}
PROC=${REDOUBT_PROC_ROOT:-/proc}
if [[ -r $CONF ]]; then
  while IFS='=' read -r key value; do
    case $key in
      NEED_MIB|SPHERENE_VM_MIB|HH_JOB_MIB|HOST_MARGIN_MIB|MAX_PSI)
        [[ $value =~ ^[0-9]{1,7}$ ]] || { echo "bad $key in $CONF" >&2; exit 2; }
        printf -v "$key" '%s' "$value" ;;
      ''|'#'*) ;;
      *) echo "unknown key $key in $CONF" >&2; exit 2 ;;
    esac
  done < "$CONF"
fi

log() { logger -t redoubt-boxb-ctl -- "$*" 2>/dev/null || true; printf '%s\n' "$*"; }
mib_of_stat() {  # anon + shmem of a cgroup, MiB (0 when unreadable)
  awk '$1 == "anon" || $1 == "shmem" {s += $2} END {print int(s / 1048576)}' "$1/memory.stat" 2>/dev/null || echo 0
}

gate() {
  local avail psi scope grown slots=0 vms=0 sph=0 head max cur hh=0 hh_note="" member uid slice
  avail=$(awk '$1 == "MemAvailable:" {print int($2 / 1024)}' "$PROC/meminfo")
  psi=$(awk '$1 == "some" {sub("avg60=", "", $3); print int($3)}' "$PROC/pressure/memory" 2>/dev/null || echo 0)
  # spherene (the other project's libvirt VMs), read-only.
  for scope in "$CG/machine.slice/$GHCI_SLICE"/*.scope; do
    [[ -d $scope ]] || continue
    vms=$(( vms + 1 ))
    grown=$(mib_of_stat "$scope")
    (( grown < SPHERENE_VM_MIB )) && sph=$(( sph + SPHERENE_VM_MIB - grown ))
  done
  slots=$(systemctl list-units --state=active --no-legend --plain "$SLOT_UNIT_GLOB" 2>/dev/null | wc -l)
  (( slots > vms )) && sph=$(( sph + (slots - vms) * SPHERENE_VM_MIB ))
  max=$(systemctl show "$GHCI_SLICE" -p MemoryMax --value 2>/dev/null || true)
  cur=$(systemctl show "$GHCI_SLICE" -p MemoryCurrent --value 2>/dev/null || true)
  [[ $cur =~ ^[0-9]+$ ]] || cur=0
  if [[ $max =~ ^[0-9]+$ ]]; then
    head=$(( max > cur ? (max - cur) / 1048576 : 0 ))
    (( sph > head )) && sph=$head
  fi
  # hasteheart slot accounts with a running job.
  for member in $(getent group "$HH_GROUP" | cut -d: -f4 | tr ',' ' '); do
    uid=$(id -u "$member" 2>/dev/null) || continue
    [[ $uid != "$(id -u)" ]] || continue
    slice=$CG/user.slice/user-$uid.slice
    compgen -G "$slice/user@$uid.service/app.slice/$HH_SCOPE_GLOB" >/dev/null || continue
    grown=$(mib_of_stat "$slice")
    (( grown < HH_JOB_MIB )) && hh=$(( hh + HH_JOB_MIB - grown ))
    hh_note+="${hh_note:+, }$member job grown $grown"
  done
  ROOM=$(( avail - sph - hh - HOST_MARGIN_MIB ))
  GATE_DETAIL="room $ROOM MiB = MemAvailable $avail - spherene growth $sph ($vms VM(s), $slots slot(s)) - hasteheart growth $hh (${hh_note:-no job running}) - host margin $HOST_MARGIN_MIB; need $NEED_MIB; memory PSI some avg60 $psi (max $MAX_PSI)"
  (( ROOM >= NEED_MIB && psi <= MAX_PSI ))
}

if [[ -n ${SSH_ORIGINAL_COMMAND+x} ]]; then
  read -r -a words <<< "$SSH_ORIGINAL_COMMAND"
else
  words=("$@")
fi
verb=${words[0]:-}
reason=${words[*]:1}
reason=${reason//[^A-Za-z0-9 ._:\/()=,-]/}
reason=${reason:0:300}

state=$(systemctl --user show "$UNIT" -p ActiveState --value)
case $verb in
  status)
    entered=$(systemctl --user show --timestamp=unix "$UNIT" -p ActiveEnterTimestamp --value)
    printf 'state=%s entered=%s\n' "$state" "${entered#@}" ;;
  gate)
    if gate; then echo "gate ok: $GATE_DETAIL"; else echo "gate defer: $GATE_DETAIL"; exit 3; fi ;;
  start)
    exec 9>"${XDG_RUNTIME_DIR:-/tmp}/redoubt-boxb-ctl.lock"
    flock -w 30 9
    state=$(systemctl --user show "$UNIT" -p ActiveState --value)
    if [[ $state != inactive && $state != failed ]]; then
      echo "not starting: $UNIT is $state"; exit 0
    fi
    if ! gate; then
      log "deferring start (${reason:-no reason given}): $GATE_DETAIL"; exit 3
    fi
    log "starting $UNIT (${reason:-no reason given}): $GATE_DETAIL"
    systemctl --user reset-failed "$UNIT" 2>/dev/null || true
    systemctl --user start --no-block "$UNIT" ;;
  stop)
    exec 9>"${XDG_RUNTIME_DIR:-/tmp}/redoubt-boxb-ctl.lock"
    flock -w 30 9
    log "stopping $UNIT (${reason:-requested})"
    systemctl --user stop "$UNIT" ;;
  *)
    echo "usage: boxb-ctl.sh status | gate | start REASON | stop [REASON]" >&2; exit 2 ;;
esac
