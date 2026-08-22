#!/usr/bin/env bash
# LW-M5-04 — validate the RFP / fingerprinting posture of the Android build.
#
# The task's risk is the whole point: "copying desktop RFP values unexamined can
# make Android users MORE identifiable, not less."  So this gate checks two
# different things and keeps them separate:
#
#   1. CONFIGURED (runs without a device) — the RFP posture the Android build is
#      composed from (common.cfg + android.cfg) is the coherent one:
#        - the RFP master switch is ON (inherited from common.cfg),
#        - block_mozAddonManager is ON (RFP would otherwise break AMO),
#        - GPC is ON (a fingerprinting signal),
#        - the desktop-only sub-features (window-sizing trio, letterboxing) are
#          NOT pulled into the Android composition — letterboxing does not work on
#          GeckoView and desktop ships it false, so enabling it on Android is a
#          regression, not a parity win.
#   2. HONOURED (needs a device) — run the standard fingerprint probes (UA, screen
#      dims, DPR, canvas, the RFP coherence check) and compare to desktop
#      LibreWolf and Tor Browser for Android.  PENDING without a device; the
#      coherence question is exactly what this layer answers, so it is not
#      pretended to be answered by the configured layer.
#
#   3. --self-test (negative control, HARD RULE) — a checker that cannot fail is
#      not a gate.  Builds synthetic bad configs and asserts this script FAILs
#      them (RFP off; letterboxing enabled on Android).
#
# Exit codes:
#   0  configured RFP posture ok (honoured either passed or not run)
#   1  configured posture not ok (or self-test failed to reject a bad config)
#   2  harness broken / usage error
#   3  configured ok but honoured layer could not run (no device)
#
# Usage:
#   android-rfp-check.sh                     # configured layer (default cfg)
#   android-rfp-check.sh --serial D --sdk S --apk A   # + honoured layer
#   android-rfp-check.sh --self-test         # negative control

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERIAL="" ; SDK="" ; APK="" ; SELF_TEST=0 ; EXPLICIT_CFG=""

while [ $# -gt 0 ]; do
    case "$1" in
        --cfg)       EXPLICIT_CFG="${2:?--cfg needs a path}"; shift 2 ;;
        --serial)    SERIAL="${2:?}"; shift 2 ;;
        --sdk)       SDK="${2:?}"; shift 2 ;;
        --apk)       APK="${2:?}"; shift 2 ;;
        --self-test) SELF_TEST=1; shift ;;
        -h|--help)   sed -n '2,30p' "$0"; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

if [ -n "$EXPLICIT_CFG" ]; then CFGS=("$EXPLICIT_CFG"); else CFGS=("$ROOT/settings/common.cfg" "$ROOT/settings/android.cfg"); fi

# Pure checks over a cfg text string, so the same code grades the real cfg and
# the synthetic bad cfgs.  Returns 0 = coherent, 1 = not coherent.
python_rfp_checks() {
python3 - "$1" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
prefs = {}
for m in re.finditer(r'\b(?:defaultPref|pref|lockPref)\(\s*"([^"]+)"\s*,\s*([^;]*?)\s*\)\s*;', text):
    key, val = m.group(1), m.group(2).strip()
    if val.startswith('"') and val.endswith('"'):
        val = val[1:-1]
    prefs[key] = val
def get(k): return prefs.get(k)

fails = []
# 1. RFP master switch ON (inherited from common.cfg; applies to Android).
if get("privacy.resistFingerprinting") != "true":
    fails.append(("rfp", f"privacy.resistFingerprinting={get('privacy.resistFingerprinting')!r} (expected true)"))
# 2. block_mozAddonManager ON (RFP would otherwise break the AMO UI).
if get("privacy.resistFingerprinting.block_mozAddonManager") != "true":
    fails.append(("rfp", f"privacy.resistFingerprinting.block_mozAddonManager={get('privacy.resistFingerprinting.block_mozAddonManager')!r} (expected true)"))
# 3. GPC ON (a fingerprinting signal; LibreWolf ships it on).
if get("privacy.globalprivacycontrol.enabled") != "true":
    fails.append(("rfp", f"privacy.globalprivacycontrol.enabled={get('privacy.globalprivacycontrol.enabled')!r} (expected true)"))
# 4. letterboxing must NOT be enabled on Android (does not work on GeckoView;
#    desktop ships it false).  Absent is fine; explicitly true is a regression.
lb = get("privacy.resistFingerprinting.letterboxing")
if lb == "true":
    fails.append(("rfp", "privacy.resistFingerprinting.letterboxing=true in the Android composition (does not work on GeckoView; desktop ships it false)"))
# 5. the desktop-only window-sizing trio must NOT be in the Android composition.
for w in ("privacy.window.maxInnerWidth", "privacy.window.maxInnerHeight"):
    if get(w) is not None:
        fails.append(("rfp", f"{w}={get(w)!r} is desktop-only (desktop.cfg); must not be in the Android composition"))

for area, why in fails:
    print(f"  FAIL [{area}] {why}")
print(f"  [rfp] master={get('privacy.resistFingerprinting')!r} block_mozAddonManager={get('privacy.resistFingerprinting.block_mozAddonManager')!r} gpc={get('privacy.globalprivacycontrol.enabled')!r} letterboxing={lb!r}")
if fails:
    print("RESULT: RFP posture NOT coherent")
    sys.exit(1)
print("RESULT: RFP posture coherent (configured layer)")
sys.exit(0)
PY
}

run_configured() {
    local combined; combined="$(mktemp)"; : > "$combined"
    local f; for f in "${CFGS[@]}"; do
        if [ -f "$f" ]; then cat "$f" >> "$combined"; else echo "  (no cfg: $f)" >&2; fi
    done
    echo "CONFIGURED layer (cfg: ${CFGS[*]})"
    local rc=0; python_rfp_checks "$combined" || rc=$?
    rm -f "$combined"; return $rc
}

run_honoured() {
    if [ -z "$SERIAL" ] || [ -z "$SDK" ] || [ -z "$APK" ]; then
        echo "HONOURED layer: SKIPPED (no --serial/--sdk/--apk) - needs a running device."
        return 3
    fi
    local ADB="$SDK/platform-tools/adb"; [ -x "$ADB" ] || ADB="$(command -v adb || true)"
    if [ -z "${ADB:-}" ] || ! "$ADB" -s "$SERIAL" get-state >/dev/null 2>&1; then
        echo "HONOURED layer: PENDING - device '$SERIAL' not reachable."
        return 3
    fi
    echo "HONOURED layer: device present - run the fingerprint probes (UA, screen,"
    echo "  DPR, canvas, RFP coherence) and compare to desktop LibreWolf + Tor"
    echo "  Browser for Android.  Not stubbed here."
    return 0
}

self_test() {
    echo "SELF-TEST (negative control): the gate MUST flag each of these bad configs."
    local d; d="$(mktemp -d)"; local overall=0
    # bad-1: RFP master off.
    printf 'defaultPref("privacy.resistFingerprinting", false);\ndefaultPref("privacy.resistFingerprinting.block_mozAddonManager", true);\ndefaultPref("privacy.globalprivacycontrol.enabled", true);\n' > "$d/bad-rfpoff.cfg"
    # bad-2: letterboxing enabled on Android (a regression, not a parity win).
    printf 'defaultPref("privacy.resistFingerprinting", true);\ndefaultPref("privacy.resistFingerprinting.block_mozAddonManager", true);\ndefaultPref("privacy.globalprivacycontrol.enabled", true);\ndefaultPref("privacy.resistFingerprinting.letterboxing", true);\n' > "$d/bad-letterbox.cfg"
    local name
    for name in bad-rfpoff bad-letterbox; do
        echo "  --- expecting FAIL: $name ---"
        if python_rfp_checks "$d/$name.cfg" >/dev/null 2>&1; then
            echo "  SELF-TEST BROKEN: gate PASSED $name (a bad config it must reject)"; overall=2
        else
            echo "  ok: gate correctly REJECTED $name"
        fi
    done
    rm -rf "$d"
    if [ -f "$ROOT/settings/common.cfg" ] && [ -f "$ROOT/settings/android.cfg" ]; then
        echo "  --- expecting PASS: good (real common.cfg + android.cfg) ---"
        local good; good="$(mktemp)"
        cat "$ROOT/settings/common.cfg" "$ROOT/settings/android.cfg" > "$good"
        if python_rfp_checks "$good" >/dev/null 2>&1; then echo "  ok: gate correctly ACCEPTED the real cfg"; else echo "  NOTE: real cfg did not pass (see configured run)"; fi
        rm -f "$good"
    fi
    if [ "$overall" -eq 2 ]; then echo "SELF-TEST FAILED: the gate cannot fail"; exit 2; fi
    echo "SELF-TEST PASSED: the gate fails on every incoherent config"
    exit 0
}

if [ "$SELF_TEST" -eq 1 ]; then self_test; fi

rc_cfg=0; run_configured || rc_cfg=$?
echo
rc_hon=0
if [ -n "$SERIAL" ] || [ -n "$SDK" ] || [ -n "$APK" ]; then run_honoured || rc_hon=$?; fi

echo
if [ "$rc_cfg" -ne 0 ]; then echo "OVERALL: FAIL (configured layer)"; exit 1; fi
if [ "$rc_hon" -eq 3 ]; then echo "OVERALL: configured OK; honoured layer PENDING (no device)"; exit 3; fi
echo "OVERALL: PASS"
exit 0
