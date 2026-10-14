#!/bin/bash
I=/home/mgysin/redoubt-artifacts/iso-proto/treecmp
for d in base feat; do (cd $I/$d && make android-dir TARGETS=android > $I/$d.make.log 2>&1; echo "$d make exit $?" >> $I/result.txt); done
cd $I && diff -r --no-dereference base/librewolf-158.0-1 feat/librewolf-158.0-1 > $I/tree-diff.txt 2>&1; echo "diff exit $?" >> $I/result.txt
for d in base feat; do (cd $I/$d/librewolf-158.0-1 && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > $I/$d.tree.sha256; echo "$d files $(wc -l < $I/$d.tree.sha256) manifest $(sha256sum $I/$d.tree.sha256 | cut -d' ' -f1)" >> $I/result.txt); done
echo done >> $I/result.txt
