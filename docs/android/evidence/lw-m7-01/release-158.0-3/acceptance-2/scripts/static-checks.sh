#!/bin/bash
# Static checks of the four unsigned APKs of the 158.0-3 release run (158.0-2 + LW-M7-39 DRM under isolation + LW-M7-38).
# Copied from the 158.0-2 acceptance; the reference build is now 158.0-2 (the unsigned APKs of CI run
# 38549776387, the same Firefox 158.0 source tarball). S1 also lists 158.0-1's and 157.0.1-1's codes.
# S11 now runs isolation-gate-dex.py on the reference too (158.0-2 has the same gate). New for 158.0-3:
# S16 (isolation-eme.patch compiled in). Second 158.0-3 acceptance: S10 uses BUILD_DATE; new S17 (the Android 12-13
# fix's log lines in libxul) and S18 (APK entries against the first 158.0-3 build, CI run 38775774781).
# usage: static-checks.sh OUTDIR    (writes the static/*.txt files; reads only, builds nothing)
set -u
R=/home/mgysin/redoubt-artifacts/release-158.0-3/accept2
REPO=$R/repo
CI=$R/ci/redoubt-android-unsigned
B5=/home/mgysin/redoubt-artifacts/release-158.0-2/ci/redoubt-android-unsigned   # 158.0-2 unsigned, CI run 38549776387 (variable name kept: the reference build)
B1=/home/mgysin/redoubt-artifacts/release-158.0-1/ci/redoubt-android-unsigned   # 158.0-1 unsigned, CI run 38432799414
P3=/home/mgysin/redoubt-artifacts/release-157.0.1-1/signing-bundle   # 157.0.1-1 unsigned, CI run 37993605790
AAPT2=$R/x/aapt2/aapt2
APKSIGNER=~/.local/state/codex-desktop/tmp/fivur-android-sdk36/build-tools/36.0.0/apksigner
O=$1; mkdir -p "$O"
BUILD_DATE=${BUILD_DATE:?set BUILD_DATE}
F3=/home/mgysin/redoubt-artifacts/release-158.0-3/ci/redoubt-android-unsigned   # first 158.0-3 build, CI run 38775774781 (not signed, superseded)
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
  echo "== 158.0-2 (CI run 38549776387, unsigned)"; for a in $ABIS; do echo "$a $($AAPT2 dump badging $B5/fenix-$a-release-unsigned.apk | grep -oE "versionCode='[0-9]*'|versionName='[^']*'" | tr '\n' ' ')"; done
  echo "== 158.0-1 (CI run 38432799414, unsigned)"; for a in $ABIS; do echo "$a $($AAPT2 dump badging $B1/fenix-$a-release-unsigned.apk | grep -oE "versionCode='[0-9]*'|versionName='[^']*'" | tr '\n' ' ')"; done
  echo "== 157.0.1-1 (CI run 37993605790, unsigned)"; for a in $ABIS; do echo "$a $($AAPT2 dump badging $P3/fenix-$a-release-unsigned.apk | grep -oE "versionCode='[0-9]*'|versionName='[^']*'" | tr '\n' ' ')"; done
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
  echo "-- against 158.0-2 x86_64 omni.ja:"
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

# S10 build id + entries vs 158.0-2
{ echo "Build ID / version as packaged (x86_64):"
  grep -nE 'MOZ_APP_VERSION|MOZ_BUILDID|MOZ_UPDATE_CHANNEL' $X/omnix/modules/AppConstants.sys.mjs | sed 's/^/  /'
  for a in x86_64 arm64-v8a armeabi-v7a; do echo "  lib/$a/libxul.so contains $BUILD_DATE: $(grep -c -a $BUILD_DATE $X/elf/$a/lib/$a/libxul.so)"; done
} > $O/build-id.txt
python3 - $CI/fenix-x86_64-release-unsigned.apk $B5/fenix-x86_64-release-unsigned.apk $X/omni/x86_64/assets/omni.ja $X/b5omni/omni.ja > $O/entries-vs-158.0-2-x86_64.txt <<'PY'
import sys, zipfile, hashlib
def h(z): return {i.filename: hashlib.sha256(z.read(i)).hexdigest() for i in z.infolist() if not i.is_dir()}
for label, a, b in (("APK", sys.argv[1], sys.argv[2]), ("omni.ja", sys.argv[3], sys.argv[4])):
    A, B = h(zipfile.ZipFile(a)), h(zipfile.ZipFile(b))
    diff = sorted(k for k in set(A) | set(B) if A.get(k) != B.get(k))
    print("== %s: %d entries here, %d in 158.0-2, %d differ" % (label, len(A), len(B), len(diff)))
    for k in diff: print("  %s%s" % (k, "" if k in A and k in B else "  (only in %s)" % ("158.0-3" if k in A else "158.0-2")))
PY

# S6b packaged cfg vs 158.0-2's packaged cfg
{ a=$(sha256sum $X/omnix/defaults/autoconfig/librewolf.cfg | cut -c1-64); b=$(sha256sum $X/b5omni/defaults/autoconfig/librewolf.cfg | cut -c1-64)
  echo "158.0-3 packaged librewolf.cfg sha256 $a"; echo "158.0-2 packaged librewolf.cfg sha256 $b"
  cmp -s $X/omnix/defaults/autoconfig/librewolf.cfg $X/b5omni/defaults/autoconfig/librewolf.cfg && echo "byte-equal: yes" || { echo "byte-equal: NO"; diff -u $X/b5omni/defaults/autoconfig/librewolf.cfg $X/omnix/defaults/autoconfig/librewolf.cfg; }
} > $O/librewolf-cfg-vs-158.0-2.txt

# S11 isolation (158.0-2): the runtime gate GeckoProvider.isolatedContentEnabled() (SDK_INT >= 31) feeds both
# GeckoRuntimeSettings.Builder calls; the gate pref and its eleven media prefs are compiled into libxul.
DD=~/.local/state/codex-desktop/tmp/fivur-android-sdk36/build-tools/36.0.0/dexdump
S=$(dirname "$(readlink -f "$0")")
{ for a in $ABIS; do echo "== $a (158.0-3)"; for d in $X/omni/$a/classes*.dex; do
    if $DD -d $d 2>/dev/null > $X/dexdump.txt && grep -q "GeckoProvider.createRuntime:" $X/dexdump.txt; then
      echo "-- $(basename $d)"; python3 $S/isolation-gate-dex.py $X/dexdump.txt; echo "isolation-gate-dex exit: $?"; fi; done; done
  echo "== x86_64 (158.0-2 reference: the same gate, isolation-gate-dex.py)"; rm -rf $X/p2dex; mkdir -p $X/p2dex; unzip -q -o $B5/fenix-x86_64-release-unsigned.apk 'classes*.dex' -d $X/p2dex
  for d in $X/p2dex/classes*.dex; do if $DD -d $d 2>/dev/null > $X/dexdump.txt && grep -q "GeckoProvider.createRuntime:" $X/dexdump.txt; then
      echo "-- $(basename $d)"; python3 $S/isolation-gate-dex.py $X/dexdump.txt; echo "isolation-gate-dex exit: $?"; fi; done
  rm -f $X/dexdump.txt
  echo; echo "Gate pref and GeckoView side (strings):"
  for a in x86_64 arm64-v8a armeabi-v7a; do echo "  lib/$a/libxul.so 'media.redoubt-isolation-media.enabled': $(grep -c -a -F media.redoubt-isolation-media.enabled $X/elf/$a/lib/$a/libxul.so)"; done
  for a in $ABIS; do for d in $X/omni/$a/classes*.dex; do c=$(grep -c -a -F media.redoubt-isolation-media.enabled $d); [ $c -gt 0 ] && echo "  $a $(basename $d) 'media.redoubt-isolation-media.enabled' x$c"; done; done
  echo "  158.0-2 x86_64 libxul.so 'media.redoubt-isolation-media.enabled': $(unzip -p $B5/fenix-x86_64-release-unsigned.apk lib/x86_64/libxul.so | grep -c -a -F media.redoubt-isolation-media.enabled)"
  echo; echo "Manifest (aapt2 dump xmltree), services with isolatedProcess=true / useAppZygote, x86_64:"
  for n in 158.0-3:$(apk x86_64) 158.0-2:$B5/fenix-x86_64-release-unsigned.apk; do
    $AAPT2 dump xmltree --file AndroidManifest.xml ${n#*:} > $X/manifest.txt
    echo "  ${n%%:*}: isolatedProcess=true attrs $(grep -c 'isolatedProcess.*=true' $X/manifest.txt), useAppZygote=true attrs $(grep -c 'useAppZygote.*=true' $X/manifest.txt)"; done
  rm -f $X/manifest.txt
} > $O/isolation-static.txt 2>&1

# S15 no build overlay (dev-app, patches/android/dev-app.patch) in the release APKs: package, label, deep-link scheme,
# launcher colour; and the workflow's own overlay guard in the CI log.
{ for a in $ABIS; do echo "== $a"
    $AAPT2 dump badging "$(apk $a)" | grep -oE "^package: name='[^']*'|^application-label:'[^']*'" | tr '\n' ' '; echo
    $AAPT2 dump strings "$(apk $a)" 2>/dev/null > $X/strings.txt
    echo "  resource strings 'Redoubt Dev': $(grep -c -F 'Redoubt Dev' $X/strings.txt)  'redoubt-dev': $(grep -c -F 'redoubt-dev' $X/strings.txt)"
    $AAPT2 dump resources "$(apk $a)" 2>/dev/null | grep -A1 'color/ic_launcher_background' | tr -s ' ' | tr '\n' ' '; echo
    n=0; for d in $X/omni/$a/classes*.dex; do n=$((n + $(grep -c -a -F 'org.redoubtbrowser.dev' $d))); done; echo "  dex 'org.redoubtbrowser.dev': $n"
    echo "  omni.ja librewolf.cfg 'OVERLAY' lines: $(cd $X/omni/$a/assets && unzip -p omni.ja defaults/autoconfig/librewolf.cfg | grep -c OVERLAY)"
  done; rm -f $X/strings.txt
  echo "== CI log (run.log.gz): $(zcat $R/ci/run.log.gz 2>/dev/null | grep -m1 -oE 'build overlays: none')"
} > $O/overlays-absent.txt 2>&1

# S12 store-installer list in the dex (UpdateCheck.STORE_INSTALLERS)
{ for a in $ABIS; do echo "== $a"; for d in $X/omni/$a/classes*.dex; do
    for s in org.fdroid.fdroid org.fdroid.basic com.looker.droidify com.machiav3lli.fdroid app.accrescent.client com.android.vending; do
      c=$(grep -c -a -F "$s" $d); [ $c -gt 0 ] && echo "  $(basename $d): $s x$c"; done; done; done
} > $O/store-installers-static.txt
# S14 LW-M7-46: the quiet-notice pref is compiled in (StaticPrefList in libxul, the pref name in the dex)
{ for a in x86_64 arm64-v8a armeabi-v7a; do echo "lib/$a/libxul.so 'librewolf.webgl.prompt.notice': $(grep -c -a -F librewolf.webgl.prompt.notice $X/elf/$a/lib/$a/libxul.so)"; done
  for a in $ABIS; do for d in $X/omni/$a/classes*.dex; do c=$(grep -c -a -F librewolf.webgl.prompt.notice $d); [ $c -gt 0 ] && echo "$a $(basename $d) 'librewolf.webgl.prompt.notice' x$c"; done; done
  echo "158.0-2 x86_64 libxul.so 'librewolf.webgl.prompt.notice': $(unzip -p $B5/fenix-x86_64-release-unsigned.apk lib/x86_64/libxul.so | grep -c -a -F librewolf.webgl.prompt.notice)"
  echo "'Canvas or WebGL was protected' string in the x86_64 APK resources (still present upstream of the gate, not shown):"
  $AAPT2 dump strings "$(apk x86_64)" 2>/dev/null | grep -c "Canvas or WebGL was protected"
} > $O/webgl-notice-static.txt
# S16 LW-M7-39 (isolation-eme.patch): the locked Widevine-answer pref and the parent's log line are in libxul;
# 158.0-2 has neither. LW-M7-38 (no-webcompat-reporter.patch) is graded on the device (menu), not here.
{ for a in x86_64 arm64-v8a armeabi-v7a; do echo "lib/$a/libxul.so 'media.redoubt-eme.widevine-support': $(grep -c -a -F media.redoubt-eme.widevine-support $X/elf/$a/lib/$a/libxul.so)  'Redoubt isolation-eme': $(grep -c -a -F 'Redoubt isolation-eme' $X/elf/$a/lib/$a/libxul.so)"; done
  echo "158.0-2 x86_64 libxul.so 'media.redoubt-eme.widevine-support': $(unzip -p $B5/fenix-x86_64-release-unsigned.apk lib/x86_64/libxul.so | grep -c -a -F media.redoubt-eme.widevine-support)"
  echo "packaged librewolf.cfg (x86_64) lines setting media.eme.enabled: $(grep -cE '^[[:space:]]*(lockPref|defaultPref|pref)\("media\.eme\.enabled"' $X/omnix/defaults/autoconfig/librewolf.cfg)"
  echo "158.0-2 packaged librewolf.cfg lines setting media.eme.enabled: $(grep -cE '^[[:space:]]*(lockPref|defaultPref|pref)\("media\.eme\.enabled"' $X/b5omni/defaults/autoconfig/librewolf.cfg)"
} > $O/eme-static.txt
# S17 LW-M7-39 Android 12-13 fix (isolation-eme.patch item 7): its two log lines are in every ABI's libxul, and in
# none of the first 158.0-3 build's.
{ for a in x86_64 arm64-v8a armeabi-v7a; do echo "lib/$a/libxul.so 'service certificate provided; requesting the': $(grep -c -a -F 'service certificate provided; requesting the' $X/elf/$a/lib/$a/libxul.so)  'KEY_REQUIRED after the service certificate': $(grep -c -a -F 'KEY_REQUIRED after the service certificate' $X/elf/$a/lib/$a/libxul.so)"; done
  echo "first 158.0-3 build x86_64 libxul.so 'service certificate provided; requesting the': $(unzip -p $F3/fenix-x86_64-release-unsigned.apk lib/x86_64/libxul.so | grep -c -a -F 'service certificate provided; requesting the')"
} > $O/eme-fix-static.txt
# S18 entries against the first 158.0-3 build (x86_64)
rm -rf $X/f3zip; mkdir -p $X/f3zip; unzip -q -o $F3/fenix-x86_64-release-unsigned.apk assets/omni.ja -d $X/f3zip
python3 - $CI/fenix-x86_64-release-unsigned.apk $F3/fenix-x86_64-release-unsigned.apk $X/omni/x86_64/assets/omni.ja $X/f3zip/assets/omni.ja > $O/entries-vs-first-158.0-3-x86_64.txt <<'PY'
import sys, zipfile, hashlib
def h(z): return {i.filename: hashlib.sha256(z.read(i)).hexdigest() for i in z.infolist() if not i.is_dir()}
for label, a, b in (("APK", sys.argv[1], sys.argv[2]), ("omni.ja", sys.argv[3], sys.argv[4])):
    A, B = h(zipfile.ZipFile(a)), h(zipfile.ZipFile(b))
    diff = sorted(k for k in set(A) | set(B) if A.get(k) != B.get(k))
    print("== %s: %d entries here, %d in the first 158.0-3 build, %d differ" % (label, len(A), len(B), len(diff)))
    for k in diff: print("  %s" % k)
PY
rm -rf $X/f3zip
echo STATIC DONE
