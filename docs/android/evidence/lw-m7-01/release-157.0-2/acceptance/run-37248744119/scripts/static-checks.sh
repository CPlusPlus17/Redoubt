#!/bin/bash
# Static checks of the four unsigned APKs of CI run 37248744119 (157.0-2 rebuild).
# usage: static-checks.sh OUTDIR    (writes the static/*.txt files; reads only, builds nothing)
set -u
R=/home/mgysin/redoubt-artifacts/stable/accept2
REPO=$R/repo
CI=$R/ci/redoubt-android-unsigned
B5=/home/mgysin/redoubt-artifacts/keep/beta5-unsigned
AAPT2=$R/x/aapt2/aapt2
APKSIGNER=~/.local/state/codex-desktop/tmp/fivur-android-sdk36/build-tools/36.0.0/apksigner
O=$1; mkdir -p "$O"
X=$R/x; ABIS="universal arm64-v8a armeabi-v7a x86_64"
apk() { echo "$CI/fenix-$1-release-unsigned.apk"; }

# extract
for a in $ABIS; do
  rm -rf $X/elf/$a $X/omni/$a; mkdir -p $X/elf/$a $X/omni/$a
  unzip -q -o "$(apk $a)" 'lib/*' -d $X/elf/$a
  unzip -q -o "$(apk $a)" 'assets/omni.ja' 'assets/extensions/*' 'classes*.dex' -d $X/omni/$a 2>/dev/null
done
rm -rf $X/omnix $X/b5omni; mkdir -p $X/omnix $X/b5omni
(cd $X/omnix && unzip -q -o $X/omni/x86_64/assets/omni.ja 2>/dev/null)
unzip -q -o $B5/fenix-x86_64-release-unsigned.apk assets/omni.ja -d $X/b5zip; mv $X/b5zip/assets/omni.ja $X/b5omni/; rm -rf $X/b5zip
(cd $X/b5omni && unzip -q -o omni.ja 2>/dev/null)

# S1 badging
{ for a in $ABIS; do echo "== $a"; $AAPT2 dump badging "$(apk $a)" | grep -E "^package:|^targetSdk|^application-label:|^native-code"; done
  echo "== Beta 5 (keep/beta5-unsigned)"; for a in $ABIS; do echo "$a $($AAPT2 dump badging $B5/fenix-$a-release-unsigned.apk | grep -o "versionCode='[0-9]*'")"; done
} > $O/apk-badging.txt

# S2 ELF per ABI
{ for a in $ABIS; do echo "== $a"
  (cd $X/elf/$a && for f in lib/*/*; do d=$(basename $(dirname $f)); t=$(file -b "$f" | cut -d, -f1-2); echo -e "$d\t$t"; done | sort | uniq -c | awk '{c=$1; $1=""; sub(/^ /,""); print $0"\t"c" libs"}')
  echo "libxul:"; for f in $X/elf/$a/lib/*/libxul.so; do echo "  ${f#$X/elf/} $(file -b $f | cut -d, -f1-2)"; done
done; } > $O/elf-per-abi.txt

# S3 unsigned
{ echo "apksigner 36.0.0 verify on each unsigned APK (exit 1 + 'no signatures' = unsigned):"
  for a in $ABIS; do n=$(unzip -Z1 "$(apk $a)" | grep -cE '^META-INF/[^/]*\.(RSA|DSA|EC|SF)$'); echo "-- $a: META-INF signature entries (.RSA/.DSA/.EC/.SF): $n"
    $APKSIGNER verify "$(apk $a)" 2>&1 | grep -v WARNING; echo "apksigner exit: ${PIPESTATUS[0]}"; done; } > $O/unsigned.txt

# S4 branding
{ echo "omni.ja branding (x86_64):"
  echo "-- localization/en-US/branding/brand.ftl"; grep -E "^-(brand|vendor)" $X/omnix/localization/en-US/branding/brand.ftl | sed 's/^/   /'
  echo "-- chrome/en-US/locale/branding/brand.properties"; grep -E "^brand" $X/omnix/chrome/en-US/locale/branding/brand.properties | sed 's/^/   /'
  echo "-- against Beta 5 x86_64 omni.ja:"
  for f in localization/en-US/branding/brand.ftl localization/en-US/toolkit/branding/brandings.ftl chrome/en-US/locale/branding/brand.properties; do
    cmp -s $X/omnix/$f $X/b5omni/$f && echo "   $f: same" || echo "   $f: DIFFERS"; done
  for f in $(cd $X/omnix && find . -path '*branding*' -type f -name '*.png' | sort); do cmp -s $X/omnix/$f $X/b5omni/$f && echo "   $f: same" || echo "   $f: DIFFERS"; done
  echo "-- omni.ja sha256 per APK:"; for a in $ABIS; do echo "   $a $(sha256sum $X/omni/$a/assets/omni.ja | cut -c1-64)"; done
} > $O/omni-branding.txt

# S5 uBO
{ for a in $ABIS; do echo "== $a"; d=$X/omni/$a/assets/extensions
  echo "ubo-extension.json (repo): $(tr -d '\n' < $REPO/assets/ubo-extension.json 2>/dev/null | cut -c1-300)"
  x=$(find $d -name 'ublock*.xpi' | head -1); echo "xpi: ${x#$X/omni/$a/}"
  echo "xpi sha256: $(sha256sum $x | cut -c1-64)"
  echo "xpi manifest version: $(unzip -p $x manifest.json | python3 -c 'import json,sys; m=json.load(sys.stdin); print(m["version"], (m.get("browser_specific_settings") or m.get("applications"))["gecko"]["id"])')"
  echo "xpi signed: $(unzip -Z1 $x | grep -E '^META-INF/' | tr '\n' ' ')"
done; } > $O/ubo-and-omni.txt 2>&1

# S6 librewolf.cfg
{ c=$X/omnix/defaults/autoconfig/librewolf.cfg
  echo "Packaged cfg: assets/omni.ja!/defaults/autoconfig/librewolf.cfg, sha256 $(sha256sum $c | cut -c1-64)"
  for a in $ABIS; do (cd $X/omni/$a/assets && unzip -p omni.ja defaults/autoconfig/librewolf.cfg | sha256sum | sed "s/ .*/  $a/"); done
  cat $REPO/settings/common.cfg $REPO/settings/android.cfg > $X/cfg-expected
  echo "Byte-equal to settings/common.cfg + settings/android.cfg at settings $(git -C $REPO/settings rev-parse HEAD): $(cmp -s $c $X/cfg-expected && echo yes || echo NO)"
  echo; echo "Active lines of interest:"
  grep -nE '^\s*(lockPref|defaultPref|pref)\("(network\.lna\.allow_top_level_navigation|browser\.ipProtection\.[a-z.]*|privacy\.restrict3rdpartystorage\.heuristic\.(navigation|recently_visited))"' $c
  echo; echo "uBO catalog bootstrap values (in file order; the later android.cfg value wins):"
  grep -nA2 '"librewolf.uBO.assetsBootstrapLocation",$' $c | grep -E 'https?://'
} > $O/librewolf-cfg.txt

# S7 update-check key + endpoint in dex
{ K=$REPO/assets/update-check.android.pubkey; key=$(grep -v -- ----- $K | tr -d '\n'); [ -z "$key" ] && key=$(tr -d '\n' < $K)
  echo "assets/update-check.android.pubkey sha256 $(sha256sum $K | cut -c1-64)"; echo "key: $key"
  echo "endpoint: https://redoubtbrowser.org/update/android/latest.json"
  for a in $ABIS; do echo "== $a"; for d in $X/omni/$a/classes*.dex; do
    k=$(grep -c -a -F "$key" $d); e=$(grep -c -a -F "https://redoubtbrowser.org/update/android/latest.json" $d); u=$(grep -c -a -F "Redoubt-UpdateCheck/1" $d); o=$(grep -c -a -F "/updates/android/" $d)
    [ $((k+e+u+o)) -gt 0 ] && echo "  $(basename $d): key=$k endpoint=$e user-agent=$u old-/updates/-path=$o"; done; done
} > $O/update-check-static.txt

# S10 build id + entries vs Beta 5
{ echo "Build ID / version as packaged (x86_64):"
  grep -nE 'MOZ_APP_VERSION|MOZ_BUILDID|MOZ_UPDATE_CHANNEL' $X/omnix/modules/AppConstants.sys.mjs | sed 's/^/  /'
  for a in x86_64 arm64-v8a armeabi-v7a; do echo "  lib/$a/libxul.so contains 20261005000000: $(grep -c -a 20261005000000 $X/elf/$a/lib/$a/libxul.so)"; done
} > $O/build-id.txt
python3 - $CI/fenix-x86_64-release-unsigned.apk $B5/fenix-x86_64-release-unsigned.apk $X/omni/x86_64/assets/omni.ja $X/b5omni/omni.ja > $O/entries-vs-beta5-x86_64.txt <<'PY'
import sys, zipfile, hashlib
def h(z): return {i.filename: hashlib.sha256(z.read(i)).hexdigest() for i in z.infolist() if not i.is_dir()}
for label, a, b in (("APK", sys.argv[1], sys.argv[2]), ("omni.ja", sys.argv[3], sys.argv[4])):
    A, B = h(zipfile.ZipFile(a)), h(zipfile.ZipFile(b))
    diff = sorted(k for k in set(A) | set(B) if A.get(k) != B.get(k))
    print("== %s: %d entries here, %d in Beta 5, %d differ" % (label, len(A), len(B), len(diff)))
    for k in diff: print("  %s%s" % (k, "" if k in A and k in B else "  (only in %s)" % ("157.0-2" if k in A else "Beta 5")))
PY
echo STATIC DONE
