#!/bin/bash
# usage: run-check.sh NAME [harness args...]   (env SERIAL empty => harness boots the emulator and keeps it)
# Adapted from the 158.0-2 acceptance runner (evidence/lw-m7-01/release-158.0-2/acceptance/scripts/run-check.sh):
# records repo HEAD, uncommitted script changes, harness hash, installed APK hash, pcap growth, logcat stream.
P=~/redoubt-artifacts/port-sept24
SDK=${SDK:-~/redoubt-artifacts/release-158.0-2/sdk34}; WORK=${WORK:-$P/work-emu}
REPO=$P/repo
ADB=~/redoubt-artifacts/android-sdk/platform-tools/adb
name=$1; shift
out=${RUNS:-$P/runs}/$name; mkdir -p $out $WORK
cd $REPO
APK=${APK:?set APK}
AAPT2=~/redoubt-artifacts/release-158.0-2/x/aapt2/aapt2
dev=(--emulator --keep-emulator --dns-server 9.9.9.9)
if [ -n "$SERIAL" ]; then dev=(--serial "$SERIAL"); export LW_SMOKE_PCAP=$WORK/capture.pcap LW_SMOKE_DNS=9.9.9.9; fi
export LW_SMOKE_REPO=$REPO LW_SMOKE_PACKAGE=org.redoubtbrowser
cmd=(scripts/android-smoke.sh "${dev[@]}" --sdk $SDK --work $WORK --apk "$APK" --aapt2 "$AAPT2" "$@" --json $out/$name.json)
started=$(date -u +%FT%TZ); hs=$(sha256sum scripts/android-smoke.sh | cut -c1-64); head=$(git rev-parse HEAD); dirty=$(git status --porcelain -- scripts | wc -l)
pcap_start=$(stat -c %s $WORK/capture.pcap 2>/dev/null || echo 0)
lc=""
if [ -n "$SERIAL" ]; then $ADB -s $SERIAL logcat -v threadtime > $out/$name.logcat 2>&1 & lc=$!; fi
timeout ${TO:-580} "${cmd[@]}" > $out/$name.out 2> $out/$name.err; rc=$?
[ -n "$lc" ] && { sleep 2; kill $lc 2>/dev/null; wait $lc 2>/dev/null; gzip -f $out/$name.logcat; }
pcap_end=$(stat -c %s $WORK/capture.pcap 2>/dev/null || echo 0)
python3 - "$name" "$rc" "$started" "$hs" "$pcap_start" "$pcap_end" "$(sha256sum "$APK"|cut -c1-64)" "$head" "$dirty" "${cmd[@]}" >> ${RUNS:-$P/runs}/exit-status.jsonl <<'PY'
import json,sys,datetime
n,rc,st,hs,ps,pe,ah,head,dirty=sys.argv[1:10]
print(json.dumps({"check":n,"exit":int(rc),"started":st,"completed":datetime.datetime.now(datetime.timezone.utc).isoformat(),"harness_sha256_at_start":hs,"installed_apk_sha256":ah,"repo_head":head,"uncommitted_script_changes":int(dirty),"capture_pcap_bytes":[int(ps),int(pe)],"command":sys.argv[10:]}))
PY
echo "$(date -u +%T) $name exit=$rc"
