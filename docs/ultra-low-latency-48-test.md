# 48/48 @ 48 kHz: deliberately aggressive full-duplex experiment

**Status:** committed on separate branch; **not compiled on the HP**, USB hardware behavior and actual latency unverified. This is a disruptive experiment, not a production mixer configuration.

## Goal and limitations

Try 48-frame (~1 ms) capture and playback software targets; externally force PipeWire's graph quantum to 48 frames / 48 kHz; run three 1-ms USB OUT URBs and ~1-ms USB BULK IN requests.

**This does not guarantee 4 ms analog-to-analog roundtrip.** The USB host controller's queued OUT URBs, actual hardware FIFOs, PipeWire graph scheduling, DSP stream processing, and ADC/DAC conversion still contribute. And forcing the PipeWire quantum to 48 only works if the active graph and native DSP accept it. Verify with `pw-top`.

The ISO transfer change here is fixed for this *experimental branch*: even running without `--ultra-low-latency` will use 1-ms URBs and smaller capture bulk requests. Return to the saved previous binary for a true A/B.

## Changes

- `NUM_ISO_PACKETS` 40 -> 8 (one 1-ms OUT USB transfer)
- `NUM_ISO_TRANSFERS` 4 -> 3 (roughly three 1-ms OUT transfers outstanding; scheduling details depend on the host controller)
- USB Bulk IN `BULK_BUF_SIZE` 16384 -> 3072 bytes = 96 32-byte frames = ~48 audio samples per transfer.
- `--ultra-low-latency --sink-target 48 --source-target 48` enables 48-frame source request fallback, 24-frame sink startup margin instead of hardcoded 512, and a 16-frame sink slip deadband. Existing `--stable-playback` fade protection and `--smooth-capture` fractional interpolator are retained.
- Feedback USB IN URBs still collect five 1-ms tokens: this could prove a blocker for consistent sub-4-ms roundtrip and requires measured follow-up.

## Test from two SSH sessions

**At a break in audio, stop running tascamd with Ctrl+C in AUDIO SSH.** DSP and Node can keep running. Do not start two USB drivers.

AUDIO:

```bash
cd ~/projects/tascam_us1641_linux
git status --short
cp -a build/tascamd /tmp/tascamd-good-sound-before-ultra
git fetch origin
git switch experiment/ultra-low-latency-48
git pull --ff-only origin experiment/ultra-low-latency-48
make
./build/tascamd --help | grep -E 'ultra-low|sink-target|source-target'
```

CONTROL (or third SSH): temporarily enforce 48-frame PipeWire graph quantum. Observe if native DSP accepts and follows it:

```bash
pw-metadata -n settings 0 clock.force-quantum 48
pw-top
```

NOTE: `pw-top` is interactive; Ctrl+C only exits the monitor. Watch the real `QUANT` and `ERR` for the tascam and festimix streams. **If the DSP remains at 1024, this experiment cannot demonstrate 4ms.** Do not assume the forced setting succeeded.

AUDIO:

```bash
./build/tascamd --preroll 256 --stable-playback --smooth-capture --ultra-low-latency --sink-target 48 --source-target 48
```

CONTROL:

```bash
cd ~/projects/festimix-audio-bench
python3 linux/link_tascam.py --rack --apply
cat "${XDG_RUNTIME_DIR:-/tmp}/tascamd_diagnostic.stats"
```

Keep listening level low at startup; extreme settings may cause loud crackles/dropouts. Test brief bass fingerstyle and slap, and note latency and `pw-top` errors, `sink_starvation_episodes`, `src_underruns`, `bulk_transfer_error`, `iso_transfer_error`, `fb_missing`. Stop on persistent distortion.

To restore PipeWire's forced graph quantum to normal:

```bash
pw-metadata -n settings 0 clock.force-quantum 0
```

Restore the previous known-good binary in AUDIO (stop experimental driver first):

```bash
/tmp/tascamd-good-sound-before-ultra --preroll 256 --stable-playback --smooth-capture --sink-target 1024 --source-target 512
```

If no audio after switching back, relink using `python3 linux/link_tascam.py --rack --apply` in CONTROL. Keep Ethernet/Wi-Fi unchanged; this experiment only changes audio paths.

## Evaluation

The success criteria are a stable graph at quantum=48, correct duplex channels, no audible dropouts or repeated-packet artifacts, then a **measured** physical loopback impulse round-trip around 4 ms. If it fails, test a 64-frame quantum with matching targets as a diagnostic; do not silently claim the 4 ms target has been achieved.
