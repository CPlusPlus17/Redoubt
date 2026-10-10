#!/bin/bash
# Downgrade guard (new in 157.0.1-1). 157.0.1-1's versionCodes (…816-823) sit BELOW 158.0-1 Beta 1's
# (…904-911) on purpose, so a beta tester is never moved back to 157. Proof on the device:
#   1. fresh install of the 158.0-1 Beta 1 x86_64 APK (throwaway-signed, the same cert as the candidate),
#      one launch so a 158 profile exists;
#   2. `adb install -r` of the 157.0.1-1 candidate (no -d) must FAIL with INSTALL_FAILED_VERSION_DOWNGRADE;
#   3. Beta 1 must still be installed: same versionCode, same firstInstallTime, and it starts.
# The two certificates are printed so the refusal cannot be a signer mismatch.
# usage: downgrade-guard.sh SERIAL OUTDIR
S=$1; O=$2; mkdir -p $O
R=/home/mgysin/redoubt-artifacts/release-157.0.1-1
ADB="/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb -s $S"
APKSIGNER=~/.local/state/codex-desktop/tmp/fivur-android-sdk36/build-tools/36.0.0/apksigner
BETA=$R/apk/fenix-x86_64-158.0-1-beta1-throwaway.apk
CAND=$R/apk/fenix-x86_64-157.0.1-1-throwaway.apk
PKG=org.redoubtbrowser
pkginfo() { $ADB shell dumpsys package $PKG | grep -E 'versionCode=|versionName=|firstInstallTime=|lastUpdateTime=' | sed 's/^ *//'; }
{
echo "== inputs"; sha256sum $BETA $CAND
for a in $BETA $CAND; do echo "-- certs of $(basename $a)"; $APKSIGNER verify --print-certs $a 2>/dev/null | grep -E 'certificate (DN|SHA-256)'; done
echo "== 1. fresh install of 158.0-1 Beta 1"
$ADB uninstall $PKG >/dev/null 2>&1
$ADB install $BETA; echo "install exit: $?"
$ADB shell monkey -p $PKG -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; sleep 25
echo "alive after 25 s: $($ADB shell pidof $PKG)"
$ADB shell am force-stop $PKG
before=$(pkginfo); echo "$before"
echo "== 2. adb install -r 157.0.1-1 over it (no -d)"
$ADB logcat -c
$ADB install -r $CAND > $O/install-r.out 2>&1; rc=$?
cat $O/install-r.out; echo "install -r exit: $rc"
$ADB logcat -d | grep -iE 'VERSION_DOWNGRADE|Downgrade detected|PackageManager.*downgrade' | head -5
echo "== 2b. the same through pm install (streamed), as an installer app would"
$ADB push $CAND /data/local/tmp/cand.apk >/dev/null
$ADB shell pm install -r /data/local/tmp/cand.apk > $O/pm-install-r.out 2>&1; rc2=$?
$ADB shell rm -f /data/local/tmp/cand.apk
cat $O/pm-install-r.out; echo "pm install -r exit: $rc2"
echo "== 3. Beta 1 still installed and starts"
after=$(pkginfo); echo "$after"
[ "$before" = "$after" ] && echo "package record unchanged: yes" || echo "package record unchanged: NO"
$ADB logcat -b crash -c
$ADB shell monkey -p $PKG -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; sleep 20
echo "alive after 20 s: $($ADB shell pidof $PKG)"; echo "crash buffer lines: $($ADB logcat -d -b crash | grep -c $PKG)"
$ADB exec-out screencap -p > $O/beta1-after-refusal.png
$ADB shell am force-stop $PKG
grep -q INSTALL_FAILED_VERSION_DOWNGRADE $O/install-r.out && [ $rc -ne 0 ] && v1=1 || v1=0
grep -q INSTALL_FAILED_VERSION_DOWNGRADE $O/pm-install-r.out && v2=1 || v2=0
[ "$before" = "$after" ] && v3=1 || v3=0
echo "== verdict: adb-install-refused=$v1 pm-install-refused=$v2 beta-untouched=$v3"
[ $v1 = 1 ] && [ $v2 = 1 ] && [ $v3 = 1 ] && echo "DOWNGRADE GUARD PASS" || echo "DOWNGRADE GUARD FAIL"
} > $O/downgrade-guard.txt 2>&1
cat $O/downgrade-guard.txt
grep -q "DOWNGRADE GUARD PASS" $O/downgrade-guard.txt
