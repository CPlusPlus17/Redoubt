#!/usr/bin/env bash
# Compile LibreWolfStartupCleanup.kt and its test against the signature stubs in
# ./stubs with -Werror, then run the JUnit tests. Not a Fenix build: the stubs
# stand in for Android, android-components and Fenix types.
#   run-jvm-tests.sh PATCHED_TREE JAR_DIR
# JAR_DIR holds the jars listed in toolchain.sha256 (Maven Central).
set -euo pipefail
tree=$1 jars=$2 here=$(cd "$(dirname "$0")" && pwd)
src=$tree/mobile/android/fenix/app/src
out=$(mktemp -d); trap 'rm -rf -- "$out"' EXIT
(cd "$jars" && sha256sum -c "$here/toolchain.sha256" >/dev/null)
cp=$(ls "$jars"/*.jar | grep -v compiler-embeddable | tr '\n' ':')
java -cp "$(ls "$jars"/*.jar | tr '\n' ':')" org.jetbrains.kotlin.cli.jvm.K2JVMCompiler \
  -no-stdlib -cp "$cp" -Werror -opt-in=kotlinx.coroutines.ExperimentalCoroutinesApi -d "$out" \
  "$here"/stubs/*.kt \
  "$src/main/java/org/mozilla/fenix/components/LibreWolfStartupCleanup.kt" \
  "$src/test/java/org/mozilla/fenix/components/LibreWolfStartupCleanupTest.kt"
java -cp "$out:$cp" org.junit.runner.JUnitCore org.mozilla.fenix.components.LibreWolfStartupCleanupTest
