# Lab notebook

One row per experiment. Command, expected, observed. Never trust memory.
Paste this file into an AI chat when you're stuck — it is the highest-signal
thing you own.

| Date | Machine | Command | Expected | Observed | Conclusion |
|---|---|---|---|---|---|
| 2026-07-14 | laptop | `python main.py` | Connects, no traceback, peak in the "sane" range (20 < peak < 1900) | Connected OK. `peak = 99.36` (from `results/2026-07-14_111211_report.json`). Full run saved to `results/2026-07-14_111211_*`. | **Phase 1 (link check) PASSES.** Whole chain confirmed: laptop → Ethernet → iiod → ad9361/ad9364 driver → FPGA DMA → Python. |
| 2026-07-14 | laptop | (analysis of `2026-07-14_111211_samples.npy`, offline) | If this is real RF and not just noise, expect a non-flat spectrum | FFT shows one dominant, narrow tone at **≈ −996 kHz from the 100 MHz LO (≈ 99.0 MHz)**, magnitude ~8943 vs. a median bin magnitude of ~372 (~24×) | Strong evidence the RXA antenna (Molex 105263) is genuinely receiving something real off-air, not just internal noise — good independent confirmation of `HARDWARE_NOTES.md` Test 3. Worth checking 99.0 MHz against a local FM station list to confirm what it is. |
| 2026-07-14 | laptop | (dtype check of same capture) | Assumed `complex64` (typical pyadi-iio default, per draft docs) | Actual `dtype` returned was `complex128` | Not a bug — script works fine either way — but **don't hardcode an assumption of complex64** in future scripts (e.g. FFT size / memory calculations). Verify with `x.dtype` instead of assuming. |
|  | laptop | `python link_check.py` | PASS, tone at +200 kHz |  |  |
|  | board  | `for c in /sys/class/gpio/gpiochip*; ...` | base=? ngpio=? |  |  |

## Open questions

- [x] ~~Does the whole laptop→board→radio chain work at all?~~ **Answered 2026-07-14: yes.** See row above.
- [ ] Is GPIO 963 an EMIO pin (i.e. routed through the FPGA)? See `HARDWARE_NOTES.md`. Still not run.
- [ ] Does `sdr.loopback` work over the network backend, or only via debugfs on the board?
- [ ] What is the actual maximum sustained sample rate over this Ethernet link?
- [ ] What FM station (if any) sits at ≈99.0 MHz locally? Would confirm the FFT peak found in the 2026-07-14_111211 capture is a known real broadcast, not e.g. a spur or interference source.
