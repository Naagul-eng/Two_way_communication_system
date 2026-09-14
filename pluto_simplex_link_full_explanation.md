# CDP — PlutoSDR Simplex Digital Communication Link (BPSK)

A two-node, one-direction (simplex) wireless data link built in GNU Radio Companion (GRC), using two PlutoSDR (AD9363) units. One flowgraph transmits a text message as BPSK over 2.4 GHz; the other receives it, synchronizes, equalizes, demodulates, checks for errors, and reassembles/prints the original message.

**Files:**
- `packetised_transmitter_bpsk.grc` — TX flowgraph (title: `CDP`)
- `packetised_receiver_bpsk.grc` — RX flowgraph (title: `CDP`)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Requirements](#requirements)
3. [Signal Chain Diagram](#signal-chain-diagram)
4. [Transmitter (TX) — Block by Block](#transmitter-tx--block-by-block)
5. [Receiver (RX) — Block by Block](#receiver-rx--block-by-block)
6. [Packet / Frame Structure](#packet--frame-structure)
7. [Parameter Reference Table](#parameter-reference-table)
8. [Transmission Rate Calculations](#transmission-rate-calculations)
9. [How to Run](#how-to-run)
10. [Design Rationale](#design-rationale)
11. [Known Limitations / Future Work](#known-limitations--future-work)

---

## System Overview

This project demonstrates a complete practical digital communications chain over real RF hardware:

```
Text message → Framing → CRC → Physical-layer header/sync word → BPSK modulation
   → PlutoSDR TX → [ 2.4 GHz over the air ] → PlutoSDR RX
   → AGC → Timing recovery → Blind equalization → Carrier recovery
   → Demodulation → Frame detection → CRC check → De-framing/reassembly → Printed text
```

It is **simplex**: one Pluto is permanently the transmitter, the other permanently the receiver. There is no feedback/acknowledgment path, so the receiver cannot request retransmission of anything it misses — reliability depends entirely on getting each packet right the first time (good SNR, correct synchronization, adequate error tolerance).

---

## Requirements

- GNU Radio 3.10.x (developed/tested on GRC `3.10.9.2`)
- `gr-iio` (PlutoSDR / IIO support)
- Two ADALM-Pluto (PlutoSDR) units, reachable on the network:
  - RX unit: `ip:192.168.1.10`
  - TX unit: `ip:192.168.1.11`
- Python 3 (GRC-generated flowgraphs run as `{python} -u {filename}`)

---

## Signal Chain Diagram

```
TRANSMITTER (packetised_transmitter_bpsk.grc)
──────────────────────────────────────────────
tx_message (GUI text) 
   │
   ▼
[Message Strobe] (fires every 1000 ms)
   │
   ▼
[Packet Builder] (epy_block_0)  ── adds SRC/DST/TYPE/SEQ/TOTAL/LEN header, splits into ≤200-byte segments
   │
   ▼
[CRC32 Append] (digital_crc_append_0)
   │
   ▼
[Protocol Formatter Async] ── splits into "header" (sync word) and "payload" streams
   │                 │
   ▼                 ▼
[PDU→Tagged Stream] [PDU→Tagged Stream]
   │                 │
   └──────┬──────────┘
          ▼
   [Tagged Stream Mux] ── recombines header + payload into one burst
          ▼
   [Tagged Stream → PDU]
          ▼
   [PDU Prepend Dummy Bytes] (epy_block_3) ── adds 1500-byte warm-up preamble
          ▼
   [PDU → Tagged Stream]
          ▼
   [BPSK Constellation Modulator] ── differential encoding, RRC pulse shaping
          ▼
   [Multiply Const (0.8)] ── amplitude scaling
          ▼
   [PlutoSDR Sink] ── transmits at 2.4 GHz, 2 MHz analog BW, 10 dB attenuation
          │
          ═══════════ OVER THE AIR ═══════════
          │
          ▼
RECEIVER (packetised_receiver_bpsk.grc)
──────────────────────────────────────────────
   [PlutoSDR Source] ── receives at 2.4 GHz, 2 MHz analog BW, AGC gain mode
          ▼
   [AGC] ── normalizes amplitude
          ▼
   [Symbol Sync] (Gardner TED + PFB matched filter) ── timing recovery, 4→1 samples/symbol
          ▼
   [Linear Equalizer] (CMA, 15 taps) ── blind multipath/ISI correction
          ▼  (also feeds "After linear equilizer" constellation sink)
   [Costas Loop] (order 2) ── carrier phase/frequency recovery
          ▼  (also feeds "After syncronization" constellation sink)
   [Constellation Decoder] ── symbols → bits
          ▼
   [Differential Decoder] ── resolves 180° phase ambiguity
          ▼
   [Map (bb)] ── bit remap (identity in this design)
          ▼
   [Unpack k Bits] ── byte stream → 1-bit-per-byte stream
          ▼
   [Correlate Access Code] ── finds the 68-bit sync word, tags packet start (error tolerance: 4 bits)
          ▼
   [Repack Bits] ── 1-bit-per-byte → proper 8-bit bytes (MSB first)
          ▼
   [Tagged Stream → PDU] ── one message per detected packet
          ▼
   [CRC32 Check] ── discards corrupted packets (only "ok" output wired)
          ▼
   [Packet Parser] (epy_block_1) ── strips header, filters by address, reassembles segments
          ▼                    ▼
   [Message Debug]      [Plain Text Printer] (epy_block_0) ── decodes UTF-8, prints "SUCCESS! RECEIVED MESSAGE: ..."
```

---

## Transmitter (TX) — Block by Block

### Variables

| Variable | Value | Purpose |
|---|---|---|
| `samp_rate` | `2400000` | Baseband sample rate fed to the Pluto (2.4 Msps) |
| `sps` | `4` | Samples per symbol |
| `freq` | `2.4e9` | Carrier frequency variable (2.4 GHz) |
| `excess_bw` | `0.35` | RRC pulse-shaping roll-off factor |
| `nfilts` | `32` | Number of polyphase filter arms for the RRC filter |
| `rrc_taps` | `firdes.root_raised_cosine(...)` | Generated RRC filter tap coefficients |
| `phase_bw` | `62.8e-3` | Loop bandwidth (shared reference; used on RX side for Costas/Symbol Sync) |
| `damp_fac` | `0.707` | Damping factor for tracking loops (RX side) |
| `max_dev` / `max_dev_0` | `0.05` | Max timing deviation allowed (RX side; `_0` is an unused duplicate) |
| `access_key` | 68-bit binary string | The fixed sync-word bit pattern marking the start of every packet |
| `hdr_format` | `digital.header_format_default(access_key, 0)` | Defines the physical-layer header format embedding the access code |
| `taps` | `[1.0, 0.7, 0.4, 0.15]` | Leftover simulated multipath channel taps — **no longer connected to anything** now that the channel model block has been removed from the live path |
| `noise_volt` | `0.3` | Leftover simulated noise level — unused now |
| `freq_offset` | `0.01` | Leftover simulated frequency offset — unused now |
| `time_offset` | `1.002` | Leftover simulated timing offset — unused now |
| `tx_message` | GUI text entry, default `"Hello University of Moratuwa"` | The message being transmitted; editable live in the GUI |
| `my_addr` | `'B1'` (string) | Defined but **not wired to anything** — dead variable (actual addressing is hardcoded as integers inside the embedded Python blocks) |
| `variable_qtgui_entry_0` | GUI int entry, default `0` | Defined but **not wired to anything** — unused |

### Blocks (signal path order)

1. **Message Strobe (`blocks_message_strobe_0`)** — Fires a new message containing `tx_message` (UTF-8 encoded) every `period = 1000` ms. This is what starts a new transmission cycle.

2. **Packet Builder (`epy_block_0`, embedded Python)** — Custom block that:
   - Splits the message into segments of at most `MAX_PAYLOAD = 200` bytes each.
   - Prepends a 7-byte header to each segment: `SRC(1B) DST(1B) TYPE(1B) SEQ(1B) TOTAL(1B) LEN(2B)`.
   - Hardcoded here: `src_addr = 1`, `dst_addr = 3`, `msg_type = 1` (TEXT).
   - Emits one PDU per segment.

3. **CRC32 Append (`digital_crc_append_0`)** — Appends a standard CRC-32 (`poly 0x4C11DB7`, `init 0xFFFFFFFF`, `final XOR 0xFFFFFFFF`, reflected in/out) to each packet, letting the receiver detect (not correct) bit errors.

4. **Protocol Formatter Async (`digital_protocol_formatter_async_0`)** — Uses `hdr_format` to generate the physical-layer sync-word/header, splitting the burst into a `header` output (access code + length info) and a `payload` output (the CRC'd data).

5. **PDU → Tagged Stream ×2 (`pdu_pdu_to_tagged_stream_0`, `_1`)** — Converts the header PDU and payload PDU into tagged byte streams (tagged `packet_len`) so they can be recombined sample-by-sample.

6. **Tagged Stream Mux (`blocks_tagged_stream_mux_0`)** — Concatenates the header stream (input 0) and payload stream (input 1) into one combined burst: `[sync word/header][payload+CRC]`.

7. **Tagged Stream → PDU (`pdu_tagged_stream_to_pdu_0`)** — Converts the muxed stream back into a single PDU representing one full burst.

8. **PDU Prepend Dummy Bytes (`epy_block_3`, embedded Python)** — Prepends `num_dummy_bytes = 1500` random bytes to the front of the burst, giving the receiver's AGC, symbol sync, and Costas loop something to lock onto before the real header/payload arrives. *(This is still at the original 1500-byte size — see [Known Limitations](#known-limitations--future-work) for the recommended reduction.)*

9. **PDU → Tagged Stream (`pdu_pdu_to_tagged_stream_2`)** — Converts the dummy-prepended PDU into a tagged byte stream for the modulator.

10. **BPSK Constellation Modulator (`digital_constellation_modulator_0`)** — Maps bits onto the `bpsk` constellation (points at +1/−1), with:
    - `differential: True` — differential encoding (protects against 180° phase ambiguity at RX).
    - `excess_bw: 0.35` — RRC pulse shaping.
    - `samples_per_symbol: sps (4)` — upsamples to 4 samples/symbol.

11. **Multiply Const (`blocks_multiply_const_vxx_0`)** — Scales the complex signal amplitude by `0.8` (headroom/output level control).

12. **PlutoSDR Sink (`iio_pluto_sink_0`)** — Transmits the signal via hardware:
    - `frequency: 2,400,000,000` Hz (2.4 GHz)
    - `samplerate: samp_rate` (2.4 Msps)
    - `bandwidth: 2,000,000` Hz (**2 MHz analog filter — narrowed from the original 20 MHz**)
    - `attenuation1: 10.0` dB

    > **Note:** the simulated `channels_channel_model` block that previously sat between the amplitude scaler and this sink has been **removed** — the TX chain now goes directly from `blocks_multiply_const_vxx_0` to `iio_pluto_sink_0`, so the only channel effects present are real over-the-air ones.

---

## Receiver (RX) — Block by Block

### Variables

Mirrors most TX variables (`samp_rate`, `sps`, `excess_bw`, `nfilts`, `rrc_taps`, `phase_bw`, `damp_fac`, `max_dev`/`max_dev_0`, `freq`, `taps`, `noise_volt`, `freq_offset`, `time_offset`, `my_addr` — all must numerically match TX for correct demodulation), plus:

| Variable | Value | Purpose |
|---|---|---|
| `bpsk` (`variable_constellation_rect`) | 2-point constellation at `[-1, 1]` | The reference BPSK constellation object used by the decoder and symbol sync |
| `cma_alg` (`variable_adaptive_algorithm`) | `type: cma`, `modulus: 1`, `step_size: 0.01`, `ffactor: 0.99`, `delta: 10.0` | Configuration for the blind equalizer. **`modulus` has been corrected from 4 → 1** to match BPSK's actual constellation radius. |

### Blocks (signal path order)

1. **PlutoSDR Source (`iio_pluto_source_0`)** — Receives hardware samples:
   - `frequency: 2,400,000,000` Hz (2.4 GHz)
   - `samplerate: samp_rate` (2.4 Msps)
   - `bandwidth: 2,000,000` Hz (**2 MHz analog filter — narrowed from the original 20 MHz**)
   - `gain1: 'slow_attack'` — AGC gain mode (note: `manual_gain1: 80` is set but has no effect while in this automatic mode)
   - `bbdc`, `rfdc`: `True` — DC-offset correction enabled

2. **AGC (`analog_agc_xx_0`)** — Software Automatic Gain Control. Scales incoming amplitude toward `reference: 1.0`, adaptation `rate: 1e-4`, `max_gain: 100`.

3. **Symbol Sync (`digital_symbol_sync_xx_0_1_0`)** — **Timing recovery.** Aligns the receiver's sampling instants to the transmitter's actual symbol clock:
   - **Gardner Timing Error Detector** (`ted_type: TED_GARDNER`)
   - **Polyphase filterbank matched filtering** (`resamp_type: IR_PFB_MF`) using `rrc_taps` split across `nfilters: 32`
   - `loop_bw: phase_bw`, `damping: damp_fac`
   - Input 4 samples/symbol (`sps`) → output `osps: 1` (exactly one sample per symbol)

4. **Linear Equalizer (`digital_linear_equalizer_0`)** — **Blind adaptive equalizer** using CMA (`cma_alg`), `num_taps: 15`. Corrects inter-symbol interference from multipath without a known training sequence (`training_sequence: '[ ]'`), by adapting until symbols have a constant magnitude. `adapt_after_training: True` — keeps adapting continuously.

5. **Constellation Sink — "After linear equilizer" (`qtgui_const_sink_x_1`)** — Displays the signal right after equalization but before carrier recovery (expect a rotating/blurred ring at this stage — phase isn't corrected yet).

6. **Costas Loop (`digital_costas_loop_cc_0_0`)** — **Carrier phase/frequency recovery**, `order: 2` (correct for BPSK's 2-fold symmetry), loop bandwidth `w: phase_bw`. Removes any residual carrier offset not corrected by the RF hardware's own oscillator.

7. **Constellation Sink — "After syncronization" (`qtgui_const_sink_x_0_0`)** — Displays the signal after carrier recovery. In a healthy link this should show two tight, stationary clusters at approximately +1 and −1.

8. **Constellation Decoder (`digital_constellation_decoder_cb_0_0`)** — Slices each received symbol against the `bpsk` reference points, deciding the most likely bit value, outputting one byte per symbol.

9. **Differential Decoder (`digital_diff_decoder_bb_0_0`)** — Undoes the TX-side differential encoding, resolving the Costas loop's inherent 0°/180° lock ambiguity so the recovered data bits are correct regardless of which phase the loop settled on.

10. **Map (`digital_map_bb_0_0`)** — Applies `map: [0, 1]`, effectively an identity mapping in this configuration (a general-purpose remapping stage).

11. **Unpack k Bits (`blocks_unpack_k_bits_bb_0_0`)** — Unpacks each byte into individual bits (`k: 1`), so each output byte holds one bit (0 or 1) — needed for bit-level pattern matching next.

12. **Correlate Access Code (`digital_correlate_access_code_xx_ts_0_0`)** — Continuously scans the bit stream for the known 68-bit `access_code`. On a match within **`threshold: 4`** bit errors (**loosened from the original 2**), it tags the packet start (`tagname: packet_len`).

13. **Repack Bits (`blocks_repack_bits_bb_1_0_0_0`)** — Repacks the 1-bit-per-byte stream back into proper 8-bit bytes (`k: 1`, `l: 8`, `endianness: GR_MSB_FIRST`), reconstructing the actual header+payload+CRC bytes while preserving the `packet_len` tag.

14. **Tagged Stream → PDU (`pdu_tagged_stream_to_pdu_0_0_0`)** — Converts the tagged byte stream into discrete PDU messages, one per detected packet.

15. **CRC32 Check (`digital_crc_check_0_0`)** — Recomputes CRC32 over each received packet and compares to the appended value. Only the `ok` (valid) output is wired onward — packets that fail are implicitly dropped.

16. **Packet Parser (`epy_block_1`, embedded Python)** — For each valid packet:
    - Strips the 7-byte header (`SRC, DST, TYPE, SEQ, TOTAL, LEN`).
    - Checks the destination address against `my_addr` (hardcoded `3` in this block) or broadcast (`0xFF`); drops non-matching packets.
    - Buffers segments by `(src, msg_type)` key, indexed by `SEQ`.
    - Once `total` segments are collected, concatenates them in order and publishes the full reassembled message.

17. **Message Debug (`blocks_message_debug_3`)** — Prints every reassembled PDU for debug visibility.

18. **Plain Text Printer (`epy_block_0`, embedded Python — RX side)** — Decodes the final reassembled bytes as UTF-8 and prints:
    ```
    SUCCESS! RECEIVED MESSAGE: <original text>
    ```

---

## Packet / Frame Structure

```
┌────────────────────┬──────────────┬─────┬─────┬──────┬──────┬───────┬───────────────────┬─────────┐
│   Dummy Preamble    │ Access Code  │ SRC │ DST │ TYPE │ SEQ  │ TOTAL │   Payload data     │  CRC32  │
│   (random bytes)    │  (sync word) │ 1B  │ 1B  │  1B  │ 1B   │  1B   │  ≤ 200 bytes       │   4B    │
├────────────────────┼──────────────┼─────┴─────┴──────┴──────┴───────┴────────────────────┼─────────┤
│     1500 bytes      │   68 bits    │              7-byte custom header                     │         │
│                      │ (8.5 bytes)  │                                                        │         │
└────────────────────┴──────────────┴────────────────────────────────────────────────────────┴─────────┘
```

- **Header fields:** `SRC(1B)`, `DST(1B)`, `TYPE(1B)` (`0x01=TEXT, 0x02=IMAGE, 0x03=AUDIO`), `SEQ(1B)`, `TOTAL(1B)`, `LEN(2B, big-endian)`.
- **CRC32** covers the header + payload for error detection only (no correction, no retransmission possible in this simplex design).
- **Access code** (68 bits) is a fixed pattern unrelated to message content, used solely so the RX correlator can find packet boundaries in the continuous bit stream.

---

## Parameter Reference Table

| Parameter | Value | Notes |
|---|---|---|
| Carrier frequency | 2.4 GHz | Both Plutos |
| Sample rate | 2,400,000 sps | `samp_rate` |
| Samples per symbol | 4 | `sps` |
| Modulation | BPSK, differentially encoded | |
| Pulse shaping | RRC, roll-off 0.35 | `excess_bw` |
| Polyphase filter arms | 32 | `nfilts` |
| Symbol timing recovery | Gardner TED + PFB matched filter | |
| Equalizer | CMA (blind), 15 taps, **modulus = 1** | Corrected for BPSK |
| Carrier recovery | 2nd-order Costas loop | |
| Access code | 68 bits | `access_key` |
| Access-code error tolerance | **4 bits** | Loosened from 2 |
| Header size | 7 bytes | Packet Builder / Parser |
| CRC | CRC-32 (`0x4C11DB7`) | |
| Max payload per segment | **200 bytes** | Increased from 10 |
| Dummy preamble | 1500 bytes | *(not yet reduced — see limitations)* |
| Message send interval | 1000 ms | Message Strobe |
| TX attenuation | 10 dB | |
| RX gain mode | AGC (`slow_attack`) | `manual_gain1` unused in this mode |
| Analog filter bandwidth | **2 MHz** | Narrowed from 20 MHz, both Plutos |
| Simulated channel model | **Removed** | TX now feeds the Pluto sink directly |

---

## Transmission Rate Calculations

**Symbol rate:**

R_s = f_s / sps = 2,400,000 / 4 = 600,000 symbols/sec (600 kBaud)

**Raw physical-layer bit rate** (BPSK = 1 bit/symbol):

R_b = R_s × 1 = 600,000 bps = 600 kbps

**Occupied RF bandwidth** (RRC roll-off 0.35):

BW = R_s × (1 + α) = 600,000 × 1.35 = 810,000 Hz ≈ 810 kHz

This is why the 2 MHz analog filter setting is reasonable — it comfortably passes the ~810 kHz occupied signal while excluding far more out-of-band noise than the original 20 MHz setting did.

**Overhead per burst (current parameters):**

| Component | Size |
|---|---|
| Dummy preamble | 1500 bytes = 12,000 bits |
| Access code | 68 bits |
| Header | 7 bytes = 56 bits |
| Payload (max) | 200 bytes = 1600 bits |
| CRC32 | 4 bytes = 32 bits |
| **Total burst (max payload)** | **13,756 bits ≈ 1719.5 bytes** |

**Efficiency** (payload bits ÷ total bits), at max payload:

η = 1600 / 13,756 ≈ 11.6%

**Time on air per max-size burst:**

t_burst = 13,756 / 600,000 ≈ 22.9 ms

**Effective application throughput**, sample message `"Hello University of Moratuwa"` (29 bytes, fits in a single 200-byte segment now — `TOTAL = 1`):
- One burst per message send, ~22.9 ms airtime, but the message strobe only fires once every 1000 ms.

Effective throughput = (29 × 8) / 1 sec = 232 bps ≈ 0.23 kbps

This is still governed by the 1-second strobe period, not the physical layer — same as before, since the strobe timing wasn't changed. If bursts were sent back-to-back instead (removing the strobe's artificial gap), the theoretical maximum effective throughput at max payload would be:

1600 bits / 22.9 ms ≈ 69,870 bps ≈ 69.9 kbps

*(Efficiency is still capped well below the 600 kbps physical rate mainly because the 1500-byte dummy preamble remains unchanged — reducing it, as noted below, would raise this substantially, similar to the earlier ~325 kbps estimate calculated with a 150-byte preamble.)*

---

## How to Run

1. Power on both PlutoSDR units and confirm network reachability:
   ```
   ping 192.168.1.10   # RX unit
   ping 192.168.1.11   # TX unit
   ```
2. Open `packetised_receiver_bpsk.grc` in GRC, generate, and run it first (so the receiver is listening before any burst is sent).
3. Open `packetised_transmitter_bpsk.grc` in GRC, generate, and run it.
4. Edit the "Transmitted message" GUI field on the TX window if you want to send something other than the default text.
5. Watch the RX console for:
   ```
   RX pkt  src=0x1 dst=0x3 type=TEXT seg=1/1 len=29
   SUCCESS! RECEIVED MESSAGE: Hello University of Moratuwa
   ```
6. Watch the "After linear equilizer" and "After syncronization" constellation sinks on RX to visually confirm lock quality.

---

## Design Rationale

| Choice | Reason |
|---|---|
| BPSK (not QPSK/QAM) | Simplest, most noise-robust modulation; trades off lower bits/symbol for reliability. |
| Differential encoding + decoding | A 2nd-order Costas loop cannot distinguish 0° from 180° carrier lock; differential coding makes recovered data correct regardless of which the loop settles on. |
| Gardner TED for timing recovery | Standard non-data-aided detector; works without knowing the data in advance. |
| CMA (blind) equalizer | No training sequence is transmitted, so a decision-directed/blind method is required to correct multipath ISI. |
| Dummy preamble before every burst | AGC, symbol sync, and Costas loop all need convergence time before they can reliably track — without it, the real header/payload bits risk corruption while loops are still settling. |
| Access-code correlator with error tolerance | Real channels introduce bit errors even in symbols that pass the equalizer/decoder; a bit-perfect match requirement would cause valid packets to be missed. |
| CRC32 (detection only, no FEC) | Lets corrupted packets be identified and discarded — but since the link is simplex, detection is all that's possible; there's no retransmission request and no error-correcting code, so any detected error means that segment is lost. |
| Custom SRC/DST/TYPE/SEQ/TOTAL header | The GNU Radio physical-layer framing only handles "where does one burst start/end" — it has no concept of application addressing or multi-burst message reassembly, which the custom header adds. |
| Narrowed analog bandwidth (2 MHz) | The signal only occupies ~810 kHz; a much wider filter (originally 20 MHz) let in unnecessary noise, worsening receive SNR. |
| Removed simulated channel model from TX path | Real RF already provides real noise/multipath/offsets; stacking a software-simulated channel on top of the real hardware path needlessly degraded the achievable link quality. |
| CMA `modulus = 1` (corrected from 4) | BPSK symbols sit at ±1 — a `modulus` of 4 pointed the equalizer's convergence target at the wrong radius, slowing/destabilizing convergence. |

---

## Known Limitations / Future Work

- **Dummy preamble still 1500 bytes.** This remains oversized relative to what the AGC/Costas/symbol-sync loops need to converge (a few hundred bytes is typically sufficient for BPSK). Reducing this (e.g., to 150 bytes, verifying constellation lock is still reliable) would substantially raise effective throughput, since the preamble currently makes up the vast majority of every burst's airtime.
- **No forward error correction (FEC).** Only error *detection* (CRC32) exists; any corrupted packet is simply lost with no possibility of recovery, since the link is simplex.
- **No reassembly timeout.** If a segment is lost, the Packet Parser's partial-message buffer for that `(src, mtype)` key will wait indefinitely for the missing segment unless a timeout/cleanup mechanism is added.
- **Message strobe period (1000 ms) dominates effective throughput** far more than any physical-layer parameter — sending continuously (event-driven, rather than a fixed periodic strobe) would be the single largest throughput improvement available.
- **Dead/unused variables** (`my_addr`, `variable_qtgui_entry_0` on TX; `taps`, `noise_volt`, `freq_offset`, `time_offset` now orphaned after channel-model removal) could be cleaned up for clarity, though they don't affect functionality.
- **Simplex-only design.** Without a return channel, there is no acknowledgment/retransmission mechanism — reliability depends entirely on first-attempt success. Adding even a minimal low-rate ACK/NACK back-channel, or FEC, would be the most impactful reliability upgrade beyond parameter tuning.

