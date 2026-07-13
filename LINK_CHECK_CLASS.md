# `link_check.py` (class version) — what it is, how to run it, how to test it

This is a rewrite of the original `link_check.py` script (from the
`spectrumAnalyzerTutorial` project this repo grew out of) as a **class**,
with **every line commented** for someone new to Python/SDR. It does exactly
the same thing as the original, in the same order — nothing about the
behavior has changed, only the organization.

Two files:

| File | Runs on | What it is |
|---|---|---|
| `link_check.py` | — | Defines the `LinkChecker` class. Not meant to be edited often. |
| `main_link_check.py` | **laptop** | Imports `LinkChecker`, sets your settings, runs it. Edit this one. |

---

## What it proves

Same as the original: that the whole chain works —

```
Your Python  →  libiio  →  Ethernet  →  iiod (on the board)
             →  ad9361/ad9364 driver  →  FPGA DMA  →  back to Python
```

If this script succeeds, any bug you hit later is in your own math or logic —
not in the network, the driver, or the FPGA bitstream. That rules out an
entire category of problems before you write anything else.

**It only receives (RX). It never transmits.** That means it's safe to run
even with your antennas physically connected (per your current
`HARDWARE_NOTES.md` / `CONTEXT.md` setup) — there is nothing to radiate.

---

## Why a class this time?

The original was one long function. Splitting it into methods means:

- You can run **one step at a time** in a Python shell to see exactly what
  each part does (great for learning — see the "empirical testing" section
  below).
- Later scripts (e.g. a future live-spectrum script) can `import LinkChecker`
  and reuse `connect()` / `configure()` instead of copy-pasting code.
- Settings live in `__init__`, as named parameters — no hunting through the
  function body to find a hardcoded number.

### The methods, in the order `run()` calls them

| Method | Same as original step | What it does |
|---|---|---|
| `connect()` | Step 1 | Opens the network connection to the board; tries `ad9364`, falls back to `ad9361`. |
| `print_properties()` | Step 2 | Prints every attribute the connected object actually has — ground truth over memory. |
| `configure()` | Steps 3–4 | Sets sample rate, RX frequency, bandwidth, buffer size; forces manual gain (disables AGC). |
| `capture()` | Steps 5–6 | Throws away 5 "settling" buffers, then returns one real buffer of samples. |
| `analyze(x)` | Step 6b | Checks the peak amplitude and tells you if it's clipping, too weak, or fine. |
| `cleanup()` | Step 7 | Releases the DMA buffer on the board. |
| `run()` | all of the above | Calls every method above, in order, and prints a final "OK" message. |

---

## How to launch it

**Prerequisites** (same as the rest of this repo):
- Windows laptop, Python 3.11, with `pyadi-iio` and `libiio 0.25` installed
  (see `README.md` → "Python on the laptop" for the conda/pip setup).
- Board powered on, on the network, reachable at `192.168.1.50`.
- Both files (`link_check.py` and `main_link_check.py`) in the **same folder**.

**Run it** (on the **laptop**, in PowerShell, with your `sdr` conda/venv
environment activated):

```powershell
python main_link_check.py
```

That's it — no arguments needed. If you want different settings (a different
sample rate, a different frequency, a different gain), open
`main_link_check.py` and edit the values near the top (`SAMPLE_RATE`, `RX_LO`,
`RX_BUFFER_SIZE`, `RX_GAIN`) rather than touching `link_check.py`.

You can also still run `python link_check.py` directly — it will use the
built-in defaults (same as the originals: 4 MS/s, 100 MHz, 1024 samples,
40 dB gain).

---

## What success looks like

You should see, in order:

1. `Connecting to ip:192.168.1.50 ...`
2. A block of ~4-per-line property names (`Available properties:`).
3. A `Configured:` block showing the sample rate, `rx_lo`, and bandwidth that
   actually got applied.
4. `Got 1024 complex samples, dtype=complex64` (or similar), the first 4
   sample values, and a `|peak| = ...` line.
5. Either `Signal level looks sane.`, a clipping warning, or a "almost
   nothing" warning — this is data-dependent, see below.
6. `OK. The whole chain works.`

If it stops with a Python traceback instead of reaching step 6, the chain is
broken somewhere before your own logic even runs — check the network/SSH/iiod
basics in `README.md` §Quick Start before suspecting your code.

---

## How to test it empirically

"Empirically" means: don't just trust that it printed `OK` — **change a real,
physical thing and confirm the numbers move the way you'd expect.** These
tests are ordered from easiest to most convincing.

### Test 1 — Does it fail correctly when it should?
Temporarily set `URI = "ip:192.168.1.99"` (a wrong address) in
`main_link_check.py` and run it. **Expected:** it should fail to connect and
print a clear error, not hang forever or silently succeed. This proves the
script's error path actually works, not just its happy path. Put the correct
URI back afterward.

### Test 2 — Does the peak respond to gain, the way physics says it should?
Run it once with `RX_GAIN = 20`, note the `|peak|` value, then run it again
with `RX_GAIN = 60`. **Expected:** the second peak should be noticeably
higher than the first (more gain → bigger apparent signal), until it starts
clipping near 2048. If raising the gain does *nothing* to the peak, that's a
real signal — something is wrong (wrong channel, gain not actually applied,
etc.), not just "noise."

### Test 3 — Does the peak respond to a real, known signal?
Your board's RXA port has a **Molex 105263 Series Flexible Cellular 6-Band
Antenna** connected right now (per `HARDWARE_NOTES.md`) — so at the default
`RX_LO = 100e6` (100 MHz), you're sitting inside the FM broadcast band
(88–108 MHz). This gives you a free, real-world test signal:

1. Run the script as-is (100 MHz, gain 40) and note `|peak|`.
2. Change `RX_LO` to something clearly *outside* any broadcast band, e.g.
   `int(200e6)` (200 MHz — no local broadcast service there), and run again.
3. **Expected:** the 100 MHz peak should generally be higher/noisier-looking
   than the 200 MHz "quiet" frequency, because you're picking up real FM
   stations in one case and mostly just noise in the other. This is the
   single best proof that samples are coming from the real world and not
   from some cached/fake value.

*(If your two readings look identical regardless of frequency, that's a
useful failure — it tells you the RF front end, antenna connection, or
`rx_lo` isn't doing what you think, and it's a concrete, testable clue rather
than a vague "it doesn't work."*)*

### Test 4 — Does it agree with an independent tool?
Run **IIO Oscilloscope** (mentioned in `README.md`) pointed at the same board
and same frequency, and compare what it shows against this script's
`|peak|` reading and clipping/weak warnings. **Expected:** the two should
agree in spirit (both see a signal, or both see near-nothing). If the GUI
sees something and this script doesn't (or vice versa), the bug is isolated
to one side — that's exactly the kind of narrowing-down your `AI_CONTEXT.md`
recommends.

### Recording your results
Your project already has a lab notebook convention — add rows to `NOTES.md`
for each test above: date, machine (`laptop`), exact command, expected vs.
observed. That turns "I think it works" into a record you (or an AI
assistant) can check against later.

---

## Things intentionally *not* changed from the original

- The default `rx_lo = 100e6` is left as-is (matching the original tutorial),
  because this script is RX-only and safe regardless. It is **not** the same
  as your project's TX default of 433 MHz (`CONTEXT.md`) — that number only
  matters for scripts that transmit, which this one does not.
- No new IIO attribute names were introduced. Every attribute used
  (`rx_lo`, `sample_rate`, `rx_rf_bandwidth`, `rx_buffer_size`,
  `gain_control_mode_chan0` / `gain_control_mode`,
  `rx_hardwaregain_chan0` / `rx_hardwaregain`, `rx_destroy_buffer`) is taken
  directly from the original script — none were guessed.
