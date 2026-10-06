#!/bin/bash
# Gates on the merged android/firefox-158 (scratch worktree, version files set to 158.0b4, not committed).
D=/home/mgysin/redoubt-artifacts/delete-on-quit; G=$D/build3/gates158
r(){ local n=$1; shift; "$@" > $G/$n.out 2>&1; echo "$n exit=$?" | tee -a $G/summary.txt; }
cd $D/repo158
: > $G/summary.txt
echo "HEAD $(git rev-parse HEAD)" >> $G/summary.txt
r board-check python3 docs/android/board.py --check
r board-scope python3 docs/android/board.py --check-scope
r lint-patch-scope python3 scripts/lint-patch-scope.py
r check-patch-order python3 scripts/check-patch-order.py
r site-check python3 scripts/site-check.py site
echo 158.0b4 > version; echo 158.0b4 > version.android
r patchfail-android-158.0b4 ./scripts/check-patchfail.sh --targets=android
r patchfail-desktop-158.0b4 ./scripts/check-patchfail.sh --targets=desktop
git checkout -- version version.android
echo ALLDONE >> $G/summary.txt
