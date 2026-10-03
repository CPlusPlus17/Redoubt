#!/bin/bash
# Stage 2: every remaining harness check, once, each on a fresh profile (the harness wipes app data).
export SERIAL=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb devices | awk '/^emulator-/{print $1; exit}')
R=/home/mgysin/redoubt-artifacts/release-157/acceptance/rc3
$R/run-check.sh check-ubo-preinstall --check-ubo-preinstall
$R/run-check.sh check-ubo-lifecycle --check-ubo-lifecycle
$R/run-check.sh check-ubo --check-ubo
$R/run-check.sh check-search --check-search
$R/run-check.sh check-no-suggest --check-no-suggest
$R/run-check.sh check-no-suggest-negative-control --check-no-suggest --no-suggest-negative-control
$R/run-check.sh baseline-smoke
$R/run-check.sh check-update-privacy --check-update-privacy
$R/run-check.sh check-https-only --check-https-only
$R/run-check.sh static-no-gms-no-adjust --check-no-gms --check-no-adjust
$R/run-check.sh check-strings --check-strings
$R/run-check.sh self-test --self-test
$R/run-check.sh first-run-capture --first-run-capture
$R/run-check.sh check-no-remote-settings --check-no-remote-settings
echo BATCH2 DONE
