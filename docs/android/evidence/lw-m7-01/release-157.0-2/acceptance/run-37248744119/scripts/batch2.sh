#!/bin/bash
# Stage 2: every remaining harness check, once, each on a fresh profile (the harness wipes app data).
R=/home/mgysin/redoubt-artifacts/stable/accept2; S=$R/repo/docs/android/evidence/lw-m7-01/release-157.0-2/acceptance/run-37248744119/scripts
export SERIAL=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb devices | awk '/^emulator-/{print $1; exit}') RUNS=$R/runs
$S/run-check.sh check-ubo-preinstall --check-ubo-preinstall
$S/run-check.sh check-ubo-lifecycle --check-ubo-lifecycle
$S/run-check.sh check-ubo --check-ubo
$S/run-check.sh check-search --check-search
$S/run-check.sh check-no-suggest --check-no-suggest
$S/run-check.sh check-no-suggest-negative-control --check-no-suggest --no-suggest-negative-control
$S/run-check.sh baseline-smoke
$S/run-check.sh check-update-privacy --check-update-privacy
$S/run-check.sh check-https-only --check-https-only
$S/run-check.sh static-no-gms-no-adjust --check-no-gms --check-no-adjust
$S/run-check.sh check-strings --check-strings
$S/run-check.sh self-test --self-test
$S/run-check.sh first-run-capture --first-run-capture
$S/run-check.sh check-no-remote-settings --check-no-remote-settings
echo BATCH2 DONE
