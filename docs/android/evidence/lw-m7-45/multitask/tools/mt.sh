#!/bin/bash
# LW-M7-45 multi-task device driver (source after doq.sh and doq2.sh).
#   tasks <label>            -- the app's tasks and activities (dumpsys) to $EV/<label>-tasks.txt
#   openpwa <url>            -- a legacy (Fennec) web-app shortcut intent: FennecWebAppIntentProcessor
#                               -> ExternalAppBrowserActivity in its own document task (NEW_DOCUMENT)
#   openforeignct <url>      -- a custom tab opened by the test client app ctclient inside ITS task
#   marker                   -- the marker file's state line
CT=org.redoubt.ctclient

tasks(){
  $A shell dumpsys activity activities > $EV/$1-activities.txt
  grep -E '^\s*\* Task\{|\* ActivityRecord\{|Hist  #' $EV/$1-activities.txt | grep -E "redoubt|$CT" > $EV/$1-tasks.txt
  log "tasks [$1]: $(grep -E '\* Task\{' $EV/$1-tasks.txt | sed -E 's/.*Task\{[0-9a-f]+ #([0-9]+) [^ ]* ?(A=[^ ]*)?.*/#\1 \2/' | tr '\n' ';') | activities: $(grep -oE 'ActivityRecord\{[0-9a-f]+ u0 [^ ]+ t[0-9]+' $EV/$1-tasks.txt | awk '{print $3"@"$4}' | sort -u | tr '\n' ' ')"
}

marker(){ $A shell "cat /data/data/$PKG/no_backup/redoubt_session_end 2>/dev/null" | grep state= | tr -d '\r'; }

openpwa(){
  local P=$(profdir) own=$($A shell stat -c %u:%g /data/data/$PKG | tr -d '\r')
  cat > $EV/pwa-manifest.json <<J
{"manifest": {"name": "DOQ PWA", "short_name": "DOQ", "start_url": "http://10.0.2.2:8765/report.html?tag=pwa-start", "scope": "http://10.0.2.2:8765/", "display": "standalone"}}
J
  $A push $EV/pwa-manifest.json /data/local/tmp/doq-pwa.json >/dev/null
  $A shell "mkdir -p $P/manifests && cp /data/local/tmp/doq-pwa.json $P/manifests/doq.json && chown -R $own $P/manifests && chmod 700 $P/manifests && chmod 600 $P/manifests/doq.json && restorecon -R $P/manifests"
  wake
  $A shell am start -a org.mozilla.gecko.WEBAPP -n $PKG/org.mozilla.gecko.LauncherActivity -d "'$1'" --es MANIFEST_PATH "$P/manifests/doq.json" > /dev/null
}

openforeignct(){ wake; $A shell am start -n $CT/.Main --es url "'$1'" >/dev/null; }

# Populate the main task: two pages that set cookies + localStorage, then wait for autosave.
populate(){
  $A logcat -c; launch; sleep 10
  uitap '^OK$' >/dev/null
  openurl "http://10.0.2.2:8765/a.html"; sleep 6
  openurl "http://10.0.2.2:8765/b.html"; sleep 6
  log "populated; waiting 35 s for session autosave and cookie flush"; sleep 35
}

grab(){ # label: logcat + filtered
  $A logcat -d -v threadtime > $EV/$1-logcat.txt
  grep -E "RedoubtDeleteOnQuit|Start proc .*$PKG|Killing .*$PKG|ActivityTaskManager: START|onTaskRemoved" $EV/$1-logcat.txt > $EV/$1-logcat.filtered.txt || true
  log "$1 guard lines: $(grep RedoubtDeleteOnQuit $EV/$1-logcat.txt | sed -E 's/.*RedoubtDeleteOnQuit: //' | tr '\n' '|' | cut -c1-900)"
}
