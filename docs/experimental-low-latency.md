# Experimental low-latency Tascam US-1641 mode

**Not validated on physical hardware yet.** Use only for bench tests, never for a live show.

This branch keeps the original 256+ frame behavior as the default. The optional
`--experimental-low-latency` flag permits 128 or 64 pre-roll frames. In these
two modes only, the playback startup/recovery headroom changes from 512 to 128
frames. The capture startup logic, USB bulk transfer size (16384 bytes),
USB isochronous scheduling, clock drift thresholds, and underrun behavior are
otherwise unchanged. The number in `--preroll` is a target ring-buffer depth,
**not a measured end-to-end latency**.

## On the HP

From the existing local fork:

```bash
cd ~/projects/tascam_us1641_linux
git status --short
git fetch origin
git switch experimental/low-latency
git pull --ff-only origin experimental/low-latency
make
./build/tascamd --help
```

If `git status --short` shows changes, preserve them before switching branches.
Do **not** run `make install` or replace the original stable binary or service.
Make sure only one tascamd instance owns the USB device. Stop the running
daemon with Ctrl+C before starting another.

**Baseline:** first test the newly built binary against the known 256-frame
setting and compare to the original one:

```bash
./build/tascamd --preroll 256 --debug-log
```

Next, after stopping it, test 128:

```bash
./build/tascamd --preroll 128 --experimental-low-latency --debug-log
```

Only if that is clean, test 64:

```bash
./build/tascamd --preroll 64 --experimental-low-latency --debug-log
```

For each run keep the PipeWire sample rate at 48000, and use the same quantum,
routing and signal. Listen for distortion, intermittent crackles, channel
swaps, clock slips and any growing audible latency. Collect statistics printed
or written by the daemon, particularly `sink_q`, `src_q`, `u_runs`,
`o_runs`, `src_u`, `src_o`, `locked`, `hw_err` and `xfers`.
Look for increasing counters *during continuous audio*, not merely at startup.

The current experimental setting is intentionally conservative regarding
USB packet scheduling. At pre-roll 64/128, unchanged +-1024-frame drift
deadbands may allow substantially varying queue depth. A stable playback
without crackles is not proof of low latency: measure round-trip separately.

**Revert quickly:**

```bash
# Stop the experimental tascamd first (Ctrl+C).
cd ~/projects/tascam_us1641_linux
git switch main
make
./build/tascamd --preroll 256
```

If the service starts automatically, disable/stop it before manual testing
and restore the original service state afterwards. Do not start it with
`sudo` against a different user PipeWire session.

## Changes to review

- CLI and config allow 64..8192 internally but refuse values under 256 unless
  the dedicated experimental flag is present.
- Playback startup headroom uses 128 rather than 512 only for experimental
  64/128-frame tests. Both startup and emergency recentering use the same
  headroom variable.
- No changes to USB transactions or the `tascamd` service.

## Original work

Fork of Aerankas/tascam_us1641_linux, released under MIT license.
Keep the original LICENSE and copyright notices.
