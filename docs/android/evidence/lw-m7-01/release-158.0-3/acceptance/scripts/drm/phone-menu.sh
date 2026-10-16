#!/bin/bash
# 158.0-3: LW-M7-38 menu check (no "Report broken site") on ONE named phone; installs the arm64-v8a candidate,
# runs menu-check.py, uninstalls. org.redoubtbrowser must not be installed before. usage: phone-menu.sh SERIAL NAME OUT
set -u
SERIAL=$1; NAME=$2; OUT=$3
R=/home/mgysin/redoubt-artifacts/release-158.0-3; D=$(cd "$(dirname "$0")" && pwd)
ADB=/home/mgysin/redoubt-artifacts/android-sdk/platform-tools/adb
export DRM_ALLOW_DEVICE=$SERIAL EME_OUT=$R/eme-out
[ -z "$($ADB -s $SERIAL shell pm list packages org.redoubtbrowser | tr -d '\r' | grep -x package:org.redoubtbrowser)" ] || { echo "already installed; stopping"; exit 1; }
mkdir -p $OUT
$ADB -s $SERIAL install $R/apk/fenix-arm64-v8a-158.0-3-throwaway.apk
$ADB -s $SERIAL reverse tcp:18766 tcp:18766
$ADB -s $SERIAL shell am start -n org.redoubtbrowser/org.mozilla.fenix.HomeActivity >/dev/null 2>&1; sleep 8
python3 $D/menu-check.py $SERIAL $NAME $OUT 18766; echo "menu-check exit=$?"
python3 -c "import json;d=json.load(open('$OUT/$NAME-menu.json'));print('report_broken_site_offered',d['report_broken_site_offered'],'raw_xml_mentions',d['raw_xml_mentions']);print('more:',d['more'])"
$ADB -s $SERIAL reverse --remove tcp:18766
$ADB -s $SERIAL uninstall org.redoubtbrowser
