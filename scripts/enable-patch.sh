#!/usr/bin/env bash
#
# enable-patch.sh - add a patch to one of the platform patch lists.
#
# The lists the build actually reads are assets/patches/{common,desktop,android}.txt,
# and they are the only lists there are. scripts/librewolf-patches.py applies
# common.txt first, then one list per --targets; check-patchfail.sh and
# fuzzfail.sh walk the same lists for the same targets. This script used to also
# regenerate assets/patches.txt, the generated common+desktop compatibility shim
# from LW-M0-02 - that file is retired (LW-M7-01) and must not come back. If you
# find it on disk again, something here regrew it: delete it and fix the script.
#
# WHICH LIST: this script never guesses. Pass --list, or answer the prompt when
# run interactively. A wrong list is silent - a patch in desktop.txt simply
# never reaches an Android build and nothing errors - which is landmine L4 in
# docs/android/AGENTS.md, and it is the defect this script exists to not have.
# Path-based inference is exactly the heuristic docs/android/PATCH-SCOPE.md
# flags as unreliable (landmine L3), so it is not offered.
#
# ORDERING: entries are appended to the end of the chosen list. Order inside a
# list is load-bearing - four pairs share a tree file and only apply in one
# order (docs/android/AGENTS.md, "Patch ordering constraints"). The list is
# never re-sorted (the old version sorted the shim; both are gone). If the patch
# being added must precede one already in the same list, it is inserted
# immediately before it and that is printed. If the constraint spans two lists
# in the wrong direction, it cannot be fixed by insertion, so it is reported
# loudly and left to the maintainer. scripts/check-patch-order.py (LW-M1-10)
# will enforce all of this properly.
#

set -euo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
LIST_DIR="$REPO_DIR/assets/patches"
KNOWN_LISTS=(common desktop android)

# first-then pairs, keyed by patch basename without the '.patch' suffix and
# without a '-common' suffix, so the halves the M1 split tasks produce
# (webgl-permission-common.patch) match the same key as the unsplit patch.
ORDER_PAIRS=(
  "autoconfig-setEnv|profile-directory"   # extensions/.../prefcalls.js
  "firefox-in-ua|moz-configure"           # toolkit/moz.configure
  "fpp-canvas-fix|webgl-permission"       # dom/canvas/ClientWebGLContext.cpp
  "mozilla_dirs|xdg-dir"                  # toolkit/xre/nsXREDirProvider.cpp
)

usage() {
  cat <<EOF
Usage: ${0##*/} [--list common|desktop|android] <patch>

Adds <patch> to one of the patch lists the build reads.

  --list, -l NAME   which list to add to: common, desktop or android.
                    common  - applied to every target
                    desktop - applied only to desktop builds
                    android - applied only to Android builds
                    Without it you are prompted; with no terminal to prompt on
                    (CI, scripts) the run fails rather than guessing.
  --help, -h        this text

<patch> may be a repo-relative path or a bare name:
  ${0##*/} --list common patches/limit-access.patch
  ${0##*/} --list desktop ui-patches/neterror
  ${0##*/} -l android my-android-fix

See docs/android/PATCH-SCOPE.md for which patches belong where, and
docs/android/AGENTS.md for the ordering constraints.
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

# Which lists already contain an entry (may print more than one).
lists_holding() {
  local entry="$1" name
  for name in "${KNOWN_LISTS[@]}"; do
    if list_entries "$name" | grep -Fxq -- "$entry"; then
      printf '%s\n' "$name"
    fi
  done
}

order_key() {
  local base="${1##*/}"
  base="${base%.patch}"
  printf '%s\n' "${base%-common}"
}

# common.txt is applied before every target list, so an entry in common always
# precedes one in desktop/android. Two different target lists never apply
# together, so nothing can be ordered across them.
applies_before() {
  local a="$1" b="$2"
  [ "$a" = "common" ] && [ "$b" != "common" ]
}

# Resolve a user-supplied name to a repo-relative patch path that exists on
# disk. Enabling a patch file that is not there is a build failure later on, so
# it is refused here.
resolve_patch() {
  local arg="$1" cand matches
  arg="${arg#"$REPO_DIR"/}"
  arg="${arg#./}"
  for cand in "$arg" "$arg.patch" "patches/$arg" "patches/$arg.patch"; do
    if [ -f "$REPO_DIR/$cand" ]; then
      printf '%s\n' "$cand"
      return 0
    fi
  done
  # Bare basename: search the patches/ tree, but only accept a unique hit.
  matches="$(cd -- "$REPO_DIR" && find patches -type f \
    \( -name "${arg##*/}" -o -name "${arg##*/}.patch" \) | sort)"
  case "$(printf '%s' "$matches" | grep -c . || true)" in
    1) printf '%s\n' "$matches"; return 0 ;;
    0) die "no patch file matches '$1' (looked for patches/${arg}.patch and friends under $REPO_DIR)" ;;
    *) printf 'error: '\''%s'\'' is ambiguous:\n' "$1" >&2
       printf '  %s\n' $matches >&2
       exit 1 ;;
  esac
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

entry="$(resolve_patch "$patch_arg")"

# Ask, do not infer: a wrong list produces a patch that silently never applies.
if [ -z "$target_list" ]; then
  if [ -t 0 ] && [ -t 1 ]; then
    printf 'Which list should %s go in?\n' "$entry"
    printf '  common  - applied to every target (desktop and Android)\n'
    printf '  desktop - desktop builds only\n'
    printf '  android - Android builds only\n'
    printf 'See docs/android/PATCH-SCOPE.md if you are unsure.\n'
    read -r -p 'list [common/desktop/android]: ' target_list
    target_list="$(printf '%s' "$target_list" | tr -d '[:space:]')"
  else
    printf 'error: no --list given and no terminal to ask on.\n' >&2
    printf '  Pass --list common|desktop|android. This script does not guess:\n' >&2
    printf '  the wrong list is silent - the patch simply never reaches that\n' >&2
    printf '  build. See landmine L4 in docs/android/AGENTS.md.\n' >&2
    exit 1
  fi
fi

case " ${KNOWN_LISTS[*]} " in
  *" $target_list "*) ;;
  *) die "unknown list '$target_list'; expected one of: ${KNOWN_LISTS[*]}" ;;
esac

# Already enabled? In the same list it is a no-op; in another list it would be
# applied twice on any build that reads both (common + desktop), so refuse.
mapfile -t holders < <(lists_holding "$entry")
for holder in "${holders[@]:-}"; do
  [ -n "$holder" ] || continue
  if [ "$holder" = "$target_list" ]; then
    printf '%s is already in assets/patches/%s.txt - nothing to do.\n' "$entry" "$holder"
    exit 1
  fi
  die "$entry is already in assets/patches/$holder.txt.
  A patch belongs to exactly one list; adding it to '$target_list' as well would
  apply it twice on any build that reads both. Run
    scripts/disable-patch.sh $entry
  first if you meant to move it."
done

# Ordering constraints (docs/android/AGENTS.md).
insert_before=""
key="$(order_key "$entry")"
for pair in "${ORDER_PAIRS[@]}"; do
  first="${pair%%|*}"
  then_="${pair#*|}"
  partner=""
  role=""
  if [ "$key" = "$first" ]; then partner="$then_"; role="first"; fi
  if [ "$key" = "$then_" ]; then partner="$first"; role="then"; fi
  [ -n "$partner" ] || continue

  partner_entry=""
  partner_list=""
  for name in "${KNOWN_LISTS[@]}"; do
    while IFS= read -r candidate; do
      if [ "$(order_key "$candidate")" = "$partner" ]; then
        partner_entry="$candidate"
        partner_list="$name"
      fi
    done < <(list_entries "$name")
  done

  if [ -z "$partner_entry" ]; then
    printf 'note: ordering constraint: %s must apply %s %s, which is not enabled anywhere.\n' \
      "$key" "$([ "$role" = first ] && echo before || echo after)" "$partner" >&2
    continue
  fi

  if [ "$role" = "first" ]; then
    if [ "$partner_list" = "$target_list" ]; then
      insert_before="$partner_entry"
    elif applies_before "$target_list" "$partner_list"; then
      : # common before a target list - already correct.
    elif applies_before "$partner_list" "$target_list"; then
      printf 'WARNING: ordering constraint broken: %s must apply BEFORE %s,\n' "$key" "$partner" >&2
      printf 'WARNING:   but %s is in %s.txt, which is applied before %s.txt.\n' \
        "$partner_entry" "$partner_list" "$target_list" >&2
      printf 'WARNING:   Insertion cannot fix this; move one of the two. See\n' >&2
      printf 'WARNING:   "Patch ordering constraints" in docs/android/AGENTS.md.\n' >&2
    fi
  else
    if [ "$partner_list" = "$target_list" ]; then
      : # appended at the end, so after the partner. Correct.
    elif applies_before "$partner_list" "$target_list"; then
      : # partner is in common, applied first. Correct.
    elif applies_before "$target_list" "$partner_list"; then
      printf 'WARNING: ordering constraint broken: %s must apply AFTER %s,\n' "$key" "$partner" >&2
      printf 'WARNING:   but %s is in %s.txt, which is applied after %s.txt.\n' \
        "$partner_entry" "$partner_list" "$target_list" >&2
      printf 'WARNING:   Insertion cannot fix this; move one of the two. See\n' >&2
      printf 'WARNING:   "Patch ordering constraints" in docs/android/AGENTS.md.\n' >&2
    fi
  fi
done

target_file="$(list_path "$target_list")"

if [ -n "$insert_before" ]; then
  tmp="$(mktemp "${TMPDIR:-/tmp}/patch-list.XXXXXX")"
  awk -v want="$insert_before" -v add="$entry" '
    !done {
      stripped = $0
      sub(/#.*/, "", stripped)
      gsub(/^[ \t]+|[ \t]+$/, "", stripped)
      if (stripped == want) { print add; done = 1 }
    }
    { print }
  ' "$target_file" > "$tmp"
  cat -- "$tmp" > "$target_file"
  rm -f -- "$tmp"
  printf 'Added %s to assets/patches/%s.txt, before %s (ordering constraint).\n' \
    "$entry" "$target_list" "$insert_before"
else
  # Append. Never sort: relative order inside a list is load-bearing.
  if [ -s "$target_file" ] && [ "$(tail -c 1 -- "$target_file" | wc -l)" -eq 0 ]; then
    printf '\n' >> "$target_file"
  fi
  printf '%s\n' "$entry" >> "$target_file"
  printf 'Added %s to the end of assets/patches/%s.txt.\n' "$entry" "$target_list"
fi

if [ "$target_list" = "android" ]; then
  printf 'Note: check-patchfail.sh defaults to the desktop lists, so it will not test\n'
  printf '      this patch unless you ask for the android target:\n'
  printf '        ./scripts/check-patchfail.sh --targets=android\n'
  printf '      (add --use-desktop-tarball if the ESR tarball is not downloaded yet;\n'
  printf '      that result is indicative only). Build with: make dir TARGETS=android\n'
fi
