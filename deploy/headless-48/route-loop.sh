#!/usr/bin/env bash
set -u
cd "$HOME/projects/festimix-audio-bench" || exit 1
# PipeWire links are ephemeral. Keep checking/reconnecting after service restarts.
while true; do
  if ! python3 linux/link_tascam.py --rack --apply >/dev/null; then
    echo "[festimix] Links not ready; retrying in 5s" >&2
  fi
  sleep 5
done
