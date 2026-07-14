# LAB.md — project experiment log

The whole project's append-only lab notebook. One row per experiment.
Command, expected, observed. **Never edit an old row to "clean it up"** — a
wrong-but-honest entry is more useful later than a tidied one. If you want
to jot down a half-formed idea instead of a completed experiment, that
belongs in `NOTES.md`, not here.

Paste this file into an AI chat when you're stuck — it is the highest-signal
thing you own.

| Date | Machine | Command | Expected | Observed | Conclusion |
|---|---|---|---|---|---|
| 2026-07-14 | laptop | `python main.py` (from `LinkChecker/`) | Connects, no traceback, peak in the "sane" range (20 < peak < 1900) | Connected OK. `peak = 99.36` (from `LinkChecker/results/2026-07-14_111211_report.json`). | **Phase 1 (link check) PASSES.** Whole chain confirmed: laptop → Ethernet → iiod → ad9361/ad9364 driver → FPGA DMA → Python. |
| 2026-07-14 | laptop | (offline analysis of `2026-07-14_111211_samples.npy`) | If this is real RF and not just noise, expect a non-flat spectrum | FFT shows one dominant, narrow tone at **≈ −996 kHz from the 100 MHz LO (≈ 99.0 MHz)**, magnitude ~8943 vs. a median bin magnitude of ~372 (~24×) | Strong evidence the RXA antenna (Molex 105263) is genuinely receiving something real off-air, not just internal noise. Confirms `HARDWARE_NOTES.md` Test 3. Worth checking 99.0 MHz against a local FM station list. |
| 2026-07-14 | laptop | (dtype check of same capture) | Assumed `complex64` (typical pyadi-iio default, per draft docs) | Actual `dtype` returned was `complex128` | Not a bug — works fine either way — but don't hardcode an assumption of `complex64` in future scripts. Verify with `x.dtype` instead of assuming. |
| 2026-07-14 | laptop | `python main.py` (2nd run, same Settings: 100 MHz, 40 dB) | Similar `peak` and same FFT tone location as the first run, if the signal is real and repeatable | `peak = 107.42` (`2026-07-14_125119_report.json`, close to first run's 99.36). FFT dominant tone at ≈ −1031 kHz from LO (≈98.97 MHz), magnitude ratio ~72× median — same neighborhood as the first run's ≈99.00 MHz, ~24× | **Reproducibility confirmed.** Two independent runs land the dominant tone within ~35 kHz (~9 FFT bins) of each other at the same settings — consistent with a real, stable broadcast source, not a one-off fluke or measurement artifact. `summarize.py` now shows both rows side by side. |
|  | laptop | `python link_check.py` (original, pre-rewrite) | PASS, tone at +200 kHz |  |  |
|  | board  | `for c in /sys/class/gpio/gpiochip*; ...` | base=? ngpio=? |  |  |

## Open questions

- [x] ~~Does the whole laptop→board→radio chain work at all?~~ **Answered 2026-07-14: yes.**
- [ ] Is GPIO 963 an EMIO pin (i.e. routed through the FPGA)? See `HARDWARE_NOTES.md`. Still not run.
- [ ] Does `sdr.loopback` work over the network backend, or only via debugfs on the board?
- [ ] What is the actual maximum sustained sample rate over this Ethernet link?
- [ ] What FM station (if any) sits at ≈99.0 MHz locally? Two independent runs (`111211`, `125119`) now confirm a real, repeatable tone in that neighborhood — worth checking against a local FM station list to identify it.
