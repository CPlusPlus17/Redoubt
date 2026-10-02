#!/bin/bash
G=/home/mgysin/redoubt-artifacts/esr-153.4/build/rc2/final/gates
cd /home/mgysin/redoubt-artifacts/esr-153.4/repo
git rev-parse HEAD > $G/head.txt; git status --porcelain > $G/status.txt
./scripts/check-patchfail.sh --targets=android > $G/patchfail.out 2>&1; echo patchfail=$? > $G/summary.txt
python3 scripts/lint-patch-scope.py > $G/lint.out 2>&1; echo lint=$? >> $G/summary.txt
python3 scripts/check-patch-order.py > $G/order.out 2>&1; echo order=$? >> $G/summary.txt
python3 docs/android/board.py --check > $G/check.out 2>&1; echo check=$? >> $G/summary.txt
python3 docs/android/board.py --check-scope > $G/scope.out 2>&1; echo scope=$? >> $G/summary.txt
for t in scripts/tests/test-*.py; do n=$(basename $t .py); python3 $t > $G/tests-$n.out 2>&1; echo "$n=$?" >> $G/summary.txt; done
echo GATES DONE >> $G/summary.txt
