#!/bin/bash
# final 158.0-1 driver (copied from Beta 2; batch2 turns Wi-Fi off before its captures). Everything runs on ONE emulator: API 34 google_apis x86_64, booted by the
# harness from the android-34-only SDK view $R/sdk34 (-dns-server 9.9.9.9 -tcpdump). The first check
# boots it (--emulator --keep-emulator); batches 1-3 reuse it with --serial.
R=/home/mgysin/redoubt-artifacts/release-158.0-1; S=$R/repo/docs/android/evidence/lw-m7-01/release-158.0-1/acceptance/scripts
cd $R
RUNS=$R/runs SERIAL= $S/run-check.sh check-launcher-start --check-launcher-start
[ "$(tail -1 runs/exit-status.jsonl | python3 -c "import json,sys; print(json.load(sys.stdin)[\"exit\"])")" = 0 ] || { echo "check-launcher-start failed; stopping"; exit 1; }   # added for Beta 2
bash $S/batch1.sh > runs/batch1.log 2>&1
bash $S/batch2.sh > runs/batch2.log 2>&1
bash $S/batch3.sh > runs/batch3.log 2>&1
echo DRIVE DONE
