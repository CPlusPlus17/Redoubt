#!/bin/bash
# Pref audit: the official generator + audit, unchanged, on a fresh profile (the harness wipes app data).
R=/home/mgysin/redoubt-artifacts/release-157.0.1-1
P=$R/runs/pref-audit; mkdir -p $P
cd /home/mgysin/redoubt-artifacts/release-157.0.1-1/repo
export ANDROID_SERIAL=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb devices | awk '/^emulator-/{print $1; exit}') ANDROID_SDK_ROOT=/home/mgysin/redoubt-artifacts/android-sdk LW_SMOKE_APK=$R/apk/fenix-x86_64-157.0.1-1-throwaway.apk LW_SMOKE_WORK=$R/work
{ git rev-parse HEAD; sha256sum scripts/android-smoke.sh scripts/generate-android-pref-baseline.sh scripts/android-pref-audit.sh docs/android/expected-prefs.txt docs/android/must-lock.txt; sha256sum $LW_SMOKE_APK; date -u +%FT%TZ; } > $P/inputs.txt
cp docs/android/expected-prefs.txt $P/expected-prefs-before.txt
./scripts/generate-android-pref-baseline.sh > $P/generator.out 2> $P/generator.err; echo "generator exit=$?" | tee $P/generator.exit
cp docs/android/expected-prefs.txt $P/expected-prefs-generated.txt
diff -u $P/expected-prefs-before.txt $P/expected-prefs-generated.txt > $P/baseline-diff.out
git checkout -- docs/android/expected-prefs.txt
./scripts/android-pref-audit.sh > $P/audit-vs-committed.out 2> $P/audit-vs-committed.err; echo "audit exit=$?" | tee $P/audit-vs-committed.exit
echo BATCH3 DONE
