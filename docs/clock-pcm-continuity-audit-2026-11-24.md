# TASCAM US-1641 clock and PCM continuity audit — 2026-11-24

Scope: source file `src/tascamd.c` from the `main` branch (reviewed 2026-11-24). Objective is to explain intermittent vinyl-pop-like clicks that occur even at low amplitudes and sometimes without PipeWire ERR increments. The active Festimix Linux host has 14 analog mono inputs, master L/R, AUX1/2; the driver still exposes 16/4 physical ports. **Do not interpret an ERR=0 as proof of uninterrupted USB/PCM flow.**

## End-to-end capture: hardware → browser/mixer

1. Hardware ADC crystal and FPGA serialize **seven odd-numbered analog channels** in even 32-byte bitplane frames, and **seven even-numbered channels** in odd 32-byte frames. Two physical frames give one 14-channel sample time. 15/16 are digital framing, not part of the analog 14-channel demux.
2. EP 0x86 **bulk IN** uses four simultaneously pending 16 KiB transfers. `bulk_in_cb` calculates `num_frames = actual_length / 32` and advances `g_global_frame_idx` to assign even/odd parity. It does not preserve incomplete 32-byte USB fragments or recover phase after a dropped/errored transfer. Callback ordering across multiple in-flight requests is assumed rather than sequence-verified.
3. After each odd half-frame, `g_current_sample[16]` is copied to the SPSC `g_source_rb` queue. A full ring overwrites unread data by advancing the consumer `read_idx` from the producer thread: a data race and possible discontinuity.
4. `on_process_source` pulls variable PipeWire requested quanta. An initial pre-roll/discontinuity may reposition the read pointer; sustained queue drift triggers explicit sample drop/duplication at the first sample of a block.
5. The 16-channel PipeWire source sends only the first 14 active analog channel ports to Festimix input_1..input_14. On the dedicated rack the remaining two digital inputs should not be linked. Festimix copies each mono input to both legs of its stereo-input DSP strip, processes channel DSP and routes master/AUX.
6. Input capture from this driver is paced by its own source ring and PipeWire graph; **there is no working capture asynchronous resampler in this source** despite the README claim. The `s_source_ratio` variable is displayed but not applied to PCM.

## End-to-end playback: mixer → DAC

1. Festimix computes 48 kHz floating-point master L/R, AUX1, AUX2 and exposes four Tascam sink playback ports through PipeWire.
2. `on_process_sink` copies four-channel F32 frames into `g_sink_rb` until full; previously dropped frames were silent and uncounted.
3. USB OUT EP 0x02 sends 40 high-speed isochronous packets (5 ms) per transfer. Four buffers are initially queued (20 ms). Each callback prepares and submits the next transfer.
4. Hardware DAC feedback EP 0x81 reports a **1 ms sample-count token**. A FIFO carries these to the OUT generator. In every 5 ms ISO transfer, `prepare_iso_transfer_buffer` consumes five tokens; if absent, it sends nominal sample counts. There is no explicit timestamp/sequence tying a token to the precise outgoing 1 ms interval. Interleaving of feedback and ISO callbacks can cause backlog or default-token insertion that remains invisible to PipeWire.
5. PCM samples are consumed from the playback ring independently of USB transfer completion. `fill_audio_packet` may move the read pointer to pre-roll, inject silence on underrun, drop a sample or repeat one sample at its initial packet position to control queue drift. Any of these can produce clicks without a PipeWire ERR.
6. Float-to-signed-24 conversion saturates at full scale. Pure amplitude clipping is less likely given low-amplitude clicks, but NaN/Inf samples and discontinuities are not tracked.
7. Tascam DAC consumes isochronous packets; the physical DAC audio and analog output are **not observed by a PipeWire ERR counter**.

## Findings and priority

| Priority | Finding | Why it is suspect | Proof to collect / proposed fix |
|---|---|---|---|
| **P0** | `queued - n_frames/2` in capture queue EMA uses unsigned 32-bit subtraction. | When queued < half the PipeWire quantum, arithmetic wraps to ~4.29 billion. Float EMA gets corrupted, possibly producing repeated aggressive drop decisions; especially hazardous with preroll 256 and quantum 1024. | Log `source_q` and `source_q_ema`. For the later tested fix, cast to signed or float **before** subtracting and clamp valid queue depths. |
| **P0** | Both ring buffers use `volatile` read/write indices rather than atomics; capture overflow also changes the consumer's read pointer from producer. | Not C-level safe synchronization, risks torn/reordered/stale reads and consumer/producer collisions. | Replace with C11 atomics (release/acquire) and consumer-owned ring overrun policy; stress-test with ThreadSanitizer (not in RT live run). |
| **P0** | USB bulk capture demux assumes packet-aligned `actual_length` and uninterrupted parity across all completions. | A short transfer or errored completion can shift EVEN/ODD phase, corrupt multi-channel reconstructed audio. | Track `bulk_unaligned`, `bulk_transfer_error`, and capture frame parity. Handle byte carryover, frame recovery and a documented resync strategy. |
| **P1** | Source/payout drift correction intentionally duplicates/drops raw PCM samples, without zero-crossing search despite the comment. | A single frame drop/repeat can create a click even for low-level audio. | Track all `*_slip_drop/repeat` counters and align click timestamps. Replace with bounded fractional resampling / interpolation, tested independently. |
| **P1** | Sink pre-roll code repositions read pointer, inserting silence and restarting abruptly after underflow; ring drops were uncounted. | Creates hard discontinuities that PipeWire need not flag. | Track `sink_reprime`, underruns, ring drops, `sink_q`. Add controlled ramp-to-zero or seamless recovery after causes are resolved. |
| **P1** | EP 0x81 feedback FIFO has no timestamp and silently fills missing tokens with nominal 48. | A clock mismatch may accumulate then require correction; output and feedback callback scheduling is not guaranteed phase-matched. | Track `fb_missing/invalid/overflow`, feedback packet rate, USB status and queue trajectories; later design timestamped count accumulator. |
| **P1** | All four ISO transfer completions are re-submitted even after abnormal packet-level status, with no per-packet diagnostics previously. | Audible dropout may be confined to USB packet status despite successful outer transfer callback. | Track `iso_packet_error` and transfer errors. |
| **P2** | README claims 32.32 capture resampler and `±1 sample` DAC lock that source does not implement. | Incorrect assurance, complicates timing investigation. | Revise technical documentation after confirmed protocol measurement. |
| **P2** | Runtime states and USB feedback counters are `volatile` rather than atomic. | Undefined cross-thread data races and stale telemetry. | Convert to C11 atomics when fixing rings; keep measurements scoped to minimal events now. |
| **P2** | Existing `s_sink_target_buffer` may be 256 with fixed `+512` activation threshold while graph quantum is 1024. | Large queue oscillations/reprime events can be more likely with low preroll. | Compare measured sink queue over time before changing buffer or clock. |

## Diagnostic branch implementation (nonfunctional changes only)

Branch: `diagnostic/clock-pcm-continuity`. Does not change the deliberately chosen PCM slips, feedback clock decisions, buffer sizes, sound formatting, or USB endpoint behavior. Adds event counters (increments only, no I/O in realtime callbacks) and `tascamd_diagnostic.stats` once per second on the non-RT thread.

Recorded counters: sink/source queue size, filtered queue EMA, sink/source underruns and overruns, slip drop/repeat counts, repriming, feedback underflow/invalid/overflow, feedback outer transfer errors, ISO outer and per-packet errors, bulk transfer errors/non-32-byte lengths, ring overwrite/drop, feedback packet count, and capture pushed frames.

The watcher `tools/clock_pcm_watch.py` works **immediately on the existing running driver**, falling back to the existing `tascamd.stats` if instrumented driver is not running. It logs differences between samples, and ENTER adds a **CLICK** marker. With legacy driver, detailed new counters are unavailable until an explicit diagnostic driver build/restart; the watcher makes this visible.

Read-only watcher:
```bash
cd ~/projects/tascam_us1641_linux
git fetch origin diagnostic/clock-pcm-continuity
git show origin/diagnostic/clock-pcm-continuity:tools/clock_pcm_watch.py > /tmp/clock_pcm_watch.py
python3 /tmp/clock_pcm_watch.py --output /tmp/festimix-clock-diag.csv
```

This does not switch branches or restart/recompile the running driver.

**Later, deliberate maintenance window only**, with audio stopped and a known rollback copy of `./build/tascamd`:
```bash
cd ~/projects/tascam_us1641_linux
git switch diagnostic/clock-pcm-continuity
make
# Inspect build output and save existing binary before ANY driver restart.
```

Do NOT start another USB driver while the original one owns the hardware. The current hardware has not been compiled or tested on this branch; a successful GitHub commit is not a successful runtime verification.

## Decision matrix for next click capture

- `src_slip_drop/repeat` or `src_reprime` changes at CLICK => capture queue clock/pacing.
- `sink_slip_drop/repeat`, `sink_reprime`, `sink_underruns` or `sink_ring_drop` changes => playback queue discontinuity.
- `bulk_unaligned`, `bulk_transfer_error` or `source_ring_overwrite` changes => USB capture/driver framing.
- `fb_missing`, `fb_overflow`, `fb_transfer_error`, `iso_packet_error` changes => hardware feedback/output path.
- All counters stable but audible pop persists => sample-level PCM trace needed at **three boundaries** (USB capture decoded, PipeWire mixer input and driver playback), paired with verified physical playback monitoring; avoid attributing it to PipeWire just from ERR=0.
