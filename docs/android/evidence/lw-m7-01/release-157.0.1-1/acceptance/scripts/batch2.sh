#!/bin/bash
# Stage 2: every remaining harness check, once, each on a fresh profile (the harness wipes app data).
# New since 157.0-3: --check-ubo-user-disable (LW-M7-44) and --check-delete-on-quit (LW-M7-45).
R=/home/mgysin/redoubt-artifacts/release-157.0.1-1; S=$R/repo/docs/android/evidence/lw-m7-01/release-157.0.1-1/acceptance/scripts
export SERIAL=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb devices | awk '/^emulator-/{print $1; exit}') RUNS=$R/runs
# The API 34 google_apis image routes the default network over netsim Wi-Fi (wlan0), which the
# emulator's -tcpdump does NOT see: the first attempt (runs-attempt1-wifi/) captured nothing after boot
# and check-no-suggest failed on "0 total capture bytes". With Wi-Fi off the default network is the
# emulated LTE link on eth0 (slirp), which -tcpdump captures, as on the android-30 default image.
ADB=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
$ADB -s $SERIAL shell svc wifi disable
echo "wifi disabled; $($ADB -s $SERIAL shell dumpsys connectivity 2>/dev/null | grep -m1 'Active default network')"
$S/run-check.sh check-ubo-preinstall --check-ubo-preinstall
$S/run-check.sh check-ubo-lifecycle --check-ubo-lifecycle
$S/run-check.sh check-ubo-user-disable --check-ubo-user-disable
$S/run-check.sh check-ubo --check-ubo
$S/run-check.sh check-search --check-search
$S/run-check.sh check-no-suggest --check-no-suggest
$S/run-check.sh check-no-suggest-negative-control --check-no-suggest --no-suggest-negative-control
$S/run-check.sh baseline-smoke
$S/run-check.sh check-update-privacy --check-update-privacy
$S/run-check.sh check-https-only --check-https-only
$S/run-check.sh check-video --check-video
$S/run-check.sh check-delete-on-quit --check-delete-on-quit
$S/run-check.sh static-no-gms-no-adjust --check-no-gms --check-no-adjust
$S/run-check.sh check-strings --check-strings
$S/run-check.sh self-test --self-test
$S/run-check.sh first-run-capture --first-run-capture
$S/run-check.sh check-no-remote-settings --check-no-remote-settings
echo BATCH2 DONE
