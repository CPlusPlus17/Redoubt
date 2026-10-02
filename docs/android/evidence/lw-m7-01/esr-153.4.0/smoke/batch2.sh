export SERIAL=emulator-5584
/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh pref-dump-primed --keep-state --pref-dump
/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh baseline-smoke-primed --keep-state
/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh check-ubo-primed --keep-state --check-ubo
/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh check-search-primed --keep-state --check-search
/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh check-no-suggest-primed --keep-state --check-no-suggest
/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh check-update-privacy-primed --keep-state --check-update-privacy
/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh check-aboutconfig-primed --keep-state --check-aboutconfig
/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh check-strings-primed --keep-state --check-strings
echo BATCH2 DONE
