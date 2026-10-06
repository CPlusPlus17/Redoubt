#!/bin/bash
# Regenerates delete-on-quit-swipe.patch (header + diff) from the edited 157 tree.
# gen/base2 holds the four upstream files as the series leaves them without this patch.
set -eu
V=/home/mgysin/redoubt-artifacts/delete-on-quit
T=$V/repo/librewolf-157.0-3
B=$V/gen/base2
P=mobile/android/fenix/app/src/main
d(){ # rel, basefile-or-empty
  local rel=$1 bf=$2
  echo "diff --git a/$rel b/$rel"
  if [ -z "$bf" ]; then
    echo "new file mode 100644"
    diff -u --label /dev/null --label "b/$rel" /dev/null "$T/$rel" || true
  else
    diff -u --label "a/$rel" --label "b/$rel" "$bf" "$T/$rel" || true
  fi
}
{
cat $V/gen/header2.txt
d $P/AndroidManifest.xml $B/$P/AndroidManifest.xml
d $P/java/org/mozilla/fenix/FenixApplication.kt $B/$P/java/org/mozilla/fenix/FenixApplication.kt
d $P/java/org/mozilla/fenix/components/Core.kt $B/$P/java/org/mozilla/fenix/components/Core.kt
d $P/java/org/mozilla/fenix/components/menu/MenuDialogFragment.kt $B/$P/java/org/mozilla/fenix/components/menu/MenuDialogFragment.kt
d $P/java/org/mozilla/fenix/lw/DeleteOnQuitGuard.kt ""
d $P/java/org/mozilla/fenix/lw/DeleteOnQuitStartGateMiddleware.kt ""
d mobile/android/fenix/app/src/test/java/org/mozilla/fenix/lw/DeleteOnQuitGuardTest.kt ""
d mobile/android/fenix/app/src/test/java/org/mozilla/fenix/lw/DeleteOnQuitStartGateMiddlewareTest.kt ""
} > $V/repo/patches/android/delete-on-quit-swipe.patch
grep -c '^@@' $V/repo/patches/android/delete-on-quit-swipe.patch
