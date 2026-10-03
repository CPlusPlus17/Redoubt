#!/bin/bash
# Regression smoke on the Beta 5 candidate, each check on a fresh profile (the harness wipes app data).
export SERIAL=emulator-5584
R=/home/mgysin/redoubt-artifacts/beta5/accept
$R/run-check.sh check-ubo-preinstall --check-ubo-preinstall
$R/run-check.sh check-ubo-lifecycle --check-ubo-lifecycle
$R/run-check.sh check-ubo --check-ubo
$R/run-check.sh baseline-smoke
$R/run-check.sh check-no-suggest --check-no-suggest
$R/run-check.sh check-aboutconfig --check-aboutconfig
$R/run-check.sh check-update-privacy --check-update-privacy
$R/run-check.sh check-https-only --check-https-only
$R/run-check.sh check-strings --check-strings
$R/run-check.sh first-run-capture --first-run-capture
echo BATCH DONE
