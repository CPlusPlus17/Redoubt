#!/bin/bash
while true; do printf '%s %s\n' "$(date -u +%FT%TZ)" "$(awk '/MemAvailable/{print $2}' /proc/meminfo)"; sleep 10; done
