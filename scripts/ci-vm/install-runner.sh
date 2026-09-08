#!/usr/bin/env bash
# Run as root INSIDE the provisioned guest; archive must arrive separately.
set -euo pipefail
[[ $EUID -eq 0 && $(systemd-detect-virt) == kvm ]]
archive=${1:?Usage: install-runner.sh /path/to/actions-runner-linux-x64-2.337.0.tar.gz}
expected=70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613
actual=$(sha256sum "$archive")
[[ ${actual%% *} == "$expected" ]]
[[ ! -e /home/runner/actions-runner/.runner ]]
install -d -o runner -g runner -m 700 /home/runner/actions-runner
tar -xzf "$archive" -C /home/runner/actions-runner --no-same-owner
chown -R runner:runner /home/runner/actions-runner
cat > /etc/systemd/system/redoubt-actions-runner.service <<'UNIT'
[Unit]
Description=Redoubt GitHub Actions runner (inside QEMU)
After=network-online.target redoubt-guest-firewall.service
Wants=network-online.target
Requires=redoubt-guest-firewall.service
ConditionPathExists=/home/runner/actions-runner/.runner

[Service]
User=runner
Group=runner
WorkingDirectory=/home/runner/actions-runner
Environment=HOME=/home/runner
Environment=XDG_RUNTIME_DIR=/run/user/1001
ExecStart=/usr/bin/bash /home/runner/actions-runner/run.sh
Restart=always
RestartSec=10
KillSignal=SIGINT
TimeoutStopSec=5min

[Install]
WantedBy=multi-user.target
UNIT
# UID is assigned by cloud-init and must not be assumed on a rebuilt image.
sed -i "s@XDG_RUNTIME_DIR=/run/user/1001@XDG_RUNTIME_DIR=/run/user/$(id -u runner)@" \
  /etc/systemd/system/redoubt-actions-runner.service
systemctl daemon-reload
echo 'Runner installed. Register with a fresh repository token before enabling its service.'
