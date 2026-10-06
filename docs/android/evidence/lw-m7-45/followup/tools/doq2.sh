#!/bin/bash
# LW-M7-45 follow-up device driver (source it after doq.sh). Adds:
#   CATS=<list> setprefs on|off  -- choose the categories (default: all six)
#   runcase_start <name> <mode> <exit> <start>  -- cold start through launch|view|ct
#   runcase_history <name> <mode>              -- one tab with h1 -> h2 history
# Serial and evidence dir as in doq.sh.

# Category keys by short name.
declare -A DOQ_KEY=(
  [tabs]=pref_key_delete_open_tabs_on_quit
  [history]=pref_key_delete_browsing_history_on_quit
  [cookies]=pref_key_delete_cookies_and_site_data_on_quit
  [caches]=pref_key_delete_caches_on_quit
  [permissions]=pref_key_delete_permissions_on_quit
  [downloads]=pref_key_delete_downloads_on_quit
)

setprefs(){
  local mode=$1 v=true
  [ "$mode" = off ] && v=false
  local cats=${CATS:-tabs,history,cookies,caches,permissions,downloads}
  $A shell am force-stop $PKG
  local f=/data/data/$PKG/shared_prefs/fenix_preferences.xml
  $A shell "cat $f" > $EV/prefs.in.xml 2>/dev/null
  local on=""
  for c in ${cats//,/ }; do on="$on ${DOQ_KEY[$c]}"; done
  python3 - "$EV/prefs.in.xml" "$EV/prefs.out.xml" "$v" "$on" <<'PY'
import sys, re
src, dst, v, on = sys.argv[1:]
on = on.split()
try: s = open(src).read()
except FileNotFoundError: s = ""
if "<map" not in s: s = "<?xml version='1.0' encoding='utf-8' standalone='yes' ?>\n<map>\n</map>\n"
master = "pref_key_delete_browsing_data_on_quit"
cats = ["pref_key_delete_open_tabs_on_quit", "pref_key_delete_browsing_history_on_quit",
        "pref_key_delete_cookies_and_site_data_on_quit", "pref_key_delete_caches_on_quit",
        "pref_key_delete_permissions_on_quit", "pref_key_delete_downloads_on_quit"]
for k in [master] + cats:
    s = re.sub(r'\s*<boolean name="%s" value="[a-z]+" />' % re.escape(k), "", s)
    val = v if k == master else ("true" if k in on else "false")
    s = s.replace("</map>", '    <boolean name="%s" value="%s" />\n</map>' % (k, val))
s = re.sub(r'\s*<boolean name="pref_key_https_only" value="[a-z]+" />', "", s)
s = s.replace("</map>", '    <boolean name="pref_key_https_only" value="false" />\n</map>')
open(dst, "w").write(s)
PY
  $A push $EV/prefs.out.xml /data/local/tmp/fp.xml >/dev/null
  local own=$($A shell stat -c %u:%g /data/data/$PKG)
  $A shell "mkdir -p /data/data/$PKG/shared_prefs && cp /data/local/tmp/fp.xml $f && chown $own $f /data/data/$PKG/shared_prefs && chmod 660 $f && restorecon -R /data/data/$PKG/shared_prefs"
  log "prefs: delete-on-quit master=$v, categories on: ${cats}"
}

# A custom tab, as a client app would send it: VIEW + the Custom Tabs session extra.
opencustomtab(){
  wake
  $A shell am start -a android.intent.action.VIEW -d "'$1'" \
    --es android.support.customtabs.extra.SESSION doq-test-client $PKG >/dev/null
}

# Back/forward entries per saved tab, from the session file's GeckoView state.
histcount(){ # file
  python3 - "$1" <<'PY'
import json, sys
t = open(sys.argv[1]).read().strip()
if not t: print("no-session-file"); sys.exit()
def dec(x):
    if isinstance(x, str) and x[:1] in "{[":
        try: return dec(json.loads(x))
        except Exception: return x
    if isinstance(x, dict): return {k: dec(v) for k, v in x.items()}
    if isinstance(x, list): return [dec(v) for v in x]
    return x
d = dec(json.loads(t))
out = []
for tup in d.get("sessionStateTuples", []):
    tab = tup.get("tab", {})
    es = tup.get("engineSession")
    entries = None
    def find(o):
        global entries
        if isinstance(o, dict):
            h = o.get("history")
            if isinstance(h, dict) and isinstance(h.get("entries"), list):
                return [e.get("url") for e in h["entries"]]
            for v in o.values():
                r = find(v)
                if r is not None: return r
        if isinstance(o, list):
            for v in o:
                r = find(v)
                if r is not None: return r
        return None
    out.append({"url": tab.get("url"), "history": find(es) if es else None})
print(json.dumps(out))
PY
}

filterlog(){ # in out
  grep -E "RedoubtDeleteOnQuit|Start proc .*$PKG|CreateEngineSessionAction|LinkEngineSessionAction|LoadUrlAction|AddCustomTabAction|AddTabAction|RestoreAction|RestoreCompleteAction|ActivityTaskManager: START" "$1" > "$2" || true
}

# Populate (two tabs), exit, then cold start through <start>:
#   launch  -- launcher; view -- a VIEW intent link; ct -- a custom tab.
runcase_start(){
  local name=$1 mode=$2 how=$3 start=$4
  log "=== case $name: setting $mode (${CATS:-all}), exit $how, cold start via $start"
  setprefs $mode
  $A logcat -c; launch; sleep 10
  uitap '^OK$' >/dev/null
  openurl "http://10.0.2.2:8765/a.html"; sleep 6
  openurl "http://10.0.2.2:8765/b.html"; sleep 6
  log "populated; waiting 35 s for session autosave and cookie flush"; sleep 35
  log "before exit: $(snapshot $name-before) procs=$(procs)"
  $A logcat -c
  case $how in
    swipe) exit_swipe $name ;;
    forcestop) exit_forcestop ;;
    kill9) exit_kill9 ;;
  esac
  sleep 3
  $A logcat -d -v threadtime > $EV/$name-2-exit-logcat.txt
  $A shell dumpsys activity exit-info $PKG > $EV/$name-2-exit-info.txt
  $A shell "cat /data/data/$PKG/no_backup/redoubt_session_end" > $EV/$name-2-marker-after-exit.txt
  log "after exit: procs=$(procs) marker=$(tr '\n' ' ' < $EV/$name-2-marker-after-exit.txt)"
  [ -n "$(mainpid)" ] && log "WARNING process still alive after $how"
  $A logcat -c
  local url="http://10.0.2.2:8765/report.html?tag=$name-first"
  log "cold start via $start: $url"
  case $start in
    launch) launch ;;
    view) openurl "$url" ;;
    ct) opencustomtab "$url" ;;
  esac
  sleep 15
  $A logcat -d -v threadtime > $EV/$name-3-coldstart-logcat.txt
  filterlog $EV/$name-3-coldstart-logcat.txt $EV/$name-3-coldstart-logcat.filtered.txt
  $A exec-out screencap -p > $EV/$name-3-coldstart.png
  log "after cold start: $(snapshot $name-after)"
  log "server saw: $(grep "\"$name-first\"" $EV/server.jsonl | tr '\n' ' ')"
}

# One tab with history (h1 -> h2), exit, launcher cold start, then Back.
runcase_history(){
  local name=$1 mode=$2 how=${3:-swipe}
  log "=== case $name: setting $mode (${CATS:-all}), one tab h1 -> h2, exit $how, then Back${PMCLEAR:+ (app data cleared first)}"
  [ -n "${PMCLEAR:-}" ] && $A shell pm clear $PKG >/dev/null
  setprefs $mode
  $A logcat -c; launch; sleep 10
  uitap '^OK$' >/dev/null
  openurl "http://10.0.2.2:8765/h1.html"; sleep 8
  log "populated; waiting 35 s for session autosave"; sleep 35
  log "before exit: $(snapshot $name-before) procs=$(procs)"
  log "before exit history: $(histcount $EV/$name-before/session.json)"
  $A logcat -c
  case $how in
    swipe) exit_swipe $name ;;
    kill9) exit_kill9 ;;
  esac
  sleep 3
  $A shell "cat /data/data/$PKG/no_backup/redoubt_session_end" > $EV/$name-2-marker-after-exit.txt
  log "after exit: procs=$(procs) marker=$(tr '\n' ' ' < $EV/$name-2-marker-after-exit.txt)"
  $A logcat -c
  log "cold start via launcher"
  launch; sleep 15
  $A exec-out screencap -p > $EV/$name-3-coldstart.png
  log "waiting 35 s for the session file to be rewritten"; sleep 35
  log "after: $(snapshot $name-after)"
  log "after history: $(histcount $EV/$name-after/session.json)"
  # Open the restored tab from the tabs tray (a fresh profile starts on the home screen).
  wake; log "tabs tray: $(uitap 'open tab|Tabs|tabs')"; sleep 3
  $A exec-out screencap -p > $EV/$name-3b-tray.png
  log "tab: $(uitap 'DOQ h2')"; sleep 8
  $A exec-out screencap -p > $EV/$name-3c-tab.png
  log "tab page reported: $(grep -E '/seen/h2/' $EV/server.jsonl | tail -1)"
  log "waiting 35 s for the session file to be rewritten with the loaded tab"; sleep 35
  log "loaded: $(snapshot $name-loaded)"
  log "loaded history: $(histcount $EV/$name-loaded/session.json)"
  # The tab's own Back control: the main menu's Back button is enabled only if
  # the session can go back. Read its state, then tap it.
  wake; uitap 'Main menu|More options|^Menu$' >/dev/null; sleep 3
  $A exec-out screencap -p > $EV/$name-4-menu.png
  $A shell uiautomator dump /data/local/tmp/ui.xml >/dev/null 2>&1; $A shell cat /data/local/tmp/ui.xml > $EV/$name-4-menu-ui.xml
  python3 - "$EV/$name-4-menu-ui.xml" <<'PY' | tee $EV/$name-4-back-button.txt | while read l; do log "$l"; done
import re, sys
xml = open(sys.argv[1]).read()
hits = []
for m in re.finditer(r'<node [^>]*>', xml):
    n = m.group(0)
    d = re.search(r'content-desc="([^"]*)"', n).group(1); t = re.search(r' text="([^"]*)"', n).group(1)
    if re.fullmatch(r'(Back|Go back|Navigate back)', d) or re.fullmatch(r'(Back|Go back)', t):
        hits.append((d or t, re.search(r'enabled="([a-z]+)"', n).group(1), re.search(r'bounds="([^"]*)"', n).group(1)))
print("menu Back control(s): %s" % hits)
print("BACK_ENABLED=%s" % (hits[0][1] if hits else "not-found"))
PY
  local mark=$(date +%Y-%m-%dT%H:%M:%S.%3N)
  log "tapping the menu's Back (server mark $mark): $(uitap '^(Back|Go back|Navigate back)$')"; sleep 6
  $A exec-out screencap -p > $EV/$name-5-after-back.png
  python3 - "$EV/server.jsonl" "$mark" <<'PY' | tee $EV/$name-5-back-result.txt | while read l; do log "$l"; done
import json, sys
mark = sys.argv[2]
recs = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
after = [r for r in recs if r["t"] >= mark]
print("requests after Back: %s" % [(r["t"], r["path"]) for r in after])
print("BACK_REACHED_H1=%s" % ("yes" if any(r["path"] == "/h1.html" for r in after) else "no"))
PY
}
