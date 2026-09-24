#!/usr/bin/env bash
# OCI-driver wrapper for long guest build jobs; no change to application inputs.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
if [[ ${1:-} == run ]]; then
  shift
  exec podman run --memory=14g --memory-swap=22g --cpus=6 "$@"
fi
exec podman "$@"
