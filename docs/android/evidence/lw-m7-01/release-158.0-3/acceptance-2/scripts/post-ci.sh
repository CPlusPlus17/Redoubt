#!/bin/bash
# Second 158.0-3 acceptance, after the CI run: download, check sums, throwaway-sign x86_64 (emulators) and arm64-v8a
# (phones), put output-metadata.json next to them (the harness reads the package name from it).
# usage: post-ci.sh RUN_ID
set -eu
R=/home/mgysin/redoubt-artifacts/release-158.0-3/accept2; RUN=$1
BT=/home/mgysin/.local/state/codex-desktop/tmp/fivur-android-sdk36/build-tools/36.0.0
K=/home/mgysin/redoubt-artifacts/keep/throwaway-keys
mkdir -p $R/ci $R/apk && cd $R/ci
gh run view $RUN -R CPlusPlus17/Redoubt --json databaseId,headSha,status,conclusion,createdAt,updatedAt,event,headBranch,workflowName,url,jobs > run.json
gh run view $RUN -R CPlusPlus17/Redoubt --log 2>/dev/null | gzip -9 > run.log.gz
gh api repos/CPlusPlus17/Redoubt/actions/runs/$RUN/artifacts > artifacts.json
rm -rf redoubt-android-unsigned; gh run download $RUN -R CPlusPlus17/Redoubt -n redoubt-android-unsigned -D redoubt-android-unsigned
(cd redoubt-android-unsigned && sha256sum -c SHA256SUMS) | tee SHA256SUMS.check.txt
for a in x86_64 arm64-v8a; do
  out=$R/apk/fenix-$a-158.0-3-throwaway.apk
  $BT/apksigner sign --ks $K/throwaway.p12 --ks-pass file:$K/throwaway.pass --out $out redoubt-android-unsigned/fenix-$a-release-unsigned.apk
  $BT/apksigner verify --print-certs $out | grep -E "Signer #1 certificate (DN|SHA-256)"
done
cp redoubt-android-unsigned/output-metadata.json $R/apk/
sha256sum $R/apk/*.apk
echo POST-CI DONE
