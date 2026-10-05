set -eu
cd /work/src
patch -p1 --no-backup-if-mismatch -R < /s/old/SettingsFragment.kt.diff
patch -p1 --no-backup-if-mismatch -R < /s/old/preferences.xml.diff
patch -p1 --no-backup-if-mismatch < /s/new/SettingsFragment.kt.diff
patch -p1 --no-backup-if-mismatch < /s/new/preferences.xml.diff
for f in UpdateCheck.kt lw_update_check.xml UpdateCheckerTest.kt UpdateCheckSwitchTest.kt; do
  p=$(sed -n 's/^+++ b\///p' /s/new/$f.diff)
  rm -f "$p"
  patch -p1 --no-backup-if-mismatch < /s/new/$f.diff
done
git diff --stat 2>/dev/null || true
set +e
./mach gradle :fenix:testDebugUnitTest --tests 'org.mozilla.fenix.lw.*' --tests org.mozilla.fenix.settings.SettingsFragmentTest \
  --no-daemon --no-build-cache --max-workers=4 -PgleanBuildDate=2026-10-04T12:00:00
rc=$?
mkdir -p /s/results; cp -r obj-x86_64/gradle/build/mobile/android/fenix/app/test-results/testDebugUnitTest/. /s/results/ 2>/dev/null
echo GRADLE_EXIT=$rc
exit $rc
