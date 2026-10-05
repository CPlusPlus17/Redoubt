#!/usr/bin/env bash
#
# test-update-check-jvm.sh -- run the update check's own Kotlin on the host JVM,
# without building Fenix, and cross-check it against the publishing tools.
#
#   scripts/tests/test-update-check-jvm.sh --tree <firefox source tree> \
#       --gradle-home <a Fenix build's gradle-home> --android-jar <platforms/android-NN/android.jar>
#
# What it does, in order:
#   1. extracts UpdateCheck.kt and UpdateCheckerTest.kt from
#      patches/android/update-check.patch (the files a build would compile),
#      and checks the Settings-switch wiring in the same patch: the row is
#      android:persistent="false", SettingsFragment hands it to
#      UpdateCheck.bindSwitch, and UpdateCheckSwitchTest is there (see below);
#   2. compiles UpdateCheck.kt with -Werror (the Fenix build's setting) against
#      android.jar, androidx.core, androidx.preference, kotlinx.coroutines, the
#      tree's real android-components concept-fetch sources, and the
#      compile-only stubs in scripts/tests/update-check-jvm/stubs for the few
#      Fenix classes it touches;
#   3. runs UpdateCheckerTest with JUnit, Robolectric's runner and
#      android.util.Base64 replaced by the shims in update-check-jvm/shims, and
#      the real org.json;
#   4. generates a document with scripts/update-manifest.py from the fixtures,
#      signs it with scripts/sign-update-manifest.sh and a THROWAWAY key made
#      here (in the work directory, deleted afterwards), and feeds the result
#      through the patch's UpdateChecker (update-check-jvm/CrossCheck.kt) and
#      through update-manifest.py's mirror, requiring the same verdict from both
#      for: an older install, every APK of the same build, a tampered document,
#      a signature by another key, and a malformed signature.
#
# What it does NOT prove: that the Fenix module compiles (the stubs are
# signatures copied from the 157 tree, not the tree) or anything about the UI,
# the 24 h gate or the request on a device. In particular it does NOT run
# UpdateCheckSwitchTest -- whether turning the Settings switch on makes
# UpdateCheck.isEnabled true. That needs an Android Context and the real
# Settings/SharedPreferences, i.e. Robolectric; on a plain JVM every android.jar
# constructor throws "Stub!". 157.0-2 shipped with a switch that wrote one
# SharedPreferences file while the check read another, and this harness (which
# only ever exercised UpdateChecker, with everything injected) passed. Step 1's
# grep is the most it can do: it fails if the wiring is undone. `./mach gradle
# fenix:testDebugUnitTest --tests 'org.mozilla.fenix.lw.*'` and
# `android-smoke.sh --check-update-privacy` remain the authorities.
#
# Needs: java 17+ (a JRE is enough; the Kotlin compiler comes from the
# gradle-home), git, openssl, python3. Nothing is downloaded.

set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
HERE="$ROOT/scripts/tests/update-check-jvm"
FIX="$ROOT/scripts/tests/fixtures/update-manifest"
PATCH="$ROOT/patches/android/update-check.patch"
TREE=""
GRADLE_HOME_DIR=""
ANDROID_JAR=""
KEEP=0

die() { printf 'test-update-check-jvm: %s\n' "$*" >&2; exit 2; }
while [ $# -gt 0 ]; do
    case "$1" in
        --tree) TREE=$2; shift 2 ;;
        --gradle-home) GRADLE_HOME_DIR=$2; shift 2 ;;
        --android-jar) ANDROID_JAR=$2; shift 2 ;;
        --patch) PATCH=$2; shift 2 ;;
        --keep) KEEP=1; shift ;;
        -h|--help) sed -n '2,45p' "$0"; exit 0 ;;
        *) die "unknown argument: $1" ;;
    esac
done
[ -n "$TREE" ] && [ -n "$GRADLE_HOME_DIR" ] && [ -n "$ANDROID_JAR" ] ||
    die "usage: $0 --tree DIR --gradle-home DIR --android-jar FILE"
FETCH="$TREE/mobile/android/android-components/components/concept/fetch/src/main/java/mozilla/components/concept/fetch"
[ -f "$FETCH/Client.kt" ] || die "no concept-fetch sources under $TREE"
[ -f "$ANDROID_JAR" ] || die "no such android.jar: $ANDROID_JAR"
for t in java git openssl python3 unzip; do command -v "$t" >/dev/null || die "$t is required"; done

# Newest file matching a glob below a directory, by version-aware sort.
pick() {
    local found
    found=$(find "$1" -path "$2" -type f ! -name '*-sources.jar' 2>/dev/null | sort -V | tail -1)
    [ -n "$found" ] || die "nothing matches $2 under $1"
    printf '%s' "$found"
}
LIB=$(dirname "$(pick "$GRADLE_HOME_DIR/wrapper/dists" '*/lib/kotlin-compiler-embeddable-*.jar')")
CACHE="$GRADLE_HOME_DIR/caches/modules-2/files-2.1"
KOTLINC_CP=$(ls "$LIB"/kotlin-compiler-embeddable-*.jar "$LIB"/kotlin-stdlib-[0-9]*.jar "$LIB"/kotlin-reflect-*.jar \
    "$LIB"/kotlin-script-runtime-*.jar "$LIB"/kotlin-daemon-embeddable-*.jar "$LIB"/kotlinx-coroutines-core-jvm-*.jar \
    "$LIB"/annotations-*.jar | paste -sd: -)
STDLIB=$(ls "$LIB"/kotlin-stdlib-[0-9]*.jar | head -1)
COROUTINES=$(ls "$LIB"/kotlinx-coroutines-core-jvm-*.jar | head -1)
CORE_AAR=$(pick "$CACHE/androidx.core/core" '*/core-[0-9]*.aar')
PREFERENCE_AAR=$(pick "$CACHE/androidx.preference/preference" '*/preference-[0-9]*.aar')
ANNOTATION=$(pick "$CACHE/androidx.annotation" '*/annotation-jvm-[0-9]*.jar')
JUNIT=$(pick "$CACHE/junit/junit" '*/junit-4*.jar')
# hamcrest-core 2.x is an empty jar that points at hamcrest 2.x: take every
# hamcrest jar there is rather than guess which one JUnit will reach.
HAMCREST=$(find "$CACHE/org.hamcrest" -type f \( -name 'hamcrest-core-*.jar' -o -name 'hamcrest-[0-9]*.jar' \) \
    ! -name '*-sources.jar' 2>/dev/null | sort -V | paste -sd: -)
[ -n "$HAMCREST" ] || die "no hamcrest jar under $CACHE/org.hamcrest"
JSON=$(pick "$CACHE/org.json/json" '*/json-*.jar')

WORK=$(mktemp -d "${TMPDIR:-/tmp}/redoubt-update-jvm.XXXXXX")
if [ "$KEEP" -eq 1 ]; then echo "work directory kept: $WORK"; else trap 'rm -rf "$WORK"' 0; fi
mkdir -p "$WORK/src" "$WORK/main" "$WORK/shims" "$WORK/test" "$WORK/aar" "$WORK/aar-preference"
unzip -q -o "$CORE_AAR" classes.jar -d "$WORK/aar"
unzip -q -o "$PREFERENCE_AAR" classes.jar -d "$WORK/aar-preference"

kotlinc() {
    java -cp "$KOTLINC_CP" org.jetbrains.kotlin.cli.jvm.K2JVMCompiler -no-stdlib -jvm-target 17 "$@" 2>&1 |
        grep -v -e '^WARNING' -e '^$' || true
}

echo "== 1/4 extracting the patch's Kotlin"
git -C "$WORK/src" init -q
git -C "$WORK/src" apply --include='*/fenix/lw/*' "$PATCH"
MAIN_KT="$WORK/src/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/lw/UpdateCheck.kt"
TEST_KT="$WORK/src/mobile/android/fenix/app/src/test/java/org/mozilla/fenix/lw/UpdateCheckerTest.kt"
[ -f "$MAIN_KT" ] && [ -f "$TEST_KT" ] || die "the patch no longer adds UpdateCheck.kt and UpdateCheckerTest.kt"
# The Settings switch must reach the file UpdateCheck.isEnabled reads
# (fenix_preferences). androidx alone would persist it to the default
# SharedPreferences file, which nothing reads -- the 157.0-2 defect.
wiring() { grep -q -e "$1" "$PATCH" || die "update-check.patch lost the switch wiring: no '$1' ($2)"; }
wiring '^+            android:persistent="false"$' "preferences.xml row must not be persisted by androidx"
wiring '^+        )?.let { org.mozilla.fenix.lw.UpdateCheck.bindSwitch(it) }$' "SettingsFragment must bind the row"
wiring '^+        switch.onPreferenceChangeListener = SharedPreferenceUpdater()$' "bindSwitch must write fenix_preferences"
wiring '^+++ b/mobile/android/fenix/app/src/test/java/org/mozilla/fenix/lw/UpdateCheckSwitchTest.kt$' "the Robolectric switch test"
echo "   switch wiring present (UpdateCheckSwitchTest itself needs Robolectric; not run here)"

echo "== 2/4 compiling UpdateCheck.kt with -Werror (kotlin $(basename "$STDLIB" .jar | sed 's/kotlin-stdlib-//'))"
CP="$STDLIB:$ANDROID_JAR:$WORK/aar/classes.jar:$WORK/aar-preference/classes.jar:$ANNOTATION:$COROUTINES"
kotlinc -Werror -cp "$CP" -d "$WORK/main" "$HERE"/stubs/*.kt \
    "$FETCH/Client.kt" "$FETCH/Headers.kt" "$FETCH/Request.kt" "$FETCH/Response.kt" "$MAIN_KT"
[ -f "$WORK/main/org/mozilla/fenix/lw/UpdateChecker.class" ] || die "UpdateCheck.kt did not compile"
kotlinc -cp "$STDLIB:$JUNIT" -d "$WORK/shims" "$HERE"/shims/*.kt
kotlinc -cp "$CP:$WORK/main:$JUNIT:$WORK/shims" -d "$WORK/test" "$TEST_KT" "$HERE/CrossCheck.kt"
[ -f "$WORK/test/org/mozilla/fenix/lw/UpdateCheckerTest.class" ] || die "UpdateCheckerTest.kt did not compile"
RUN_CP="$WORK/shims:$JSON:$WORK/test:$WORK/main:$STDLIB:$COROUTINES:$JUNIT:$HAMCREST:$ANDROID_JAR"

echo "== 3/4 UpdateCheckerTest"
if ! java -cp "$RUN_CP" org.junit.runner.JUnitCore org.mozilla.fenix.lw.UpdateCheckerTest > "$WORK/junit.log" 2>&1; then
    cat "$WORK/junit.log"
    die "UpdateCheckerTest failed"
fi
tail -3 "$WORK/junit.log"

echo "== 4/4 cross-check: update-manifest.py + openssl + sign-update-manifest.sh -> UpdateChecker"
K="$WORK/keys"; D="$WORK/doc"; mkdir -p "$K" "$D"
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -pkeyopt ec_param_enc:named_curve -out "$K/throwaway.pem" 2>/dev/null
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -pkeyopt ec_param_enc:named_curve -out "$K/other.pem" 2>/dev/null
openssl pkey -in "$K/throwaway.pem" -pubout -outform DER | openssl base64 -A > "$K/pin.pub"
PUB=$(cat "$K/pin.pub")
python3 "$ROOT/scripts/update-manifest.py" generate --metadata "$FIX/beta6-output-metadata.json" \
    --tag android-157.0-1-beta.6 --published 2026-10-05T00:00:00Z --out "$D/latest.json" 2>/dev/null
"$ROOT/scripts/sign-update-manifest.sh" "$K/throwaway.pem" "$D/latest.json" "$K/pin.pub" >/dev/null
# Tampered: one byte of the URL changed, the original signature kept.
sed 's/CPlusPlus17/CPlusPlus18/' "$D/latest.json" > "$D/tampered.json"
cp "$D/latest.json.sig" "$D/tampered.json.sig"
# Signed by another key, then a signature that is not base64.
cp "$D/latest.json" "$D/other.json"
openssl dgst -sha256 -sign "$K/other.pem" "$D/other.json" | openssl base64 -A > "$D/other.json.sig"
cp "$D/latest.json" "$D/garbage.json"; printf 'not*base64\n' > "$D/garbage.json.sig"

fail=0
check() {  # doc versionName versionCode expected-verdict
    local doc=$1 name=$2 code=$3 want=$4 jvm py
    jvm=$(java -cp "$RUN_CP" CrossCheckKt "$D/$doc" "$D/$doc.sig" "$PUB" "$name" "$code" | cut -d' ' -f1)
    # verify exits 1 on "noresult"; the verdict is what is compared here.
    py=$({ python3 "$ROOT/scripts/update-manifest.py" verify "$D/$doc" --pubkey "$PUB" \
        --current-version "$name" --current-code "$code" --json || true; } |
        python3 -c 'import json,sys; print(json.load(sys.stdin)["verdict"])')
    if [ "$jvm" = "$want" ] && [ "$py" = "$want" ]; then
        printf '   ok    %-14s %-18s %-11s -> %s\n' "$doc" "$name" "$code" "$want"
    else
        printf '   FAIL  %-14s %-18s %-11s -> jvm %s, python %s, expected %s\n' "$doc" "$name" "$code" "$jvm" "$py" "$want"
        fail=1
    fi
}
# Beta 5's real codes (lw-m7-41 apk-badging) against the Beta 6 fixture.
for code in 2016188256 2016188258 2016188262 2016188263; do check latest.json 157.0-1-default "$code" update; done
for code in 2016188448 2016188450 2016188454 2016188455; do check latest.json 157.0-1-default "$code" uptodate; done
check latest.json 157.0-1-default 0 uptodate        # own code unknown: never the string fallback
check latest.json 153.4.0esr-1-default 0 uptodate   # ... even where the strings say newer
check latest.json 158.0-1-default 2016190000 uptodate
check tampered.json 157.0-1-default 2016188262 noresult
check other.json 157.0-1-default 2016188262 noresult
check garbage.json 157.0-1-default 2016188262 noresult
[ "$fail" -eq 0 ] || die "the JVM and the publishing tools disagree"
echo "all checks passed"
