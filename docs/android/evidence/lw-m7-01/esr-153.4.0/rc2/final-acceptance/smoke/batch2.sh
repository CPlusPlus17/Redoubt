#!/bin/bash
# Stage 2: every remaining check, once, each on a fresh profile (the harness wipes app data).
export SERIAL=emulator-5584
R=/home/mgysin/redoubt-artifacts/esr-153.4/build/rc2/final/runtime
$R/run-check.sh check-ubo-preinstall --check-ubo-preinstall
$R/run-check.sh check-ubo-lifecycle --check-ubo-lifecycle
$R/run-check.sh check-ubo --check-ubo
$R/run-check.sh check-search --check-search
$R/run-check.sh check-no-suggest --check-no-suggest
$R/run-check.sh baseline-smoke
$R/run-check.sh check-update-privacy --check-update-privacy
$R/run-check.sh check-https-only --check-https-only
$R/run-check.sh static-no-gms-no-adjust --check-no-gms --check-no-adjust
$R/run-check.sh check-strings --check-strings
$R/run-check.sh self-test --self-test
$R/run-check.sh first-run-capture --first-run-capture
$R/run-check.sh check-no-remote-settings --check-no-remote-settings
# Negative control: Beta 2 (source 764fc91c) must FAIL the launcher cold start.
APK=$R/apk/beta2/fenix-x86_64-release-throwaway.apk $R/run-check.sh beta2-check-launcher-start --check-launcher-start
echo BATCH2 DONE
