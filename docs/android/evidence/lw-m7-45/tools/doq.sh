#!/bin/bash
# LW-M7-45 device driver (source it). Serial is fixed to this run's emulator.
D=/home/mgysin/redoubt-artifacts/delete-on-quit
SER=${SER:-emulator-5596}
A="/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $SER"
PKG=org.redoubtbrowser
EV=${EV:-$D/evidence-run}
mkdir -p $EV
log(){ echo "$(date -u +%FT%TZ) $*" | tee -a $EV/driver.log; }

wake(){ $A shell input keyevent KEYCODE_WAKEUP; $A shell wm dismiss-keyguard >/dev/null 2>&1; }
mainpid(){ $A shell pidof $PKG 2>/dev/null | tr ' ' '\n' | head -1; }
procs(){ $A shell "ps -A -o PID,NAME | grep $PKG" | tr -s ' ' | tr '\n' ';'; }

# Writes the delete-on-quit prefs. on|off ; app is force-stopped first.
setprefs(){
  local mode=$1 v=true
  [ "$mode" = off ] && v=false
  $A shell am force-stop $PKG
  local f=/data/data/$PKG/shared_prefs/fenix_preferences.xml
  $A shell "cat $f" > $EV/prefs.in.xml 2>/dev/null
  python3 - "$EV/prefs.in.xml" "$EV/prefs.out.xml" "$v" <<'PY'
import sys, re
src, dst, v = sys.argv[1:]
try: s = open(src).read()
except FileNotFoundError: s = ""
if "<map" not in s: s = "<?xml version='1.0' encoding='utf-8' standalone='yes' ?>\n<map>\n</map>\n"
keys = ["pref_key_delete_browsing_data_on_quit", "pref_key_delete_open_tabs_on_quit", "pref_key_delete_browsing_history_on_quit",
        "pref_key_delete_cookies_and_site_data_on_quit", "pref_key_delete_caches_on_quit", "pref_key_delete_permissions_on_quit",
        "pref_key_delete_downloads_on_quit"]
for k in keys:
    s = re.sub(r'\s*<boolean name="%s" value="[a-z]+" />' % re.escape(k), "", s)
    val = v if k == keys[0] else "true"   # categories all on; the master switch decides
    s = s.replace("</map>", '    <boolean name="%s" value="%s" />\n</map>' % (k, val))
# Test environment only: the server is plain HTTP on 10.0.2.2, which HTTPS-only would upgrade.
s = re.sub(r'\s*<boolean name="pref_key_https_only" value="[a-z]+" />', "", s)
s = s.replace("</map>", '    <boolean name="pref_key_https_only" value="false" />\n</map>')
open(dst, "w").write(s)
PY
  $A push $EV/prefs.out.xml /data/local/tmp/fp.xml >/dev/null
  local own=$($A shell stat -c %u:%g /data/data/$PKG)
  $A shell "mkdir -p /data/data/$PKG/shared_prefs && cp /data/local/tmp/fp.xml $f && chown $own $f /data/data/$PKG/shared_prefs && chmod 660 $f && restorecon -R /data/data/$PKG/shared_prefs"
  log "prefs: delete-on-quit master=$v, all six categories true"
}

launch(){ wake; $A shell monkey -p $PKG -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; }
openurl(){ wake; $A shell am start -a android.intent.action.VIEW -d "$1" $PKG >/dev/null; }

# Gecko profile dir (relative to app data)
profdir(){ $A shell "ls -d /data/data/$PKG/files/mozilla/*.default 2>/dev/null" | head -1 | tr -d '\r'; }

# Copies the stores to $EV/<label>/ and prints a summary line.
snapshot(){
  local label=$1 out=$EV/$1; mkdir -p $out
  local P=$(profdir)
  $A shell "cd /data/data/$PKG && ls -la files/ no_backup/ 2>/dev/null" > $out/ls.txt
  $A shell "cat /data/data/$PKG/no_backup/redoubt_session_end 2>/dev/null" > $out/marker.txt
  for f in cookies.sqlite cookies.sqlite-wal permissions.sqlite permissions.sqlite-wal; do $A shell "cat $P/$f 2>/dev/null" > $out/$f; done
  for f in places.sqlite places.sqlite-wal; do $A shell "cat /data/data/$PKG/files/$f 2>/dev/null" > $out/$f; done
  $A shell "ls /data/data/$PKG/files/ | grep session_storage" > $out/session_files.txt
  $A shell "cat /data/data/$PKG/files/mozilla_components_session_storage_gecko.json 2>/dev/null" > $out/session.json
  $A shell "ls -d $P/storage/default/* 2>/dev/null" > $out/storage_default.txt
  $A shell "ls $P/../../../cache/mozilla/*/cache2/entries 2>/dev/null | wc -l; ls /data/data/$PKG/cache 2>/dev/null" > $out/cache.txt
  python3 - "$out" <<'PY'
import sqlite3, sys, os, json, shutil, tempfile
out = sys.argv[1]
def q(db, sql):
    p = os.path.join(out, db)
    if not os.path.exists(p) or os.path.getsize(p) == 0: return "no-db"
    t = tempfile.mkdtemp(); shutil.copy(p, t)
    w = p + "-wal"
    if os.path.exists(w) and os.path.getsize(w): shutil.copy(w, os.path.join(t, db + "-wal"))
    try: return [list(r) for r in sqlite3.connect(os.path.join(t, db)).execute(sql)]
    except Exception as e: return "err:%s" % e
s = {
 "marker": open(os.path.join(out, "marker.txt")).read().replace("\n", " ").strip(),
 "cookies_10.0.2.2": q("cookies.sqlite", "select name from moz_cookies where host like '%10.0.2.2%' order by name"),
 "history_10.0.2.2": q("places.sqlite", "select url from moz_places where url like '%10.0.2.2%' order by url"),
 "session_files": open(os.path.join(out, "session_files.txt")).read().split(),
 "session_tabs": (lambda t: len(json.loads(t).get("sessionStateTuples", [])) if t.strip() else 0)(open(os.path.join(out, "session.json")).read()),
 "ls_origins": [l.split("/")[-1] for l in open(os.path.join(out, "storage_default.txt")).read().split() if "10.0.2.2" in l],
}
json.dump(s, open(os.path.join(out, "summary.json"), "w"), indent=1)
print(json.dumps(s))
PY
}

# Exit methods
exit_swipe(){
  wake; $A shell input keyevent KEYCODE_APP_SWITCH; sleep 2.5
  $A exec-out screencap -p > $EV/$1-recents.png
  $A shell input swipe 540 1400 540 150 120; sleep 4
  $A exec-out screencap -p > $EV/$1-after-swipe.png
  $A shell input keyevent KEYCODE_HOME
}
exit_forcestop(){ $A shell am force-stop $PKG; }
exit_kill9(){ local p=$(mainpid); log "kill -9 main pid $p"; $A shell kill -9 $p; }
uitap(){ # tap the first node whose text or content-desc matches $1
  $A shell uiautomator dump /data/local/tmp/ui.xml >/dev/null 2>&1
  $A shell cat /data/local/tmp/ui.xml > $EV/ui.xml
  python3 - "$EV/ui.xml" "$1" <<'PY' | { read x y; [ -n "$x" ] && $A shell input tap $x $y && echo "tapped $x $y"; }
import re, sys
xml, pat = open(sys.argv[1]).read(), re.compile(sys.argv[2])
for m in re.finditer(r'<node [^>]*>', xml):
    n = m.group(0)
    t = re.search(r' text="([^"]*)"', n).group(1); d = re.search(r'content-desc="([^"]*)"', n).group(1)
    if pat.search(t) or pat.search(d):
        b = list(map(int, re.findall(r'\d+', re.search(r'bounds="([^"]*)"', n).group(1))))
        print((b[0]+b[2])//2, (b[1]+b[3])//2); break
PY
}

# One full case: populate under prefs <mode>, exit via <exit>, cold start, record.
runcase(){
  local name=$1 mode=$2 how=$3
  log "=== case $name: setting $mode, exit $how"
  setprefs $mode
  $A logcat -c; launch; sleep 10
  uitap '^OK$' >/dev/null
  $A logcat -d -v threadtime > $EV/$name-0-setup-logcat.txt
  openurl "http://10.0.2.2:8765/a.html"; sleep 6
  openurl "http://10.0.2.2:8765/b.html"; sleep 6
  log "populated; waiting 35 s for session autosave and cookie flush"; sleep 35
  $A exec-out screencap -p > $EV/$name-1-populated.png
  log "before exit: $(snapshot $name-before) procs=$(procs)"
  $A logcat -c
  case $how in
    swipe) exit_swipe $name ;;
    forcestop) exit_forcestop ;;
    kill9) exit_kill9 ;;
    quit) wake; uitap 'Main menu|More options|^Menu$' >/dev/null; sleep 2; $A exec-out screencap -p > $EV/$name-menu.png; uitap '^Quit'; sleep 6 ;;
  esac
  sleep 3
  $A logcat -d -v threadtime > $EV/$name-2-exit-logcat.txt
  log "after exit: procs=$(procs) exit-info: $($A shell dumpsys activity exit-info $PKG | grep -m1 -E 'reason=|description=' | tr -s ' ')"
  $A shell dumpsys activity exit-info $PKG > $EV/$name-2-exit-info.txt
  $A shell "cat /data/data/$PKG/no_backup/redoubt_session_end" > $EV/$name-2-marker-after-exit.txt
  if [ -n "$(mainpid)" ]; then log "process still alive after $how; marker: $(tr '\n' ' ' < $EV/$name-2-marker-after-exit.txt)"; fi
  $A logcat -c
  log "cold start"
  launch; sleep 15
  $A logcat -d -v threadtime > $EV/$name-3-coldstart-logcat.txt
  $A exec-out screencap -p > $EV/$name-3-coldstart.png
  log "after cold start: $(snapshot $name-after)"
  openurl "http://10.0.2.2:8765/report.html?tag=$name-after"; sleep 6
  $A exec-out screencap -p > $EV/$name-4-report.png
  log "server saw: $(grep "\"$name-after\"" $EV/server.jsonl | tail -1)"
  log "cached.js fetched since report: $(grep -c cached.js $EV/server.jsonl)"
}
