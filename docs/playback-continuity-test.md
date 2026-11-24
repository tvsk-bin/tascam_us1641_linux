# Playback continuity prototype: verification and rollback

**Status: experimental, GitHub source changes not yet compiled or hardware-tested.**

Scope: playback only. Created for Festimix native Linux / Tascam US-1641 and the observed case of many output-side underrun **samples** while PipeWire ERR remains stable. The previous CSV `sink_underruns` increments are per affected output sample in the code, **not discrete glitch events**.

## Changes, intentionally opt-in

Launch with `--stable-playback`. With the flag absent the legacy packet filling and configured preroll are retained.

1. At startup, sink playback watermark is clamped to **at least 1536 frames** when stable mode is enabled. The actual PipeWire graph was measured at 1024 frames / 48000 Hz. Sink startup requires target+512 frames (2048 frames minimum). This prevents the 256-frame output queue from starving during ordinary 1024-frame callback bursts. The *capture* watermark still obeys the requested `--preroll 256` value. The larger sink reserve increases output latency by approximately (1536-256)/48000 = **26.7 ms** compared to the low-preroll target; that is a cost and may be unacceptable for live monitoring. This is an evaluation, not a final latency target.
2. During a playback ring underrun, emit a **48-sample decay** from the last valid four-channel frame instead of switching instantaneously to all-zero frames. On the next available data, blend the recovered signal over 48 samples. This is a click-suppression mechanism, **not a cure for data starvation**. It may briefly color the sound, and is not bit-perfect while recovering.
3. Diagnostic `sink_starvation_episodes` and `sink_resume_episodes` counters distinguish a run of empty PCM samples from an entire audible event. Existing `sink_underruns` is a count of individual missing frames subject to the existing 240-frame streak handling.
4. USB packet counts, feedback parsing, hardware rate and capture/clock loop are deliberately unchanged. All callback-side diagnostic work is counter increments, no I/O.

## Safe test on HP server

Use the **AUDIO** SSH terminal, and only switch at a planned pause (it must briefly stop audio). Stop the currently running driver with Ctrl+C and **do not** start two USB daemons at once. If multiple branches or local edits exist, inspect `git status` before switching; never discard local work.

```bash
cd ~/projects/tascam_us1641_linux
git fetch origin
git switch fix/playback-continuity-prototype
git pull --ff-only origin fix/playback-continuity-prototype
cp -a build/tascamd /tmp/tascamd-original-before-playback-test
make
./build/tascamd --preroll 256 --stable-playback
```

Confirm startup says `Stable playback: output target 1536 frames, capture target 256 frames`. Reconnect PipeWire links in **CONTROL** SSH terminal (after driver restart) without restarting DSP:

```bash
cd ~/projects/festimix-audio-bench
python3 linux/link_tascam.py --rack --apply
```

In third SSH terminal:

```bash
cd ~/projects/tascam_us1641_linux
python3 tools/clock_pcm_watch.py --output /tmp/festimix-clock-stable.csv
```

Mark audible clicks with ENTER. Observe `sink_underruns`, `sink_starvation_episodes`, `sink_resume_episodes`, `sink_q`, `fb_missing`, `iso_packet_error`, and the separate `pw-top` `ERR`. Use the same playing material for the reference and new mode. The key success signal is fewer starvation episodes **and no audible clicks**, not merely that the recovery fades suppress a click despite continuous missing PCM frames.

## Rollback without Git operations

Stop the test driver with Ctrl+C in AUDIO terminal; launch the saved binary:

```bash
/tmp/tascamd-original-before-playback-test --preroll 256
```

Alternatively, the newly compiled binary launched **without** `--stable-playback` uses the legacy sink algorithm and watermark, with the new read-only diagnostic counters still available.

If source-level change is desired later, use separate tested commits. Do not merge this experimental branch into main until its sound and latency are measured on the real hardware.

## USB cable A/B diagnosis

A **good quality shielded USB 2.0 High-Speed A-to-B cable**, short (about 1–2 m), in good condition, directly connected to a computer USB port, is useful as a controlled A/B test. No benefit from an expensive/extra-thick 'audiophile' cable. Replace the cable only **with Tascam powered down or the stream stopped**, and keep the port, preroll and driver unchanged during the A/B. Look for changes in `iso_packet_error`, `bulk_transfer_error`, `fb_missing`, and audio artifacts. A sample buffer starvation caused by a 1024-frame PipeWire scheduling quantum may persist with any healthy cable.
