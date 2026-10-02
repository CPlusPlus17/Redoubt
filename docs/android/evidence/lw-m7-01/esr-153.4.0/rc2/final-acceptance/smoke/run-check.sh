#!/bin/bash
# usage: run-check.sh NAME [harness args...]   (env SERIAL empty => harness boots emulator)
# Records repo HEAD, uncommitted script changes, both harness hashes, installed APK hash, and
# (when a serial is given) a full `logcat -v threadtime` stream for the run's duration.
R=/home/mgysin/redoubt-artifacts/esr-153.4/build/rc2/final/runtime
REPO=/home/mgysin/redoubt-artifacts/esr-153.4/repo
ADB=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
name=$1; shift
out=$R/runs/$name; mkdir -p $out
cd $REPO
APK=${APK:-$R/apk/rc2/fenix-x86_64-release-throwaway.apk}
AAPT2=/home/mgysin/redoubt-artifacts/esr-153.4/build/rc2/librewolf-android-aar-153.4.0esr-1/gradle-home/caches/9.5.1/transforms/7a972dbdd2c1f9526bc4e36898517d46/transformed/aapt2-8.13.2-14304508-linux/aapt2
dev=(--emulator --keep-emulator --dns-server 9.9.9.9)
if [ -n "$SERIAL" ]; then dev=(--serial "$SERIAL"); export LW_SMOKE_PCAP=$R/work/capture.pcap LW_SMOKE_DNS=9.9.9.9; fi
cmd=(scripts/android-smoke.sh "${dev[@]}" --sdk /home/mgysin/redoubt-artifacts/android-sdk --work $R/work --apk "$APK" --aapt2 "$AAPT2" "$@" --json $out/$name.json)
started=$(date -u +%FT%TZ); hs=$(sha256sum scripts/android-smoke.sh | cut -c1-64); gs=$(sha256sum scripts/android-graphics-smoke.py | cut -c1-64); head=$(git rev-parse HEAD); dirty=$(git status --porcelain -- scripts | wc -l)
rm -rf $R/work/graphics-acceptance $R/work/launcher-start-* 2>/dev/null
pcap_start=$(stat -c %s $R/work/capture.pcap 2>/dev/null || echo 0)
lc=""
if [ -n "$SERIAL" ]; then $ADB -s $SERIAL logcat -v threadtime > $out/$name.logcat 2>&1 & lc=$!; fi
"${cmd[@]}" > $out/$name.out 2> $out/$name.err; rc=$?
[ -n "$lc" ] && { sleep 2; kill $lc 2>/dev/null; wait $lc 2>/dev/null; gzip -f $out/$name.logcat; }
for f in $R/work/launcher-start-* $R/work/graphics-acceptance; do [ -e "$f" ] && cp -r "$f" $out/; done
pcap_end=$(stat -c %s $R/work/capture.pcap 2>/dev/null || echo 0)
python3 - "$name" "$rc" "$started" "$hs" "$pcap_start" "$pcap_end" "$(sha256sum "$APK"|cut -c1-64)" "$gs" "$head" "$dirty" "${cmd[@]}" >> $R/runs/exit-status.jsonl <<'PY'
import json,sys,datetime
n,rc,st,hs,ps,pe,ah,gs,head,dirty=sys.argv[1:11]
print(json.dumps({"check":n,"exit":int(rc),"started":st,"completed":datetime.datetime.now(datetime.timezone.utc).isoformat(),"harness_sha256_at_start":hs,"installed_apk_sha256":ah,"graphics_harness_sha256_at_start":gs,"repo_head":head,"uncommitted_script_changes":int(dirty),"capture_pcap_bytes":[int(ps),int(pe)],"command":sys.argv[11:]}))
PY
echo "$(date -u +%T) $name exit=$rc"
