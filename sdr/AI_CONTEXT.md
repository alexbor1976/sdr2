# AI context block

Paste everything between the `---` markers into a fresh chat with Claude (or any
model) at the start of a session. It gives the model the board-specific facts it
cannot know, and the constraints that keep its answers useful.

Then add whatever you're actually stuck on.

---

## Project context — please read before answering

I am building a remote spectrum analyzer / signal generator. Beginner level.
Explain simply, and tell me which machine each command runs on.

**Hardware**
- SOM: ADRV9364-Z7020 (Xilinx Zynq XC7Z020 + Analog Devices AD9364, 1 TX / 1 RX)
- Carrier: ADRV1CRR-BOB
- OS on the board: Analog Devices Kuiper Linux, login `analog` / `analog`
- Board IP: `192.168.1.50`, IIO network port 30431
- Host: Windows laptop, Python 3.11, VS Code, `pyadi-iio` + `libiio 0.25`
- The stock Kuiper FPGA bitstream is in use. I have **not** rebuilt it in Vivado.

**Architecture**
Laptop (Python, numpy, matplotlib) ⟷ Ethernet ⟷ ARM Cortex-A9 running Kuiper
Linux (`ad9361` driver + `iiod` server) ⟷ FPGA fabric (`axi_ad9361` capture,
`axi_dmac` DMA, hardware DDS) ⟷ AD9364 RF transceiver.

**Board-specific quirks you would not otherwise know**
1. LEDs DS4/DS5/DS6 are **not physically routed** to the processor on this SOM.
   Only DS3 (red, "LED0") is controllable.
2. DS3 is on **raw GPIO 963**. The default ADI device tree wrongly assigns 963 to
   the `gpio-keys` driver as a "Down" button, locking it as an input with an IRQ.
   So `/sys/class/leds/` does nothing and `echo 963 > /sys/class/gpio/export`
   returns `Device or resource busy`. Workaround, run as root **once per boot**:
   unbind every device under `/sys/bus/platform/drivers/gpio-keys/`, then export
   963, then `echo out > /sys/class/gpio/gpio963/direction`.
3. AD9364 `loopback` debug attribute: `0` = off, `1` = digital TX→RX **inside the
   chip** with the RF section bypassed (nothing radiated), `2` = RF RX→TX in the
   HDL core, which **does transmit**. I use `1`. Never `2`.

**Safety constraints I am working under**
- I have no attenuator yet, so both SMA ports are empty. Everything must be
  RF-safe: `loopback = 1`, and `tx_hardwaregain_chan0` pinned at `-89`.
- Do not suggest connecting an antenna.

**How I want you to answer**
- Say explicitly whether code runs on the **laptop** (`uri="ip:192.168.1.50"`) or
  on the **board** (`uri="local:"`). This is the #1 source of wrong answers.
- Give me **one small testable step** at a time, not a finished 300-line program.
  Each step should print something I can check.
- Before I run anything, tell me **what I should see if it works**, and what a
  specific plausible failure would look like.
- Flag which lines you are **unsure about**, and tell me the command that would
  check them on my board.
- Never invent an API name, an IIO attribute, a register or a file path. If you
  are not certain it exists, say so and give me the discovery command instead:
  `print([a for a in dir(sdr) if not a.startswith("_")])` or
  `iio_info -u ip:192.168.1.50`.
- When I report a bug, give me a **ranked list of the most likely causes** and a
  cheap test that distinguishes them — not a single confident guess.

---

## Optional: attach ground truth

The single highest-leverage thing you can do. Run these once per session and
paste the output. Now the model reasons about your board instead of its memory.

**On the laptop:**
```powershell
iio_info -V
iio_info -u ip:192.168.1.50
pip list | findstr /i iio
```

**In Python:**
```python
import adi
sdr = adi.ad9364(uri="ip:192.168.1.50")
print([a for a in dir(sdr) if not a.startswith("_")])
```

**On the board:**
```bash
uname -a
grep "" /sys/bus/iio/devices/iio:device*/name
for c in /sys/class/gpio/gpiochip*; do echo "$c base=$(cat $c/base) label=$(cat $c/label) ngpio=$(cat $c/ngpio)"; done
dmesg | grep -i 9361
```

---

## When you report a bug, include all of these

Half of debugging is refusing to paraphrase.

1. **Which machine** you ran it on.
2. The **exact command** you ran.
3. The **complete traceback**, not a summary of it.
4. What you **expected** to see.
5. What **changed** since the last time it worked.
6. Whether `loopback_digital.py` still passes. (If yes, the bug is in RF or in
   your new code — never in the driver stack. That single fact eliminates most
   of the search space.)

---

## A prompt that works well when stuck

> Here is my ground truth (`iio_info` output attached) and my lab notebook.
> `loopback_digital.py` passes. `loopback_rf_cable.py` shows the tone 200 kHz
> **below** the LO instead of above.
>
> Give me the five most likely causes, ranked by probability, and for each one a
> single cheap test that would confirm or eliminate it. Don't write me a fix yet.

Forcing a ranked, falsifiable list is dramatically more useful than "what's
wrong?" — and it's the part of this work that models are genuinely good at.

---

## What to distrust

Models are strong on concepts, boring code, error triage and hypothesis
generation. They are unreliable on exactly the things this repo documents:

- exact API and IIO attribute names (they drift between library versions)
- GPIO numbers, `gpiochip` bases, file paths
- register names and bitfields
- Vivado / HDL branch / kernel / device-tree version pairings

None of that is in the model's memory with any reliability. **`docs/HARDWARE_NOTES.md`
is the authority. The board is the final authority.**
