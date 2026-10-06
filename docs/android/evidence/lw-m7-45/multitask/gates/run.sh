#!/bin/bash
# LW-M7-45 multi-task fix: gates in series. 157.0 in the fix worktree; 158.0b4 in a scratch
# worktree of android/firefox-158 (e55a8329) with the new patch text copied in and version
# files set to 158.0b4 (not committed).
V=/home/mgysin/redoubt-artifacts/delete-on-quit
G=$V/build3/gates
r(){ local n=$1; shift; "$@" > $G/$n.out 2>&1; echo "$n exit=$?" | tee -a $G/summary.txt; }
: > $G/summary.txt
cd $V/repo
echo "fix tree HEAD $(git rev-parse HEAD) + worktree diff sha256 $(git diff | sha256sum | cut -c1-16); patch sha256 $(sha256sum patches/android/delete-on-quit-swipe.patch | cut -c1-16)" >> $G/summary.txt
r check-patch-order python3 scripts/check-patch-order.py
r lint-patch-scope python3 scripts/lint-patch-scope.py
r board-check python3 docs/android/board.py --check
r board-scope python3 docs/android/board.py --check-scope
r patchfail-android-157.0 ./scripts/check-patchfail.sh --targets=android
cd $V/repo158
echo "158 tree HEAD $(git rev-parse HEAD); patch sha256 $(sha256sum patches/android/delete-on-quit-swipe.patch | cut -c1-16)" >> $G/summary.txt
echo 158.0b4 > version; echo 158.0b4 > version.android
r patchfail-android-158.0b4 ./scripts/check-patchfail.sh --targets=android
r patchfail-desktop-158.0b4 ./scripts/check-patchfail.sh --targets=desktop
r check-patch-order-158 python3 scripts/check-patch-order.py
git checkout -- version version.android
echo ALLDONE >> $G/summary.txt
