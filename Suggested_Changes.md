# PlutoSDR Simplex File-Transfer Link — Improvement Guide

This covers the recommended changes to the "CDP" TX/RX GNU Radio flowgraphs, the exact steps to make each change, and a plain-language explanation of what each one does and why it helps.

---

## 1. Fix CMA modulus for BPSK (4 → 1)

**Steps:**
- Double-click the `cma_alg` variable block (`variable_adaptive_algorithm`) on RX.
- Change `modulus` from `4` to `1`.
- Apply, regenerate, and check the "After linear equilizer" constellation sink.
- If it destabilizes, try `2` as a middle ground before reverting.

**What it does:**
CMA (Constant Modulus Algorithm) is a "blind" equalizer — it doesn't know your training sequence in advance. Instead, it assumes all your symbols should sit at roughly the same distance ("modulus") from the center of the constellation, and adjusts its filter taps until incoming symbols match that assumption, correcting for multipath distortion.

`modulus` is the target radius the algorithm aims for. Your constellation is BPSK, so symbols only ever sit at two points: +1 and -1 — a radius of 1, not 4. Aiming for radius 4 sends the algorithm chasing the wrong target, causing slow or unstable convergence.

Setting it to 1 aims the equalizer's error calculation at the correct target, so it converges faster and cleaner, giving a tighter RX constellation before the Costas loop and slicer.

---

## 2. Narrow Pluto analog bandwidth (20 MHz → 2–3 MHz)

**Steps:**
- Double-click `iio_pluto_source_0` (RX) → change `bandwidth` from `20000000` to `2000000`–`3000000`.
- Double-click `iio_pluto_sink_0` (TX) → same change.
- Leave `samplerate` (`samp_rate = 2400000`) unchanged — only the analog filter is narrowed.
- Apply and re-run; if you see new ISI, widen back toward 3–4 MHz.

**What it does:**
This parameter sets the analog low-pass filter width on the SDR's RF frontend — how wide a slice of spectrum the radio lets through before digitizing. Your signal only occupies ~600 kHz–1 MHz. A 20 MHz filter lets in ~20x more thermal noise/interference than needed, all of which lands in the receiver and worsens SNR.

Narrowing the filter blocks out-of-band noise while still passing the full signal, directly improving receive SNR — often visible as tighter constellation clusters with no other changes.

---

## 3. Fix RX gain mode conflict

**Steps:**
- Double-click `iio_pluto_source_0`.
- Choose one mode:
  - **Automatic (good for varying range):** keep `gain1: 'slow_attack'`; ignore `manual_gain1` (it has no effect in this mode).
  - **Manual (good for fixed bench testing):** change `gain1` to `'manual'`, then set `manual_gain1` to a real value (start around 40–60, tune while watching the const sink amplitude).
- Apply.

**What it does:**
`gain1` picks the gain mode. `'slow_attack'` is AGC — automatic real-time gain adjustment to keep signal level good. `'manual'` uses a fixed gain you set via `manual_gain1`. Previously both were set (`slow_attack` + `manual_gain1: 80`), but in automatic mode the manual value is simply ignored — it wasn't doing anything.

Automatic mode adapts continuously, better when signal strength varies (moving radios, changing range). Manual mode gives repeatable, identical gain across test runs, making it easier to isolate DSP problems from gain problems during bench testing.

---

## 4. Add reassembly timeout/cleanup in the Packet Parser

**Steps:**
- Double-click `epy_block_1` ("Packet Parser") on RX to open the source editor.
- Replace the block's code with the version below (adds a `time` import, a `_last_seen` dict, and a `_cleanup_stale` method):

```python
import struct
import time
from gnuradio import gr
import pmt

HEADER_LEN = 7
TYPE_NAMES = {0x01: 'TEXT', 0x02: 'IMAGE', 0x03: 'AUDIO'}
REASSEMBLY_TIMEOUT = 10.0  # seconds

class blk(gr.basic_block):
    def __init__(self, my_addr=0x02):
        gr.basic_block.__init__(self, name='Packet Parser', in_sig=None, out_sig=None)
        self.my_addr = my_addr & 0xFF
        self._reassembly = {}       # key -> {seq: payload}
        self._last_seen = {}        # key -> timestamp of last segment
        self.message_port_register_in(pmt.intern('pdu_in'))
        self.message_port_register_out(pmt.intern('pdu_out'))
        self.set_msg_handler(pmt.intern('pdu_in'), self.handle_msg)

    def _cleanup_stale(self, now):
        stale = [k for k, t in self._last_seen.items() if now - t > REASSEMBLY_TIMEOUT]
        for k in stale:
            print(f"Packet Parser: dropping stale incomplete message {k}")
            self._reassembly.pop(k, None)
            self._last_seen.pop(k, None)

    def handle_msg(self, msg):
        if not pmt.is_pair(msg):
            return
        try:
            raw = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        except Exception:
            return
        if len(raw) < HEADER_LEN:
            print("Packet Parser: runt packet, dropping")
            return

        now = time.time()
        self._cleanup_stale(now)

        src, dst, mtype, seq, total, plen = struct.unpack('>BBBBBH', raw[:HEADER_LEN])
        payload = raw[HEADER_LEN:HEADER_LEN + plen]

        if dst != self.my_addr and dst != 0xFF:
            print(f"Packet Parser: dropping pkt for {dst:#x} (I'm {self.my_addr:#x})")
            return

        print(f"RX pkt  src={src:#x} dst={dst:#x} type={TYPE_NAMES.get(mtype, mtype)} "
              f"seg={seq+1}/{total} len={plen}")

        key = (src, mtype)
        self._reassembly.setdefault(key, {})[seq] = payload
        self._last_seen[key] = now

        if len(self._reassembly[key]) == total:
            full = b''.join(self._reassembly[key][i] for i in range(total))
            del self._reassembly[key]
            del self._last_seen[key]
            out_vec = pmt.init_u8vector(len(full), list(full))
            meta = pmt.cons(pmt.intern("type"), pmt.from_long(mtype))
            self.message_port_pub(pmt.intern('pdu_out'), pmt.cons(meta, out_vec))
```
- Apply.

**What it does:**
Today, when a multi-segment message arrives, each segment is stored keyed by `(source, message type)`, waiting until all `total` segments arrive before reassembling. If even one segment is lost (noise, missed access-code detection, failed CRC), that entry waits forever for a segment that never comes — the whole message is silently lost, and memory slowly fills with abandoned partial messages over a long session.

The fix timestamps every incoming segment and checks, on each new packet, whether any message has gone 10+ seconds without a new segment. If so, that stale entry is deleted and logged. This doesn't recover lost data (impossible without retransmission in a simplex link), but it stops the memory leak and gives you visibility into loss instead of silent failure.

---

## 5. Shrink dummy preamble (1500 → 150 bytes)

**Steps:**
- Double-click `epy_block_3` ("PDU Prepend Dummy Bytes") on TX.
- Change the `num_dummy_bytes` **parameter field** (not the source code) from `1500` to `150`.
- Apply, run TX+RX together, watch the RX constellation sinks lock before the access code.
- Adjust up/down in steps of ~50 based on whether lock happens reliably.

**What it does:**
Before your receiver can decode anything, several DSP blocks need to "settle": AGC needs to find the right gain, symbol sync needs to lock onto timing, and the Costas loop needs to lock onto carrier phase. The dummy bytes are throwaway data sent first purely to give these loops something to converge on before your real header/payload arrives — like a runway before the actual cargo.

At 1500 bytes, each burst was ~99% throwaway preamble. Well-behaved BPSK loops typically converge within a few hundred symbols — 150 bytes is generous. Shrinking it cuts wasted airtime dramatically, directly increasing effective throughput, as long as the constellation sinks confirm lock still happens reliably.

---

## 6. Increase MAX_PAYLOAD (10 → 200 bytes)

**Steps:**
- Double-click `epy_block_0` ("Packet Builder") on TX, edit source code.
- Change:
  ```python
  MAX_PAYLOAD = 10
  ```
  to:
  ```python
  MAX_PAYLOAD = 200
  ```
- Apply. No RX-side changes needed — the Packet Parser reads `total`/`plen` dynamically from the header.

**What it does:**
This controls how many bytes of your actual message get packed into each burst, before the header (7 bytes) and CRC (4 bytes) are added. At 10 bytes payload, roughly 3 bytes of fixed overhead exist per 1 byte of content (~30% overhead), and messages get split into many small bursts, each paying the preamble/lock-time cost from item 5 again.

At 200 bytes payload, the same 11 bytes of header+CRC overhead is spread across 20x more content (~5% overhead), and fewer, larger bursts mean fewer preamble/lock cycles overall — compounding the throughput gain from shrinking the preamble.

---

## 7. Loosen access-code correlator threshold (2 → 4)

**Steps:**
- Double-click `digital_correlate_access_code_xx_ts_0_0` on RX.
- Change `threshold` from `2` to `4`.
- Apply, test; raise further only if you still see missed detections in the console log.

**What it does:**
The receiver constantly scans the incoming bitstream for a known 68-bit pattern (the access code) marking "a packet starts here." Because real signals have noise, the correlator tolerates some bit errors and still calls it a match — `threshold` is how many errors it will accept.

Threshold 2 (under 3% error tolerance across 68 bits) is very strict. Real RF with any fading or imperfect equalization can easily corrupt more than 2 bits, causing the correlator to miss the packet start entirely — the whole burst is silently dropped even if the payload behind it would have been fine.

Threshold 4 makes detection more forgiving of real-world noise, so more valid packets get recognized (fewer missed detections), at a very small increase in the already-low risk of a false trigger from random noise.

---

## 8. Remove the channel model from the TX-to-Pluto hardware path

**Steps:**
- Delete the wire from `blocks_multiply_const_vxx_0` → `channels_channel_model_0_1`.
- Delete the wire from `channels_channel_model_0_1` → `iio_pluto_sink_0`.
- Connect `blocks_multiply_const_vxx_0`'s output directly to `iio_pluto_sink_0`'s input.
- Select `channels_channel_model_0_1` and press `D` to disable it (keeps it available later for pure-software simulation runs without hardware).
- Apply/regenerate.

**What it does:**
`channels_channel_model` is a *software simulation* block — it artificially adds noise, multipath echoes, frequency offset, and timing offset, mimicking what a real wireless channel would do. It's meant for testing DSP algorithms without real hardware.

Your actual RF path (Pluto TX → real air → Pluto RX) already introduces real noise, multipath, and offsets naturally. Having the simulation block in line before the real Pluto sink meant you were stacking simulated degradation on top of real degradation, making the link's effective SNR/multipath worse than either alone.

Removing it sends your clean modulated signal straight to the real radio, so the only channel effects present are genuine physical ones — an honest test of real link performance, and a link that's noticeably easier to close since you're no longer fighting a self-inflicted noise source.

---

## Suggested test order

1. **No-code, quick wins first:** items 8, 7, 6, 5 — re-run a cable-connected bench test after each.
2. Confirm constellations lock and text messages arrive correctly.
3. **Signal-quality tuning:** item 1 (CMA modulus) and item 2 (bandwidth) — re-test.
4. **Hardware setup:** item 3 (gain mode) once you move to real antenna range testing rather than cabled bench testing.
5. **Robustness:** item 4 (reassembly timeout) last — it's a cleanup/robustness feature, not something that affects whether a single test message gets through.

## Note on this being a simplex link

Since there's no ACK path back to the sender, there's no retransmission possible. The goal is to maximize the chance each packet gets through cleanly the first time, and handle loss gracefully when it doesn't (item 4). The two biggest levers for reliability beyond the tuning above are:
- **Forward Error Correction (FEC)** — GNU Radio's `fec_...` blocks let you recover from some bit errors without needing a repeat.
- **A minimal back-channel** — even a low-rate ACK/NACK path (if your application allows it) would be a bigger reliability win than any parameter tuning alone.
