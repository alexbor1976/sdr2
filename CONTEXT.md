# sdr2 — project context

> Paste this whole file into a fresh AI chat at the start of a session. It's
> the one thing that needs to be current — everything here is facts, not
> a tutorial. For a running diary of experiments, see `LAB.md`. `NOTES.md`
> is a personal scratchpad — not usually worth pasting into a fresh chat.

> Based on `sdr` (original project) — reorganized into `sdr2`'s own file
> layout. See the original project's README for the phase-by-phase build log
> this one grew out of, if deeper history is ever needed.

---

## What this is

A remote spectrum analyzer / signal generator. Beginner level — explain
things simply, and always say which machine a command or piece of code runs
on (laptop or board). That single fact is the #1 source of wrong answers.

---

## Status

- **Phase 1 (network + link check): DONE, verified 2026-07-14.** Run via
  `cd LinkChecker && python main.py` on the laptop (see `LinkChecker/`).
  Result: connected cleanly, `peak = 99.36` (sane range), full details in
  `LinkChecker/results/2026-07-14_111211_report.json` and the matching
  `_samples.npy`. An offline FFT of that capture also shows a strong,
  narrow tone ≈99.0 MHz (≈996 kHz below the 100 MHz LO) — good independent
  evidence the RXA antenna is genuinely receiving real off-air signal, not
  just noise. See `LAB.md` for the full row.
- Phases 2+ (live spectrum plot, signal generation, RF cable loopback,
  board-side PSD, FPGA work): not started yet.

---

## Hardware

| | |
|---|---|
| SOM | ADRV9364-Z7020 (Xilinx Zynq XC7Z020 + Analog Devices AD9364, 1 TX / 1 RX) |
| Carrier | ADRV1CRR-BOB |
| OS on the board | Analog Devices Kuiper Linux, login `analog` / `analog` |
| Board IP | `192.168.1.50`, IIO network port 30431 |
| Host | Windows laptop, Python 3.11, VS Code, `pyadi-iio` + `libiio 0.25` |
| FPGA bitstream | Stock Kuiper image. Not rebuilt in Vivado. |

**Architecture** (four "computers" — always state which one code runs on):

```
Laptop (Python, numpy, matplotlib) ⟷ Ethernet ⟷ ARM Cortex-A9 running Kuiper
Linux (ad9361 driver + iiod server) ⟷ FPGA fabric (axi_ad9361 capture,
axi_dmac DMA, hardware DDS) ⟷ AD9364 RF transceiver.
```

`libiio` makes a remote radio look local; `pyadi-iio` wraps it in friendly
Python. `uri="ip:192.168.1.50"` from the laptop, `uri="local:"` on the board.

---

## Current RF configuration — read this before writing or running anything

**This is not a bench-safe, empty-SMA setup.** Real antennas are physically
connected:

| Port | Antenna |
|---|---|
| RXA | Molex 105263 Series Flexible Cellular 6-Band Antenna |
| TXA | Siretta Delta 2 Series Right-Angle Stubby Antenna |

Consequences:

- Any TX buffer radiates for real — RF-loopback-style tests are **not**
  safe-by-default the way digital loopback (`loopback = 1`, RF section
  bypassed) is.
- Default generator frequency is **433 MHz** (checked for legal use in this
  band/region), not the original tutorial's 100 MHz. If recreating or porting
  code from the original project, check every hardcoded `TX_LO` / `CENTER`.
- Keep `tx_hardwaregain_chan0` conservative (large negative = more
  attenuation, range roughly −89.75 … 0 dB) until actual radiated power has
  been measured. Do not suggest connecting a different antenna or increasing
  power without discussing it first.
- RX-only tests (like the Phase 1 link check above, run at `rx_lo = 100 MHz`)
  are always safe regardless of antenna state, since nothing is transmitted.

---

## Hardware quirks (board-specific — not in any generic tutorial)

### LEDs (DS3–DS6)

- Only **DS3 (red, "LED0")** is controllable. DS4/DS5/DS6 are not physically
  routed to the processor on this SOM — no software will light them.
- DS3 is on **raw GPIO 963**. The default device tree wrongly assigns 963 to
  the `gpio-keys` driver as a "Down" button, locking it as an input with an
  IRQ. So `/sys/class/leds/` does nothing, and
  `echo 963 > /sys/class/gpio/export` fails with `Device or resource busy`.
- **Workaround, root, once per boot:** unbind every device under
  `/sys/bus/platform/drivers/gpio-keys/`, then export 963, then
  `echo out > /sys/class/gpio/gpio963/direction`. The device tree resets on
  every reboot, so this must be re-run each boot.
- Open question, not yet verified: whether GPIO 963 is an EMIO pin (i.e.
  routed through the FPGA fabric). If `gpiochip` base is 906 and `ngpio` 118,
  then `963 − 906 = 57` → EMIO pin 3. Check with:
  ```bash
  for c in /sys/class/gpio/gpiochip*; do echo "$c base=$(cat $c/base) label=$(cat $c/label) ngpio=$(cat $c/ngpio)"; done
  ```

### AD9364 loopback modes (debug attribute, debugfs, needs root)

| Value | Meaning | Radiates? |
|---|---|---|
| `0` | Disabled, normal operation | Yes, when TX active |
| `1` | Digital TX → digital RX, inside the chip. RF section bypassed. | **No** |
| `2` | RF RX → RF TX, loops in the HDL core, chip retransmits. | **Yes** |

Use `1` for digital-only bench testing. Never `2`. In mode `1`, `rx_lo`,
`tx_lo`, `rx_hardwaregain`, `rx_rf_bandwidth` have no effect — the RF section
they configure is bypassed.

### IIO device names

```bash
grep "" /sys/bus/iio/devices/iio:device*/name
```

| Name | Role |
|---|---|
| `ad9361-phy` | Transceiver control device — all RF attributes |
| `cf-ad9361-lpc` | RX data device (DMA into DDR) |
| `cf-ad9361-dds-core-lpc` | TX data device, and FPGA hardware DDS |
| `xadc` | Zynq internal voltage/temperature ADC |

If `ad9361-phy` is missing, the bitstream/device tree didn't load — nothing
else will work until that's fixed.

### Numbers worth remembering

| | |
|---|---|
| AD9364 tuning range | 70 MHz – 6 GHz |
| Sample rate | up to 61.44 MS/s (complex) |
| RX ADC full scale | ≈ ±2048 (12-bit) → divide by `2**11` |
| TX DAC full scale | `2**14` in pyadi convention |
| `rx_hardwaregain_chan0` | gain in dB, roughly −3 … 71 (band-dependent) |
| Analog filter corner | ~80% of sample rate — distrust the outer 20% |
| Ethernet ceiling | ~5 MS/s continuous (`5e6 × 2 × 2 B` ≈ 160 Mbit/s) |
| RX sample dtype (observed) | `complex128` in practice on this setup — don't assume `complex64` |

---

## Safety constraints (must hold for all code and suggestions)

- `loopback = 1` and `tx_hardwaregain_chan0` pinned negative for any bench/dev
  work not deliberately testing real RF transmission.
- ≥30 dB attenuation for any cable-based TX↔RX loopback.
- With antennas connected (current state — see above), treat every transmit
  as real and keep power conservative until measured.
- Never invent an API name, IIO attribute, register, or file path. If unsure,
  say so and give the discovery command instead:
  `print([a for a in dir(sdr) if not a.startswith("_")])` or
  `iio_info -u ip:192.168.1.50`.

---

## Conventions established so far

- **Settings pattern:** all tunable values live in `Settings.py` as class
  attributes (`Settings.rx_lo`), never instantiated. Scripts import the
  class and read/override directly, e.g. `Settings.rx_lo = int(200e6)` in
  `main.py` before running. No constructor arguments — deliberate, so it
  scales to many settings without an unreadable constructor signature.
- **Each script that talks to the radio is a class** (e.g. `LinkChecker`)
  with one method per logical step, plus a `run()` that calls them in
  order. A thin `main.py` overrides `Settings` if needed and instantiates
  the class.
- **Every run saves ground truth to disk automatically**: a
  `save_report()`-style method writes `results/<timestamp>_report.json`
  (settings + key results — small, safe to paste into an AI chat) and
  `results/<timestamp>_samples.npy` (raw data). Follow this pattern for
  new scripts (e.g. a future `SpectrumLive` class).
- **Each script gets a matching `.md`** (e.g. `LinkChecker.md`) documenting
  what it does, how to run it, and how to test it empirically.
- **Each script lives in its own subfolder** (e.g. `LinkChecker/`), holding
  that script's `.py`, its `.md`, and its own `results/`. `Settings.py`
  is the one exception — it stays at the project root since it's shared by
  every script's folder, not owned by any single one. A script's `main.py`
  is responsible for making the root importable (see `LinkChecker/main.py`'s
  `sys.path` bootstrap) so this works regardless of where you launch it from.
  **Always `cd` into a script's own folder before running it** — `results/`
  is a relative path, and doing this keeps each script's output next to
  itself instead of scattered into wherever you happened to launch Python.
- **Two separate log files, different purposes:** `LAB.md` is the
  structured, append-only project log (one row per experiment — never
  edited after the fact). `NOTES.md` is a personal, free-form scratchpad
  (ideas, reminders, half-formed questions) — fine to edit or delete
  entries in.

---

## Repo layout

`sdr2` reorganizes the original project's files into its own structure, one
subfolder per script. Current state:

```
CONTEXT.md              ← this file
LAB.md                   ← project-wide experiment log (one row per run, append-only)
NOTES.md                  ← personal scratchpad (ideas, reminders — not structured)
HARDWARE_NOTES.md          ← board quirks: LED / GPIO 963 device-tree bug, loopback modes
Settings.py                 ← SHARED config, class attributes only (Settings.rx_lo, ...)
                               used by every script's folder below
LinkChecker/                  ← Phase 1: link check
├── LinkChecker.py              ← the class
├── main.py                      ← entry point (run this, from inside this folder)
├── LinkChecker.md                 ← how to run/test it, what its results contain
└── results/                        ← auto-saved per run
    ├── summarize.py                  ← prints a one-line-per-run table across all reports
    ├── <run_id>_report.json
    └── <run_id>_samples.npy
```

Still to design/port from the original project (Phases 2–7), each expected
to get its own subfolder the same way `LinkChecker/` does:
`spectrum_live.py`, `siggen.py`, `loopback_rf_cable.py`, `board_psd_server.py`,
`laptop_psd_client.py`, `scripts/led_init.sh`, `scripts/led.py`.

---

## How to work with AI on this project

- **Say explicitly whether code runs on the laptop or the board.** Biggest
  single source of wrong answers.
- **One small testable step at a time**, not a finished large program. Each
  step should print something checkable.
- **Before running anything**, state what success looks like, and what a
  specific plausible failure would look like.
- **Flag uncertain lines** and give the command to verify them on the board.
- **When reporting a bug**, give: which machine, exact command, complete
  traceback (not paraphrased), what was expected, what changed since it last
  worked. Ask for a ranked list of likely causes with a cheap test for each —
  not a single confident guess.
- **Ground truth beats memory.** API names, GPIO numbers, register names and
  file paths drift between library/board versions — verify against the board,
  don't trust a remembered answer. Prefer pasting an actual
  `<script>/results/*_report.json` over describing a result from memory.
- **Paste `LAB.md`, not `NOTES.md`, when asking for help on a specific bug.**
  `LAB.md` has the structured expected-vs-observed rows an AI can reason
  about; `NOTES.md` is personal and unstructured.
