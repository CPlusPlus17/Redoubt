#!/bin/bash
# Regenerates the diff part of delete-on-quit-swipe.patch from the 157 tree.
set -eu
V=/home/mgysin/redoubt-artifacts/delete-on-quit
T=$V/repo/librewolf-157.0-3
B=$V/gen/base
rm -rf $B; mkdir -p $B
P=mobile/android/fenix/app/src/main
python3 - "$T" "$B" <<'PY'
import sys, os, shutil
T, B = sys.argv[1:]
P = "mobile/android/fenix/app/src/main"
def base(rel, pairs):
    s = open(os.path.join(T, rel)).read()
    for new, old in pairs:
        assert s.count(new) == 1, (rel, new[:60])
        s = s.replace(new, old)
    os.makedirs(os.path.dirname(os.path.join(B, rel)), exist_ok=True)
    open(os.path.join(B, rel), "w").write(s)
base(P + "/java/org/mozilla/fenix/components/menu/MenuDialogFragment.kt", [(
"""                            // Redoubt LW-M7-45: confirm the deletion, then record the clean quit.
                            org.mozilla.fenix.lw.DeleteOnQuitGuard.get(activity).onSessionEnding("quit")
""", "")])
base(P + "/AndroidManifest.xml", [(
"""
        <!-- Redoubt LW-M7-45: receives onTaskRemoved for "Delete browsing data on quit". -->
        <service
            android:name=".lw.DeleteOnQuitTaskService"
            android:exported="false"
            android:stopWithTask="false" />
""", "")])
PY
cp $V/FenixApplication.kt.base $B/FenixApplication.kt
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
d $P/AndroidManifest.xml $B/$P/AndroidManifest.xml
d $P/java/org/mozilla/fenix/FenixApplication.kt $B/FenixApplication.kt
d $P/java/org/mozilla/fenix/components/menu/MenuDialogFragment.kt $B/$P/java/org/mozilla/fenix/components/menu/MenuDialogFragment.kt
d $P/java/org/mozilla/fenix/lw/DeleteOnQuitGuard.kt ""
d mobile/android/fenix/app/src/test/java/org/mozilla/fenix/lw/DeleteOnQuitGuardTest.kt ""
} > $V/gen/body.diff
grep -c '^@@' $V/gen/body.diff
