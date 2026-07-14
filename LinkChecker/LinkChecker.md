# `LinkChecker` — what it is, how to run it, how to test it

Rewrite of the original `link_check.py` (from the `spectrumAnalyzerTutorial`
project this repo grew from). Behavior is unchanged from the original — same
steps, same order.

## Where everything lives now

```
sdr2/                         ← project root
├── CONTEXT.md
├── NOTES.md                   ← your personal scratch notes
├── LAB.md                      ← the project's append-only experiment log
├── HARDWARE_NOTES.md
├── Settings.py                  ← SHARED config, used by every script — stays at the root
└── LinkChecker/                  ← this script's own folder
    ├── LinkChecker.py              ← the class (logic)
    ├── main.py                      ← entry point — run this
    ├── LinkChecker.md                 ← this file
    └── results/
        ├── summarize.py                ← prints a one-line-per-run table
        ├── 2026-07-14_111211_report.json
        └── 2026-07-14_111211_samples.npy
```

`Settings.py` lives one level **up** from `LinkChecker/`, since it's shared
by every script in the project (today just `LinkChecker`; later maybe
`SpectrumLive`, `SigGen`, etc.), not owned by any one of them. `main.py`
handles reaching it automatically — see below.

---

## What it proves

Same as the original: that the whole chain works —

```
Your Python  →  libiio  →  Ethernet  →  iiod (on the board)
             →  ad9361/ad9364 driver  →  FPGA DMA  →  back to Python
```

**It only receives (RX). It never transmits** — safe with your antennas
physically connected, since nothing is radiated.

---

## How to launch it

**Prerequisites**: `pyadi-iio` + `libiio 0.25` on the laptop, board powered
on and reachable at `192.168.1.50`.

**Run it** (on the **laptop**, with your `sdr` environment activated):

```powershell
cd LinkChecker
python main.py
```

**Always `cd LinkChecker` first.** Two reasons:
1. `results/` is a path *relative to wherever you launched Python from*. Run
   from inside `LinkChecker/` and results land in `LinkChecker/results/`,
   next to this script, where `summarize.py` expects to find them.
2. `main.py` finds `Settings.py` correctly regardless of your working
   directory (it adds the project root to `sys.path` itself), so this part
   isn't actually required for imports to work — just for `results/` to land
   in a sane place.

To change settings for a given run, either edit the defaults directly in
`Settings.py` (project root), or override them in `main.py` before
`checker.run()`:

```python
Settings.rx_lo = int(200e6)
Settings.rx_hardwaregain = 30
```

---

## `results/summarize.py` — see trends across runs at a glance

Every run writes a `<run_id>_report.json`. Once you have more than one or
two, opening each by hand gets tedious. `summarize.py` scans all of them and
prints a table:

```powershell
cd LinkChecker/results
python summarize.py
```

```
Scanning: LinkChecker/results

run_id                   rx_lo_hz  gain_db       peak  samples
--------------------------------------------------------------
2026-07-14_111211       100000000       40      99.36     1024
```

You can also point it at a different folder without moving it:
```powershell
python summarize.py C:\path\to\some\other\results
```

It's read-only — it never modifies your saved reports, so it's always safe
to run.

---

## Why saving results matters, and what gets saved

`CONTEXT.md` already says "ground truth beats memory." A saved report is
exactly that — a file you (or an AI assistant reading it) can trust, instead
of retyping "I think the peak was around 800" from memory. It also lets you
compare today's run against a known-good run from the past.

- **`*_samples.npy`** — the full raw complex buffer. Load later with:
  ```python
  import numpy as np
  x = np.load("results/2026-07-14_111211_samples.npy")
  ```
- **`*_report.json`** — small and safe to paste straight into an AI chat.

---

## How to test it empirically

### Test 1 — Does it fail correctly when it should?
Set `Settings.uri = "ip:192.168.1.99"` (wrong address) temporarily in
`main.py` and run it. **Expected:** a clear connection error, not a hang or
silent success. Revert afterward.

### Test 2 — Does the peak respond to gain, the way physics says it should?
Run once with `Settings.rx_hardwaregain = 20`, note the `peak`, then run
again with `Settings.rx_hardwaregain = 60`. **Expected:** the second run's
`peak` should be clearly higher, until it clips near 2048. Then run
`summarize.py` and confirm the trend across both rows.

### Test 3 — Does the peak respond to a real, known signal?
Your RXA port has a **Molex 105263** antenna connected (`HARDWARE_NOTES.md`),
so at the default `Settings.rx_lo = 100e6` you're inside the FM broadcast
band (88–108 MHz). This was already confirmed on the 2026-07-14_111211 run —
see `LAB.md` — where the saved capture showed a strong, narrow FFT peak near
99.0 MHz, ~24× the noise floor. To reproduce: set `Settings.rx_lo =
int(200e6)` (outside any broadcast band) and compare peaks.

### Test 4 — Does it agree with an independent tool?
Point **IIO Oscilloscope** at the same board/frequency and compare against
the saved `peak` and clipping/weak warnings. **Expected:** agreement in
spirit — both see a signal, or both see near-nothing.

### Recording results
Add a row to `LAB.md` for each test (date, machine, command, expected vs.
observed) — the JSON is the *raw* ground truth, `LAB.md` is the project's
running record of what was tested and why. Use `NOTES.md` for anything more
personal or half-formed (ideas, reminders, questions to look into later).

---

## Things intentionally unchanged from the original

- `rx_lo` default stays `100e6`, matching the original tutorial — RX-only,
  unaffected by the project's TX default of 433 MHz noted in `CONTEXT.md`.
- No new IIO attribute names were introduced anywhere. Every attribute used
  (`rx_lo`, `sample_rate`, `rx_rf_bandwidth`, `rx_buffer_size`,
  `gain_control_mode_chan0` / `gain_control_mode`,
  `rx_hardwaregain_chan0` / `rx_hardwaregain`, `rx_destroy_buffer`) comes
  directly from the original script — none were guessed.
