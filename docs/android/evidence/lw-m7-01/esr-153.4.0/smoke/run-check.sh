#!/bin/bash
# usage: run-check.sh NAME [harness args...]   (env SERIAL empty => harness boots emulator)
R=/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime
REPO=/home/mgysin/redoubt-artifacts/esr-153.4/repo
name=$1; shift
out=$R/runs/$name; mkdir -p $out
cd $REPO
APK=${APK:-$R/apk/new/fenix-x86_64-release-throwaway.apk}
AAPT2=/home/mgysin/redoubt-artifacts/esr-153.4/build/librewolf-android-aar-153.4.0esr-1/gradle-home/caches/9.5.1/transforms/7a972dbdd2c1f9526bc4e36898517d46/transformed/aapt2-8.13.2-14304508-linux/aapt2
dev=(--emulator --keep-emulator --dns-server 9.9.9.9)
if [ -n "$SERIAL" ]; then dev=(--serial "$SERIAL"); export LW_SMOKE_PCAP=$R/work/capture.pcap LW_SMOKE_DNS=9.9.9.9; fi
cmd=(scripts/android-smoke.sh "${dev[@]}" --sdk /home/mgysin/redoubt-artifacts/android-sdk --work $R/work --apk "$APK" --aapt2 "$AAPT2" "$@" --json $out/$name.json)
started=$(date -u +%FT%TZ); hs=$(sha256sum scripts/android-smoke.sh | cut -c1-64)
pcap_start=$(stat -c %s $R/work/capture.pcap 2>/dev/null || echo 0)
"${cmd[@]}" > $out/$name.out 2> $out/$name.err; rc=$?
pcap_end=$(stat -c %s $R/work/capture.pcap 2>/dev/null || echo 0)
python3 - "$name" "$rc" "$started" "$hs" "$pcap_start" "$pcap_end" "$(sha256sum "$APK"|cut -c1-64)" "${cmd[@]}" >> $R/runs/exit-status.jsonl <<'PY'
import json,sys,datetime
n,rc,st,hs,ps,pe,ah=sys.argv[1:8]
print(json.dumps({"check":n,"exit":int(rc),"started":st,"completed":datetime.datetime.utcnow().isoformat()+"Z","harness_sha256_at_start":hs,"installed_apk_sha256":ah,"capture_pcap_bytes":[int(ps),int(pe)],"command":sys.argv[8:]}))
PY
echo "$name exit=$rc"
