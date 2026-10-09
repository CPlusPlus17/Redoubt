#!/bin/bash
# usage: run-check.sh NAME [harness args...]   (env SERIAL empty => harness boots the emulator)
# Copied (via the 158.0-1 Beta 1 acceptance) from the Beta 5 acceptance (evidence/lw-m7-41/migration/scripts/run-check.sh), paths changed
# to the 158.0-1 Beta 2 acceptance area (copied from the 157.0-3 acceptance; --sdk is now the android-34-only view $R/sdk34). Records repo HEAD, uncommitted script changes, both harness hashes,
# the installed APK hash and (with a serial) a full `logcat -v threadtime` stream for the run.
R=/home/mgysin/redoubt-artifacts/beta-158.0-1-b2
SDK=${SDK:-$R/sdk34}; WORK=${WORK:-$R/work}   # the android-30 session sets both
REPO=$R/repo
ADB=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
name=$1; shift
out=${RUNS:-$R/runs}/$name; mkdir -p $out
cd $REPO
APK=${APK:-$R/apk/fenix-x86_64-158.0-1-beta2-throwaway.apk}
AAPT2=$R/x/aapt2/aapt2
dev=(--emulator --keep-emulator --dns-server 9.9.9.9)
if [ -n "$SERIAL" ]; then dev=(--serial "$SERIAL"); export LW_SMOKE_PCAP=$WORK/capture.pcap LW_SMOKE_DNS=9.9.9.9; fi
export LW_SMOKE_REPO=$REPO
cmd=(scripts/android-smoke.sh "${dev[@]}" --sdk $SDK --work $WORK --apk "$APK" --aapt2 "$AAPT2" "$@" --json $out/$name.json)
started=$(date -u +%FT%TZ); hs=$(sha256sum scripts/android-smoke.sh | cut -c1-64); gs=$(sha256sum scripts/android-graphics-smoke.py | cut -c1-64); head=$(git rev-parse HEAD); dirty=$(git status --porcelain -- scripts | wc -l)
rm -rf $WORK/graphics-acceptance $WORK/launcher-start-* 2>/dev/null
pcap_start=$(stat -c %s $WORK/capture.pcap 2>/dev/null || echo 0)
lc=""
if [ -n "$SERIAL" ]; then $ADB -s $SERIAL logcat -v threadtime > $out/$name.logcat 2>&1 & lc=$!; fi
"${cmd[@]}" > $out/$name.out 2> $out/$name.err; rc=$?
[ -n "$lc" ] && { sleep 2; kill $lc 2>/dev/null; wait $lc 2>/dev/null; gzip -f $out/$name.logcat; }
for f in $WORK/launcher-start-* $WORK/graphics-acceptance; do [ -e "$f" ] && cp -r "$f" $out/; done
pcap_end=$(stat -c %s $WORK/capture.pcap 2>/dev/null || echo 0)
python3 - "$name" "$rc" "$started" "$hs" "$pcap_start" "$pcap_end" "$(sha256sum "$APK"|cut -c1-64)" "$gs" "$head" "$dirty" "${cmd[@]}" >> ${RUNS:-$R/runs}/exit-status.jsonl <<'PY'
import json,sys,datetime
n,rc,st,hs,ps,pe,ah,gs,head,dirty=sys.argv[1:11]
print(json.dumps({"check":n,"exit":int(rc),"started":st,"completed":datetime.datetime.now(datetime.timezone.utc).isoformat(),"harness_sha256_at_start":hs,"installed_apk_sha256":ah,"graphics_harness_sha256_at_start":gs,"repo_head":head,"uncommitted_script_changes":int(dirty),"capture_pcap_bytes":[int(ps),int(pe)],"command":sys.argv[11:]}))
PY
echo "$(date -u +%T) $name exit=$rc"
