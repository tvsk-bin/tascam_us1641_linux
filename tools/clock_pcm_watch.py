#!/usr/bin/env python3
"""Non-invasive Tascam USB/PipeWire clock watcher: run from a third SSH session.

No USB control, no service restart, no realtime callback changes. ENTER marks a click.
For deeper counters the instrumented diagnostic branch must be built and restarted
*only during an agreed maintenance/test window*.
"""
import argparse
import csv
import datetime as dt
import os
import pathlib
import select
import sys
import time

METRICS = (
    "sink_q", "source_q", "sink_target", "source_target", "sink_q_ema", "source_q_ema",
    "sink_underruns", "sink_overruns", "src_underruns", "src_overruns",
    "sink_slip_drop", "sink_slip_repeat", "src_slip_drop", "src_slip_repeat",
    "sink_reprime", "src_reprime", "fb_missing", "fb_invalid", "fb_overflow",
    "fb_transfer_error", "iso_transfer_error", "iso_packet_error",
    "bulk_transfer_error", "bulk_unaligned", "source_ring_overwrite",
    "sink_ring_drop", "source_unsigned_underflow", "sink_starvation_episodes",
    "sink_resume_episodes", "fb_packets", "source_frames"
)
COUNTERS = set(METRICS) - {"sink_q", "source_q", "sink_target", "source_target", "sink_q_ema", "source_q_ema"}

def runtime_path(filename):
    return pathlib.Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp")) / filename

def fallback_path(filename):
    return pathlib.Path(f"/tmp/{filename}-{os.getuid()}")

def read_snapshot():
    for p in (runtime_path("tascamd_diagnostic.stats"),
              fallback_path("tascamd_diagnostic.stats"),
              runtime_path("tascamd.stats"),
              fallback_path("tascamd.stats")):
        try:
            raw = p.read_text(errors="replace")
        except (OSError, UnicodeError):
            continue
        out = {}
        for segment in raw.replace("|", " ").split():
            if "=" not in segment:
                continue
            key, val = segment.split("=", 1)
            try:
                out[key] = float(val)
            except ValueError:
                pass
        if "u_runs" in out:
            out["sink_underruns"] = out["u_runs"]
        if "o_runs" in out:
            out["sink_overruns"] = out["o_runs"]
        if "src_u" in out:
            out["src_underruns"] = out["src_u"]
        if "src_o" in out:
            out["src_overruns"] = out["src_o"]
        if "src_q" in out and "source_q" not in out:
            out["source_q"] = out["src_q"]
        return p, out
    return None, {}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--output", default="/tmp/festimix-clock-diag.csv")
    args = parser.parse_args()
    if args.interval < 0.2:
        parser.error("interval must be >= 0.2s")
    out_file = pathlib.Path(args.output)
    previous = {}
    print("Watching Tascam. Press ENTER exactly when a click is heard. Ctrl+C exits.")
    print(f"CSV log: {out_file}", flush=True)
    with out_file.open("w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["local_time", "marker", "snapshot_file"] + list(METRICS) +
                        ["delta_" + key for key in METRICS if key in COUNTERS])
        try:
            while True:
                path, now = read_snapshot()
                marker = ""
                if select.select([sys.stdin], [], [], 0)[0]:
                    marker = "CLICK"
                    sys.stdin.readline()
                timestamp = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="milliseconds")
                deltas = {k: int(now[k] - previous[k]) for k in COUNTERS
                          if k in previous and k in now}
                writer.writerow([timestamp, marker, str(path) if path else "MISSING"] +
                    [now.get(k, "") for k in METRICS] +
                    [deltas.get(k, "") for k in METRICS if k in COUNTERS])
                out.flush()
                changed = {k: v for k, v in sorted(deltas.items()) if v}
                if not path:
                    print(f"{timestamp} NO STATS (is tascamd running?)", flush=True)
                else:
                    print(f"{timestamp} sink={now.get('sink_q','?')} source={now.get('source_q','?')} "+
                          f"changes={changed or '-'} {marker}", flush=True)
                previous = now
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print(f"Stopped. Saved {out_file}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
