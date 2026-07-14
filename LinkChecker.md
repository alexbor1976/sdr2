# `LinkChecker` — what it is, how to run it, how to test it

Rewrite of the original `link_check.py` (from the `spectrumAnalyzerTutorial`
project this repo grew from), split into three files. Behavior is unchanged
from the original — same steps, same order.

| File | Runs on | What it is |
|---|---|---|
| `Settings.py` | — | The `Settings` class: shared config, as **class attributes** (`Settings.uri`, not `settings_instance.uri`). Edit rarely. |
| `LinkChecker.py` | — | The `LinkChecker` class: the logic. Reads `Settings.*` directly. Edit rarely. |
| `main.py` | **laptop** | Entry point. **Edit this one** if you want different values for a specific run. |

All three files must be in the same folder.

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

## The `Settings` pattern: shared class attributes, not an object you pass around

`Settings` is never instantiated. Nothing ever does `Settings()`. Instead,
every value is a **class attribute**, and any file just imports the class
and reads off it directly:

```python
from Settings import Settings
print(Settings.uri)          # "ip:192.168.1.50"
```

`LinkChecker` does the same internally — it is never handed a settings
object in its constructor. It just does `from Settings import Settings` at
the top of the file and reads `Settings.sample_rate`, `Settings.rx_lo`, etc.
wherever it needs them.

**Why this shape, specifically:**
- One shared class, not one-instance-per-script, means every script in this
  project (today: `LinkChecker.py`; later: maybe `spectrum_live.py`,
  `siggen.py`) reads the *same* values, from the *same* place.
- No constructor arguments. As this project grows, `Settings` could hold
  dozens or hundreds of values — a constructor with that many parameters
  becomes unreadable fast. Class attributes, each with its own comment,
  scale better and stay easy to scan.
- To change a value for one run, reassign it directly, e.g. in `main.py`:
  ```python
  Settings.rx_lo = int(200e6)
  ```
  This changes it for every file that reads `Settings` afterward, for the
  rest of that program's execution — including inside `LinkChecker`.

### `Settings` — every current field, in plain terms

| Field | Meaning | Default |
|---|---|---|
| `Settings.uri` | Network address of the board's IIO server | `"ip:192.168.1.50"` |
| `Settings.sample_rate` | Samples/second captured (Hz) | 4,000,000 |
| `Settings.rx_lo` | Receive center frequency (Hz) | 100,000,000 (100 MHz, inside FM broadcast) |
| `Settings.rx_buffer_size` | Samples returned per `sdr.rx()` call | 1024 |
| `Settings.rx_hardwaregain` | Fixed manual receive gain (dB) | 40 |
| `Settings.discard_buffers` | "Settling" buffers thrown away after retuning | 5 |
| `Settings.results_dir` | Folder where each run's data gets saved | `"results"` |

Two class methods live on `Settings` too (called as `Settings.method()`,
same as the fields):
- `Settings.timestamped_run_id()` — builds a filename-safe timestamp.
- `Settings.ensure_results_dir()` — creates `results_dir` if missing.

### `LinkChecker` — methods, same order as the original script

| Method | Original step | What it does |
|---|---|---|
| `connect()` | 1 | Opens the network connection; tries `ad9364`, falls back to `ad9361`. |
| `print_properties()` | 2 | Prints every attribute the connected object actually has. |
| `configure()` | 3–4 | Applies `Settings.*` to the radio; forces manual gain (disables AGC). |
| `capture()` | 5–6 | Discards `Settings.discard_buffers` buffers, returns one real one. |
| `analyze(x)` | 6b | Checks peak amplitude: clipping / too weak / sane. |
| `cleanup()` | 7 | Releases the DMA buffer. |
| `save_report()` | *(new)* | Saves samples + a JSON summary to `Settings.results_dir`. |
| `run()` | all | Calls every method above, in order. |

---

## How to launch it

**Prerequisites**: `pyadi-iio` + `libiio 0.25` on the laptop (see
`README.md`), board powered on and reachable at `192.168.1.50`.

**Run it** (on the **laptop**, with your `sdr` environment activated):

```powershell
python main.py
```

To change settings for a given run, either edit the defaults directly in
`Settings.py`, or override them in `main.py` before `checker.run()`:

```python
Settings.rx_lo = int(200e6)
Settings.rx_hardwaregain = 30
```

You can still run `python LinkChecker.py` directly (it will just use
whatever is currently set in `Settings.py`).

---

## Why saving results matters, and what gets saved

Your `AI_CONTEXT.md` / `CONTEXT.md` already say "ground truth beats memory"
and ask you to paste real command output into AI chats. A saved report is
exactly that — a file you (or an AI assistant reading it) can trust, instead
of retyping "I think the peak was around 800" from memory. It also lets you
compare today's run against a known-good run from the past without needing
the board connected at that moment.

Each `checker.run()` creates two files inside `results/`:

```
results/
├── 2026-07-14_193045_samples.npy    ← the full raw complex sample buffer
└── 2026-07-14_193045_report.json    ← settings used + a short summary
```

- **`*_samples.npy`** — load later with:
  ```python
  import numpy as np
  x = np.load("results/2026-07-14_193045_samples.npy")
  ```
- **`*_report.json`** — small and safe to paste straight into an AI chat:
  ```json
  {
    "run_id": "2026-07-14_193045",
    "uri": "ip:192.168.1.50",
    "sample_rate_hz": 4000000,
    "rx_lo_hz": 100000000,
    "rx_buffer_size": 1024,
    "rx_hardwaregain_db": 40,
    "peak": 842.0,
    "num_samples": 1024,
    "dtype": "complex64",
    "first_4_samples": ["(12+5j)", "(-3+9j)", "(7-2j)", "(1+1j)"],
    "samples_file": "results/2026-07-14_193045_samples.npy"
  }
  ```

---

## How to test it empirically

### Test 1 — Does it fail correctly when it should?
Set `Settings.uri = "ip:192.168.1.99"` (wrong address) temporarily in
`main.py` and run it. **Expected:** a clear connection error, not a hang or
silent success. Revert afterward.

### Test 2 — Does the peak respond to gain, the way physics says it should?
Run once with `Settings.rx_hardwaregain = 20`, note the `peak` in the saved
JSON, then run again with `Settings.rx_hardwaregain = 60`. **Expected:** the
second run's `peak` should be clearly higher, until it clips near 2048.

### Test 3 — Does the peak respond to a real, known signal?
Your RXA port has a **Molex 105263** antenna connected (`HARDWARE_NOTES.md`),
so at the default `Settings.rx_lo = 100e6` you're inside the FM broadcast
band (88–108 MHz) — a free real-world test signal.

1. Run as-is (100 MHz), note `peak`.
2. Set `Settings.rx_lo = int(200e6)` (outside any broadcast band), run again.
3. **Expected:** the 100 MHz run's `peak` should generally read
   higher/noisier than the 200 MHz "quiet" run.

*(Identical readings at both frequencies is itself a useful clue — it points
at the antenna connection or `rx_lo` handling, not at "the code is broken"
in general.)*

### Test 4 — Does it agree with an independent tool?
Point **IIO Oscilloscope** at the same board/frequency and compare against
the saved `peak` and clipping/weak warnings. **Expected:** agreement in
spirit — both see a signal, or both see near-nothing.

### Recording results
Still add a row to `NOTES.md` for each test (date, machine, command,
expected vs. observed). The JSON is the *raw* ground truth; `NOTES.md` is
your *narrative* of what you were testing and why.

---

## Things intentionally unchanged from the original

- `rx_lo` default stays `100e6`, matching the original tutorial — RX-only,
  unaffected by the project's TX default of 433 MHz noted in `CONTEXT.md`.
- No new IIO attribute names were introduced anywhere. Every attribute used
  (`rx_lo`, `sample_rate`, `rx_rf_bandwidth`, `rx_buffer_size`,
  `gain_control_mode_chan0` / `gain_control_mode`,
  `rx_hardwaregain_chan0` / `rx_hardwaregain`, `rx_destroy_buffer`) comes
  directly from the original script — none were guessed.
