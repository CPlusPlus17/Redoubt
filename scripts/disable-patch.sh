#!/usr/bin/env bash
#
# disable-patch.sh - remove a patch from the platform patch lists.
#
# The lists the build actually reads are assets/patches/{common,desktop,android}.txt,
# and they are the only lists there are. This script used to also regenerate
# assets/patches.txt, the generated common+desktop compatibility shim from
# LW-M0-02 - that file is retired (LW-M7-01) and must not come back. If you find
# it on disk again, something here regrew it: delete it and fix the script.
#
# WHICH LIST: unlike enable-patch.sh, nothing is guessed here either - the lists
# are searched and the patch is removed from whichever one actually holds it,
# and that is printed. If it is in more than one, --list disambiguates rather
# than the script picking. If it is in none, that is an error, not a silent
# no-op (the old version's sed deleted nothing and still exited 0).
#
# The whole line goes, including any trailing '# (?)' or '# STRADDLER -> LW-M1-0x'
# provenance comment, which is what those comments belong to. Header comments
# and blank lines are untouched, and the remaining entries keep their relative
# order - removing a line cannot break the ordering constraints in
# docs/android/AGENTS.md, though it can leave a patch enabled whose predecessor
# is gone, which is noted when it happens.
#

set -euo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
LIST_DIR="$REPO_DIR/assets/patches"
KNOWN_LISTS=(common desktop android)

# See the same table in scripts/enable-patch.sh and in docs/android/AGENTS.md.
ORDER_PAIRS=(
  "autoconfig-setEnv|profile-directory"   # extensions/.../prefcalls.js
  "firefox-in-ua|moz-configure"           # toolkit/moz.configure
  "fpp-canvas-fix|webgl-permission"       # dom/canvas/ClientWebGLContext.cpp
  "mozilla_dirs|xdg-dir"                  # toolkit/xre/nsXREDirProvider.cpp
)

usage() {
  cat <<EOF
Usage: ${0##*/} [--list common|desktop|android] <patch>

Removes <patch> from the patch list that holds it.

  --list, -l NAME   only look in this list: common, desktop or android.
                    Needed only when the same patch is in more than one.
  --help, -h        this text

<patch> may be a repo-relative path or a bare name:
  ${0##*/} patches/limit-access.patch
  ${0##*/} ui-patches/neterror
  ${0##*/} --list common xdg-dir
EOF
}

die() {
  printf 'error: %s\n' "$1" >&2
  exit 1
}

list_path() {
  printf '%s\n' "$LIST_DIR/$1.txt"
}

# The entries of a list, comments and blank lines stripped, in file order.
# Same rules as read_patch_list() in scripts/librewolf-patches.py.
list_entries() {
  sed -e 's/#.*//' -e 's/[[:space:]]*$//' -- "$(list_path "$1")" | grep . || true
}

order_key() {
  local base="${1##*/}"
  base="${base%.patch}"
  printf '%s\n' "${base%-common}"
}

target_list=""
patch_arg=""
end_of_options=""
while [ $# -gt 0 ]; do
  if [ -n "$end_of_options" ]; then
    [ -z "$patch_arg" ] || die "expected one patch, got '$patch_arg' and '$1'"
    patch_arg="$1"
    shift
    continue
  fi
  case "$1" in
    -h|--help) usage; exit 0 ;;
    -l|--list) [ $# -ge 2 ] || die "--list needs a value"; target_list="$2"; shift 2 ;;
    --list=*)  target_list="${1#--list=}"; shift ;;
    --) end_of_options=yes; shift ;;
    -*) die "unknown option '$1' (try --help)" ;;
    *) [ -z "$patch_arg" ] || die "expected one patch, got '$patch_arg' and '$1'"
       patch_arg="$1"; shift ;;
  esac
done

if [ -z "$patch_arg" ]; then
  usage >&2
  exit 1
fi

for name in "${KNOWN_LISTS[@]}"; do
  [ -f "$(list_path "$name")" ] || die "patch list $(list_path "$name") is missing"
done

search_lists=("${KNOWN_LISTS[@]}")
if [ -n "$target_list" ]; then
  case " ${KNOWN_LISTS[*]} " in
    *" $target_list "*) ;;
    *) die "unknown list '$target_list'; expected one of: ${KNOWN_LISTS[*]}" ;;
  esac
  search_lists=("$target_list")
fi

# Resolve against what is actually in the lists, not against the filesystem: a
# patch file that has already been deleted must still be removable from a list.
# Accepts the full entry, or any unambiguous suffix of it ('neterror',
# 'ui-patches/neterror', 'neterror.patch').
norm="${patch_arg#"$REPO_DIR"/}"
norm="${norm#./}"
hits=()
for name in "${search_lists[@]}"; do
  while IFS= read -r candidate; do
    [ -n "$candidate" ] || continue
    if [ "$candidate" = "$norm" ] ||
       [ "$candidate" = "patches/$norm" ] ||
       [ "$candidate" = "$norm.patch" ] ||
       [ "$candidate" = "patches/$norm.patch" ] ||
       [ "${candidate##*/}" = "$norm" ] ||
       [ "${candidate##*/}" = "$norm.patch" ]; then
      hits+=("$name|$candidate")
    fi
  done < <(list_entries "$name")
done

if [ "${#hits[@]}" -eq 0 ]; then
  printf 'error: '\''%s'\'' is not in %s.\n' "$patch_arg" \
    "$([ -n "$target_list" ] && printf 'assets/patches/%s.txt' "$target_list" \
       || printf 'any of assets/patches/{%s}.txt' "$(IFS=,; printf '%s' "${KNOWN_LISTS[*]}")")" >&2
  printf '  Nothing was changed. Check the spelling, or list the entries with:\n' >&2
  printf '    grep -rn . assets/patches/*.txt\n' >&2
  exit 1
fi

if [ "${#hits[@]}" -gt 1 ]; then
  printf 'error: '\''%s'\'' matches more than one entry:\n' "$patch_arg" >&2
  for hit in "${hits[@]}"; do
    printf '  %s.txt: %s\n' "${hit%%|*}" "${hit#*|}" >&2
  done
  printf '  Nothing was changed. Narrow it down with --list, or pass the full path.\n' >&2
  exit 1
fi

hit="${hits[0]}"
holder="${hit%%|*}"
entry="${hit#*|}"
target_file="$(list_path "$holder")"

tmp="$(mktemp "${TMPDIR:-/tmp}/patch-list.XXXXXX")"
# Drop the entry's whole line, comment and all. Everything else - header
# comments, blank lines, the order of the remaining entries - is preserved.
awk -v want="$entry" '
  {
    stripped = $0
    sub(/#.*/, "", stripped)
    gsub(/^[ \t]+|[ \t]+$/, "", stripped)
    if (stripped == want) next
    print
  }
' "$target_file" > "$tmp"
cat -- "$tmp" > "$target_file"
rm -f -- "$tmp"

printf 'Removed %s from assets/patches/%s.txt.\n' "$entry" "$holder"

# A patch whose predecessor just went away still applies in a valid order, but
# it may now be applying against context the predecessor used to create.
key="$(order_key "$entry")"
for pair in "${ORDER_PAIRS[@]}"; do
  first="${pair%%|*}"
  then_="${pair#*|}"
  [ "$key" = "$first" ] || continue
  for name in "${KNOWN_LISTS[@]}"; do
    while IFS= read -r candidate; do
      if [ "$(order_key "$candidate")" = "$then_" ]; then
        printf 'note: %s is still enabled in %s.txt and shares a file with the\n' \
          "$candidate" "$name" >&2
        printf 'note:   patch you just removed - it expected %s to apply first.\n' "$key" >&2
        printf 'note:   See "Patch ordering constraints" in docs/android/AGENTS.md.\n' >&2
      fi
    done < <(list_entries "$name")
  done
done
