#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/generate-android-pref-baseline.sh
#
# (Re)generate docs/android/expected-prefs.txt, the baseline that
# scripts/android-pref-audit.sh (LW-M3-05) diffs against.
#
# The baseline is the smoke harness's --pref-dump output against a RUNNING
# Android build, checked in verbatim.  The payload is tab-separated:
#
#     # librewolf-android-smoke pref-dump v1
#     # name<TAB>type<TAB>value<TAB>locked<TAB>user
#     <name><TAB><type><TAB><value><TAB><locked|-><TAB><user|->
#
# It is GENERATED, never hand-written: a hand edit is how a rebase that
# reverts a privacy pref would stop being noticed.  See
# docs/android/pref-audit.md for the whole scheme and its gap declaration.
#
# REQUIREMENTS: a running Android environment (an emulator or a device with
# the APK installed, reachable by adb) -- the smoke harness exits 2 without
# one.  On such a machine:  ./scripts/android-smoke.sh --emulator --pref-dump
# or point LW_SMOKE_APK / --serial / --sdk at your setup, as documented in
# docs/android/SMOKE.md.
#
# EXIT CODES -- a failure here must never look like a pass:
#   0  baseline (re)written
#   2  the baseline could not be generated (missing harness, no device,
#      malformed payload).  Any existing baseline is left untouched.
# ---------------------------------------------------------------------------
set -euo pipefail

SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SELF")/.." && pwd)"
SMOKE="$REPO_ROOT/scripts/android-smoke.sh"
BASELINE_DIR="$REPO_ROOT/docs/android"
BASELINE="$BASELINE_DIR/expected-prefs.txt"
MARKER="# librewolf-android-smoke pref-dump v1"

die() {
  printf 'generate-android-pref-baseline: %s\n' "$1" >&2
  exit 2
}

# -- preflight: fail loud, never write a bogus baseline ----------------------
[ -f "$SMOKE" ] || die "scripts/android-smoke.sh is missing -- the smoke harness is the only source of the baseline"
[ -x "$SMOKE" ] || die "scripts/android-smoke.sh is not executable"
command -v awk  >/dev/null 2>&1 || die "awk is required"
command -v head >/dev/null 2>&1 || die "head is required"

WORK="$(mktemp -d)" || die "cannot create a temporary work directory"
trap 'rm -rf "$WORK"' EXIT

# Keep the existing baseline around for the change summary at the end.
OLD=""
if [ -f "$BASELINE" ]; then
  OLD="$WORK/old-baseline.txt"
  cp "$BASELINE" "$OLD" || die "cannot read the existing baseline $BASELINE"
fi

# -- run the dump -------------------------------------------------------------
# stdout carries the payload only; stderr carries the harness's progress.
# Keep them apart: a stray progress line in the payload would poison the
# baseline (SMOKE.md, "Watch out for pipelines").
DUMP="$WORK/prefs.txt"
SMOKE_ERR="$WORK/stderr.log"
rc=0
"$SMOKE" --pref-dump >"$DUMP" 2>"$SMOKE_ERR" || rc=$?
if [ "$rc" -ne 0 ]; then
  printf 'generate-android-pref-baseline: android-smoke.sh --pref-dump failed (exit %d); no baseline written.\n' "$rc" >&2
  if [ -s "$SMOKE_ERR" ]; then
    printf -- '--- harness stderr ---\n' >&2
    cat "$SMOKE_ERR" >&2
  else
    printf '(no stderr captured)\n' >&2
  fi
  exit 2
fi

# -- validate the payload before letting it become the baseline ---------------
first_line="$(head -n 1 "$DUMP" 2>/dev/null || true)"
[ "$first_line" = "$MARKER" ] || die "payload does not look like a pref-dump (first line: ${first_line:-<empty>}) -- refusing to write it"

data_count="$(awk '$0 !~ /^[[:space:]]*(#|$)/ { n++ } END { print n + 0 }' "$DUMP")"
[ "$data_count" -gt 0 ] || die "payload has no pref rows -- refusing to write an empty baseline"

# -- install: stage then rename, so readers never see a partial file ----------
mkdir -p "$BASELINE_DIR" || die "cannot create $BASELINE_DIR"
STAGE="$WORK/expected-prefs.txt"
cp "$DUMP" "$STAGE" || die "cannot stage the baseline"
mv "$STAGE" "$BASELINE" || die "cannot move the baseline into place"

printf 'generate-android-pref-baseline: wrote %s (%s pref row(s))\n' "$BASELINE" "$data_count"
if [ -n "$OLD" ]; then
  if cmp -s "$OLD" "$BASELINE"; then
    printf 'generate-android-pref-baseline: baseline unchanged\n'
  else
    # diff exits 1 on differences, which is the expected case here; || true
    # keeps set -e from reading the (correct) diff status as a crash.
    added="$(diff "$OLD" "$BASELINE" | awk '/^>/{ n++ } END { print n + 0 }' || true)"
    removed="$(diff "$OLD" "$BASELINE" | awk '/^</{ n++ } END { print n + 0 }' || true)"
    printf 'generate-android-pref-baseline: baseline changed: %s line(s) added, %s line(s) removed -- review the diff before committing\n' "$added" "$removed" >&2
  fi
fi
exit 0
