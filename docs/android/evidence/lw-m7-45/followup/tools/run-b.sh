#!/bin/bash
# New cases (follow-up): link and custom-tab cold starts after a swipe, HISTORY-without-TABS, its control.
D=/home/mgysin/redoubt-artifacts/delete-on-quit
export EV=$D/evidence-run2 SER=emulator-5596
source $D/dev/doq.sh
source $D/dev/doq2.sh
for c in "$@"; do
  IFS=: read name kind mode extra cats <<< "$c"
  if [ "$kind" = history ]; then CATS=$cats runcase_history "$name" "$mode" "$extra"
  elif [ "$kind" = start ]; then CATS=$cats runcase_start "$name" "$mode" swipe "$extra"
  else CATS=$cats runcase "$name" "$mode" "$extra"; fi
done
log "BATCH DONE"
