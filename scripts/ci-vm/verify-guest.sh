#!/usr/bin/env bash
# Run INSIDE the guest, over SSH as ciadmin (or as root). No registration needed.
# Before invoking, the host must prove its canary is listening on TCP 8765 and
# reachable locally. The flag records that prerequisite; a guest cannot prove
# that an intentionally unreachable host service is alive.
set -euo pipefail
umask 077

die() { printf 'FAIL %s\n' "$*" >&2; exit 1; }
pass() { printf 'PASS %s\n' "$*"; }
[[ ${1:-} == --host-canary-confirmed && $# == 1 ]] ||
    die 'usage: verify-guest.sh --host-canary-confirmed (host must check TCP 8765 first)'
virt=$(systemd-detect-virt --vm) || die 'requires the KVM guest; never run on the host'
[[ $virt == kvm ]] || die "expected KVM, found $virt"
pass "virtualization=$virt"

as_root=()
if ((EUID != 0)); then
    [[ $(id -un) == ciadmin ]] || die 'run as ciadmin or root inside the guest'
    as_root=(sudo -n)
fi
"${as_root[@]}" true || die 'noninteractive guest administration unavailable'
runner_uid=$(id -u runner) || die 'runner account missing'
((runner_uid >= 1000)) || die 'runner is not an ordinary unprivileged account'
[[ $(getent passwd runner | cut -d: -f6) == /home/runner ]] || die 'unexpected runner home'
as_runner() {
    "${as_root[@]}" runuser -u runner -- env \
        XDG_RUNTIME_DIR="/run/user/$runner_uid" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$runner_uid/bus" \
        bash -c 'cd /home/runner && exec "$@"' bash "$@"
}

python3 - <<'PY'
import os
from pathlib import Path

def require(ok, detail):
    if not ok:
        raise SystemExit('FAIL ' + detail)

mem = {line.split(':')[0]: int(line.split()[1]) * 1024
       for line in Path('/proc/meminfo').read_text().splitlines()
       if line.split(':')[0] in {'MemTotal', 'SwapTotal'}}
cpus = os.cpu_count()
disk = os.statvfs('/home')
free = disk.f_bavail * disk.f_frsize
gib = 1024**3
require(cpus == 8, f'expected 8 CPUs, found {cpus}')
require(19*gib <= mem['MemTotal'] <= 20*gib,
        f'RAM outside the 20 GiB guest allocation: {mem["MemTotal"]} bytes')
require(free >= 150*gib, f'/home free space below 150 GiB: {free} bytes')
# A 16 GiB swap file reserves one page for its header.
require(mem['SwapTotal'] >= 16*gib-os.sysconf('SC_PAGE_SIZE'),
        f'usable swap below a 16 GiB swap file: {mem["SwapTotal"]} bytes')
print(f'PASS resources: CPUs={cpus} RAM={mem["MemTotal"]/gib:.2f}GiB '
      f'/home-free={free/gib:.2f}GiB swap-usable={mem["SwapTotal"]/gib:.5f}GiB')
PY
swap_file=/var/lib/redoubt-swap/swapfile
[[ $("${as_root[@]}" stat -c %s "$swap_file") == 17179869184 ]] || die 'swap file is not 16 GiB'
"${as_root[@]}" swapon --show=NAME --noheadings | grep -Fxq "$swap_file" || die '16 GiB swap file is inactive'
pass '16 GiB swap file active'

[[ $("${as_root[@]}" systemctl show "user-${runner_uid}.slice" -p MemoryMax --value) == 19327352832 ]] || die 'runner slice memory limit is not 18 GiB'
[[ $("${as_root[@]}" systemctl show "user-${runner_uid}.slice" -p MemorySwapMax --value) == 6442450944 ]] || die 'runner slice swap limit is not 6 GiB'
pass 'runner slice bounds all driver and rootless container scopes at 18 GiB RAM / 6 GiB swap'

if sudo_policy=$("${as_root[@]}" env LC_ALL=C sudo -l -U runner 2>&1); then
    policy_status=0
else
    policy_status=$?
fi
printf '%s\n' "$sudo_policy" | python3 -c '
import re, sys
text = sys.stdin.read()
status = int(sys.argv[1])
if status and "is not allowed to run sudo" not in text:
    raise SystemExit("FAIL could not inspect runner sudo policy: " + text)
rules = [line.strip() for line in text.splitlines() if re.match(r"^\s+\(", line)]
if any(not re.fullmatch(r"\([^)]*\)\s+!ALL", line) for line in rules):
    raise SystemExit("FAIL runner has a sudo grant: " + repr(rules))
if not rules and "is not allowed to run sudo" not in text:
    raise SystemExit("FAIL runner sudo policy was not recognizable")
print("PASS runner sudo policy denies every command")
' "$policy_status"

"${as_root[@]}" systemctl is-active --quiet redoubt-guest-firewall.service || die 'guest firewall inactive'
"${as_root[@]}" systemctl is-enabled --quiet redoubt-guest-firewall.service || die 'guest firewall not enabled'
nft_rules=$("${as_root[@]}" nft --json list table inet redoubt_guest) || die 'guest nft table unavailable'
printf '%s\n' "$nft_rules" | python3 -c '
import hashlib, ipaddress, json, sys
text = sys.stdin.read()
def require(ok, why):
    if not ok: raise SystemExit("FAIL nft policy: " + why)
objects = json.loads(text)["nftables"]
chains = [r["chain"] for r in objects if "chain" in r and r["chain"]["name"] == "output"]
require(len(chains) == 1, "output chain missing or ambiguous")
chain = chains[0]
require(chain.get("type") == "filter" and chain.get("hook") == "output" and
        chain.get("prio") == -10 and chain.get("policy") == "accept",
        "wrong hook, priority or policy")
rules = [r["rule"]["expr"] for r in objects
         if "rule" in r and r["rule"].get("chain") == "output"]
def matched(expressions, left, right):
    return any(e.get("match", {}).get("left") == left and
               e["match"].get("op") in {"==", "in"} and
               e["match"].get("right") == right for e in expressions)
private_ranges = set()
ipv6_rejected = False
for expressions in rules:
    # Accepts must remain confined to loopback, replies, or root-owned DHCP.
    # Inspect meaning rather than nft pretty-print spelling or total rule count.
    if any("accept" in e for e in expressions):
        loopback = matched(expressions, {"meta": {"key": "oifname"}}, "lo")
        replies = any(e.get("match", {}).get("left") == {"ct": {"key": "state"}} and
                      e["match"].get("op") in {"==", "in"} and
                      isinstance(e["match"].get("right"), list) and
                      set(e["match"]["right"]) <= {"established", "related"}
                      for e in expressions)
        dhcp = (matched(expressions, {"meta": {"key": "skuid"}}, 0) and
                matched(expressions, {"payload": {"protocol": "udp", "field": "sport"}}, 68) and
                matched(expressions, {"payload": {"protocol": "udp", "field": "dport"}}, 67))
        require(loopback or replies or dhcp, "unconfined accept rule")
    require(not any(set(e) & {"jump", "goto", "return", "queue"} for e in expressions),
            "uninspected output control flow")
    rejects = [e["reject"] for e in expressions if "reject" in e]
    matches = [e["match"] for e in expressions if "match" in e]
    if {"type": "icmp", "expr": "admin-prohibited"} in rejects:
        allowed_left = [{"ct": {"key": "state"}},
                        {"payload": {"protocol": "ip", "field": "daddr"}}]
        require(all(m.get("left") in allowed_left and m.get("op") in {"==", "in"}
                    for m in matches), "private rejection has uninspected restrictions")
        require(matched(expressions, {"ct": {"key": "state"}}, "new"),
                "private rejection does not cover new connections")
        for match in matches:
            if match.get("left") == allowed_left[1]:
                for entry in match.get("right", {}).get("set", []):
                    prefix = entry.get("prefix", {})
                    private_ranges.add(str(ipaddress.IPv4Network(
                        str(prefix["addr"]) + "/" + str(prefix["len"]))))
    if {"type": "icmpv6", "expr": "admin-prohibited"} in rejects:
        # nft omits a redundant nfproto match when icmpv6 already implies it.
        ipv6_rejected |= not matches or (len(matches) == 1 and
            matched(expressions, {"meta": {"key": "nfproto"}}, "ipv6"))
required = {"10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "100.64.0.0/10"}
require(required <= private_ranges, "missing private ranges: " + repr(required-private_ranges))
require(ipv6_rejected, "IPv6 administrative rejection missing")
print("PASS active/enabled nft output policy sha256=" + hashlib.sha256(text.encode()).hexdigest())
'
python3 - <<'PY'
from pathlib import Path
values = {p.parent.name: p.read_text().strip()
          for p in Path('/proc/sys/net/ipv6/conf').glob('*/disable_ipv6')}
if not {'all', 'default'} <= values.keys() or any(v != '1' for v in values.values()):
    raise SystemExit('FAIL IPv6 is not disabled on all interfaces: ' + repr(values))
print('PASS IPv6 disabled for all/default and every current interface')
PY

findmnt --json --output TARGET,SOURCE,FSTYPE | python3 -c '
import json, sys
def walk(rows):
    for row in rows:
        yield row
        yield from walk(row.get("children", []))
rows = list(walk(json.load(sys.stdin)["filesystems"]))
bad = [r for r in rows if r.get("fstype") in {"9p", "virtiofs"}]
if bad: raise SystemExit("FAIL host filesystem mounts present: " + repr(bad))
print("PASS no 9p or virtiofs mounts")
'
for absent in /home/mgysin /home/mgysin/redoubt-release.p12; do
    "${as_root[@]}" test ! -e "$absent" && "${as_root[@]}" test ! -L "$absent" ||
        die "host path exists in guest: $absent"
    pass "host path absent (existence check only): $absent"
done

podman_info=$(as_runner timeout 30 podman info --format json) || die 'runner Podman info failed'
printf '%s\n' "$podman_info" | python3 -c '
import json, sys
info = json.load(sys.stdin)
if info.get("host", {}).get("security", {}).get("rootless") is not True:
    raise SystemExit("FAIL Podman is not rootless")
print("PASS runner Podman rootless")
'
expected_image=c5b57d94cf9e0ed1de7061cee9e0dbfde19d5651e3e2f3824b0e1466116fd687
image_id=$(as_runner timeout 20 podman image inspect --format '{{.Id}}' librewolf-android-build) || die 'Android image missing'
[[ ${image_id#sha256:} == "$expected_image" ]] || die "Android image ID differs: $image_id"
pass "Android image=$expected_image"
as_runner timeout --kill-after=5 90 podman run --rm --pull=never "$expected_image" bash -ceu '
    for tool in gcc java curl; do command -v "$tool" >/dev/null; done
    clang_bin=$(command -v clang || true)
    if [[ -z $clang_bin && -n ${MOZBUILD_STATE_PATH:-} ]]; then
        clang_bin=$MOZBUILD_STATE_PATH/clang/bin/clang
    fi
    [[ -x $clang_bin ]] || { echo "FAIL image Clang unavailable" >&2; exit 1; }
    gcc --version | head -1
    "$clang_bin" --version | head -1
    version=$(java -version 2>&1)
    printf "%s\n" "$version" | head -1
    [[ $version =~ version\ \"17\. ]] || { echo "FAIL container Java is not 17" >&2; exit 1; }
    status=$(curl --fail --silent --show-error --connect-timeout 10 --max-time 25 \
        --output /dev/null --write-out "%{http_code}" https://api.github.com)
    [[ $status == 200 ]] || { echo "FAIL GitHub HTTPS status=$status" >&2; exit 1; }
    echo "PASS image compiler tools, Java 17 and GitHub HTTPS=200"
' || die 'Android container toolchain/HTTPS probe failed'

as_runner python3 - <<'PY'
import errno
import socket
import struct
import time

for host in ('10.0.0.135', '10.77.0.1'):
    start = time.monotonic()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        recverr = getattr(socket, 'IP_RECVERR', 11)
        connection.setsockopt(socket.IPPROTO_IP, recverr, 1)
        connection.settimeout(3)
        try:
            connection.connect((host, 8765))
            raise SystemExit(f'FAIL runner reached private canary {host}:8765')
        except OSError as error:
            elapsed = time.monotonic() - start
            icmp_admin = False
            # Linux maps ICMP type 3/code 13 (administratively prohibited) to
            # EHOSTUNREACH too. Distinguish it from an absent route using the
            # kernel error queue rather than declaring every unreachable host
            # evidence of a working firewall.
            connection.setblocking(False)
            try:
                _, ancillary, _, _ = connection.recvmsg(
                    4096, 4096, socket.MSG_ERRQUEUE | socket.MSG_DONTWAIT)
                for level, kind, data in ancillary:
                    if level == socket.IPPROTO_IP and kind == recverr and len(data) >= 16:
                        _, origin, icmp_type, code, _, _, _ = struct.unpack('=IBBBBII', data[:16])
                        icmp_admin |= (origin, icmp_type, code) == (2, 3, 13)
            except OSError:
                pass
            denied = error.errno in {errno.EACCES, errno.EPERM} or (
                error.errno == errno.EHOSTUNREACH and icmp_admin)
            if not denied or elapsed >= 2:
                raise SystemExit(f'FAIL canary {host}:8765 inconclusive: '
                                 f'errno={error.errno} icmp-admin={icmp_admin} elapsed={elapsed:.3f}s; '
                                 'refusal, timeout or missing route is not administrative denial')
            print(f'PASS runner private canary {host}:8765 administratively denied '
                  f'errno={error.errno} icmp-admin={icmp_admin} elapsed={elapsed:.3f}s '
                  '(host readiness confirmed)')
PY
pass 'guest acceptance complete; Actions registration not required by these checks'
