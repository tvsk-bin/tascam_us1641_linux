# One-variable playback sample-slip A/B — preserve usable 48/48 baseline

**Baseline:** `stable/usable-48x48-2026-11-24` at commit `5a5729c3cf8afad5a170da441eda4e0b4b4d14f8`. This GitHub branch is a reference snapshot by convention, not branch-protected or proof the running binary is byte-for-byte identical. Preserve the **actual** host executable separately.

The first experiment disables the existing periodic playback sample drop/repeat with `--playback-no-slip` while retaining all other 48-frame and USB code. **This is intentionally diagnostic, not a final fix.** The separate USB and PipeWire clocks then drift uncorrected, which can worsen output underruns; test only for ~30-60 seconds and record the counter deltas. The output underrun fade is unchanged. The flag is optional and off by default.

## First: freeze actual working HP binary, while it is running

On CONTROL or third SSH (not AUDIO), with driver still running:

```bash
cd ~/projects/tascam_us1641_linux
mkdir -p ~/festimix-known-good/2026-11-24-48x48
cp -a build/tascamd ~/festimix-known-good/2026-11-24-48x48/tascamd
sha256sum build/tascamd | tee ~/festimix-known-good/2026-11-24-48x48/sha256.txt
git rev-parse HEAD | tee ~/festimix-known-good/2026-11-24-48x48/git-commit.txt
pw-metadata -n settings 0 clock.force-quantum
```

Record working invocation separately; do not include secrets. Preserve `pw-top` and startup notes if desired. **Only after backing up**, stop active driver in AUDIO at controlled break.

## Build experimental branch without overwriting reference binary

```bash
cd ~/projects/tascam_us1641_linux
git fetch origin
git switch experiment/playback-slip-isolation
git pull --ff-only origin experiment/playback-slip-isolation
make
```

Keep PipeWire quantum forced to 48; run same command as baseline but add `--playback-no-slip`:

```bash
./build/tascamd --preroll 256 --stable-playback --smooth-capture --ultra-low-latency --sink-target 48 --source-target 48 --playback-no-slip
```

Relink from CONTROL with `python3 linux/link_tascam.py --rack --apply`; compare with 48-frame baseline for only 30–60 seconds. In diagnostic stats, `sink_slip_drop` and `sink_slip_repeat` should remain flat; watch `sink_starvation_episodes`, `sink_underruns`, `sink_q_ema`, `src_underruns`, and audibility. **If continuous distortion or rapid starvation occurs, stop immediately.** No-slip is not a clock-drift solution.

## Full, prompt rollback to known-good executable

Stop experiment in AUDIO via Ctrl+C, then:

```bash
pw-metadata -n settings 0 clock.force-quantum 48
~/festimix-known-good/2026-11-24-48x48/tascamd --preroll 256 --stable-playback --smooth-capture --ultra-low-latency --sink-target 48 --source-target 48
```

Reconnect PipeWire ports as needed. To restore the source checkout, `git switch stable/usable-48x48-2026-11-24`, **without running make over the backup binary**.

## Caveat

Measured analog roundtrip latency remains unknown. Preserve the user's qualitative finding: latency playable, occasional crackles and a rough attack, 48-frame PipeWire QUANT, zero driver USB transfer errors but rising playback underrun and sample slip counters.
