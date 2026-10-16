#!/bin/bash
# Copies the run outputs of this acceptance into the evidence directory, laid out like the first 158.0-3 acceptance.
# Phone logcats are cut down to the app's own lines (trim-logcat.py for the DRM flows; a Redoubt/Gecko/isolation
# filter for the harness runs), so that no other app's lines are committed. Full captures stay in $R/runs*.
set -eu
R=/home/mgysin/redoubt-artifacts/release-158.0-3/accept2; E=$R/repo/docs/android/evidence/lw-m7-01/release-158.0-3/acceptance-2
S=$E/scripts
dev() {  # dev RUNS OUT LOGS...
  local src=$1 out=$2; shift 2; mkdir -p $out/smoke $out/drm $out/logs
  cp $src/exit-status.jsonl $out/smoke/
  for c in $(python3 -c "import json,sys;[print(json.loads(l)['check']) for l in open(sys.argv[1])]" $src/exit-status.jsonl | sort -u); do cp -r $src/$c $out/smoke/; done
  for d in $src/drm-api*; do [ -d $d ] && cp -r $d $out/drm/; done
  cp $src/drm-batch.log $src/drm-batch.console $out/drm/ 2>/dev/null || true
  for d in aboutconfig-csp autofill pref-audit process-labels reddit-cold store-installer update-check-live update-check-local upgrade-from-158.0-2 webgl-manual; do [ -d $src/$d ] && cp -r $src/$d $out/; done
  for f in $src/*.console $src/batch*.log "$@"; do [ -f $f ] && [ "$(basename $f)" != drm-batch.console ] && cp $f $out/logs/; done
  return 0
}
dev $R/runs $E/device-api34 $R/drive.log
dev $R/runs31 $E/device-api31 $R/drive31.log
dev $R/runs33 $E/device-api33 $R/drive33.log
[ -d $R/runs30 ] && dev $R/runs30 $E/device-api30 $R/drive30.log
mkdir -p $E/phones; cp $R/phone-*.log $E/phones/
for p in mi8 pixel9a mi8-control-158.0-2; do
  rm -rf $E/phones/$p; cp -r $R/runs-phones/$p $E/phones/$p
  find $E/phones/$p -name 'logcat.txt.gz' | while read f; do
    d=$(dirname $f)
    if [ -f $d/flow.out ]; then python3 $S/drm/trim-logcat.py $f $d/logcat.txt-trimmed.gz > /dev/null
    else zcat $f | grep -E 'org\.redoubtbrowser|isolated_app|GeckoView|Gecko|NdkMediaDrm|MediaDrm|has died|FATAL EXCEPTION|Fatal signal' | gzip -9 > $d/logcat.txt-filtered.gz; fi
    rm $f
  done
done
mkdir -p $E/ci $E/update-check
cp $R/ci/run.json $R/ci/run.log.gz $R/ci/artifacts.json $R/ci/SHA256SUMS.check.txt $E/ci/
cp $R/ci/redoubt-android-unsigned/SHA256SUMS $R/ci/redoubt-android-unsigned/output-metadata.json $E/ci/
cp $R/update-host/latest.json $R/update-host/throwaway-signed-latest.json.sig $R/update-host/throwaway-update-test.pubkey $E/update-check/
sed "s#$R#<R>#g" $R/update-host/host-verifier.txt > $E/update-check/host-verifier.txt
# local paths -> <R> in the text logs
grep -rlI "$R" $E --include='*.log' --include='*.console' --include='*.txt' --include='*.jsonl' --include='*.out' --include='*.err' 2>/dev/null | xargs -r sed -i "s#$R#<R>#g"
du -sh $E
