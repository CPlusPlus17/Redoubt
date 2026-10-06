#!/bin/bash
D=/home/mgysin/redoubt-artifacts/delete-on-quit
export EV=$D/evidence-run2 SER=emulator-5596
source $D/dev/doq.sh
source $D/dev/doq2.sh
name=c7-bgfg
log "=== case $name: setting on (all), populate, HOME, wait, return (twice); no deletion expected"
setprefs on
$A logcat -c; launch; sleep 10
openurl "http://10.0.2.2:8765/a.html"; sleep 6
openurl "http://10.0.2.2:8765/b.html"; sleep 6
log "populated; waiting 35 s"; sleep 35
log "before: $(snapshot $name-before)"
$A logcat -c
for i in 1 2; do wake; $A shell input keyevent KEYCODE_HOME; sleep 20; launch; sleep 8; done
$A logcat -d -v threadtime > $EV/$name-logcat.txt
filterlog $EV/$name-logcat.txt $EV/$name-logcat.filtered.txt
log "deletion lines during bg/fg: $(grep -c 'cold start after\|deleting' $EV/$name-logcat.txt)"
log "after: $(snapshot $name-after)"
log "BATCH DONE"
