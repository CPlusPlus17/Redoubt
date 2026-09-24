#!/usr/bin/env bash
# Native compilation in the 20 GiB guest; Fenix keeps its separate smaller limit.
set -euo pipefail
[[ $(systemd-detect-virt --vm) == kvm && $(id -un) == runner ]]
if [[ ${1:-} == run ]]; then
  shift
  exec podman run --memory=17g --memory-swap=23g --cpus=6 "$@"
fi
exec podman "$@"
