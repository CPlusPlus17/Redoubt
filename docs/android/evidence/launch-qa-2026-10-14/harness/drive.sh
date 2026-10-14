#!/bin/bash
# Real-device QA pass of the signed Redoubt 158.0-2 arm64 release APK.
# usage: drive.sh SERIAL LABEL
# Installs org.redoubtbrowser (fresh profile), visits the test URLs, records screenshots,
# UI text, process labels, video results, memory and crashes, then uninstalls.
set -u
S=$1; L=$2
B=${QA_DIR:?set QA_DIR to a directory with apk/fenix-arm64-v8a-release.apk, www/ (video.html and clips) and tools/}
O=$B/out/$L; mkdir -p "$O"
APK=$B/apk/fenix-arm64-v8a-release.apk
PKG=org.redoubtbrowser
PORT=8471
A=(adb -s "$S")
log() { echo "[$(date +%T)] $*" | tee -a "$O/log.txt"; }
dump() { "${A[@]}" shell uiautomator dump /sdcard/qa-ui.xml >/dev/null 2>&1; "${A[@]}" exec-out cat /sdcard/qa-ui.xml > "$O/$1.xml" 2>/dev/null; }
shot() {
  "${A[@]}" exec-out screencap -p > "$O/$1.png"; dump "$1"
  local t; t=$(grep -o 'text="[^"]\{2,\}"' "$O/$1.xml" | grep -v 'text="redoubt\|reddit.com/\|text="[0-9:]*"' | head -14 | tr '\n' ' ')
  log "$1: $t"
}
open_url() { "${A[@]}" shell "am start -a android.intent.action.VIEW -d '$1' $PKG" >/dev/null 2>&1; }
tap() { python3 -I "$B/tools/tap_text.py" "$S" "$O/$1.xml" "${@:2}"; }

log "device: $("${A[@]}" shell 'getprop ro.product.model; getprop ro.build.version.release; getprop ro.build.version.sdk; getprop ro.product.cpu.abi; getprop persist.sys.locale; grep MemTotal /proc/meminfo' | tr '\n' ' ')"
T0=$("${A[@]}" shell "date +'%m-%d %H:%M:%S.000'" | tr -d '\r')
log "device clock T0: $T0"

log "install: $("${A[@]}" install "$APK" 2>&1 | tail -1)"
log "installed: $("${A[@]}" shell dumpsys package $PKG | grep -E -m2 'versionName|versionCode' | tr -s ' ' | tr '\n' ' ')"
"${A[@]}" shell input keyevent KEYCODE_WAKEUP; "${A[@]}" shell wm dismiss-keyguard

# 1. Reddit: a cold start straight into the login URL, then home, then login again, then old.reddit.
open_url https://www.reddit.com/login/
sleep 18; dump 00-first-start
log "uBO sheet: $(REQUIRE='uBlock Origin' tap 00-first-start OK)"
sleep 12; shot 01-reddit-login-cold-30s
sleep 30; shot 02-reddit-login-cold-60s
open_url https://www.reddit.com/; sleep 30; shot 03-reddit-home
open_url https://www.reddit.com/login/; sleep 30; shot 04-reddit-login-after-home
open_url https://old.reddit.com/login; sleep 20; shot 05-old-reddit-login

# 2. Process model on real hardware (isolation is ON for API 31+).
"${A[@]}" shell "ps -A -Z -o LABEL,USER,PID,RSS,NAME" | grep -E "redoubt|isolated_app|app_zygote" > "$O/processes-after-reddit.txt"
log "processes: $(awk '{print $1, $2, $5}' "$O/processes-after-reddit.txt" | sed 's/:s0[^ ]*//' | sort | uniq -c | tr '\n' ';')"

# 3. Local media page: H.264 (hardware, RDD) and VP9/AV1 (software, isolated content).
"${A[@]}" reverse tcp:$PORT tcp:$PORT >/dev/null
open_url "http://127.0.0.1:$PORT/video.html?dev=$L"
for i in $(seq 1 60); do grep -q "\"done\": true, \"dev\": \"$L\"" "$B/out/results.jsonl" 2>/dev/null && break; sleep 3; done
log "video page finished after ~$((i*3)) s"
shot 06-video-page
"${A[@]}" shell "ps -A -Z -o LABEL,USER,PID,RSS,NAME" | grep -E "redoubt|isolated_app|app_zygote" > "$O/processes-after-video.txt"

# 4. YouTube (real site, consent wall in Europe), then a play attempt.
open_url "https://m.youtube.com/watch?v=aqz-KE-bpKQ"; sleep 25; shot 07-youtube
log "youtube consent: $(tap 07-youtube 'Reject all' 'Alle ablehnen' 'Tout refuser' 'Rifiuta tutto')"
sleep 12; shot 08-youtube-after-consent
"${A[@]}" shell input tap 540 560; sleep 20; shot 09-youtube-after-tap
"${A[@]}" shell dumpsys media_session | grep -A4 -i "$PKG" | grep -E "package|state=|active" | head -6 > "$O/media-session.txt"
log "media session: $(tr -s ' ' < "$O/media-session.txt" | tr '\n' ' ')"

# 5. Ordinary sites.
n=10
for u in https://en.m.wikipedia.org/wiki/Web_browser https://github.com/CPlusPlus17/Redoubt https://www.bbc.com/news \
         "https://www.google.com/search?q=redoubt+browser" "https://duckduckgo.com/?q=redoubt+browser" https://www.theguardian.com/international; do
  open_url "$u"; sleep 20; shot "$n-$(echo "$u" | sed 's#https://##; s#[/?=+.]#_#g' | cut -c1-40)"; n=$((n+1))
done

# 6. Memory with ~14 tabs open, and the process picture.
"${A[@]}" shell dumpsys meminfo > "$O/meminfo-all.txt"
grep -E "redoubt|isolated" "$O/meminfo-all.txt" | head -40 > "$O/meminfo-redoubt.txt"
"${A[@]}" shell dumpsys meminfo $PKG | grep -E "TOTAL PSS|TOTAL RSS|TOTAL:|Native Heap|Java Heap" | head -8 > "$O/meminfo-main.txt"
"${A[@]}" shell "ps -A -Z -o LABEL,USER,PID,RSS,NAME" | grep -E "redoubt|isolated_app|app_zygote" > "$O/processes-end.txt"
log "pss lines: $(wc -l < "$O/meminfo-redoubt.txt")"

# 7. Crashes, ANRs and media-isolation messages since T0.
"${A[@]}" logcat -b crash -d -T "$T0" > "$O/crash-buffer.txt" 2>&1
"${A[@]}" logcat -d -T "$T0" -v threadtime > "$O/logcat.txt" 2>&1
log "crash buffer lines: $(grep -c . "$O/crash-buffer.txt")"
log "fatal/anr: $(grep -c -E 'FATAL EXCEPTION|Fatal signal|ANR in org.redoubtbrowser' "$O/logcat.txt")"
log "isolation-media lines: $(grep -c -i 'isolation-media\|refused a decoder' "$O/logcat.txt")"
gzip -f "$O/logcat.txt"

# 8. Clean up: uninstall, remove the reverse port and the dump file.
log "uninstall: $("${A[@]}" uninstall $PKG 2>&1 | tail -1)"
"${A[@]}" reverse --remove tcp:$PORT >/dev/null 2>&1
"${A[@]}" shell rm -f /sdcard/qa-ui.xml
log "DONE"
