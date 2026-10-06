#!/bin/bash
# LW-M7-45 multi-task fix: device cases A (PWA task + main), B1 (custom tab in its own task + main),
# B2 (custom tab inside another app's task + main), then C (regressions) via run-c-mt.sh.
D=/home/mgysin/redoubt-artifacts/delete-on-quit
export EV=${EV:-$D/evidence-run3} SER=${SER:-emulator-5596}
source $D/dev/doq.sh
source $D/dev/doq2.sh
source $D/dev/mt.sh
APK=${APK:-$D/apk/redoubt-doq4-x86_64-throwaway.apk}
log "APK $(sha256sum $APK | cut -c1-64)"
log "version: $($A shell dumpsys package $PKG | grep -m1 versionName | tr -s ' ')"
[ -z "${SKIPFIRST:-}" ] && log "first run"; $A logcat -c; launch; sleep 15; uitap '^OK$'; $A logcat -d -v threadtime > $EV/00-first-run-logcat.txt

case_A(){
  local n=A-pwa
  log "=== case $n: main task (2 tabs, cookies) + PWA document task; swipe ONLY the PWA task, then the main task"
  setprefs on
  populate
  openpwa "http://10.0.2.2:8765/report.html?tag=$n-pwa-open"; sleep 10
  $A exec-out screencap -p > $EV/$n-1-pwa.png
  tasks $n-1
  log "before PWA swipe: $(snapshot $n-1-before) marker=$(marker) procs=$(procs)"
  $A logcat -c
  exit_swipe $n-2-pwa; sleep 4
  grab $n-2-pwa-swipe
  tasks $n-2
  log "after PWA swipe: procs=$(procs) marker=$(marker)"
  log "after PWA swipe: $(snapshot $n-2-after-pwa-swipe)"
  # The main task is still usable and still logged in: a page in it gets the cookies.
  launch; sleep 5
  openurl "http://10.0.2.2:8765/report.html?tag=$n-main-after-pwa-swipe"; sleep 8
  $A exec-out screencap -p > $EV/$n-3-main-report.png
  log "server saw: $(grep "\"$n-main-after-pwa-swipe\"" $EV/server.jsonl | tail -2 | tr '\n' ' ')"
  log "marker while main continues: $(marker)"
  log "waiting 35 s for session autosave"; sleep 35
  log "before main swipe: $(snapshot $n-3-before-main-swipe) procs=$(procs)"
  tasks $n-3
  $A logcat -c
  exit_swipe $n-4-main; sleep 4
  grab $n-4-main-swipe
  log "after main swipe: procs=$(procs) marker=$(marker) exit-info: $($A shell dumpsys activity exit-info $PKG | grep -m1 -E 'reason=' | tr -s ' ')"
  $A logcat -c
  log "cold start"
  launch; sleep 15
  grab $n-5-coldstart
  log "after cold start: $(snapshot $n-5-after)"
  openurl "http://10.0.2.2:8765/report.html?tag=$n-after"; sleep 8
  $A exec-out screencap -p > $EV/$n-5-report.png
  log "server saw: $(grep "\"$n-after\"" $EV/server.jsonl | tail -2 | tr '\n' ' ')"
}

case_B1(){
  local n=B1-ct-own-task
  log "=== case $n: main task (2 tabs, cookies) + custom tab started by am start (own task); swipe the main task"
  setprefs on
  populate
  opencustomtab "http://10.0.2.2:8765/report.html?tag=$n-ct-open"; sleep 10
  tasks $n-1
  launch; sleep 5     # bring the main task to the front
  tasks $n-1b
  log "before main swipe: $(snapshot $n-1-before) marker=$(marker) procs=$(procs)"
  $A logcat -c
  exit_swipe $n-2-main; sleep 4
  grab $n-2-main-swipe
  tasks $n-2
  log "after main swipe: procs=$(procs) marker=$(marker)"
  log "after main swipe: $(snapshot $n-2-after-main-swipe)"
  # Then the custom tab task goes too (the last task): a deletion is expected now or at the next cold start.
  $A logcat -c
  exit_swipe $n-3-ct; sleep 4
  grab $n-3-ct-swipe
  log "after custom-tab swipe: procs=$(procs) marker=$(marker)"
  $A logcat -c; launch; sleep 15
  grab $n-4-coldstart
  log "after cold start: $(snapshot $n-4-after)"
}

case_B2(){
  local n=B2-ct-foreign-task
  log "=== case $n: main task (2 tabs, cookies) + custom tab inside the ctclient app's task; swipe the main task"
  setprefs on
  populate
  openforeignct "http://10.0.2.2:8765/report.html?tag=$n-ct-open"; sleep 10
  $A exec-out screencap -p > $EV/$n-1-ct.png
  tasks $n-1
  launch; sleep 5
  tasks $n-1b
  log "before main swipe: $(snapshot $n-1-before) marker=$(marker) procs=$(procs)"
  $A logcat -c
  exit_swipe $n-2-main; sleep 4
  grab $n-2-main-swipe
  tasks $n-2
  log "after main swipe: procs=$(procs) marker=$(marker)"
  log "after main swipe: $(snapshot $n-2-after-main-swipe)"
  # The custom tab still works with the session's cookies: reload it from the client.
  openforeignct "http://10.0.2.2:8765/report.html?tag=$n-ct-after-main-swipe"; sleep 8
  $A exec-out screencap -p > $EV/$n-3-ct-after.png
  log "server saw: $(grep "\"$n-ct-after-main-swipe\"" $EV/server.jsonl | tail -2 | tr '\n' ' ')"
  # A later kill while the marker is running: the next cold start deletes.
  log "kill -9 main pid $(mainpid)"; $A shell kill -9 $(mainpid); sleep 3
  $A shell am force-stop $CT
  log "after kill: procs=$(procs) marker=$(marker)"
  $A logcat -c; launch; sleep 15
  grab $n-4-coldstart
  log "after cold start: $(snapshot $n-4-after)"
}

for c in ${@:-A B1 B2}; do case_$c; done
log "BATCH DONE"
