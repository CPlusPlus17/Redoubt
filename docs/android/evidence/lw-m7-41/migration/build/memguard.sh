#!/bin/bash
# pause lw- build containers when MemAvailable < 8.25 GB; resume when > 10 GB
LOG=/home/mgysin/redoubt-artifacts/beta5/work/memguard.log
paused=""
while true; do
  a=$(awk '/MemAvailable/{print $2}' /proc/meminfo)
  if [ -z "$paused" ] && [ "$a" -lt 8650752 ]; then
    for c in $(podman ps --format '{{.Names}}' | grep -E '^lw-'); do podman pause "$c" >/dev/null && paused="$paused $c"; done
    [ -n "$paused" ] && echo "$(date -u +%FT%TZ) PAUSE $paused MemAvailable=$a" >> $LOG
  elif [ -n "$paused" ] && [ "$a" -gt 10485760 ]; then
    for c in $paused; do podman unpause "$c" >/dev/null; done
    echo "$(date -u +%FT%TZ) RESUME $paused MemAvailable=$a" >> $LOG; paused=""
  fi
  sleep 3
done
