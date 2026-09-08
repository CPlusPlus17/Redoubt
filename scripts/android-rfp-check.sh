#!/usr/bin/env bash
# Check static Android cfg expectations without executing configuration code.
# This wrapper does not measure live network or fingerprinting behavior.
# Android packages autoconfig, but cfg text alone cannot prove its effective
# values after profile loading, overrides and Fenix Settings initialization.
# Live parity probes belong to LW-M7-11 and remain pending here, even with adb.
#
# Exit codes:
#   0  selected static cfg expectations pass, or all self-test controls pass
#   1  cfg expectations fail, a required file is missing, or syntax is unsupported
#   2  usage error or a self-test control does not produce its expected result
#   3  cfg passes and live verification was requested but is not implemented
#
# Usage:
#   android-rfp-check.sh                     # static checks; does not verify live parity
#   android-rfp-check.sh --cfg FILE          # check a supplied flat cfg
#   android-rfp-check.sh --serial D --sdk S --apk A   # live verification: PENDING, exit 3
#   android-rfp-check.sh --self-test         # positive, negative and selected-cfg controls

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERIAL=""; SDK=""; APK=""; SELF_TEST=0; EXPLICIT_CFG=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --cfg|--serial|--sdk|--apk)
            if [ "$#" -lt 2 ] || [ -z "$2" ]; then
                echo "$1 needs a value" >&2; exit 2
            fi
            case "$1" in
                --cfg) EXPLICIT_CFG="$2" ;;
                --serial) SERIAL="$2" ;;
                --sdk) SDK="$2" ;;
                --apk) APK="$2" ;;
            esac
            shift 2 ;;
        --self-test) SELF_TEST=1; shift ;;
        -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done
if [ -n "$EXPLICIT_CFG" ]; then
    CFGS=("$EXPLICIT_CFG")
else
    CFGS=("$ROOT/settings/common.cfg" "$ROOT/settings/android.cfg")
fi

python_cfg_checks() {
python3 - "$@" <<'PY'

import re
import sys
from pathlib import Path

# This is a deliberately limited, nonexecuting parser for the shipped flat cfg
# format. Unknown JavaScript fails closed instead of guessing its effects. The
# same parser is embedded in both standalone wrappers; black-box tests cover both.
TOKEN = re.compile(
    r'(?P<space>\s+)|(?P<line>//[^\n]*)|(?P<block>/\*[\s\S]*?\*/)'
    r'|(?P<string>"(?:\\[\s\S]|[^"\\])*"|\'(?:\\[\s\S]|[^\'\\])*\'|`(?:\\[\s\S]|[^`\\])*`)'
    r'|(?P<number>-?\d+)|(?P<name>[A-Za-z_$][\w$]*)|(?P<punct>[(),;])'
)

def decode_string(raw):
    value = raw[1:-1]
    if raw[0] == '`' and '${' in value:
        raise ValueError('template interpolation cannot be checked statically')
    if raw[0] != '`' and ('\n' in value or '\r' in value):
        raise ValueError('newline in quoted string')
    escapes = {'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t', 'v': '\v', '0': '\0'}
    out = []
    i = 0
    while i < len(value):
        char = value[i]
        i += 1
        if char != '\\':
            out.append(char)
            continue
        char = value[i]
        i += 1
        if char in ('x', 'u'):
            count = 2 if char == 'x' else 4
            digits = value[i:i + count]
            if len(digits) != count or not re.fullmatch('[0-9A-Fa-f]+', digits):
                raise ValueError('unsupported string escape')
            out.append(chr(int(digits, 16)))
            i += count
        elif char in '\r\n':
            raise ValueError('string line continuation is not supported')
        elif char.isdigit() and char != '0':
            raise ValueError('legacy octal string escape is not supported')
        else:
            out.append(escapes.get(char, char))
    return ''.join(out)

def parse_calls(path):
    source = Path(path).read_text(encoding='utf-8')
    tokens = []
    position = 0
    while position < len(source):
        match = TOKEN.match(source, position)
        if not match:
            line = source.count('\n', 0, position) + 1
            raise ValueError(f'{path}:{line}: unsupported or malformed cfg syntax')
        position = match.end()
        kind = match.lastgroup
        raw = match.group()
        if kind in ('space', 'line', 'block'):
            continue
        value = decode_string(raw) if kind == 'string' else int(raw) if kind == 'number' else raw
        tokens.append((kind, value))
    index = 0

    def take(kind, value=None):
        nonlocal index
        if index >= len(tokens):
            raise ValueError(f'{path}: incomplete cfg statement')
        token = tokens[index]
        index += 1
        if token[0] != kind or (value is not None and token[1] != value):
            raise ValueError(f'{path}: expected {value or kind}, got {token!r}')
        return token[1]

    calls = []
    while index < len(tokens):
        name = take('name')
        if name == 'null':  # Sacrificial first line of common.cfg.
            take('punct', ';')
            continue
        if name not in ('pref', 'defaultPref', 'lockPref', 'unlockPref', 'clearPref', 'setEnv'):
            raise ValueError(f'{path}: unsupported cfg operation {name!r}')
        take('punct', '(')
        key = take('string')
        value = None
        if name not in ('unlockPref', 'clearPref'):
            take('punct', ',')
            if index >= len(tokens):
                raise ValueError(f'{path}: missing preference value')
            kind, raw = tokens[index]
            if kind in ('string', 'number'):
                value = take(kind)
            elif kind == 'name' and raw in ('true', 'false'):
                value = take('name') == 'true'
            else:
                raise ValueError(f'{path}: preference value must be a literal')
        take('punct', ')')
        take('punct', ';')
        calls.append((name, key, value))
    return calls

# Model only cfg execution on an otherwise empty preference store. prefcalls.js
# writes pref() to the user branch, defaultPref() to defaults, and lockPref()
# unlocks, replaces the default, then locks it. A user write equal to its
# nonsticky default clears that user value (Preferences.cpp::SetUserValue).
# This does NOT model Gecko
# packaged defaults, profile values, overrides, or subsequent Fenix writes.
defaults, users, locked = {}, {}, set()
try:
    for path in sys.argv[1:]:
        for name, key, value in parse_calls(path):
            if name in ('pref', 'defaultPref', 'lockPref'):
                previous = defaults.get(key, users.get(key))
                if previous is not None and type(previous) is not type(value):
                    raise ValueError(f'{path}: conflicting preference types for {key!r}')
                if type(value) is int and not -(2 ** 31) <= value < 2 ** 31:
                    raise ValueError(f'{path}: preference integer outside signed 32-bit range')
            if name == 'pref':
                if key in defaults and value == defaults[key]:
                    users.pop(key, None)
                else:
                    users[key] = value
            elif name == 'defaultPref' and key not in locked:
                defaults[key] = value
            elif name == 'lockPref':
                defaults[key] = value
                locked.add(key)
            elif name == 'unlockPref':
                locked.discard(key)
            elif name == 'clearPref':
                users.pop(key, None)
            # setEnv is a recognized non-preference call; never execute it.
except (OSError, UnicodeError, ValueError) as error:
    print(f'FAIL [cfg input] {error}')
    sys.exit(1)

def get(key):
    return defaults.get(key) if key in locked else users.get(key, defaults.get(key))

fails = []

def expect(key, expected, area):
    actual = get(key)
    if type(actual) is not type(expected) or actual != expected:
        fails.append((area, f'{key}={actual!r} (expected {expected!r})'))

expect('privacy.resistFingerprinting', True, 'rfp')
expect('privacy.resistFingerprinting.block_mozAddonManager', True, 'rfp')
expect('privacy.globalprivacycontrol.enabled', True, 'gpc')
letterboxing = get('privacy.resistFingerprinting.letterboxing')
if letterboxing is not None and letterboxing is not False:
    fails.append(('rfp', f'letterboxing={letterboxing!r} changes the expected disabled default'))
for key in ('privacy.window.maxInnerWidth', 'privacy.window.maxInnerHeight'):
    if get(key) is not None:
        fails.append(('rfp', f'{key} is a desktop window-sizing preference in the Android cfg'))
print(f"  [rfp] configured master={get('privacy.resistFingerprinting')!r}; letterboxing={letterboxing!r}")
print('  UNMEASURED: effective RFP, UA, language, timezone, screen, DPR and canvas behavior.')
print('  UNMEASURED: fingerprint coherence across devices and optional letterboxing support.')

for area, why in fails:
    print(f'  FAIL [{area}] {why}')
if fails:
    print('RESULT: configured expectations FAIL')
    sys.exit(1)
print('RESULT: configured expectations PASS (static cfg only; live behavior unmeasured)')
PY
}

write_good_cfg() {
cat <<'CFG'
lockPref("privacy.resistFingerprinting", true);
defaultPref("privacy.resistFingerprinting.block_mozAddonManager", true);
defaultPref("privacy.globalprivacycontrol.enabled", true);
CFG
}

write_bad_cfgs() {
    write_good_cfg > "$1/bad-rfp-off.cfg"
    cat <<'CFG' >> "$1/bad-rfp-off.cfg"
lockPref("privacy.resistFingerprinting", false);
CFG
    write_good_cfg > "$1/bad-letterboxing.cfg"
    cat <<'CFG' >> "$1/bad-letterboxing.cfg"
defaultPref("privacy.resistFingerprinting.letterboxing", true);
CFG
    write_good_cfg > "$1/bad-window-sizing.cfg"
    cat <<'CFG' >> "$1/bad-window-sizing.cfg"
defaultPref("privacy.window.maxInnerWidth", 1000);
CFG
}

run_configured() {
    echo "CONFIGURED layer (cfg: ${CFGS[*]})"
    echo "Scope: static cfg execution on empty branches; effective app settings and live behavior are UNMEASURED."
    python_cfg_checks "${CFGS[@]}"
}

run_honoured() {
    if [ -z "$SERIAL" ] || [ -z "$SDK" ] || [ -z "$APK" ]; then
        echo "HONOURED layer: PENDING — complete --serial/--sdk/--apk inputs and live probes are required."
        return 3
    fi
    if [ ! -f "$APK" ]; then
        echo "HONOURED layer: PENDING — APK does not exist: $APK"
        return 3
    fi
    local adb_path="$SDK/platform-tools/adb"
    if [ ! -x "$adb_path" ] || ! "$adb_path" -s "$SERIAL" get-state >/dev/null 2>&1; then
        echo "HONOURED layer: PENDING — device '$SERIAL' is not reachable using the supplied SDK."
        return 3
    fi
    echo "HONOURED layer: PENDING — adb is connected, but this wrapper implements no live behavior probes."
    echo "No candidate was installed, no behavior was measured, and no honoured result exists (LW-M7-11)."
    return 3
}

self_test() {
    echo "SELF-TEST: enforce both acceptance and rejection controls."
    local scratch
    scratch="$(mktemp -d)" || exit 2
    trap 'rm -rf -- "$scratch"' EXIT
    write_good_cfg > "$scratch/good.cfg"
    local overall=0 actual name
    actual=0; python_cfg_checks "$scratch/good.cfg" || actual=$?
    if [ "$actual" -ne 0 ]; then
        echo "SELF-TEST BROKEN: positive control rejected (exit $actual)"
        overall=2
    else
        echo "  ok: positive control accepted"
    fi
    # The selected cfg is also mandatory: a broken/missing repository cfg cannot
    # be excused with a NOTE while the synthetic controls make the gate green.
    actual=0; run_configured || actual=$?
    if [ "$actual" -ne 0 ]; then
        echo "SELF-TEST BROKEN: selected cfg rejected (exit $actual)"
        overall=2
    else
        echo "  ok: selected cfg accepted"
    fi
    write_bad_cfgs "$scratch"
    for name in "$scratch"/bad-*.cfg; do
        actual=0; python_cfg_checks "$name" > "$scratch/control.log" 2>&1 || actual=$?
        if [ "$actual" -ne 1 ]; then
            echo "SELF-TEST BROKEN: ${name##*/} returned $actual (expected configured failure 1)"
            cat "$scratch/control.log"
            overall=2
        else
            echo "  ok: ${name##*/} rejected"
        fi
    done
    if [ "$overall" -ne 0 ]; then
        echo "SELF-TEST FAILED: at least one control produced the wrong result"
        exit 2
    fi
    echo "SELF-TEST PASSED: positive, negative and selected-cfg controls behaved as expected"
    exit 0
}

if [ "$SELF_TEST" -eq 1 ]; then self_test; fi
rc_cfg=0; run_configured || rc_cfg=$?
if [ "$rc_cfg" -ne 0 ]; then
    echo "OVERALL: FAIL (configured layer; live behavior unmeasured)"
    exit 1
fi
if [ -n "$SERIAL" ] || [ -n "$SDK" ] || [ -n "$APK" ]; then
    run_honoured
    echo "OVERALL: configured expectations PASS; honoured layer PENDING"
    exit 3
fi
echo "OVERALL: CONFIGURED ONLY — static expectations PASS; live behavior UNMEASURED"
exit 0
