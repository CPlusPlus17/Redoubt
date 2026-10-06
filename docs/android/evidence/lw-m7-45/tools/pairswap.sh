#!/bin/bash
# Per-file replay on pristine 157.0: list order vs delete-on-quit-swipe moved
# directly before each partner. Prints apply status and whether results match.
set -u
V=/home/mgysin/redoubt-artifacts/delete-on-quit
R=${R:-$V/repo}
UP=${UP:-$V/up157/firefox-157.0}
ME=patches/android/delete-on-quit-swipe.patch
cd $R
mapfile -t LIST < <( (grep -v '^#' assets/patches/common.txt; grep -v '^#' assets/patches/android.txt) | awk 'NF{print $1}')
replay() { # outdir file order...
  local out=$1 f=$2; shift 2
  mkdir -p $out/$(dirname $f); cp $UP/$f $out/$f
  for p in "$@"; do
    filterdiff -i "*/$f" $R/$p > $out/x.diff
    [ -s $out/x.diff ] || continue
    if ! (cd $out && patch -p1 -s --no-backup-if-mismatch < x.diff > x.log 2>&1); then echo "  FAIL $p"; cat $out/x.log; return 1; fi
    grep -q fuzz $out/x.log && echo "  fuzz in $p: $(grep fuzz $out/x.log)"
  done; return 0
}
for partner in "$@"; do
  for f in mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt mobile/android/fenix/app/src/main/AndroidManifest.xml; do
    filterdiff -i "*/$f" $R/$partner | grep -q . || continue
    W=$(mktemp -d)
    replay $W/a $f "${LIST[@]}" || { echo "$partner $f: list order FAILS"; continue; }
    swapped=()
    for p in "${LIST[@]}"; do [ "$p" = "$ME" ] && continue; [ "$p" = "$partner" ] && swapped+=("$ME"); swapped+=("$p"); done
    if replay $W/b $f "${swapped[@]}"; then
      cmp -s $W/a/$f $W/b/$f && r=identical || r=DIFFERENT
      echo "$(basename $partner) $(basename $f): swapped applies, $r"
    else echo "$(basename $partner) $(basename $f): swapped FAILS"; fi
    rm -rf $W
  done
done
