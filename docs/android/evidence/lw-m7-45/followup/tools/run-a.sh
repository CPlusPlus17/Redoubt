#!/bin/bash
D=/home/mgysin/redoubt-artifacts/delete-on-quit
export EV=$D/evidence-run2 SER=emulator-5596
source $D/dev/doq.sh
source $D/dev/doq2.sh
log "APK $(sha256sum $D/apk/redoubt-doq3-x86_64-throwaway.apk | cut -c1-64)"
log "first run"; $A logcat -c; launch; sleep 15; uitap '^OK$'; $A logcat -d -v threadtime > $EV/00-first-run-logcat.txt
for c in "$@"; do
  set -- $(echo $c | tr ':' ' ')
  runcase "$1" "$2" "$3"
done
log "BATCH DONE"
