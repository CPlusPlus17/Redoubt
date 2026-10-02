#!/bin/bash
export SERIAL=emulator-5584
R=/home/mgysin/redoubt-artifacts/esr-153.4/build/rc2/runtime
$R/run-check.sh check-launcher-start --check-launcher-start
$R/run-check.sh check-aboutconfig --check-aboutconfig
$R/run-check.sh check-ubo-preinstall --check-ubo-preinstall
$R/run-check.sh check-ubo-lifecycle --check-ubo-lifecycle
$R/run-check.sh check-ubo --check-ubo
$R/run-check.sh check-search --check-search
$R/run-check.sh check-no-suggest --check-no-suggest
$R/run-check.sh check-update-privacy --check-update-privacy
$R/run-check.sh check-https-only --check-https-only
$R/run-check.sh static-no-gms-no-adjust --check-no-gms --check-no-adjust
$R/run-check.sh check-strings --check-strings
$R/run-check.sh first-run-capture --first-run-capture
$R/run-check.sh check-no-remote-settings --check-no-remote-settings
echo BATCH1 DONE
