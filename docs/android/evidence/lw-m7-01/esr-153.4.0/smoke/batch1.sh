export SERIAL=emulator-5584
/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh check-no-remote-settings --check-no-remote-settings
/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh check-ubo-preinstall --check-ubo-preinstall
/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh static-no-gms-no-adjust --check-no-gms --check-no-adjust
APK=/home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/apk/old/fenix-x86_64-release-throwaway.apk /home/mgysin/redoubt-artifacts/esr-153.4/build/runtime/run-check.sh beta2-first-run-capture --first-run-capture
echo BATCH1 DONE
