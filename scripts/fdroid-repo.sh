#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/fdroid-repo.sh -- run the Redoubt F-Droid repository (LW-M6-03).
#
# The repository is served from the owner's Hetzner Object Storage bucket,
# https://<bucket>.<location>.your-objectstorage.com/repo (bucket and location:
# assets/fdroid/deploy.conf). It serves the SAME owner-signed per-ABI APKs as
# the GitHub release. It builds nothing and re-signs nothing: the only new
# signature is the repository key's signature over the index. The newest
# KEEP_VERSIONS releases are in repo/, every older release in archive/; no
# release is ever deleted. The human page stays on redoubtbrowser.org
# (site/fdroid.html). Runbook and design: docs/android/FDROID.md.
#
# Never run this under `bash -x` / `set -x`: the trace prints the S3 secret
# (load_s3_env and the rclone exports). Credentials are otherwise never in
# argv or logs.
#
#   init [--bucket <name>] [--location fsn1|nbg1|hel1]
#                        create the repository signing key (owner, once) and
#                        the working directory; fill the bucket into
#                        assets/fdroid/deploy.conf if it is still empty;
#                        print the repo fingerprint
#   add <release-tag>    fetch the release's per-ABI APKs + SHA256SUMS.signed
#                        from GitHub, verify sha256 (against SHA256SUMS.signed
#                        AND GitHub's asset digest) and the APK certificate
#                        (== the published fingerprint, v2+v3, no v1), refuse
#                        otherwise, and stage them in the working repo/
#   update               re-verify every APK (repo/ and archive/), run
#                        `fdroid update` with archive_older = KEEP_VERSIONS
#                        releases (signs both indexes, no network)
#   deploy               upload to the bucket with the pinned rclone: APKs
#                        first (never overwritten, never deleted), then the
#                        other files, then the archive index, then the repo
#                        index, entry.jar last; then `verify --quick`.
#                        S3 credentials come from $REDOUBT_FDROID_HOME/s3.env
#                        (mode 600, never in the repo, never in argv or logs)
#   verify [<repo-url>] [--quick]
#                        fetch the published repo and archive indexes, check
#                        their signature against the repo fingerprint and the
#                        release signer of every APK; without --quick also
#                        download every listed APK and compare size + sha256
#   publish-page <checkout>
#                        write the human page site/fdroid.html, its QR code
#                        site/fdroid-qr.svg and the pinned repo fingerprint
#                        assets/fdroid/repo-fingerprint into a checkout; run
#                        the site check; print what changed. The owner commits.
#   fingerprint          print the repo fingerprint from the local keystore
#
# fdroidserver runs in F-Droid's own container image, pinned by digest
# (FDROID_IMAGE below; why: FDROID.md, "Tooling"). init and update run it
# with --network=none: the container that sees the repository key has no
# network. The repository key, its passphrase and the S3 credentials never
# enter a git checkout: they live in $REDOUBT_FDROID_HOME (default
# ~/redoubt-fdroid); the passphrase is typed at a prompt and handed to that
# one container through its environment.
#
# Environment:
#   REDOUBT_FDROID_HOME   working home (default ~/redoubt-fdroid)
#   REDOUBT_FDROID_S3_ENV S3 credentials file (default $REDOUBT_FDROID_HOME/s3.env)
#   FDROID_DEPLOY_CONF    hosting config (default assets/fdroid/deploy.conf;
#                         point it elsewhere only for throwaway tests)
#   FDROID_KEYSTORE_PASS  repository keystore passphrase; prompted when unset
#                         (set it only for throwaway-key tests)
#   APKSIGNER             apksigner for the certificate check (default: the
#                         SDK, $PATH, else the one inside the pinned image)
#   KEEP_VERSIONS         releases in the main section (default: deploy.conf,
#                         else 5); older ones go to archive/
#   GITHUB_REPO           default CPlusPlus17/Redoubt
# ---------------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# F-Droid's official image, registry.gitlab.com/fdroid/docker-executable-fdroidserver,
# tag `master` as of 2026-10-04 (fdroidserver commit c21c177ff6d8, 2026-10-01,
# Debian 13). The `latest` tag is a 2024 build; do not use it.
FDROID_IMAGE="registry.gitlab.com/fdroid/docker-executable-fdroidserver@sha256:75f6b88ef13a63fc5c49aa4c4dde35607c4a364d22cf57d534aa75c54effa56d"
PODMAN="${PODMAN:-podman}"

# rclone, pinned by version and by the sha256 of the release zip. The sums are
# from https://downloads.rclone.org/v1.75.1/SHA256SUMS, whose PGP signature
# verified 2026-10-05 against rclone's release key FBF737ECE9F8AB18604BD2AC93935E02FF3B54FA
# (FDROID.md, "Tooling"). Not fdroidserver's own `deploy`: it runs
# `rclone sync --delete-after`, which deletes remote files.
RCLONE_VERSION="v1.75.1"
RCLONE_SHA256_amd64="982b5aa772841168f8e380f139e9e787b2a105403e32b94da8676a0e1c0a13ab"
RCLONE_SHA256_arm64="03f2504174034b6d004152ed7369251c9a9ec1f7e0836eda420f5c7a5ec0dff9"

PACKAGE="org.redoubtbrowser"
GITHUB_REPO="${GITHUB_REPO:-CPlusPlus17/Redoubt}"
KEY_ALIAS="redoubt-fdroid-repo"
# The ABIs served. The universal APK is NOT served: F-Droid clients pick the
# APK whose nativecode matches the device, every device matches one of these
# three, and the universal APK would carry the highest versionCode of its build
# and cost 2.2 times the bytes (FDROID.md, "What the repository serves").
ABIS=(arm64-v8a armeabi-v7a x86_64)

HOME_DIR="${REDOUBT_FDROID_HOME:-$HOME/redoubt-fdroid}"
WORK="$HOME_DIR/work"
KEYSTORE="$HOME_DIR/keystore.p12"
DOWNLOADS="$HOME_DIR/downloads"
S3_ENV_FILE="${REDOUBT_FDROID_S3_ENV:-$HOME_DIR/s3.env}"
CONF="${FDROID_DEPLOY_CONF:-$REPO_ROOT/assets/fdroid/deploy.conf}"

# The index files fdroidserver writes into each section. deploy uploads them
# LAST, in this order, entry.jar at the very end: a client that sees the new
# entry.jar finds every file it names already in place.
INDEX_FILES=(index-v1.json index-v1.jar index.jar index-v2.json entry.json entry.jar)
# Written by fdroidserver but never uploaded: its own HTML page and QR image,
# the unsigned v0 XML (index.jar carries v0 for old clients), and scratch.
NOT_UPLOADED=(index.html index.css index.png index.xml 'status/**' 'tmp/**')

die()  { printf 'fdroid-repo: %s\n' "$*" >&2; exit 2; }
fail() { printf 'fdroid-repo: REFUSED: %s\n' "$*" >&2; exit 1; }
say()  { printf '==> %s\n' "$*"; }

usage() {
    sed -n '3,64p' "$0" | sed 's/^# \{0,1\}//'
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

# deploy.conf: KEY=value lines, parsed here (never sourced, so it cannot run
# code). Hetzner's documented URL forms (FDROID.md, "Hosting"):
#   S3 API endpoint   https://<location>.your-objectstorage.com
#   public objects    https://<bucket>.<location>.your-objectstorage.com/<object>
# S3_ENDPOINT and PUBLIC_BASE_URL override them, for throwaway tests only;
# site-check.py refuses a committed deploy.conf that sets either.
conf_get() {
    sed -n "s/^$1=//p" "$CONF" | tail -1 | tr -d '\r'
}

load_conf() {
    [ -f "$CONF" ] || die "no hosting config at $CONF"
    BUCKET="$(conf_get S3_BUCKET)"
    LOCATION="$(conf_get S3_LOCATION)"
    KEEP_VERSIONS="${KEEP_VERSIONS:-$(conf_get KEEP_VERSIONS)}"; KEEP_VERSIONS="${KEEP_VERSIONS:-5}"
    S3_ENDPOINT="$(conf_get S3_ENDPOINT)"
    PUBLIC_BASE_URL="$(conf_get PUBLIC_BASE_URL)"
    case "$LOCATION" in fsn1|nbg1|hel1) ;;
        *) die "$CONF: S3_LOCATION must be fsn1, nbg1 or hel1 (Hetzner's Object Storage locations), not '$LOCATION'" ;; esac
    [[ "$KEEP_VERSIONS" =~ ^[1-9][0-9]?$ ]] || die "KEEP_VERSIONS must be 1-99, not '$KEEP_VERSIONS'"
    if [ -n "$BUCKET" ]; then valid_bucket "$BUCKET" || die "$CONF: '$BUCKET' is not a valid bucket name"; fi
    : "${S3_ENDPOINT:=https://$LOCATION.your-objectstorage.com}"
    if [ -z "$PUBLIC_BASE_URL" ] && [ -n "$BUCKET" ]; then
        PUBLIC_BASE_URL="https://$BUCKET.$LOCATION.your-objectstorage.com"
    fi
    PUBLIC_BASE_URL="${PUBLIC_BASE_URL%/}"
    REPO_URL="${PUBLIC_BASE_URL:+$PUBLIC_BASE_URL/repo}"
}

# Hetzner's bucket name rules (FDROID.md, "Hosting"), and no dots, so the
# bucket's virtual-hosted name stays under the *.<location> TLS wildcard.
valid_bucket() {
    [[ "$1" =~ ^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$ ]] && ! [[ "$1" =~ ^[0-9]+(-[0-9]+){3}$ ]]
}

need_bucket() {
    load_conf
    [ -n "$BUCKET" ] || die "no bucket in $CONF (run init --bucket <name> --location <loc>; FDROID.md, 'Owner runbook')"
}

# The working directory is tied to one repo URL. Changing it is a mirror
# operation (FDROID.md, "Mirrors"), never a side effect of an edited config.
check_repo_url() {
    [ -f "$WORK/.repo_url" ] || die "no working directory at $WORK (run init first)"
    local have; have="$(cat "$WORK/.repo_url")"
    [ "$have" = "$REPO_URL" ] || fail "the working directory was created for $have, but $CONF now gives $REPO_URL. Clients that added the old URL would be orphaned; see FDROID.md, 'Mirrors'."
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
    local url archive_older
    url="$(cat "$WORK/.repo_url")"
    # fdroidserver's archive_older counts APK files per app, not releases; every
    # release has exactly one APK per ABI (add refuses anything else).
    archive_older=$((KEEP_VERSIONS * ${#ABIS[@]}))
    sed -e "s#@REPO_URL@#$url#g" -e "s#@ARCHIVE_OLDER@#$archive_older#g" \
        "$REPO_ROOT/assets/fdroid/config.yml.in" > "$WORK/config.yml"
    chmod 600 "$WORK/config.yml"   # fdroidserver refuses a world-readable config
    # fdroidserver looks for repo_icon in repo/icons/ (and archive/icons/).
    mkdir -p "$WORK/repo/icons" "$WORK/archive/icons"
    cp "$REPO_ROOT/assets/fdroid/repo-icon.png" "$WORK/repo/icons/icon.png"
    cp "$REPO_ROOT/assets/fdroid/repo-icon.png" "$WORK/archive/icons/icon.png"
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
    local bucket="" location=""
    while [ $# -gt 0 ]; do
        case "$1" in
            --bucket) bucket="${2:?--bucket needs a name}"; shift 2 ;;
            --location) location="${2:?--location needs fsn1, nbg1 or hel1}"; shift 2 ;;
            *) die "init: unknown argument $1" ;;
        esac
    done
    [ -f "$CONF" ] || die "no hosting config at $CONF"
    inside_dir "$HOME_DIR" "$REPO_ROOT" && die "$HOME_DIR is inside the git checkout; the key must live outside it"
    [ -e "$KEYSTORE" ] && fail "$KEYSTORE already exists. A second key would orphan every client that added the first one (SIGNING.md, 'The F-Droid repository key')"

    # Fill the bucket and location into deploy.conf, once. The owner commits it.
    load_conf
    local filled=0
    if [ -n "$bucket" ]; then
        valid_bucket "$bucket" || die "'$bucket' is not a valid Hetzner bucket name (3-63 of a-z 0-9 -, no dots; FDROID.md)"
        if [ -n "$BUCKET" ] && [ "$BUCKET" != "$bucket" ]; then
            fail "$CONF already names bucket $BUCKET; edit it by hand only if no client has added the repository yet"
        fi
        [ "$BUCKET" = "$bucket" ] || { sed -i "s/^S3_BUCKET=.*/S3_BUCKET=$bucket/" "$CONF"; filled=1; }
    fi
    if [ -n "$location" ]; then
        case "$location" in fsn1|nbg1|hel1) ;; *) die "--location must be fsn1, nbg1 or hel1" ;; esac
        [ "$LOCATION" = "$location" ] || { sed -i "s/^S3_LOCATION=.*/S3_LOCATION=$location/" "$CONF"; filled=1; }
    fi
    need_bucket
    local url="$REPO_URL"
    case "$url" in https://*/repo) ;; http://*/repo)
        printf 'fdroid-repo: WARNING: plain-http repo URL (%s) -- for local tests only\n' "$url" >&2 ;;
        *) die "the repo URL must end in /repo: $url" ;; esac
    mkdir -p "$WORK/repo" "$WORK/archive" "$DOWNLOADS"
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
  bucket        $BUCKET ($LOCATION)   config: $CONF
  repo URL      $url
  archive URL   ${url%/repo}/archive
  fingerprint   $(printf '%s' "$fp" | tr 'a-f' 'A-F')

Users add:  $url?fingerprint=$(printf '%s' "$fp" | tr 'a-f' 'A-F')
Next:       $0 add <release-tag>
EOF
    [ "$filled" -eq 0 ] || printf '\ninit wrote the bucket into %s: review it and commit it (signed).\n' "$CONF"
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

    # provenance: which GitHub asset each repo file is. update refuses an APK
    # without it.
    { printf '# tag\t%s\n# added\t%s\n' "$tag" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      while IFS=$'\t' read -r apk appid code vname; do
          printf '%s\t%s\t%s\t%s\n' "${PACKAGE}_${code}.apk" "$(sha256sum "$dl/$apk" | cut -d' ' -f1)" \
              "https://github.com/$GITHUB_REPO/releases/download/$tag/$apk" "$tag"
      done < "$dl/ids.tsv"; } > "$WORK/provenance-$tag.tsv"
    say "staged $tag in $WORK/repo; next: $0 update"
}

# ----------------------------------------------------------------- update --

# Retention (FDROID.md, "Retention"): nothing is ever deleted. fdroidserver's
# archive_older moves every release beyond the newest KEEP_VERSIONS from repo/
# to archive/ and signs an index for each section. A "release" is one build
# hour: every APK of a Redoubt build shares versionCode >> 3.
cmd_update() {
    need_bucket
    check_repo_url
    [ -f "$KEYSTORE" ] || die "no keystore at $KEYSTORE"
    write_config
    # F-Droid shows "What's new" as the Changelog: link (the GitHub releases
    # page). fdroidserver puts per-version changelog text into index-v2 only for
    # versions it built itself, so a binary-only repository does not write any;
    # an earlier draft did, and the client never showed it (FDROID.md).
    rm -rf "$WORK/metadata/$PACKAGE"

    say "retention: the newest $KEEP_VERSIONS release(s) in repo/, every older one in archive/ (archive_older: $((KEEP_VERSIONS * ${#ABIS[@]})) APKs); nothing is deleted"

    say "re-verifying every APK (repo/ and archive/) before the indexes are signed"
    shopt -s nullglob
    local all=("$WORK"/repo/*.apk "$WORK"/archive/*.apk)
    [ "${#all[@]}" -gt 0 ] || die "repo/ and archive/ are empty; run add first"
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
    local s
    for s in repo archive; do
        [ -f "$WORK/$s/entry.jar" ] && [ -f "$WORK/$s/index-v2.json" ] || die "fdroid update produced no signed $s index"
    done

    say "repository state"
    python3 - "$WORK" <<'PY'
import json, sys
work = sys.argv[1]
grand = 0
for section in ("repo", "archive"):
    idx = json.load(open(f"{work}/{section}/index-v2.json"))
    total, hours = 0, set()
    for pkg, p in idx.get("packages", {}).items():
        for v in sorted(p["versions"].values(), key=lambda v: -v["manifest"]["versionCode"]):
            m = v["manifest"]; total += v["file"]["size"]; hours.add(m["versionCode"] >> 3)
            print(f"    {section:<8} {pkg} {m['versionName']:<18} {m['versionCode']}  {','.join(m.get('nativecode', [])):<12} {v['file']['name']}  {v['file']['size']}")
    print(f"    {section:<8} {len(hours)} release(s), {total} APK bytes")
    grand += total
print(f"    bucket storage for APKs: {grand} bytes ({grand / 1e12:.4f} TB of the 1 TB included in Hetzner's base price)")
PY
    printf '    repo fingerprint: %s\n' "$(saved_fingerprint | tr 'a-f' 'A-F')"
    say "next: $0 deploy"
}

# ----------------------------------------------------------------- deploy --

# The S3 credentials: an owner-made file, never in the repository, readable by
# the owner only. Parsed, never sourced; only the two keys below are read, and
# no line of it is ever printed.
load_s3_env() {
    local f="$S3_ENV_FILE"
    [ -f "$f" ] && [ ! -L "$f" ] || die "no S3 credentials file at $f (a regular file; FDROID.md, 'Owner runbook')"
    inside_dir "$f" "$REPO_ROOT" && fail "$f is inside the git checkout; S3 credentials must never be near git"
    [ "$(stat -c %u "$f")" = "$(id -u)" ] || fail "$f is not owned by $(id -un)"
    local mode; mode="$(stat -c %a "$f")"
    case "$mode" in 600|400) ;;
        *) fail "$f has mode $mode; S3 credentials must be readable by you only: chmod 600 $f" ;; esac
    S3_KEY_ID="" S3_SECRET=""
    local line n=0
    while IFS= read -r line || [ -n "$line" ]; do
        n=$((n + 1)); line="${line%$'\r'}"
        case "$line" in
            ''|'#'*) ;;
            S3_ACCESS_KEY_ID=*) S3_KEY_ID="${line#*=}" ;;
            S3_SECRET_ACCESS_KEY=*) S3_SECRET="${line#*=}" ;;
            *) fail "$f line $n: only S3_ACCESS_KEY_ID=... and S3_SECRET_ACCESS_KEY=... are read (line not shown)" ;;
        esac
    done < "$f"
    [ -n "$S3_KEY_ID" ] && [ -n "$S3_SECRET" ] || fail "$f must set S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY"
}

# The pinned rclone, extracted from the verified zip into a private temporary
# directory for this run only.
ensure_rclone() {
    local arch sha
    case "$(uname -m)" in
        x86_64) arch=amd64; sha="$RCLONE_SHA256_amd64" ;;
        aarch64|arm64) arch=arm64; sha="$RCLONE_SHA256_arm64" ;;
        *) die "no pinned rclone for $(uname -m)" ;;
    esac
    local name="rclone-$RCLONE_VERSION-linux-$arch"
    local zip="$HOME_DIR/tools/$name.zip" got
    mkdir -p "$HOME_DIR/tools"
    got="$( [ -f "$zip" ] && sha256sum < "$zip" | cut -d' ' -f1 || true)"
    if [ "$got" != "$sha" ]; then
        say "fetching rclone $RCLONE_VERSION ($arch) from downloads.rclone.org"
        curl -fsSL --proto '=https' --proto-redir '=https' -o "$zip.part" \
            "https://downloads.rclone.org/$RCLONE_VERSION/$name.zip"
        mv "$zip.part" "$zip"
        got="$(sha256sum < "$zip" | cut -d' ' -f1)"
    fi
    [ "$got" = "$sha" ] || { rm -f "$zip"; fail "rclone zip sha256 $got differs from the pinned $sha"; }
    RCLONE_DIR="$(mktemp -d "$HOME_DIR/tools/.run.XXXXXX")"
    trap 'rm -rf "$RCLONE_DIR"' EXIT
    python3 - "$zip" "$name/rclone" "$RCLONE_DIR/rclone" <<'PY'
import shutil, sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z, z.open(sys.argv[2]) as src, open(sys.argv[3], "wb") as dst:
    shutil.copyfileobj(src, dst)
PY
    chmod 700 "$RCLONE_DIR/rclone"
    RCLONE="$RCLONE_DIR/rclone"
    "$RCLONE" version --config /notfound | head -1 | grep -qx "rclone $RCLONE_VERSION" \
        || fail "the extracted rclone does not report $RCLONE_VERSION"
}

# rclone with an in-memory remote `fdroids3:` defined only in the environment
# of this subshell: the credentials are never in argv (visible in ps) or in a
# config file, and RCLONE_* variables of the caller do not leak in. `export`
# is a shell builtin, so the secret never appears in any process's arguments.
rcl() {
    (
        while IFS= read -r v; do unset "$v"; done < <(compgen -e | grep '^RCLONE_' || true)
        export RCLONE_CONFIG=/notfound
        export RCLONE_CONFIG_FDROIDS3_TYPE=s3 RCLONE_CONFIG_FDROIDS3_PROVIDER=Hetzner
        export RCLONE_CONFIG_FDROIDS3_ENDPOINT="$S3_ENDPOINT" RCLONE_CONFIG_FDROIDS3_REGION="$LOCATION"
        export RCLONE_CONFIG_FDROIDS3_ACL=private RCLONE_CONFIG_FDROIDS3_NO_CHECK_BUCKET=true
        export RCLONE_CONFIG_FDROIDS3_ENV_AUTH=false
        export RCLONE_CONFIG_FDROIDS3_ACCESS_KEY_ID="$S3_KEY_ID"
        export RCLONE_CONFIG_FDROIDS3_SECRET_ACCESS_KEY="$S3_SECRET"
        exec "$RCLONE" "$@"
    )
}

# Before anything is uploaded: both local indexes are signed by the repository
# key, entry.json's sha256 of index-v2.json holds, and every APK and diff the
# indexes name is present locally, byte-exact. No network, no key.
local_index_check() {
    "$PODMAN" run --rm --network=none --security-opt label=disable -v "$WORK:/w:ro" \
        --entrypoint sh "$FDROID_IMAGE" -c '
        . /etc/profile.d/bsenv.sh; cd /tmp
        python3 - "$0" <<"PY"
import hashlib, json, os, sys
sys.path.insert(0, os.environ["fdroidserver"])
from fdroidserver import common, index
common.config = {"jarsigner": "jarsigner", "keytool": "keytool"}
common.options = None
fp = sys.argv[1]
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()
for section in ("repo", "archive"):
    d = f"/w/{section}"
    entry, _, got = index.get_index_from_jar(f"{d}/entry.jar", fingerprint=fp)
    name = entry["index"]["name"].lstrip("/")
    if sha(f"{d}/{name}") != entry["index"]["sha256"]:
        sys.exit(f"{section}/{name}: sha256 differs from the signed entry.json")
    files = 0
    for diff in entry.get("diffs", {}).values():
        p = f"{d}/" + diff["name"].lstrip("/")
        if not os.path.isfile(p) or sha(p) != diff["sha256"]:
            sys.exit("%s: diff %s missing or not as signed" % (section, diff["name"]))
        files += 1
    idx = json.load(open(f"{d}/{name}"))
    for pkg in idx.get("packages", {}).values():
        for v in pkg["versions"].values():
            p = f"{d}/" + v["file"]["name"].lstrip("/")
            if not os.path.isfile(p) or os.path.getsize(p) != v["file"]["size"] or sha(p) != v["file"]["sha256"]:
                sys.exit("%s: %s missing or not as signed" % (section, v["file"]["name"]))
            files += 1
    print(f"    {section:<8} entry.jar signed by {got[:8]}...{got[-8:]}; {files} file(s) named by the index present byte-exact")
PY' "$(saved_fingerprint)" || fail "the local repository does not match its signed indexes; run update again"
}

cmd_deploy() {
    local dry=() do_verify=1
    while [ $# -gt 0 ]; do
        case "$1" in
            --dry-run) dry=(--dry-run); shift ;;
            --no-verify) do_verify=0; shift ;;
            *) die "deploy: unknown argument $1" ;;
        esac
    done
    need_bucket
    check_repo_url
    local s
    for s in repo archive; do
        [ -f "$WORK/$s/entry.jar" ] || die "nothing to deploy: no $s/entry.jar (run update first)"
    done
    load_s3_env
    if ! command -v curl >/dev/null || ! command -v python3 >/dev/null; then die "deploy needs curl and python3"; fi

    say "local check: signed indexes, every named file present"
    local_index_check
    ensure_rclone
    local remote="fdroids3:$BUCKET"
    say "target: bucket $BUCKET at $S3_ENDPOINT, public at $PUBLIC_BASE_URL ${dry[*]:+(dry run)}"

    # Common flags: compare by size + hash only, no modtime games; log every
    # transfer; stats off. Nothing here ever deletes: copy/copyto only.
    local common=(--checksum -v --stats=0 --log-format "date,time" "${dry[@]}")

    # --immutable: an APK already in the bucket is never overwritten; if its size,
    # or its MD5 where the bucket reports one (every single-part upload, which
    # is how rclone uploads files below 200 MiB), differs from the local file,
    # the deploy stops before any index is touched. Content is checked byte for
    # byte by `verify` (FDROID.md, "What deploy and verify guarantee").
    say "1/3 APKs (new ones only; an existing APK whose size or MD5 differs is REFUSED, never overwritten; nothing is deleted)"
    for s in archive repo; do
        rcl copy "${common[@]}" --immutable --include '/*.apk' \
            --header-upload 'Content-Type: application/vnd.android.package-archive' \
            --header-upload 'Cache-Control: public, max-age=31536000, immutable' \
            "$WORK/$s" "$remote/$s" 2>&1 | sed "s#^#    $s: #" \
            || fail "uploading $s APKs failed; the index was NOT updated, the public repository is unchanged"
    done

    say "2/3 icons and index diffs"
    local ex=() f
    for f in "${INDEX_FILES[@]}" "${NOT_UPLOADED[@]}"; do ex+=(--exclude "/$f"); done
    for s in archive repo; do
        rcl copy "${common[@]}" "${ex[@]}" --exclude '*.apk' --exclude '*.apk.asc' --exclude '*.idsig' \
            "$WORK/$s" "$remote/$s" 2>&1 | sed "s#^#    $s: #" \
            || fail "uploading $s icons/diffs failed; the index was NOT updated"
    done

    say "3/3 indexes, LAST: archive, then repo; entry.jar at the very end of each"
    for s in archive repo; do
        for f in "${INDEX_FILES[@]}"; do
            rcl copyto "${common[@]}" --header-upload 'Cache-Control: no-cache' \
                "$WORK/$s/$f" "$remote/$s/$f" 2>&1 | sed "s#^#    $s: #" \
                || fail "uploading $s/$f failed; re-run deploy (APKs are already in place)"
            printf '    index   %s/%s\n' "$s" "$f"
        done
    done

    # Deploy never deletes. An APK that moved from repo/ to archive/ leaves its
    # old repo/ copy behind, unreferenced; it costs storage, not correctness.
    say "remote APKs that no index names (kept; deploy never deletes)"
    local orphans=0 name
    for s in repo archive; do
        while IFS= read -r name; do
            [ -n "$name" ] || continue
            [ -f "$WORK/$s/$name" ] && continue
            printf '    orphan  %s/%s\n' "$s" "$name"; orphans=$((orphans + 1))
        done < <(rcl lsf --files-only --include '/*.apk' "$remote/$s" 2>/dev/null || true)
    done
    [ "$orphans" -eq 0 ] && echo "    none"

    if [ "${#dry[@]}" -gt 0 ]; then say "dry run: nothing was uploaded"; return 0; fi
    if [ "$do_verify" -eq 1 ]; then
        say "public check (verify --quick $REPO_URL)"
        cmd_verify --quick "$REPO_URL"
        say "deployed. Run '$0 verify' (full, downloads every APK) before announcing the release."
    fi
}

# ----------------------------------------------------------- publish-page --

cmd_publish_page() {
    local checkout=""
    while [ $# -gt 0 ]; do
        case "$1" in
            -*) die "publish-page: unknown option $1" ;;
            *) [ -z "$checkout" ] || die "publish-page: one checkout"; checkout="$1"; shift ;;
        esac
    done
    [ -n "$checkout" ] || die "usage: $0 publish-page <path to a Redoubt git checkout>"
    checkout="$(realpath "$checkout")"
    [ -f "$checkout/site/CNAME" ] && [ -f "$checkout/scripts/site-check.py" ] \
        || die "$checkout is not a Redoubt checkout with site/ and scripts/site-check.py"
    inside_dir "$HOME_DIR" "$checkout" && die "$HOME_DIR (the key's home) is inside $checkout"
    need_bucket
    check_repo_url

    local fp; fp="$(saved_fingerprint)"
    [[ "$fp" =~ ^[0-9a-f]{64}$ ]] || die "bad fingerprint in $HOME_DIR/repo-fingerprint.txt"
    local pin="$checkout/assets/fdroid/repo-fingerprint"
    if [ -f "$pin" ]; then
        [ "$(tr -d ' :\n' < "$pin" | tr 'A-F' 'a-f')" = "$fp" ] \
            || fail "$pin pins $(cat "$pin"), but this key is $fp. A new repository key orphans every client that added the old one (SIGNING.md, 'The F-Droid repository key'); a key change is never done by publish-page."
    else
        printf '%s\n' "$fp" > "$pin"
        say "first publish: pinned the repository fingerprint in assets/fdroid/repo-fingerprint"
    fi

    say "human page -> site/fdroid.html, QR code -> site/fdroid-qr.svg"
    local url="$REPO_URL"
    local FP; FP="$(printf '%s' "$fp" | tr 'a-f' 'A-F')"
    local host_path="${url#https://}"; host_path="${host_path#http://}"
    local host="${host_path%%/*}" place
    case "$LOCATION" in
        fsn1) place="Falkenstein, Germany" ;; nbg1) place="Nuremberg, Germany" ;; hel1) place="Helsinki, Finland" ;;
    esac
    sed -e "s#@REPO_URL@#$url#g" -e "s#@REPO_HOSTPATH@#$host_path#g" -e "s#@REPO_HOST@#$host#g" \
        -e "s#@ARCHIVE_URL@#${url%/repo}/archive#g" -e "s#@FINGERPRINT@#$FP#g" \
        -e "s#@LOCATION_NAME@#$place#g" -e "s#@KEEP_VERSIONS@#$KEEP_VERSIONS#g" \
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
        > "$checkout/site/fdroid-qr.svg"
    grep -q '<svg' "$checkout/site/fdroid-qr.svg" || die "QR code generation failed"
    if grep -qiE '<script|<style|javascript:' "$checkout/site/fdroid-qr.svg"; then
        die "the generated QR SVG contains script or style; refusing"
    fi

    say "what changed (commit these, signed, and push to main):"
    local paths=(site/fdroid.html site/fdroid-qr.svg assets/fdroid/repo-fingerprint assets/fdroid/deploy.conf)
    git -C "$checkout" status --short -- "${paths[@]}" | sed 's/^/    /'

    say "site check (pages.yaml runs it first)"
    local sc=0 out
    out="$(python3 "$checkout/scripts/site-check.py" "$checkout/site")" || sc=$?
    printf '%s\n' "$out" | grep -E '^(FAIL|PASS)' | sed 's/^/    /'
    [ "$sc" -eq 0 ] \
        || fail "site-check fails; do not commit (a page rendered for a test URL always fails it)"
}

# ----------------------------------------------------------------- verify --

cmd_verify() {
    local url="" fp="${EXPECT_FINGERPRINT:-}" quick=0
    while [ $# -gt 0 ]; do
        case "$1" in
            --fingerprint) fp="${2:?}"; shift 2 ;;
            --quick) quick=1; shift ;;
            -*) die "verify: unknown option $1" ;;
            *) url="$1"; shift ;;
        esac
    done
    if [ -z "$url" ]; then
        need_bucket; url="$REPO_URL"
    fi
    url="${url%/}"
    case "$url" in */repo) ;; *) die "the repo URL must end in /repo: $url" ;; esac
    local archive="${url%/repo}/archive"
    if [ -z "$fp" ]; then
        if [ -f "$HOME_DIR/repo-fingerprint.txt" ]; then fp="$(cat "$HOME_DIR/repo-fingerprint.txt")"
        elif [ -f "$REPO_ROOT/assets/fdroid/repo-fingerprint" ]; then fp="$(cat "$REPO_ROOT/assets/fdroid/repo-fingerprint")"
        else die "no expected fingerprint: pass --fingerprint, or keep $HOME_DIR/repo-fingerprint.txt"; fi
    fi
    fp="$(printf '%s' "$fp" | tr -d ': \n' | tr 'A-F' 'a-f')"
    [[ "$fp" =~ ^[0-9a-f]{64}$ ]] || die "the fingerprint must be 64 hex digits"

    say "verify $url and $archive against repo fingerprint $(printf '%s' "$fp" | tr 'a-f' 'A-F')"
    # fdroidserver's own client-side check, per section: entry.jar's JAR
    # signature, its signer == the fingerprint, then index-v2.json's sha256 ==
    # entry.json's. Network is needed here (and only here); no key is mounted.
    local out
    out="$("$PODMAN" run --rm --network=host --security-opt label=disable --entrypoint sh "$FDROID_IMAGE" -c '
        . /etc/profile.d/bsenv.sh; cd /tmp
        python3 - "$0" "$1" "$2" "$3" <<"PY"
import sys
sys.path.insert(0, __import__("os").environ["fdroidserver"])
from fdroidserver import common, index
common.config = {"jarsigner": "jarsigner", "keytool": "keytool"}
common.options = None
repo, archive, fp, pkg = sys.argv[1:5]
listed = 0
for section, url in (("repo", repo), ("archive", archive)):
    data, _ = index.download_repo_index_v2(f"{url}?fingerprint={fp}")
    print(f"signature  ok: {section}/entry.jar is signed by the expected key; index-v2.json matches entry.json")
    print("index      %s address %s timestamp %s" % (section, data["repo"].get("address"), data["repo"].get("timestamp")))
    p = data.get("packages", {}).get(pkg, {"versions": {}})
    for v in sorted(p["versions"].values(), key=lambda v: -v["manifest"]["versionCode"]):
        m = v["manifest"]; listed += 1
        signer = (m.get("signer") or {}).get("sha256", ["?"])
        print("package    %s %s %s %s %s %s %s %s signer %s" % (section, pkg, m["versionName"], m["versionCode"],
              ",".join(m.get("nativecode", [])) or "-", v["file"]["name"].lstrip("/"), v["file"]["size"],
              v["file"]["sha256"], ",".join(signer)))
if not listed:
    sys.exit("fdroid-repo: neither index lists " + pkg)
PY' "$url" "$archive" "$fp" "$PACKAGE" 2>&1)" || { printf '%s\n' "$out" >&2; fail "the published indexes did not verify"; }
    printf '%s\n' "$out"

    # Every listed APK must be signed by the release key per the index.
    local rel; rel="$(release_fingerprint)"
    if printf '%s\n' "$out" | grep '^package' | grep -v "signer $rel\$" | grep -q .; then
        fail "an index lists an APK whose signer is not the release key $rel"
    fi
    if [ "$quick" -eq 1 ]; then
        say "verified (quick): both index signatures, fingerprint, release signer. APKs not downloaded."
        return 0
    fi
    # ... and actually be served, byte-exact.
    local section name size sha got have base tmp n=0
    while read -r section name size sha; do
        base="$url"; [ "$section" = archive ] && base="$archive"
        tmp="$(mktemp)"
        curl -fsSL --max-time 900 -o "$tmp" "$base/$name" \
            || { rm -f "$tmp"; fail "the index names $section/$name but $base does not serve it"; }
        got="$(sha256sum < "$tmp" | cut -d' ' -f1)"; have="$(stat -c %s "$tmp")"; rm -f "$tmp"
        [ "$got" = "$sha" ] || fail "$section/$name is served with sha256 $got, the index says $sha"
        [ "$have" = "$size" ] || fail "$section/$name is served with $have bytes, the index says $size"
        printf '    served  %-8s %s  %s bytes, sha256 matches the signed index\n' "$section" "$name" "$size"
        n=$((n + 1))
    done < <(printf '%s\n' "$out" | awk '/^package/ {print $2, $7, $8, $9}')
    say "verified: both index signatures, fingerprint, release signer, and all $n listed APKs served byte-exact"
}

# ------------------------------------------------------------------- main --

cmd="${1:-}"; [ $# -gt 0 ] && shift
case "$cmd" in
    init)         cmd_init "$@" ;;
    add)          cmd_add "$@" ;;
    update)       cmd_update "$@" ;;
    deploy)       cmd_deploy "$@" ;;
    publish-page) cmd_publish_page "$@" ;;
    publish)      die "'publish' is gone: the repository is uploaded by 'deploy', the human page is written by 'publish-page <checkout>' (FDROID.md)" ;;
    verify)       cmd_verify "$@" ;;
    fingerprint)  keystore_fingerprint | tr 'a-f' 'A-F' ;;
    -h|--help|help|"") usage ;;
    *) die "unknown command: $cmd (try --help)" ;;
esac
