#!/bin/bash
# LW-M7-45 multi-task fix, regressions: single-task swipe -> cold start deletes; Quit -> clean.
D=/home/mgysin/redoubt-artifacts/delete-on-quit
export EV=${EV:-$D/evidence-run4} SER=${SER:-emulator-5596}
source $D/dev/doq.sh
source $D/dev/doq2.sh
source $D/dev/mt.sh
runcase C1-single-swipe on swipe
filterlog $EV/C1-single-swipe-2-exit-logcat.txt $EV/C1-single-swipe-2-exit-logcat.filtered.txt
filterlog $EV/C1-single-swipe-3-coldstart-logcat.txt $EV/C1-single-swipe-3-coldstart-logcat.filtered.txt
runcase C2-quit on quit
filterlog $EV/C2-quit-2-exit-logcat.txt $EV/C2-quit-2-exit-logcat.filtered.txt
filterlog $EV/C2-quit-3-coldstart-logcat.txt $EV/C2-quit-3-coldstart-logcat.filtered.txt
log "BATCH DONE"
