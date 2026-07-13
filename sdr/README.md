# Remote Spectrum Analyzer & Signal Generator
### ADRV9364-Z7020 SOM on ADRV1CRR-BOB · Kuiper Linux · Python

A learn-by-building SDR project. A Windows laptop drives an Analog Devices
ADRV9364-Z7020 (Zynq-7020 + AD9364 transceiver) over Ethernet, using it as a
networked spectrum analyzer and signal generator.

Written for beginners. Every step is a thing you can run and check.
**No antenna is needed for the first half of the project** — the AD9364 can
loop its own digital transmit path back into its receiver, with the entire RF
section bypassed.

---

## Status

| Phase | What | State |
|---|---|---|
| 1 | Network + SSH + `iio_info` link check | ☐ |
| 2 | **Digital loopback inside the AD9364** (no RF, empty SMA) | ☐ |
| 3 | Live spectrum plot | ☐ |
| 4 | Signal generation (FPGA DDS + arbitrary buffer) | ☐ |
| 5 | RF cable loopback (needs a ≥30 dB attenuator) | ☐ |
| 6 | Move the FFT onto the ARM core; laptop becomes a thin client | ☐ |
| 7 | FPGA: Vivado, ILA on the data path, device tree | ☐ |

Tick these as you go. They're also the commit messages.

---

## Hardware

| | |
|---|---|
| SOM | ADRV9364-Z7020 (Xilinx Zynq XC7Z020 + Analog Devices AD9364) |
| Carrier | ADRV1CRR-BOB (breakout board) |
| Radio | AD9364: 1 TX, 1 RX, 70 MHz – 6 GHz, up to 61.44 MS/s |
| OS | Analog Devices Kuiper Linux (default login `analog` / `analog`) |
| Board IP | `192.168.1.50` |
| Host | Windows, Python 3.11, VS Code |

Board-specific quirks (LED wiring, a device-tree bug) are documented in
[`docs/HARDWARE_NOTES.md`](docs/HARDWARE_NOTES.md). Read that before trying to
blink an LED — it will not work the obvious way.

---

## Architecture

Four "computers" are involved. Most beginner confusion comes from not knowing
which one a given line of code runs on.

```
  ┌────────────┐  fast digital  ┌──────────────┐  AXI/DMA  ┌──────────────┐
  │  AD9364    │───── bus ─────▶│  FPGA  (PL)  │──────────▶│   DDR RAM    │
  │  RF chip   │◀───────────────│ capture, DDS │           └──────┬───────┘
  └─────┬──────┘                └──────────────┘                  │
        │                                                  ┌──────▼───────┐
        │  ◀── digital loopback lives HERE, inside the chip │  ARM (PS)   │
        │      (RF section bypassed, nothing radiated)      │ Kuiper Linux│
        │                                                   │ ad9361 drv  │
   [SMA: TX1A / RX1A]                                       │ iiod server │
                                                            └──────┬──────┘
                                                                   │ Ethernet
                                                                   │ TCP 30431
                                                            ┌──────▼──────┐
                                                            │   Laptop    │
                                                            │  pyadi-iio  │
                                                            │ numpy, plot │
                                                            └─────────────┘
```

The glue is **IIO** (Linux Industrial I/O). `libiio` makes a remote radio look
local; `pyadi-iio` wraps it in friendly Python.

**The stock Kuiper image already contains a working FPGA bitstream, drivers and
`iiod`.** You do not need Vivado to complete Phases 1–6. Phase 7 is optional and
should be attempted last, because until the software baseline works you cannot
tell whether a failure is your bitstream or your code.

---

## Repository layout

```
├── README.md                    ← you are here
├── docs/
│   ├── GUIDE.md                 ← the long-form tutorial, phase by phase
│   ├── HARDWARE_NOTES.md        ← board quirks: the LED / GPIO 963 device-tree bug
│   └── AI_CONTEXT.md            ← paste this into a new AI chat to bring it up to speed
├── link_check.py                ← Phase 1. Proves the whole chain end to end.
├── loopback_digital.py          ← Phase 2. START HERE. No RF, empty SMA, safe.
├── spectrum_live.py             ← Phase 3. Live FFT plot.
├── siggen.py                    ← Phase 4. FPGA DDS tone, and arbitrary cyclic buffer.
├── loopback_rf_cable.py         ← Phase 5. Real RF. Needs a ≥30 dB attenuator.
├── board_psd_server.py          ← Phase 6. Runs ON THE BOARD. FFT on the ARM core.
├── laptop_psd_client.py         ← Phase 6. Runs on the laptop. Thin display client.
└── scripts/
    ├── led_init.sh              ← run on the board, once per boot
    └── led.py                   ← blink DS3 from the laptop over SSH
```

Every script's docstring says **which machine it runs on**. That is the first
thing to check when something behaves strangely.

---

## Quick start

### 1. Network

Give the laptop a static address on the board's subnet: `192.168.1.10 / 255.255.255.0`.

```powershell
ping 192.168.1.50
ssh analog@192.168.1.50        # password: analog
```

On the board, confirm the radio enumerated:

```bash
ls /sys/bus/iio/devices/
grep "" /sys/bus/iio/devices/iio:device*/name
```

You want to see `ad9361-phy`, `cf-ad9361-lpc` (RX) and `cf-ad9361-dds-core-lpc` (TX).
If `ad9361-phy` is absent, the bitstream or device tree did not load and nothing
else in this repo will work.

### 2. Python on the laptop

Conda is strongly recommended on Windows — it installs the C library *and* the
bindings together, which avoids the most common install failure.

```powershell
conda create -n sdr python=3.11
conda activate sdr
conda install -c conda-forge libiio pylibiio pyadi-iio
pip install numpy matplotlib scipy
```

<details>
<summary>pip alternative, and the version trap</summary>

```powershell
py -m venv venv && venv\Scripts\activate
pip install pyadi-iio numpy matplotlib scipy
```

Then install the **libiio v0.25 Windows installer** from the ADI `libiio` GitHub
releases page. Do **not** install libiio **v1.0** — the PyPI Python bindings are
built against the 0.x C API, and mixing them produces errors such as
`AttributeError: function 'iio_channel_read' not found`. Check with
`iio_info -V` — you want `0.25`.
</details>

Verify:

```powershell
iio_info -u ip:192.168.1.50
python link_check.py
```

### 3. The first real test — no antenna, no cable

```powershell
python loopback_digital.py
```

This is the most valuable thirty seconds in the project. See below.

---

## Why we start with digital loopback

The AD9364 exposes a debug attribute `loopback` with three values:

| Value | Meaning | Radiates? | Use it? |
|---|---|---|---|
| `0` | Disabled — normal operation | yes, when TX is on | for real RF work |
| `1` | **Digital TX → Digital RX**, inside the chip, near the internal digital interface block. The entire RF section is bypassed. | **no** | ✅ **yes, always first** |
| `2` | RF RX → RF TX, looped in the ADI HDL core. The chip retransmits whatever it hears; the full RF chain stays live. | **yes** | ❌ not for this project |

`loopback = 1` exercises everything that software can get wrong:

```
Python → libiio → Ethernet → iiod → kernel driver → FPGA DMA
       → AD9364 digital TX → [loopback] → AD9364 digital RX
       → FPGA DMA → ... → back to Python
```

If your tone lands in the FFT bin you predicted, **all of that works.** Any
later failure is, by elimination, in the analog/RF domain — cable, attenuator,
port, LO, gain. You have halved the search space before touching a screwdriver.

Corollary, and it surprises everybody: in digital loopback, `rx_lo`, `tx_lo`,
`rx_hardwaregain` and `rx_rf_bandwidth` have **no effect whatsoever**. The RF
section is bypassed. That is the point, not a bug.

`loopback` lives in debugfs and needs root on the board. `scripts/` and the
script's own docstring carry the fallback (`echo 1 > /sys/kernel/debug/iio/iio:deviceN/loopback`)
if pyadi cannot reach it over the network.

---

## ⚠️ RF safety

Applies from Phase 5 onward. Phases 1–4 are safe with empty SMA ports.

1. **Never transmit into an antenna** unless you are licensed for that band.
2. For cable loopback, put **≥ 30 dB of attenuation** between TX1A and RX1A. The
   TX can deliver roughly +7 dBm; the RX is comfortable far below that. A cheap
   SMA attenuator kit is the best €10 in this project.
3. Leave `tx_hardwaregain_chan0` at a large negative value (`-89`, maximum
   attenuation) whenever you are not deliberately transmitting. The scripts here
   do this on exit.
4. Never use `loopback = 2`.

---

## Known traps

Collected so you don't rediscover them at 1 a.m.

| Symptom | Cause |
|---|---|
| `import adi` → `function 'iio_...' not found` | libiio v1.0 installed; bindings expect v0.25 |
| A permanent spike at exactly the centre frequency | LO leakage / DC offset. Not a signal. |
| A weak mirror image of your tone at `−f` | I/Q imbalance. Normal. |
| `rx()` stalls, or overflow warnings | Streaming faster than Ethernet. Stay ≤ ~5 MS/s, or move the FFT to the board (Phase 6). |
| Amplitudes drift between runs | AGC. Use `gain_control_mode_chan0 = "manual"`. |
| Spurs spaced exactly `FS/N` apart on TX | Cyclic buffer doesn't wrap seamlessly. Snap the tone to a bin: `f = round(f*N/FS)*FS/N`. |
| Radio wedges; nothing helps | A half-dead DMA buffer. **Restart the Python interpreter.** Don't reuse a crashed VS Code kernel. |
| LED writes → `Device or resource busy` | See [`docs/HARDWARE_NOTES.md`](docs/HARDWARE_NOTES.md). It's a device-tree bug, not you. |
| `AttributeError: gain_control_mode_chan0` | pyadi version difference. Use `gain_control_mode`. Always check `dir(sdr)`. |

Ethernet budget, for intuition:
`5 MS/s × 2 (I,Q) × 2 bytes = 20 MB/s ≈ 160 Mbit/s`. That fits. 61.44 MS/s is
~2 Gbit/s and does not. This is why Phase 6 exists.

---

## The idea behind Phase 6

Stop moving data. Move the **answer**.

The board captures at full rate over `uri="local:"` — no network in the data
path — computes an averaged 4096-point PSD on the ARM cores, and ships ~16 kB of
float32 to the laptop. That's a ~100× reduction, and it's how real networked
instruments are actually built.

```powershell
scp board_psd_server.py analog@192.168.1.50:~
ssh analog@192.168.1.50 'sudo python3 board_psd_server.py'
# then, locally:
python laptop_psd_client.py
```

Note that `laptop_psd_client.py` imports no radio libraries at all. It's a plot.

The board-side server also lights DS3 while a capture is running, so you can see
from across the room whether the instrument is acquiring.

---

## Free tools used

- [pyadi-iio](https://github.com/analogdevicesinc/pyadi-iio) + [libiio](https://github.com/analogdevicesinc/libiio) — Python/C interface to the radio
- **IIO Oscilloscope** (ADI) — GUI over the same protocol. If it sees a signal and your Python doesn't, the bug is in your Python. Invaluable.
- **VS Code + Remote-SSH** — edit and run code on the board as if it were local
- **Vivado ML Standard** — free, supports the XC7Z020. Only needed for Phase 7.
- Optional: **GNU Radio + gr-iio** (via Radioconda) for cross-checking

---

## Working on this with an AI assistant

Paste [`docs/AI_CONTEXT.md`](docs/AI_CONTEXT.md) into a fresh chat. It contains
the hardware facts, the quirks, and the ground-truth commands, so the model is
reasoning about *your* board rather than a generic one.

Short version of what works:

- **Good uses:** explaining concepts, writing boring plotting/threading code,
  decoding tracebacks, and producing *ranked hypothesis lists* ("give me the
  five most likely causes of X, ordered, and how to test each").
- **Verify always:** API names, IIO attribute names, GPIO numbers, file paths,
  Vivado/HDL/kernel version pairings. Models generate plausible-looking
  attributes that don't exist. Ground truth is on your board:

  ```python
  print([a for a in dir(sdr) if not a.startswith("_")])
  ```
  ```bash
  iio_info -u ip:192.168.1.50    # every device, channel and attribute, verbatim
  ```

- **Always state which machine the code runs on.** Laptop or board. Half of all
  bad answers come from the model silently guessing wrong.
- **Ask for one testable step, not a finished system.** "The smallest script that
  proves the DMA works." Then run it. A 300-line analyzer that almost works is
  worse than useless, because you can't tell which line is wrong.
- **Keep a lab notebook** (`NOTES.md`): command, expected, observed. Paste it in
  when stuck. It also stops you repeating failed experiments.

---

## Roadmap

- [ ] Waterfall display (rolling 2D PSD history — ~15 lines with `imshow`)
- [ ] Power calibration: known tone through a known pad → turn dBFS into dBm
- [ ] Measure the receiver noise figure
- [ ] Measure the on-board oscillator's frequency error against a broadcast station
- [ ] FM receiver: `np.angle(x[1:] * np.conj(x[:-1]))`, decimate, write a `.wav`
- [ ] Swap matplotlib for PyQtGraph when the frame rate hurts (~20 fps)
- [ ] Two-tone intermodulation test → measure TX linearity (IP3)
- [ ] Phase 7: ILA on the ADC data path; fix the `gpio-keys` device-tree bug properly

## License

MIT. Do as you like.
