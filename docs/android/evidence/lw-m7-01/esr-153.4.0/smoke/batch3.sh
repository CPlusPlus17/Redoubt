export SERIAL=emulator-5584 APK=/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/apk/old/fenix-x86_64-release-throwaway.apk
/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh beta2-pref-dump-primed --keep-state --pref-dump
/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh beta2-check-aboutconfig-primed --keep-state --check-aboutconfig
/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh beta2-baseline-smoke-primed --keep-state
echo BATCH3 DONE
