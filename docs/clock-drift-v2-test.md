# Experimental clock drift v2 / Festimix

**Status:** source implementation only, not compiled or tested on the user's HP or Tascam device. Do not merge into main.

The baseline `fix/playback-continuity-prototype` made pops much less audible but left sink starvation (6 episodes in 30 s) and capture hard slips (13 in 30 s). This v2 branch is an independent optional experiment on top of that prototype.

## What changed

- `--stable-playback` now applies a tighter **128-frame** EMA error deadband (instead of 1024) to the existing 100-ms slip governor. This aims to counter the sink filling deficit reported as sink_q_ema ~810 vs target 1536. **Caveat:** it still implements discrete single-frame repeats or drops at most 10 per second; those can produce their own high-frequency artifacts. This is a transitional test, not a final fractional playback resampler.
- New `--smooth-capture`: use a slowly adapted (<= ±500 ppm) fractional read phase with per-channel linear interpolation. It replaces the old drop/duplicate capture PCM mechanism when enabled; raw USB capture framing and feedback clocking are otherwise unchanged.
- Capture EMA subtraction converted to *floating point before subtraction* (prevents unsigned wrap). Capture target is raised to at least 1024 frames only in smooth mode, to match the observed 1024-frame PipeWire graph quantum. Increases capture latency.
- Both changes are opt-in. `--stable-playback` continues to enable fade-based output starvation recovery.
- No changes to USB packet scheduling, hardware clock registers, or the existing SPSC ring concurrency (still requiring a separate atomic safety audit).

## Build and test safely

First stop the driver in the **AUDIO** SSH terminal at a planned pause. Do not start a second Tascam process while the old one owns USB. Save the previously working executable and inspect Git status:

```bash
cd ~/projects/tascam_us1641_linux
git status --short
git fetch origin
git switch fix/clock-drift-v2-experimental
git pull --ff-only origin fix/clock-drift-v2-experimental
cp -a build/tascamd /tmp/tascamd-playback-reference
make
```

Test explicit opt-in flags (keep original USB cable and PipeWire quantum during this A/B):

```bash
./build/tascamd --preroll 256 --stable-playback --smooth-capture
```

Reconnect PipeWire from CONTROL shell after USB restart:

```bash
cd ~/projects/festimix-audio-bench
python3 linux/link_tascam.py --rack --apply
```

Third SSH diagnostic monitor:

```bash
cd ~/projects/tascam_us1641_linux
python3 tools/clock_pcm_watch.py --output /tmp/festimix-clock-v2.csv
```

Compare a few minutes of slap bass for highs, pops, timing/latency and `sink_underruns`, `sink_starvation_episodes`, `src_slip_drop`, `src_underruns`, `source_ring_overwrite`, plus actual `sink_q_ema` and `source_q_ema`. The `src_slip_drop` counter should remain unchanged in smooth mode (because skips are replaced by interpolation); **that alone does not prove the sound is better or the capture is error-free**. Inspect `src_r` or `source ratio` in `tascamd.stats` as fractional correction.

Rollback: stop the test daemon, then run `/tmp/tascamd-playback-reference --preroll 256 --stable-playback` if that is the saved working playback prototype. If absent, use the old binary backup from the previous testing session.

### Performance/quality caveats

Linear interpolation is an elementary fractional resampler. It attenuates upper-frequency content near Nyquist and is not the ideal final audio-quality SRC; replace with bandlimited windowed-sinc/polyphase when the basic clock control is proven. Neither new flag has been verified on real hardware. No change to Wi-Fi or Ethernet is made by this branch.
