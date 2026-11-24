#!/usr/bin/env bash
set -euo pipefail
for attempt in $(seq 1 100); do
  if (exec 3<>/dev/tcp/127.0.0.1/47640) 2>/dev/null; then
    echo "[festimix] Native DSP TCP ready"
    exit 0
  fi
  sleep 0.2
done
echo "[festimix] Native DSP control TCP did not open; retry service" >&2
exit 1
