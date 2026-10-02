export SERIAL=emulator-5584
/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh amoblocked-baseline-smoke
/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh amoblocked-check-ubo-preinstall --check-ubo-preinstall
/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh amoblocked-check-ubo-lifecycle --check-ubo-lifecycle
cd /home/mgysin/redoubt-artifacts/esr-153.4/repo
export ANDROID_SERIAL=emulator-5584 ANDROID_SDK_ROOT=/home/mgysin/redoubt-artifacts/android-sdk LW_SMOKE_APK=/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/apk/new/fenix-x86_64-release-throwaway.apk LW_SMOKE_WORK=/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/work
mkdir -p /home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/runs/pref-audit
cp docs/android/expected-prefs.txt /home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/runs/pref-audit/expected-prefs-before.txt
./scripts/generate-android-pref-baseline.sh > /home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/runs/pref-audit/generator.out 2> /home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/runs/pref-audit/generator.err; echo "generator exit=$?" | tee /home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/runs/pref-audit/generator.exit
cp docs/android/expected-prefs.txt /home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/runs/pref-audit/expected-prefs-generated.txt
diff -u /home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/runs/pref-audit/expected-prefs-before.txt /home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/runs/pref-audit/expected-prefs-generated.txt > /home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/runs/pref-audit/baseline-diff.out
git checkout -- docs/android/expected-prefs.txt
./scripts/android-pref-audit.sh > /home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/runs/pref-audit/audit-vs-committed.out 2> /home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/runs/pref-audit/audit-vs-committed.err; echo "audit exit=$?" | tee /home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/runs/pref-audit/audit-vs-committed.exit
echo BATCH4 DONE
