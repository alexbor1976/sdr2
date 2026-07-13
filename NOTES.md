# Lab notebook (just for me)

One row per experiment. Command, expected, observed. Never trust memory.
Paste this file into an AI chat when you're stuck — it is the highest-signal
thing you own.

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
