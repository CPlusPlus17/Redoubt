#!/bin/bash
# Stage 2: every remaining harness check, once, each on a fresh profile (the harness wipes app data).
# Since 157.0-3: --check-ubo-user-disable (LW-M7-44) and --check-delete-on-quit (LW-M7-45). New for the final 158.0-1:
# --check-tls-floor, --check-revocation and --check-rfp-coherence (LW-M7-49, merged into main with the 158 rebase).
# New for 158.0-2 (LW-M7-50, isolation ON on Android 12+): --check-isolation three times and --check-video three times.
R=/home/mgysin/redoubt-artifacts/release-158.0-2; S=$R/repo/docs/android/evidence/lw-m7-01/release-158.0-2/acceptance/scripts
export SERIAL=$(/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb devices | awk '/^emulator-/{print $1; exit}') RUNS=$R/runs
[ -n "$SERIAL" ] || { echo "no emulator-* serial; stopping (never fall back to another device)"; exit 1; }   # added for Beta 2
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
$S/run-check.sh check-video-2 --check-video
$S/run-check.sh check-video-3 --check-video
$S/run-check.sh check-isolation-1 --check-isolation
$S/run-check.sh check-isolation-2 --check-isolation
$S/run-check.sh check-isolation-3 --check-isolation
$S/run-check.sh check-delete-on-quit --check-delete-on-quit
$S/run-check.sh check-tls-floor --check-tls-floor
$S/run-check.sh check-revocation --check-revocation
$S/run-check.sh check-rfp-coherence --check-rfp-coherence
$S/run-check.sh static-no-gms-no-adjust --check-no-gms --check-no-adjust
$S/run-check.sh check-strings --check-strings
$S/run-check.sh self-test --self-test
$S/run-check.sh first-run-capture --first-run-capture
$S/run-check.sh check-no-remote-settings --check-no-remote-settings
echo BATCH2 DONE
