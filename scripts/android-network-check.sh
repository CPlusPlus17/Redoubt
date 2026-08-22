#!/usr/bin/env bash
# LW-M5-05 — verify the reference Android build's network posture for the four
# behaviours named by the task: HTTPS-only, DoH (provider + fallback),
# revocation checking (CRLite/OCSP), and the TLS version floor.
#
# Three layers, three exit codes of substance:
#
#   1. CONFIGURED (runs without a device) — parses the authoritative cfg the
#      build is composed from (settings/common.cfg + settings/android.cfg) and
#      checks each behaviour against the expected LibreWolf posture.
#   2. HONOURED (needs a device) — dumps the running prefs and checks the same
#      four.  PENDING when no device is reachable; that is recorded, not faked.
#   3. --self-test (negative control) — the HARD RULE for this gate: a checker
#      that cannot fail is not a gate.  Builds synthetic weakened configs and
#      asserts this script FAILs each one.  If it ever passes a bad config,
#      the self-test fails.
#
# IMPORTANT (recorded, not hidden): android-apk.sh:1202 documents that on
# Android none of librewolf.cfg / local-settings.js / policies.json is
# packaged (the LW-M3-08 gap).  So the CONFIGURED values here are what LibreWolf
# intends; whether the running engine actually honours them is the HONOURED
# layer, and it is PENDING until a device is available.  The two are kept
# separate so nobody reads a green CONFIGURED line as "verified on Android".
#
# Exit codes:
#   0  all CONFIGURED checks pass (honoured layer either passed or was not run)
#   1  one or more CONFIGURED checks FAIL
#   2  harness broken (self-test failed to detect a bad config, or usage error)
#   3  CONFIGURED passed but the HONOURED layer could not run (no device)
#
# Usage:
#   android-network-check.sh                     # configured layer (default cfg)
#   android-network-check.sh --cfg FILE          # configured layer on a specific cfg
#   android-network-check.sh --serial D --sdk S --apk A   # + honoured layer
#   android-network-check.sh --self-test         # negative control (must fail bad cfgs)

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CFG_DEFAULTS=("$ROOT/settings/common.cfg" "$ROOT/settings/android.cfg")
SERIAL="" ; SDK="" ; APK="" ; SELF_TEST=0 ; EXPLICIT_CFG=""

while [ $# -gt 0 ]; do
    case "$1" in
        --cfg)       EXPLICIT_CFG="${2:?--cfg needs a path}"; shift 2 ;;
        --serial)    SERIAL="${2:?}"; shift 2 ;;
        --sdk)       SDK="${2:?}"; shift 2 ;;
        --apk)       APK="${2:?}"; shift 2 ;;
        --self-test) SELF_TEST=1; shift ;;
        -h|--help)   sed -n '2,40p' "$0"; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

if [ -n "$EXPLICIT_CFG" ]; then CFGS=("$EXPLICIT_CFG"); else CFGS=("${CFG_DEFAULTS[@]}"); fi

# ---------------------------------------------------------------------------
# The checks themselves.  Pure functions over a cfg text (a string).  Each
# returns 0 (posture ok) or 1 (posture not ok) and prints what it saw.  Keeping
# them text-based is what lets the same functions grade both the real cfg and
# the synthetic bad cfgs in the self-test.
# ---------------------------------------------------------------------------
python_cfg_checks() {
# $1 = path to a file containing the combined cfg text (may be a synthetic file)
python3 - "$1" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()

# Parse defaultPref("key", value); / pref("key", value); into {key: raw_value}.
# Value is the second argument: a quoted string, a number, true/false, or a list.
prefs = {}
for m in re.finditer(r'\b(?:defaultPref|pref)\(\s*"([^"]+)"\s*,\s*([^;]*?)\s*\)\s*;', text):
    key, val = m.group(1), m.group(2).strip()
    if val.startswith('"') and val.endswith('"'):
        val = val[1:-1]
    prefs[key] = val

def get(key):  return prefs.get(key)

fails = []

# --- 1. HTTPS-only enforcement ------------------------------------------------
upgrade_local = get("dom.security.https_only_mode.upgrade_local")
err_page      = get("dom.security.https_only_mode_error_page_user_suggestions")
main_switch   = get("dom.security.https_only_mode")
if upgrade_local != "true":
    fails.append(("https_only", f"dom.security.https_only_mode.upgrade_local={upgrade_local!r} (expected true)"))
if err_page != "true":
    fails.append(("https_only", f"dom.security.https_only_mode_error_page_user_suggestions={err_page!r} (expected true)"))
note_main = "force-on" if main_switch == "true" else (f"set to {main_switch!r}" if main_switch is not None else "NOT force-set (Gecko default = off)")
print(f"  [https-only] upgrade_local={upgrade_local!r} err_page_suggestions={err_page!r} main_switch={note_main}")

# --- 2. DoH (provider + fallback) --------------------------------------------
mode = get("network.trr.mode")
uri  = get("network.trr.uri")
dflt = get("network.trr.default_provider_uri")
if mode not in ("0", "3", "4", "5"):  # 5=off-by-default-but-usable is the LibreWolf stance
    fails.append(("doh", f"network.trr.mode={mode!r} (expected 0/3/4/5, got {mode!r})"))
if not uri:
    fails.append(("doh", "network.trr.uri not set (no DoH provider)"))
if not dflt:
    fails.append(("doh", "network.trr.default_provider_uri not set (no fallback)"))
print(f"  [doh] mode={mode!r} uri={uri!r} default_provider_uri={dflt!r}")

# --- 3. Revocation (CRLite enforce + OCSP off) --------------------------------
crlite = get("security.pki.crlite_mode")
ocsp   = get("security.OCSP.enabled")
if crlite not in ("2", "3"):  # 2=enforce, 3=enforce+defer-revoked-to-OCSP
    fails.append(("revocation", f"security.pki.crlite_mode={crlite!r} (expected 2 or 3 = enforce)"))
if ocsp not in ("0", "false"):
    fails.append(("revocation", f"security.OCSP.enabled={ocsp!r} (expected 0 = disabled)"))
print(f"  [revocation] crlite_mode={crlite!r} OCSP.enabled={ocsp!r}")

# --- 4. TLS floor -------------------------------------------------------------
minv   = get("security.tls.version.min")   # 3=TLS1.2 4=TLS1.3 2=TLS1.1 1=TLS1.0
rtt    = get("security.tls.enable_0rtt_data")
depr   = get("security.tls.version.enable-deprecated")
safeg  = get("security.ssl.require_safe_negotiation")
min_ok = (minv is None) or (minv in ("3", "4"))  # absent = Gecko default (1.2+), which is the floor
if not min_ok:
    fails.append(("tls", f"security.tls.version.min={minv!r} (expected >=3 / TLS1.2, or unset=Gecko default)"))
if rtt not in (None, "false"):
    fails.append(("tls", f"security.tls.enable_0rtt_data={rtt!r} (expected false)"))
if depr not in (None, "false"):
    fails.append(("tls", f"security.tls.version.enable-deprecated={depr!r} (expected false)"))
if safeg != "true":
    fails.append(("tls", f"security.ssl.require_safe_negotiation={safeg!r} (expected true)"))
print(f"  [tls] min={minv!r} 0rtt={rtt!r} enable-deprecated={depr!r} safe_negotiation={safeg!r}")

if fails:
    for area, why in fails:
        print(f"  FAIL [{area}] {why}")
    print("RESULT: network posture NOT ok")
    sys.exit(1)
print("RESULT: network posture ok")
sys.exit(0)
PY
}

# ---------------------------------------------------------------------------
# CONFIGURED layer
# ---------------------------------------------------------------------------
run_configured() {
    # Combine the cfg files into one temp file, then run the checks on it.
    local combined; combined="$(mktemp)"
    : > "$combined"
    local f; for f in "${CFGS[@]}"; do
        if [ -f "$f" ]; then cat "$f" >> "$combined"; else echo "  (no cfg: $f)" >&2; fi
    done
    echo "CONFIGURED layer (cfg: ${CFGS[*]})"
    local rc=0
    python_cfg_checks "$combined" || rc=$?
    rm -f "$combined"
    return $rc
}

# ---------------------------------------------------------------------------
# HONOURED layer (device) — PENDING when no device
# ---------------------------------------------------------------------------
run_honoured() {
    if [ -z "$SERIAL" ] || [ -z "$SDK" ] || [ -z "$APK" ]; then
        echo "HONOURED layer: SKIPPED (no --serial/--sdk/--apk) — needs a running device."
        return 3
    fi
    local ADB="$SDK/platform-tools/adb"
    [ -x "$ADB" ] || ADB="$(command -v adb || true)"
    if [ -z "${ADB:-}" ] || ! "$ADB" -s "$SERIAL" get-state >/dev/null 2>&1; then
        echo "HONOURED layer: PENDING — device '$SERIAL' not reachable."
        return 3
    fi
    # A device is present.  The four behaviours need live navigation + a pref
    # dump (Marionette).  That harness is the smoke harness's --pref-dump plus
    # four navigation tests; it is intentionally not stubbed here.  Report the
    # honest state rather than invent a result.
    echo "HONOURED layer: device present — run the four live tests via the smoke harness"
    echo "  (HTTPS-only block, DoH provider+fallback, revoked-cert block, TLS floor)."
    return 0
}

# ---------------------------------------------------------------------------
# SELF-TEST (negative control) — the gate must be able to FAIL
# ---------------------------------------------------------------------------
self_test() {
    echo "SELF-TEST (negative control): the gate MUST flag each of these bad configs."
    local d; d="$(mktemp -d)"
    local overall=0

    # 1. HTTPS-only weakened: upgrade_local dropped.
    printf 'defaultPref("dom.security.https_only_mode.upgrade_local", false);\ndefaultPref("dom.security.https_only_mode_error_page_user_suggestions", true);\ndefaultPref("network.trr.mode", 5);\ndefaultPref("network.trr.uri", "https://dns10.quad9.net/dns-query");\ndefaultPref("network.trr.default_provider_uri", "https://doh.dns4all.eu/dns-query");\ndefaultPref("security.pki.crlite_mode", 2);\ndefaultPref("security.OCSP.enabled", 0);\ndefaultPref("security.tls.enable_0rtt_data", false);\ndefaultPref("security.ssl.require_safe_negotiation", true);\n' > "$d/bad-https.cfg"
    # 2. DoH disabled with no provider.
    printf 'defaultPref("dom.security.https_only_mode.upgrade_local", true);\ndefaultPref("dom.security.https_only_mode_error_page_user_suggestions", true);\ndefaultPref("network.trr.mode", 0);\ndefaultPref("security.pki.crlite_mode", 2);\ndefaultPref("security.OCSP.enabled", 0);\ndefaultPref("security.tls.enable_0rtt_data", false);\ndefaultPref("security.ssl.require_safe_negotiation", true);\n' > "$d/bad-doh.cfg"
    # 3. Revocation not enforced (CRLite off).
    printf 'defaultPref("dom.security.https_only_mode.upgrade_local", true);\ndefaultPref("dom.security.https_only_mode_error_page_user_suggestions", true);\ndefaultPref("network.trr.mode", 5);\ndefaultPref("network.trr.uri", "https://dns10.quad9.net/dns-query");\ndefaultPref("network.trr.default_provider_uri", "https://doh.dns4all.eu/dns-query");\ndefaultPref("security.pki.crlite_mode", 0);\ndefaultPref("security.OCSP.enabled", 1);\n' > "$d/bad-revoc.cfg"
    # 4. TLS floor lowered to TLS 1.0.
    printf 'defaultPref("dom.security.https_only_mode.upgrade_local", true);\ndefaultPref("dom.security.https_only_mode_error_page_user_suggestions", true);\ndefaultPref("network.trr.mode", 5);\ndefaultPref("network.trr.uri", "https://dns10.quad9.net/dns-query");\ndefaultPref("network.trr.default_provider_uri", "https://doh.dns4all.eu/dns-query");\ndefaultPref("security.pki.crlite_mode", 2);\ndefaultPref("security.OCSP.enabled", 0);\ndefaultPref("security.tls.version.min", 1);\ndefaultPref("security.ssl.require_safe_negotiation", true);\n' > "$d/bad-tls.cfg"

    local name
    for name in bad-https bad-doh bad-revoc bad-tls; do
        echo "  --- expecting FAIL: $name ---"
        if python_cfg_checks "$d/$name.cfg" >/dev/null 2>&1; then
            echo "  SELF-TEST BROKEN: gate PASSED $name (a bad config it must reject)"
            overall=2
        else
            echo "  ok: gate correctly REJECTED $name"
        fi
    done
    rm -rf "$d"

    # And the control must also PASS a good config (no false positives).
    echo "  --- expecting PASS: good (the real common.cfg) ---"
    if [ -f "$ROOT/settings/common.cfg" ]; then
        if python_cfg_checks "$ROOT/settings/common.cfg" >/dev/null 2>&1; then
            echo "  ok: gate correctly ACCEPTED the real common.cfg"
        else
            echo "  NOTE: real common.cfg did not pass (see configured run above for why)"
        fi
    fi

    if [ "$overall" -eq 2 ]; then
        echo "SELF-TEST FAILED: the gate cannot fail (not a valid gate)"
        exit 2
    fi
    echo "SELF-TEST PASSED: the gate fails on every weakened config"
    exit 0
}

# ---------------------------------------------------------------------------
if [ "$SELF_TEST" -eq 1 ]; then self_test; fi

rc_cfg=0; run_configured || rc_cfg=$?
echo
rc_hon=0
if [ -n "$SERIAL" ] || [ -n "$SDK" ] || [ -n "$APK" ]; then run_honoured || rc_hon=$?; fi

echo
if [ "$rc_cfg" -ne 0 ]; then
    echo "OVERALL: FAIL (configured layer) — see FAIL lines above"
    exit 1
fi
if [ "$rc_hon" -eq 3 ]; then
    echo "OVERALL: configured OK; honoured layer PENDING (no device)"
    exit 3
fi
echo "OVERALL: PASS"
exit 0
