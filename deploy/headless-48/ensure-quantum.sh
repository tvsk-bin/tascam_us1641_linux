#!/usr/bin/env bash
set -euo pipefail
# Wait for PipeWire metadata; never falsely report success.
for attempt in $(seq 1 50); do
  if pw-metadata -n settings 0 clock.force-quantum 48 >/dev/null 2>&1; then
    echo "[festimix] PipeWire force-quantum=48 applied"
    exit 0
  fi
  sleep 0.2
done
echo "[festimix] Could not set PipeWire quantum; refusing to start ultra-low-latency audio" >&2
exit 1
