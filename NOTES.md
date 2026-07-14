# NOTES.md — personal scratchpad

Unlike `LAB.md` (the structured, append-only project log — one row per
experiment, never edited after the fact), this file is just for you:
half-formed ideas, questions to look into later, reminders, things that
don't fit LAB.md's format. Messy is fine. Nothing here needs to be final,
correct, or dated.

If an idea here turns into an actual experiment, move the *result* into
`LAB.md` as a proper row — this file is where things start, not where they
get recorded once they're real.

---

## instructions for the Cloude Code project's section 'instructions'
- [ ] the hardware configuration is in the attached file 'HARDWARE_NOTES.md'
- [ ] the AI Context is in the attached file 'CONTEXT.md'
- [ ] explain everything in very simple terms, I am a newcomer in many aspects of this project.

## working with the board
- [ ] @REM setup ip for my laptop: 192.168.1.10 
- [ ] @REM setup ip for the board (via PuTTY): ifconfig eth0 192.168.1.50 netmask 255.255.255.0 up
- [ ] @REM check ip of the board: ifconfig eth0
- [ ] @REM connecting to the board (from the VS Terminal): ssh root@192.168.1.50 
- [ ] @REM the psw to the board: analog

## working with the Linux on the board
- [ ] @REM delete all: root@analog:~/led# rm *
- [ ] @REM run all: python3 /root/led/main.py   

## Select the 'sdr' Interpreter for the New Project
- [ ] open the Command Palette; Type Python: Select Interpreter; click on Python 3.11.x ('sdr': conda)
- [ ] Close your current terminal by clicking the Trash Can icon;
- [ ] Open a new terminal by (Terminal > New Terminal).;

## log in time
| Date | Machine | Command | Expected | Observed | Conclusion |
|---|---|---|---|---|---|
|  | laptop | `python link_check.py` | 1024 complex samples, peak 20–1900 |  |  |
|  | laptop | `python loopback_digital.py` | PASS, tone at +200 kHz |  |  |
|  | board  | `for c in /sys/class/gpio/gpiochip*; ...` | base=? ngpio=? |  |  |

## Open questions

- [ ] Is GPIO 963 an EMIO pin (i.e. routed through the FPGA)? See `docs/HARDWARE_NOTES.md`.
- [ ] Does `sdr.loopback` work over the network backend, or only via debugfs on the board?
- [ ] What is the actual maximum sustained sample rate over this Ethernet link?

## Ideas to try later

-

## Questions I keep meaning to look into

- What FM station is actually at ~99.0 MHz here — worth a quick search
  next time I'm online, just to sanity-check the LAB.md finding.

## Reminders to self

- Always `cd LinkChecker` before `python main.py`, or results land in the
  wrong folder.
- Settings.py is shared across the whole project now — don't copy-paste it
  into a new script's folder later, import it instead.

## Random observations (not yet experiments)

-
