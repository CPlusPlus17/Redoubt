#!/bin/bash
D=/home/mgysin/redoubt-artifacts/delete-on-quit
export EV=$D/evidence-run2 SER=emulator-5596
source $D/dev/doq.sh
source $D/dev/doq2.sh
PMCLEAR=1 CATS=cookies runcase_history c21-history-kept-control-kill9 on kill9
PMCLEAR=1 CATS=history,cookies runcase_history c22-history-only-kill9 on kill9
log "BATCH DONE"
