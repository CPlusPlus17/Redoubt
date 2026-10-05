#!/bin/bash
# redoubt-boxb-ondemand: run box B's Redoubt CI VM only while CPlusPlus17/Redoubt has work for it.
#
# Runs on box A (the workstation, where `gh` is logged in), one pass per invocation, from the user
# timer redoubt-boxb-ondemand.timer every 60 s. Ported from ~/.local/lib/redoubt-ondemand/
# redoubt-ondemand.sh (box A's own VM), with the difference that box B holds no GitHub credential:
# this side reads the queue, and box B's boxb-ctl.sh (reached with a key that can run nothing else)
# makes the memory decision and starts or stops the VM unit there.
#
#   start      the VM is down and a job is queued whose labels are all among the runner's labels
#              (GitHub's matching rule, case-insensitive): ask box B to start; box B starts only
#              if its gate finds room and logs "deferring start" with the numbers otherwise.
#   stop       the VM is up, nothing matching is queued or in progress and the runner is not busy,
#              for IDLE_MINUTES in a row (and up >= MIN_UPTIME_MINUTES), re-checked right before
#              stopping.
#   keepalive  GitHub deletes a persistent runner that has not connected for 14 days, so the VM is
#              also started (for one idle period) when it has not been up for KEEPALIVE_DAYS.
#
# GitHub is only read (gh api GETs). If a read fails, or box B cannot be reached, the pass changes
# nothing. Manual work in the VM: touch ~/.local/state/redoubt-boxb-ondemand/hold. REDOUBT_DRY_RUN=1
# prints the decision (and box B's read-only gate) and acts on nothing.
set -euo pipefail
export GH_PROMPT_DISABLED=1 GH_NO_UPDATE_NOTIFIER=1 NO_COLOR=1

REPO=${REDOUBT_REPO:-CPlusPlus17/Redoubt}
RUNNER_NAME=${REDOUBT_RUNNER_NAME:-redoubt-ci-boxb}
RUNNER_LABELS=${REDOUBT_RUNNER_LABELS:-self-hosted,Linux,X64,redoubt-boxb}
IDLE_MINUTES=${REDOUBT_IDLE_MINUTES:-15}
MIN_UPTIME_MINUTES=${REDOUBT_MIN_UPTIME_MINUTES:-10}
KEEPALIVE_DAYS=${REDOUBT_KEEPALIVE_DAYS:-7}
CONTROL=${REDOUBT_BOXB_CONTROL:-$HOME/.local/state/redoubt-boxb-control}
BOXB=${REDOUBT_BOXB_HOST:-user@10.0.0.154}
STATE=${XDG_STATE_HOME:-$HOME/.local/state}/redoubt-boxb-ondemand
DRY_RUN=${REDOUBT_DRY_RUN:-0}

for v in IDLE_MINUTES MIN_UPTIME_MINUTES KEEPALIVE_DAYS DRY_RUN; do
  [[ ${!v} =~ ^[0-9]+$ ]] || { echo "ERROR: $v must be a whole number, got '${!v}'" >&2; exit 2; }
done

log() { printf '%s\n' "$*"; }
get() { cat "$STATE/$1" 2>/dev/null || true; }
put() { if (( ! DRY_RUN )); then printf '%s\n' "$2" > "$STATE/$1"; fi; }
del() { if (( ! DRY_RUN )); then rm -f "$STATE/$1"; fi; }
# say KEY MSG [DETAIL]: log when MSG changes, and every 10 min while it repeats.
say() {
  local now last t
  now=$(date +%s)
  last=$(get "say.$1")
  t=${last%% *}
  [[ $t =~ ^[0-9]+$ ]] || t=0
  if (( DRY_RUN )) || [[ ${last#* } != "$2" ]] || (( now - t >= 600 )); then
    log "$2${3:+ $3}"
    put "say.$1" "$now $2"
  fi
}
# ctl VERB [ARGS]: run boxb-ctl.sh on box B. The key is bound to that script by authorized_keys,
# so the words below are its only input; the host key is pinned.
ctl() {
  ssh -F /dev/null -i "$CONTROL/ondemand_ed25519" -o IdentitiesOnly=yes -o BatchMode=yes \
    -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$CONTROL/known_hosts" \
    -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 \
    "$BOXB" "$*" </dev/null
}

# survey: same reads and matching rule as redoubt-ondemand.sh. Sets QUEUED, RUNNING, QUEUED_NAMES,
# RUNNER_STATUS, RUNNER_BUSY. Non-zero if any read fails.
survey() {
  local q p ids id j jobs runners runner labels summary
  q=$(gh api "repos/$REPO/actions/runs?status=queued&per_page=100") || return 1
  p=$(gh api "repos/$REPO/actions/runs?status=in_progress&per_page=100") || return 1
  ids=$(printf '%s\n%s\n' "$q" "$p" | jq -r '.workflow_runs[].id' | sort -u) || return 1
  jobs=$(for id in $ids; do
      j=$(gh api "repos/$REPO/actions/runs/$id/jobs?filter=latest&per_page=100") || exit 1
      jq -c '[.jobs[] | {status, labels, runner_name, name, workflow_name, run_id}]' <<<"$j" || exit 1
    done | jq -sc 'add // []') || return 1
  runners=$(gh api "repos/$REPO/actions/runners?per_page=100") || return 1
  runner=$(jq -c --arg n "$RUNNER_NAME" 'first(.runners[] | select(.name == $n)) // {}' <<<"$runners") || return 1
  RUNNER_STATUS=$(jq -r '.status // "absent"' <<<"$runner")
  RUNNER_BUSY=$(jq -r '.busy // false' <<<"$runner")
  labels=$(jq -c '[.labels[]?.name | ascii_downcase]' <<<"$runner")
  if [[ $labels == '[]' ]]; then
    labels=$(jq -Rc 'split(",") | map(ascii_downcase)' <<<"$RUNNER_LABELS")
  fi
  summary=$(jq -c --argjson L "$labels" --arg n "$RUNNER_NAME" '
    def ours: (.labels | map(ascii_downcase)) as $want
              | ($want | length) > 0 and all($want[]; . as $x | any($L[]; . == $x));
    { queued: [.[] | select(.status == "queued" and ours)],
      running: [.[] | select(.status == "in_progress" and (ours or .runner_name == $n))] }
    | { queued: (.queued | length), running: (.running | length),
        names: ([.queued[] | "\(.workflow_name // "?")/\(.name) (run \(.run_id))"] | join(", ")) }' <<<"$jobs") || return 1
  QUEUED=$(jq -r .queued <<<"$summary")
  RUNNING=$(jq -r .running <<<"$summary")
  QUEUED_NAMES=$(jq -r .names <<<"$summary")
}

hhmm() { date -d "@$1" +%H:%M; }

# ------------------------------------------------------------------------------------------------
install -d -m 0700 "$STATE"
[[ -r $CONTROL/ondemand_ed25519 && -r $CONTROL/known_hosts ]] ||
  { log "ERROR: $CONTROL has no ondemand key or known_hosts (run install-poller.sh)"; exit 1; }
now=$(date +%s)
if ! status=$(ctl status); then
  say boxb "box B not reachable or boxb-ctl failed; nothing done"
  exit 0
fi
say boxb "box B reachable"
state=$(sed -n 's/^state=\([a-z-]*\) .*/\1/p' <<<"$status")
entered=$(sed -n 's/.* entered=\([0-9]*\)$/\1/p' <<<"$status")
case $state in
  active) up=1 ;;
  inactive|failed) up=0 ;;
  *) say unit "box B VM unit is '${state:-unknown}'; checking again next pass"; exit 0 ;;
esac
if (( up )); then put last_active "$now"; fi
last_active=$(get last_active)
if [[ ! $last_active =~ ^[0-9]+$ ]]; then last_active=$now; put last_active "$now"; fi

if ! survey; then
  say api "GitHub API not readable; leaving box B's VM $state"
  exit 0
fi
say api "GitHub API readable"

if (( ! up )); then
  del idle_since
  want=""
  if (( QUEUED > 0 )); then
    want="$QUEUED queued job(s): $QUEUED_NAMES"
  elif (( KEEPALIVE_DAYS > 0 && now - last_active >= KEEPALIVE_DAYS * 86400 )); then
    want="keepalive: not up for ${KEEPALIVE_DAYS}d, GitHub drops runners offline for 14d"
  fi
  if [[ -z $want ]]; then
    say state "box B VM $state; nothing queued for $RUNNER_NAME"
    exit 0
  fi
  if (( DRY_RUN )); then
    log "dry-run, not done: ask box B to start ($want)"
    ctl gate || true
    exit 0
  fi
  # The reason is truncated for the log on box B; the full list stays in this journal.
  set +e
  out=$(ctl start "${want:0:200}")
  rc=$?
  set -e
  case $rc in
    0) log "box B: $out"; put last_active "$now"; del say.state ;;
    3) say state "deferring start ($want):" "box B says: ${out#deferring start*): }" ;;
    *) say state "start request failed (exit $rc): $out" ;;
  esac
  exit 0
fi

# The VM is up.
[[ $entered =~ ^[0-9]+$ ]] || entered=$now
uptime_s=$(( now - entered ))
if (( uptime_s > MIN_UPTIME_MINUTES * 60 )) && [[ $RUNNER_STATUS != online ]]; then
  say runner "warning: $RUNNER_NAME is '$RUNNER_STATUS' although box B's VM is up (CI-VM.md: Box B, registration)" "(up $(( uptime_s / 60 )) min)"
fi
if (( QUEUED > 0 || RUNNING > 0 )) || [[ $RUNNER_BUSY == true ]]; then
  del idle_since
  say state "working:" "queued=$QUEUED in_progress=$RUNNING runner=$RUNNER_STATUS busy=$RUNNER_BUSY"
  exit 0
fi
since=$(get idle_since)
if [[ ! $since =~ ^[0-9]+$ ]]; then since=$now; put idle_since "$now"; fi
due=$(( since + IDLE_MINUTES * 60 ))
min_up_due=$(( entered + MIN_UPTIME_MINUTES * 60 ))
if (( min_up_due > due )); then due=$min_up_due; fi
if [[ -e $STATE/hold ]]; then
  say state "idle since $(hhmm "$since"), but $STATE/hold exists: not stopping"
  exit 0
fi
if (( now < due )); then
  say state "idle since $(hhmm "$since") (runner $RUNNER_STATUS); stop due $(hhmm "$due")"
  exit 0
fi
if ! survey; then
  say api "GitHub API not readable at the stop re-check; not stopping"
  exit 0
fi
if (( QUEUED > 0 || RUNNING > 0 )) || [[ $RUNNER_BUSY == true ]]; then
  del idle_since
  log "work appeared at the stop re-check; staying up"
  exit 0
fi
if (( DRY_RUN )); then
  log "dry-run, not done: stop box B's VM after $(( (now - since) / 60 )) min idle"
  exit 0
fi
log "stopping box B's VM after $(( (now - since) / 60 )) min idle"
if ctl stop "idle $(( (now - since) / 60 )) min"; then
  put last_active "$now"
  del idle_since
  del say.state
else
  log "stop request failed; retrying next pass"
fi
