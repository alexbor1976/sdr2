# Lab notebook

One row per experiment. Command, expected, observed. Never trust memory.
Paste this file into an AI chat when you're stuck — it is the highest-signal
thing you own.

| Date | Machine | Command | Expected | Observed | Conclusion |
|---|---|---|---|---|---|
|  | laptop | `python link_check.py` | 1024 complex samples, peak 20–1900 |  |  |
|  | laptop | `python loopback_digital.py` | PASS, tone at +200 kHz |  |  |
|  | board  | `for c in /sys/class/gpio/gpiochip*; ...` | base=? ngpio=? |  |  |

## Open questions

- [ ] Is GPIO 963 an EMIO pin (i.e. routed through the FPGA)? See `docs/HARDWARE_NOTES.md`.
- [ ] Does `sdr.loopback` work over the network backend, or only via debugfs on the board?
- [ ] What is the actual maximum sustained sample rate over this Ethernet link?
