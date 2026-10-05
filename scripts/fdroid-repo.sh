#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/fdroid-repo.sh -- run the Redoubt F-Droid repository (LW-M6-03).
#
# The repository is https://redoubtbrowser.org/fdroid/repo, served by the
# existing GitHub Pages site. It serves the SAME owner-signed per-ABI APKs as
# the GitHub release. It builds nothing and re-signs nothing: the only new
# signature is the repository key's signature over the index. Only the small
# signed index files are committed (site/fdroid/repo/); the APKs are fetched
# from the GitHub release by .github/workflows/pages.yaml at deploy time
# (scripts/fdroid-pages.py). Runbook and design: docs/android/FDROID.md.
#
#   init                 create the repository signing key (owner, once) and
#                        the working directory; print the repo fingerprint
#   add <release-tag>    fetch the release's per-ABI APKs + SHA256SUMS.signed
#                        from GitHub, verify sha256 (against SHA256SUMS.signed
#                        AND GitHub's asset digest) and the APK certificate
#                        (== the published fingerprint, v2+v3, no v1), refuse
#                        otherwise, and stage them in the working repo/
#   update               keep the newest KEEP_RELEASES releases, re-verify every
#                        APK, run `fdroid update` (signs the index, no network)
#   publish <checkout>   write the signed index files (no APKs) into
#                        <checkout>/site/fdroid/repo/, the APK source list
#                        site/fdroid/sources.json, the pinned repo fingerprint
#                        assets/fdroid/repo-fingerprint, and the human page
#                        site/fdroid.html + its QR code; run the Pages check;
#                        print exactly what changed. The owner commits.
#   verify [<repo-url>]  fetch the published index and check its signature
#                        against the repo fingerprint, the release signer of
#                        every APK, and that every listed APK is served
#   fingerprint          print the repo fingerprint from the local keystore
#
# fdroidserver runs in F-Droid's own container image, pinned by digest
# (FDROID_IMAGE below; why: FDROID.md, "Tooling"). init and update run it
# with --network=none: the container that sees the repository key has no
# network. The repository key and its passphrase never enter a git checkout:
# the keystore lives in $REDOUBT_FDROID_HOME (default ~/redoubt-fdroid), the
# passphrase is typed at a prompt and handed to that one container through
# its environment.
#
# Environment:
#   REDOUBT_FDROID_HOME   working home (default ~/redoubt-fdroid)
#   FDROID_KEYSTORE_PASS  repository keystore passphrase; prompted when unset
#                         (set it only for throwaway-key tests)
#   APKSIGNER             apksigner for the certificate check (default: the
#                         SDK, $PATH, else the one inside the pinned image)
#   KEEP_RELEASES         releases kept in the repository (default 2: the
#                         GitHub Pages site must stay under 1 GB, FDROID.md)
#   GITHUB_REPO           default CPlusPlus17/Redoubt
# ---------------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# F-Droid's official image, registry.gitlab.com/fdroid/docker-executable-fdroidserver,
# tag `master` as of 2026-10-04 (fdroidserver commit c21c177ff6d8, 2026-10-01,
# Debian 13). The `latest` tag is a 2024 build; do not use it.
FDROID_IMAGE="registry.gitlab.com/fdroid/docker-executable-fdroidserver@sha256:75f6b88ef13a63fc5c49aa4c4dde35607c4a364d22cf57d534aa75c54effa56d"
PODMAN="${PODMAN:-podman}"

PACKAGE="org.redoubtbrowser"
GITHUB_REPO="${GITHUB_REPO:-CPlusPlus17/Redoubt}"
DEFAULT_REPO_URL="https://redoubtbrowser.org/fdroid/repo"
KEY_ALIAS="redoubt-fdroid-repo"
# The ABIs served. The universal APK is NOT served: F-Droid clients pick the
# APK whose nativecode matches the device, every device matches one of these
# three, and the universal APK would add 288 MB per release to a site capped
# at 1 GB (FDROID.md, "What the repository serves").
ABIS=(arm64-v8a armeabi-v7a x86_64)
KEEP_RELEASES="${KEEP_RELEASES:-2}"

HOME_DIR="${REDOUBT_FDROID_HOME:-$HOME/redoubt-fdroid}"
WORK="$HOME_DIR/work"
KEYSTORE="$HOME_DIR/keystore.p12"
DOWNLOADS="$HOME_DIR/downloads"

die()  { printf 'fdroid-repo: %s\n' "$*" >&2; exit 2; }
fail() { printf 'fdroid-repo: REFUSED: %s\n' "$*" >&2; exit 1; }
say()  { printf '==> %s\n' "$*"; }

usage() {
    sed -n '3,50p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
}

# ---------------------------------------------------------------- helpers --

# The published APK fingerprint, read from SIGNING.md exactly the way
# scripts/android-verify-signature.sh reads it (one source of truth).
release_fingerprint() {
    sed -n '/SHA-256 fingerprint/,/^$/p' "$REPO_ROOT/docs/android/SIGNING.md" \
        | tr -d ' \n' | grep -oE '([0-9A-Fa-f]{2}:){31}[0-9A-Fa-f]{2}' | head -1 \
        | tr -d ':' | tr 'A-F' 'a-f'
}

inside_dir() {   # is $1 inside directory $2?
    local p d; p="$(realpath -m "$1")"; d="$(realpath -m "$2")"
    case "$p/" in "$d"/*) return 0 ;; esac
    return 1
}

need_pass() {
    if [ -z "${FDROID_KEYSTORE_PASS:-}" ]; then
        [ -t 0 ] || die "FDROID_KEYSTORE_PASS is unset and there is no terminal to ask on"
        read -r -s -p "Repository keystore passphrase: " FDROID_KEYSTORE_PASS; echo
        [ -n "$FDROID_KEYSTORE_PASS" ] || die "empty passphrase"
    fi
    export FDROID_KEYSTORE_PASS
}

# Run fdroidserver (or, with --entrypoint, another tool of the image) on WORK.
# --network=none unless the caller passes NET=host. Label confinement is
# disabled instead of relabelling (:Z) the owner's directories.
fdroid_run() {
    local net="${NET:-none}"
    local args=(run --rm --network="$net" --security-opt label=disable
                -v "$WORK:/repo" -w /repo)
    [ -f "$KEYSTORE" ] && args+=(-v "$KEYSTORE:/keys/keystore.p12:ro")
    [ -n "${FDROID_KEYSTORE_PASS:-}" ] && args+=(-e FDROID_KEYSTORE_PASS)
    "$PODMAN" "${args[@]}" "$@"
}

write_config() {
    local url
    url="$(cat "$WORK/.repo_url")"
    sed -e "s#@REPO_URL@#$url#g" "$REPO_ROOT/assets/fdroid/config.yml.in" > "$WORK/config.yml"
    chmod 600 "$WORK/config.yml"   # fdroidserver refuses a world-readable config
    # fdroidserver looks for repo_icon in repo/icons/.
    mkdir -p "$WORK/repo/icons"
    cp "$REPO_ROOT/assets/fdroid/repo-icon.png" "$WORK/repo/icons/icon.png"
    mkdir -p "$WORK/metadata"
    cp "$REPO_ROOT/assets/fdroid/metadata/$PACKAGE.yml" "$WORK/metadata/$PACKAGE.yml"
}

keystore_fingerprint() {   # SHA-256 of the repo certificate, lowercase hex
    [ -f "$KEYSTORE" ] || die "no keystore at $KEYSTORE (run init first)"
    need_pass
    fdroid_run --entrypoint keytool "$FDROID_IMAGE" -list -v -keystore /keys/keystore.p12 \
        -storetype PKCS12 -alias "$KEY_ALIAS" -storepass:env FDROID_KEYSTORE_PASS 2>/dev/null \
        | sed -n 's/^[[:space:]]*SHA256:[[:space:]]*//p' | head -1 | tr -d ':\r ' | tr 'A-F' 'a-f'
}

# The fingerprint without needing the passphrase (written by init).
saved_fingerprint() {
    [ -f "$HOME_DIR/repo-fingerprint.txt" ] || die "no $HOME_DIR/repo-fingerprint.txt (run init first)"
    tr -d ' :\n' < "$HOME_DIR/repo-fingerprint.txt" | tr 'A-F' 'a-f'
}

# apksigner: $APKSIGNER, the SDK, $PATH, else the pinned image's (wrapped).
resolve_apksigner() {
    [ -n "${APKSIGNER:-}" ] && return 0
    local c
    for c in "${ANDROID_SDK_ROOT:-}"/build-tools/*/apksigner "${ANDROID_HOME:-}"/build-tools/*/apksigner; do
        [ -x "$c" ] && { APKSIGNER="$c"; export APKSIGNER; return 0; }
    done
    c="$(command -v apksigner 2>/dev/null || true)"
    [ -n "$c" ] && { APKSIGNER="$c"; export APKSIGNER; return 0; }
    local wrap="$HOME_DIR/.apksigner-in-image"
    cat > "$wrap" <<EOF
#!/bin/sh
# generated by fdroid-repo.sh: apksigner from the pinned fdroidserver image
exec "$PODMAN" run --rm --network=none --security-opt label=disable \\
    -v "$HOME_DIR:$HOME_DIR:ro" --entrypoint apksigner "$FDROID_IMAGE" "\$@"
EOF
    chmod 700 "$wrap"
    APKSIGNER="$wrap"; export APKSIGNER
}

# The certificate check: v2+v3, no v1, fingerprint == SIGNING.md.
verify_apks() {
    resolve_apksigner
    "$REPO_ROOT/scripts/android-verify-signature.sh" "$@" \
        || fail "an APK does not carry the published release certificate (see above)"
}

# ------------------------------------------------------------------- init --

cmd_init() {
    local url="$DEFAULT_REPO_URL"
    while [ $# -gt 0 ]; do
        case "$1" in
            --repo-url) url="${2:?--repo-url needs a URL}"; shift 2 ;;
            *) die "init: unknown argument $1" ;;
        esac
    done
    case "$url" in https://*/repo) ;; http://*/repo)
        printf 'fdroid-repo: WARNING: plain-http repo URL (%s) -- for local tests only\n' "$url" >&2 ;;
        *) die "the repo URL must end in /repo: $url" ;; esac
    inside_dir "$HOME_DIR" "$REPO_ROOT" && die "$HOME_DIR is inside the git checkout; the key must live outside it"
    [ -e "$KEYSTORE" ] && fail "$KEYSTORE already exists. A second key would orphan every client that added the first one (SIGNING.md, 'The F-Droid repository key')"
    mkdir -p "$WORK/repo" "$DOWNLOADS"
    chmod 700 "$HOME_DIR"
    printf '%s\n' "$url" > "$WORK/.repo_url"

    if [ -z "${FDROID_KEYSTORE_PASS:-}" ]; then
        [ -t 0 ] || die "no terminal to ask for the new passphrase on"
        local again
        read -r -s -p "New repository keystore passphrase (12+ chars): " FDROID_KEYSTORE_PASS; echo
        read -r -s -p "Repeat: " again; echo
        [ "$FDROID_KEYSTORE_PASS" = "$again" ] || die "passphrases differ"
    fi
    [ "${#FDROID_KEYSTORE_PASS}" -ge 12 ] || die "passphrase shorter than 12 characters"
    export FDROID_KEYSTORE_PASS

    say "generating the repository key (RSA 4096, PKCS12) in $KEYSTORE"
    # keytool writes the keystore into a mounted directory, then we move it:
    # the keystore mount in fdroid_run is read-only by design.
    local tmp; tmp="$(mktemp -d "$HOME_DIR/.keygen.XXXXXX")"
    "$PODMAN" run --rm --network=none --security-opt label=disable -e FDROID_KEYSTORE_PASS \
        -v "$tmp:/out" --entrypoint keytool "$FDROID_IMAGE" \
        -genkeypair -keystore /out/keystore.p12 -storetype PKCS12 \
        -alias "$KEY_ALIAS" -keyalg RSA -keysize 4096 -sigalg SHA256withRSA -validity 10000 \
        -dname "CN=Redoubt F-Droid repository, O=Redoubt" \
        -storepass:env FDROID_KEYSTORE_PASS -keypass:env FDROID_KEYSTORE_PASS
    mv "$tmp/keystore.p12" "$KEYSTORE"; rmdir "$tmp"
    chmod 600 "$KEYSTORE"
    write_config

    local fp; fp="$(keystore_fingerprint)"
    [ "${#fp}" -eq 64 ] || die "could not read the new key's fingerprint"
    printf '%s\n' "$fp" > "$HOME_DIR/repo-fingerprint.txt"
    cat <<EOF

Repository created.
  keystore      $KEYSTORE   (back it up NOW: SIGNING.md, "The F-Droid repository key")
  working dir   $WORK
  repo URL      $url
  fingerprint   $(printf '%s' "$fp" | tr 'a-f' 'A-F')

Users add:  $url?fingerprint=$(printf '%s' "$fp" | tr 'a-f' 'A-F')
Next:       $0 add <release-tag>
EOF
}

# -------------------------------------------------------------------- add --

cmd_add() {
    local tag="" allow_pre=0
    while [ $# -gt 0 ]; do
        case "$1" in
            --allow-prerelease) allow_pre=1; shift ;;
            -*) die "add: unknown option $1" ;;
            *) [ -z "$tag" ] || die "add: one tag at a time"; tag="$1"; shift ;;
        esac
    done
    [[ "$tag" =~ ^android-[0-9][0-9.]*(esr)?-[0-9]+(-beta\.[0-9]+)?$ ]] || die "not a Redoubt Android release tag: '$tag'"
    [ -f "$WORK/.repo_url" ] || die "no working directory at $WORK (run init first)"
    command -v curl >/dev/null && command -v python3 >/dev/null || die "add needs curl and python3"

    local dl="$DOWNLOADS/$tag"; mkdir -p "$dl"
    say "release metadata for $tag from api.github.com"
    curl -fsSL --proto '=https' -H 'Accept: application/vnd.github+json' \
        "https://api.github.com/repos/$GITHUB_REPO/releases/tags/$tag" -o "$dl/release.json"

    # Which assets, their GitHub digests, and the prerelease/draft flags.
    python3 - "$dl/release.json" "$allow_pre" "${ABIS[@]}" > "$dl/assets.tsv" <<'PY'
import json, sys
rel = json.load(open(sys.argv[1]))
allow_pre = sys.argv[2] == "1"
abis = sys.argv[3:]
if rel.get("draft"):
    sys.exit("fdroid-repo: REFUSED: the release is a draft")
if rel.get("prerelease") and not allow_pre:
    sys.exit("fdroid-repo: REFUSED: the release is a prerelease (pass --allow-prerelease to add it anyway)")
assets = {a["name"]: a for a in rel.get("assets", [])}
want = ["SHA256SUMS.signed"] + [f"fenix-{abi}-release.apk" for abi in abis]
for name in want:
    a = assets.get(name)
    if a is None:
        sys.exit(f"fdroid-repo: REFUSED: the release has no asset {name}")
    d = a.get("digest") or ""
    if not d.startswith("sha256:") or len(d) != 71:
        sys.exit(f"fdroid-repo: REFUSED: GitHub reports no sha256 digest for {name}")
    print(f"{name}\t{d[7:]}\t{a['browser_download_url']}")
PY

    local name digest url have
    while IFS=$'\t' read -r name digest url; do
        if [ -f "$dl/$name" ] && have="$(sha256sum "$dl/$name" | cut -d' ' -f1)" && [ "$have" = "$digest" ]; then
            printf '    cached  %s\n' "$name"
            continue
        fi
        case "$url" in "https://github.com/$GITHUB_REPO/releases/download/$tag/$name") ;;
            *) fail "unexpected download URL for $name: $url" ;; esac
        printf '    fetch   %s\n' "$name"
        curl -fSL --proto '=https' --proto-redir '=https' -o "$dl/$name.part" "$url"
        mv "$dl/$name.part" "$dl/$name"
    done < "$dl/assets.tsv"

    say "sha256: SHA256SUMS.signed and GitHub's asset digests must both match"
    ( cd "$dl" && grep -E ' (fenix-(arm64-v8a|armeabi-v7a|x86_64)-release\.apk)$' SHA256SUMS.signed \
        | sha256sum -c --strict - ) || fail "an APK does not match SHA256SUMS.signed"
    for abi in "${ABIS[@]}"; do
        grep -q " fenix-$abi-release.apk\$" "$dl/SHA256SUMS.signed" || fail "SHA256SUMS.signed does not list fenix-$abi-release.apk"
    done
    while IFS=$'\t' read -r name digest url; do
        have="$(sha256sum "$dl/$name" | cut -d' ' -f1)"
        [ "$have" = "$digest" ] || fail "$name: sha256 $have differs from GitHub's digest $digest"
        printf '    ok      %s  %s\n' "$have" "$name"
    done < "$dl/assets.tsv"

    say "certificate: must be the published release key"
    local apks=(); for abi in "${ABIS[@]}"; do apks+=("$dl/fenix-$abi-release.apk"); done
    verify_apks "${apks[@]}"

    say "package, versionName and versionCode (read by fdroidserver's own parser)"
    # versionName is "<firefox>-<release>-default"; betas share their release's.
    local want_name="${tag#android-}"; want_name="${want_name%-beta.*}-default"
    mkdir -p "$WORK/repo"
    "$PODMAN" run --rm --network=none --security-opt label=disable -v "$dl:/in:ro" \
        --entrypoint sh "$FDROID_IMAGE" -c '
          . /etc/profile.d/bsenv.sh
          cd /in && for f in fenix-*-release.apk; do
            [ "$f" = fenix-universal-release.apk ] && continue
            python3 -c "import sys; sys.path.insert(0, \"$fdroidserver\")
from fdroidserver import common
common.config = {}
print(sys.argv[1], *common.get_apk_id(sys.argv[1]), sep=\"\t\")" "$f"
          done' > "$dl/ids.tsv"
    [ "$(wc -l < "$dl/ids.tsv")" -eq "${#ABIS[@]}" ] || fail "expected ${#ABIS[@]} APKs, parsed $(wc -l < "$dl/ids.tsv")"
    local apk appid code vname
    while IFS=$'\t' read -r apk appid code vname; do
        [ "$appid" = "$PACKAGE" ] || fail "$apk is $appid, not $PACKAGE"
        [ "$vname" = "$want_name" ] || fail "$apk has versionName $vname, the tag says $want_name"
        [[ "$code" =~ ^[0-9]+$ ]] || fail "$apk: unreadable versionCode '$code'"
        printf '    ok      %s  %s %s\n' "$apk" "$code" "$vname"
        # F-Droid's naming; the GitHub names repeat in every release.
        cp --reflink=auto "$dl/$apk" "$WORK/repo/${PACKAGE}_${code}.apk"
    done < "$dl/ids.tsv"

    # provenance: which GitHub asset each repo file is. publish turns this into
    # site/fdroid/sources.json, which the Pages deploy downloads from.
    { printf '# tag\t%s\n# added\t%s\n' "$tag" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      while IFS=$'\t' read -r apk appid code vname; do
          printf '%s\t%s\t%s\t%s\n' "${PACKAGE}_${code}.apk" "$(sha256sum "$dl/$apk" | cut -d' ' -f1)" \
              "https://github.com/$GITHUB_REPO/releases/download/$tag/$apk" "$tag"
      done < "$dl/ids.tsv"; } > "$WORK/provenance-$tag.tsv"
    say "staged $tag in $WORK/repo; next: $0 update"
}

# ----------------------------------------------------------------- update --

# Keep the newest KEEP_RELEASES releases. Every APK of one Redoubt build shares
# its versionCode's build hour (code >> 3: Fenix's 0x78200000 | hours << 3 | abi),
# so a "release" here is one build hour. Older APKs and their provenance are
# removed BEFORE the index is signed, so the index never names a
# file that the Pages deploy would have to fetch and the 1 GB budget holds.
prune_releases() {
    shopt -s nullglob
    local apks=("$WORK"/repo/"${PACKAGE}"_*.apk)
    [ "${#apks[@]}" -gt 0 ] || return 0
    local keep
    keep="$(printf '%s\n' "${apks[@]}" | sed -E 's/.*_([0-9]+)\.apk$/\1/' \
        | awk '{print int($1/8)}' | sort -rn | uniq | head -n "$KEEP_RELEASES" | tr '\n' ' ')"
    local f code hour
    for f in "${apks[@]}"; do
        code="$(basename "$f" .apk)"; code="${code##*_}"; hour=$((code / 8))
        case " $keep " in *" $hour "*) continue ;; esac
        printf '    prune   %s (older than the newest %s releases)\n' "$(basename "$f")" "$KEEP_RELEASES"
        rm -f "$f"
    done
    local p
    for p in "$WORK"/provenance-*.tsv; do
        local live=0 name
        while IFS=$'\t' read -r name _; do
            case "$name" in '#'*|'') continue ;; esac
            [ -f "$WORK/repo/$name" ] && live=1
        done < "$p"
        [ "$live" -eq 1 ] || { printf '    prune   %s\n' "$(basename "$p")"; rm -f "$p"; }
    done
}

cmd_update() {
    [ -f "$WORK/.repo_url" ] || die "no working directory at $WORK (run init first)"
    [ -f "$KEYSTORE" ] || die "no keystore at $KEYSTORE"
    [[ "$KEEP_RELEASES" =~ ^[1-9]$ ]] || die "KEEP_RELEASES must be 1-9"
    write_config
    # F-Droid shows "What's new" as the Changelog: link (the GitHub releases
    # page). fdroidserver puts per-version changelog text into index-v2 only for
    # versions it built itself, so a binary-only repository does not write any;
    # an earlier draft did, and the client never showed it (FDROID.md).
    rm -rf "$WORK/metadata/$PACKAGE"

    say "retention: the newest $KEEP_RELEASES release(s)"
    prune_releases

    say "re-verifying every APK before the index is signed"
    shopt -s nullglob
    local all=("$WORK"/repo/*.apk)
    [ "${#all[@]}" -gt 0 ] || die "repo/ is empty; run add first"
    local f
    for f in "${all[@]}"; do
        case "$(basename "$f")" in "${PACKAGE}"_[0-9]*.apk) ;; *) fail "unexpected file in the repository: $f" ;; esac
        grep -qs "^$(basename "$f")	" "$WORK"/provenance-*.tsv \
            || fail "$(basename "$f") has no provenance (it was not staged by 'add')"
    done
    verify_apks "${all[@]}"

    need_pass
    say "fdroid update (network: none)"
    fdroid_run "$FDROID_IMAGE" update > "$WORK/update.log" 2>&1 \
        || { tail -30 "$WORK/update.log" >&2; die "fdroid update failed (log: $WORK/update.log)"; }
    grep -vE '^\s*$' "$WORK/update.log" | sed 's/^/    /' | tail -20
    [ -f "$WORK/repo/entry.jar" ] && [ -f "$WORK/repo/index-v2.json" ] || die "fdroid update produced no signed index"

    say "repository state"
    python3 - "$WORK/repo/index-v2.json" <<'PY'
import json, sys
idx = json.load(open(sys.argv[1]))
total = 0
for pkg, p in idx.get("packages", {}).items():
    for v in sorted(p["versions"].values(), key=lambda v: -v["manifest"]["versionCode"]):
        m = v["manifest"]; total += v["file"]["size"]
        print(f"    {pkg} {m['versionName']:<18} {m['versionCode']}  {','.join(m.get('nativecode', [])):<12} {v['file']['name']}  {v['file']['size']}")
print(f"    APK bytes the Pages deploy will fetch: {total} ({total / 1e9:.3f} GB of the 1 GB site limit)")
PY
    printf '    repo fingerprint: %s\n' "$(saved_fingerprint | tr 'a-f' 'A-F')"
    say "next: $0 publish <path to a Redoubt git checkout>"
}

# ---------------------------------------------------------------- publish --

# What goes into git: the signed index and what it references, never an APK.
# index.html/.css/.png and index.xml are fdroidserver's human page and the
# unsigned v0 XML; clients do not read them (index.jar carries the v0 index),
# and the site has its own page (site/fdroid.html).
PUBLISH_EXCLUDES=(--exclude '*.apk' --exclude '*.apk.asc' --exclude '*.idsig'
                  --exclude '/index.html' --exclude '/index.css' --exclude '/index.png'
                  --exclude '/index.xml' --exclude '/status/' --exclude '/tmp/')

cmd_publish() {
    local checkout=""
    while [ $# -gt 0 ]; do
        case "$1" in
            -*) die "publish: unknown option $1" ;;
            *) [ -z "$checkout" ] || die "publish: one checkout"; checkout="$1"; shift ;;
        esac
    done
    [ -n "$checkout" ] || die "usage: $0 publish <path to a Redoubt git checkout>"
    checkout="$(realpath "$checkout")"
    [ -f "$checkout/site/CNAME" ] && [ -f "$checkout/scripts/fdroid-pages.py" ] \
        || die "$checkout is not a Redoubt checkout with site/ and scripts/fdroid-pages.py"
    inside_dir "$HOME_DIR" "$checkout" && die "$HOME_DIR (the key's home) is inside $checkout"
    [ -f "$WORK/repo/entry.jar" ] || die "nothing to publish: run update first"
    command -v rsync >/dev/null || die "publish needs rsync"

    local fp; fp="$(saved_fingerprint)"
    [[ "$fp" =~ ^[0-9a-f]{64}$ ]] || die "bad fingerprint in $HOME_DIR/repo-fingerprint.txt"
    local url; url="$(cat "$WORK/.repo_url")"
    local pin="$checkout/assets/fdroid/repo-fingerprint"
    if [ -f "$pin" ]; then
        [ "$(tr -d ' :\n' < "$pin" | tr 'A-F' 'a-f')" = "$fp" ] \
            || fail "$pin pins $(cat "$pin"), but this key is $fp. A new repository key orphans every client that added the old one (SIGNING.md, 'The F-Droid repository key'); a key change is never done by publish."
    else
        printf '%s\n' "$fp" > "$pin"
        say "first publish: pinned the repository fingerprint in assets/fdroid/repo-fingerprint"
    fi

    say "index files -> site/fdroid/repo/ (no APKs)"
    mkdir -p "$checkout/site/fdroid/repo"
    rsync -rlt --delete --checksum --itemize-changes "${PUBLISH_EXCLUDES[@]}" \
        "$WORK/repo/" "$checkout/site/fdroid/repo/" | sed 's/^/    /'

    say "APK sources -> site/fdroid/sources.json"
    python3 - "$WORK" "$checkout/site/fdroid/repo/index-v2.json" "$GITHUB_REPO" \
        > "$checkout/site/fdroid/sources.json" <<'PY'
import glob, json, sys
work, index, repo = sys.argv[1:4]
prov = {}
for p in glob.glob(f"{work}/provenance-*.tsv"):
    for line in open(p):
        if line.startswith("#") or not line.strip():
            continue
        name, sha, url, tag = line.rstrip("\n").split("\t")
        prov[name] = {"url": url, "sha256": sha, "tag": tag}
idx = json.load(open(index))
out = {}
for pkg in idx.get("packages", {}).values():
    for v in pkg["versions"].values():
        name = v["file"]["name"].lstrip("/")
        if name not in prov:
            sys.exit(f"fdroid-repo: REFUSED: the index names {name} but no release provenance exists for it")
        if prov[name]["sha256"] != v["file"]["sha256"]:
            sys.exit(f"fdroid-repo: REFUSED: {name}: index sha256 differs from the release asset's")
        out[name] = {"url": prov[name]["url"], "tag": prov[name]["tag"]}
json.dump({"comment": "Written by scripts/fdroid-repo.sh publish. Where the Pages deploy fetches each APK "
           "the signed index names; the sha256 that is enforced is the signed index's, not this file's.",
           "apks": dict(sorted(out.items()))}, sys.stdout, indent=2)
print()
PY

    say "human page -> site/fdroid.html, QR code -> site/fdroid/repo-qr.svg"
    local FP; FP="$(printf '%s' "$fp" | tr 'a-f' 'A-F')"
    local host_path="${url#https://}"; host_path="${host_path#http://}"
    sed -e "s#@REPO_URL@#$url#g" -e "s#@REPO_HOSTPATH@#$host_path#g" -e "s#@FINGERPRINT@#$FP#g" \
        -e "s#@FINGERPRINT_SPACED@#$(printf '%s' "$FP" | sed -E 's/(.{8})/\1 /g; s/ $//')#g" \
        "$REPO_ROOT/assets/fdroid/fdroid.html.in" > "$checkout/site/fdroid.html"
    # The QR code: drawn by the python3-qrcode that fdroidserver itself uses for
    # its index.png, as a path-only SVG (no script, no style element), so the
    # site's CSP (default-src 'self', no inline style) is untouched.
    "$PODMAN" run --rm --network=none --security-opt label=disable --entrypoint python3 \
        "$FDROID_IMAGE" -c '
import sys, qrcode, qrcode.image.svg
img = qrcode.make(sys.argv[1], image_factory=qrcode.image.svg.SvgPathFillImage, box_size=10, border=2)
sys.stdout.buffer.write(img.to_string())' "fdroidrepos://$host_path?fingerprint=$FP" \
        > "$checkout/site/fdroid/repo-qr.svg"
    grep -q '<svg' "$checkout/site/fdroid/repo-qr.svg" || die "QR code generation failed"
    if grep -qiE '<script|<style|javascript:' "$checkout/site/fdroid/repo-qr.svg"; then
        die "the generated QR SVG contains script or style; refusing"
    fi

    say "the Pages deploy's own index check (no download)"
    python3 "$checkout/scripts/fdroid-pages.py" check --site "$checkout/site" \
        --repo-fingerprint-file "$pin" \
        || fail "the published files fail scripts/fdroid-pages.py check"

    say "what changed (commit these, signed, and push to main):"
    git -C "$checkout" status --short -- site/fdroid site/fdroid.html assets/fdroid/repo-fingerprint | sed 's/^/    /'
    git -C "$checkout" diff --stat -- site/fdroid site/fdroid.html assets/fdroid/repo-fingerprint | tail -1 | sed 's/^/    /'
    du -sb "$checkout/site/fdroid" | awk '{printf "    site/fdroid in git: %d bytes\n", $1}'

    say "site check (pages.yaml runs it first)"
    local sc=0 out
    out="$(python3 "$checkout/scripts/site-check.py" "$checkout/site")" || sc=$?
    printf '%s\n' "$out" | grep -E '^(FAIL|PASS)' | sed 's/^/    /'
    [ "$sc" -eq 0 ] \
        || fail "site-check fails; do not commit (a non-production repo URL, as in a local test, always fails it)"
}

# ----------------------------------------------------------------- verify --

cmd_verify() {
    local url="" fp="${EXPECT_FINGERPRINT:-}"
    while [ $# -gt 0 ]; do
        case "$1" in
            --fingerprint) fp="${2:?}"; shift 2 ;;
            -*) die "verify: unknown option $1" ;;
            *) url="$1"; shift ;;
        esac
    done
    url="${url:-$DEFAULT_REPO_URL}"; url="${url%/}"
    if [ -z "$fp" ]; then
        if [ -f "$HOME_DIR/repo-fingerprint.txt" ]; then fp="$(cat "$HOME_DIR/repo-fingerprint.txt")"
        elif [ -f "$REPO_ROOT/assets/fdroid/repo-fingerprint" ]; then fp="$(cat "$REPO_ROOT/assets/fdroid/repo-fingerprint")"
        else die "no expected fingerprint: pass --fingerprint, or keep $HOME_DIR/repo-fingerprint.txt"; fi
    fi
    fp="$(printf '%s' "$fp" | tr -d ': \n' | tr 'A-F' 'a-f')"
    [[ "$fp" =~ ^[0-9a-f]{64}$ ]] || die "the fingerprint must be 64 hex digits"

    say "verify $url against repo fingerprint $(printf '%s' "$fp" | tr 'a-f' 'A-F')"
    # fdroidserver's own client-side check: entry.jar's JAR signature, its
    # signer == the fingerprint, then index-v2.json's sha256 == entry.json's.
    # Network is needed here (and only here); no key is mounted.
    local out
    out="$("$PODMAN" run --rm --network=host --security-opt label=disable --entrypoint sh "$FDROID_IMAGE" -c '
        . /etc/profile.d/bsenv.sh; cd /tmp
        python3 - "$0" "$1" "$2" <<"PY"
import sys
sys.path.insert(0, __import__("os").environ["fdroidserver"])
from fdroidserver import common, index
common.config = {"jarsigner": "jarsigner", "keytool": "keytool"}
common.options = None
url, fp, pkg = sys.argv[1:4]
data, _ = index.download_repo_index_v2(f"{url}?fingerprint={fp}")
print("signature  ok: entry.jar is signed by the expected key; index-v2.json matches entry.json")
print("repo       " + str(data["repo"].get("address")) + "  timestamp " + str(data["repo"].get("timestamp")))
p = data.get("packages", {}).get(pkg)
if not p:
    sys.exit("fdroid-repo: the index lists no " + pkg)
for v in sorted(p["versions"].values(), key=lambda v: -v["manifest"]["versionCode"]):
    m = v["manifest"]
    signer = (m.get("signer") or {}).get("sha256", ["?"])
    print("package    %s %s %s %s %s signer %s" % (pkg, m["versionName"], m["versionCode"],
          ",".join(m.get("nativecode", [])) or "-", v["file"]["sha256"], ",".join(signer)))
PY' "$url" "$fp" "$PACKAGE" 2>&1)" || { printf '%s\n' "$out" >&2; fail "the published index did not verify"; }
    printf '%s\n' "$out"

    # Every listed APK must be signed by the release key per the index, and
    # actually be served, with the index's sha256.
    local rel; rel="$(release_fingerprint)"
    if printf '%s\n' "$out" | grep '^package' | grep -v "signer $rel\$" | grep -q .; then
        fail "the index lists an APK whose signer is not the release key $rel"
    fi
    local code sha got
    while read -r code sha; do
        got="$(curl -fsSL --max-time 300 "$url/${PACKAGE}_${code}.apk" | sha256sum | cut -d' ' -f1)" \
            || fail "the index names ${PACKAGE}_${code}.apk but $url does not serve it"
        [ "$got" = "$sha" ] || fail "${PACKAGE}_${code}.apk is served with sha256 $got, the index says $sha"
        printf '    served  %s_%s.apk  sha256 matches the signed index\n' "$PACKAGE" "$code"
    done < <(printf '%s\n' "$out" | awk '/^package/ {print $4, $6}')
    say "verified: index signature, fingerprint, release signer, and every listed APK is served byte-exact"
}

# ------------------------------------------------------------------- main --

cmd="${1:-}"; [ $# -gt 0 ] && shift
case "$cmd" in
    init)        cmd_init "$@" ;;
    add)         cmd_add "$@" ;;
    update)      cmd_update "$@" ;;
    publish)     cmd_publish "$@" ;;
    verify)      cmd_verify "$@" ;;
    fingerprint) keystore_fingerprint | tr 'a-f' 'A-F' ;;
    -h|--help|help|"") usage ;;
    *) die "unknown command: $cmd (try --help)" ;;
esac
