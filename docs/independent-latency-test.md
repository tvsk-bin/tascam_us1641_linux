# Independent latency targets — staged A/B test

Status: source committed, **not built or measured on the HP**.

This branch extends the *good-sounding* `fix/clock-drift-v2-experimental`. No changes to its linear capture interpolation, playback short underflow fades, USB feedback, or drift controller; only two additional target overrides are introduced.

- `--sink-target N`: playback output buffer target, 256–8192 frames.
- `--source-target N`: input capture buffer target, 256–8192 frames.
- When unspecified, preserve previous v2 behavior (with `--stable-playback --smooth-capture --preroll 256`: sink 1536, source 1024).
- Targets are *nominal control values*, not end-to-end measured delay. Output queue EMA may be below target and both paths also have PipeWire quantum (1024 frames seen earlier), USB scheduling, DSP and any effects.
- At 48 kHz, each 256 frames represent **5.33 ms**. Reducing capture target 1024->512 saves a nominal 10.67 ms; playback 1536->1280 saves another 5.33 ms. Confirm with an actual roundtrip impulse/loopback measurement.

## Procedure, with safe reference retained

Schedule driver restart in AUDIO SSH terminal; stop the existing `tascamd` with Ctrl+C. The DSP and Node can remain running, but PipeWire ports may need relinking afterward.

```bash
cd ~/projects/tascam_us1641_linux
git status --short
cp -a build/tascamd /tmp/tascamd-good-sound-v2
git fetch origin
git switch feature/independent-latency-targets
git pull --ff-only origin feature/independent-latency-targets
make
./build/tascamd --help | grep -E 'sink-target|source-target'
```

First controlled listening test, **change capture target only**:

```bash
./build/tascamd --preroll 256 --stable-playback --smooth-capture --sink-target 1536 --source-target 512
```

After relinking via `python3 linux/link_tascam.py --rack --apply`, listen for at least 2 minutes, focusing on bass slap highs and clicking; note `src_underruns`, `source_ring_overwrite`, `src_r`, `sink_starvation_episodes`. If stable, optionally test a second run reducing sink target:

```bash
./build/tascamd --preroll 256 --stable-playback --smooth-capture --sink-target 1280 --source-target 512
```

Important: reducing sink depth can bring clicks back. Prior 1536 sink target had substantial residual output starvation; don't attempt aggressive 256 target without evidence. If the new mode misbehaves, **roll back immediately** by launching:

```bash
/tmp/tascamd-good-sound-v2 --preroll 256 --stable-playback --smooth-capture
```

If the baseline driver command has not changed and a new build is running, simply stop the daemon and restart with explicit old targets (`--sink-target 1536 --source-target 1024`).

Until latency is measured by recording a pulse sent to a physical output and returned via input, these are *latency budget targets*, not proven end-to-end measurements.
