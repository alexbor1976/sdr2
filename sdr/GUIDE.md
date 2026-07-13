# Remote Spectrum Analyzer + Signal Generator
### ADRV9364-Z7020 on ADRV1CRR-BOB — a beginner's build/experiment/debug guide

Target setup: Windows laptop (Python + VS Code) ↔ Ethernet ↔ board at `192.168.1.50` running Analog Devices Kuiper Linux.

---

> **Note on ordering.** This guide was written before the repo was reorganized.
> The recommended order is now: link check → **digital loopback (`loopback_digital.py`,
> no RF, empty SMA)** → spectrum → signal generator → RF cable loopback → board-side
> FFT → FPGA. Do the digital loopback *first*: it proves the entire software chain
> with nothing radiated. See `README.md` for the canonical phase list, and
> `docs/HARDWARE_NOTES.md` for the loopback-mode table.

---

## 0. The mental model (read this first)

Four "computers" are involved. Beginners get lost because they don't know which one a command runs on.

| Layer | What it is | What it does here | You talk to it via |
|---|---|---|---|
| **RF chip** | AD9364 transceiver | Mixes RF ↔ baseband, does the ADC/DAC. 70 MHz – 6 GHz, 1 TX + 1 RX | register writes, hidden behind a driver |
| **FPGA (PL)** | Zynq programmable logic | Grabs I/Q samples from the AD9364's fast digital bus, buffers them, DMAs them to DDR RAM. Also holds a **DDS** (tone generator) for TX | the `axi-ad9361` / DMA IP, exposed as IIO attributes |
| **ARM (PS)** | 2× Cortex-A9 running Kuiper Linux | Runs drivers, and `iiod` — a small network server | SSH, and the IIO protocol on TCP port 30431 |
| **Laptop** | Windows + Python | Asks for samples over Ethernet, does FFT, plots | `pyadi-iio` |

The glue is **IIO** (Linux Industrial I/O). `libiio` lets your laptop pretend the radio is plugged into it locally. `pyadi-iio` is a friendly Python wrapper on top.

```
[AD9364] --fast digital bus--> [FPGA: capture + DMA] --> [DDR RAM]
                                                            |
                                              [ARM Linux: ad9361 driver + iiod]
                                                            |
                                                       Ethernet
                                                            |
                                             [Laptop: pyadi-iio -> numpy -> plot]
```

**Key insight:** you do *not* need to touch the FPGA to build this project. The stock Kuiper image already contains a working FPGA bitstream. Rebuilding the FPGA is Phase 6 — optional, and the hardest part. Do it last, if at all.

---

## ⚠️ RF safety, before anything else

1. **Never transmit into an antenna** unless you know it's legal in your country and band. Use a **coax cable + attenuator** or a **50 Ω dummy load**.
2. When looping TX1A → RX1A with a cable, put **at least 30 dB of attenuation in between**. The TX can output around +7 dBm; the RX input is easily damaged/saturated well below that. A cheap SMA attenuator pack is the best €10 you'll spend.
3. If you have no attenuator: don't cable them. Use the **digital loopback** (Phase 4b) instead, or just leave two antennas a metre apart with TX attenuation set very low (`tx_hardwaregain_chan0 = -60`).
4. Never leave the SMA ports open while transmitting at high power.

---

## Phase 1 — Get a link (30 min)

### 1.1 Network
The board is `192.168.1.50`. Give your laptop a static address in the same subnet:

- Settings → Network → Ethernet → IP assignment → Manual → IPv4 on
- IP `192.168.1.10`, mask `255.255.255.0`, gateway blank

Then, in PowerShell:
```powershell
ping 192.168.1.50
```
No reply? See the debugging playbook (§7, symptom A).

### 1.2 SSH in
Windows 10/11 already has an OpenSSH client:
```powershell
ssh analog@192.168.1.50      # default Kuiper user/pass: analog / analog
```
On the board, check the radio is alive:
```bash
iio_info | head -40
dmesg | grep -i 9361
ls /sys/bus/iio/devices/
```
You should see `ad9361-phy`, `cf-ad9361-lpc` (RX data device), `cf-ad9361-dds-core-lpc` (TX data device). If `ad9361-phy` is missing, the FPGA bitstream or device tree didn't load — nothing else will work until that's fixed.

Also confirm iiod is listening for the network:
```bash
systemctl status iiod        # or: ps aux | grep iiod
```

### 1.3 Laptop toolchain
Two safe options. **Pick one and stick with it.**

**Option A — conda (recommended on Windows).** Installs the C library *and* the bindings together, which avoids the classic Windows DLL error.
```powershell
conda create -n sdr python=3.11
conda activate sdr
conda install -c conda-forge libiio pylibiio pyadi-iio
pip install numpy matplotlib scipy
```

**Option B — plain pip + manual libiio.**
```powershell
py -m venv venv
venv\Scripts\activate
pip install pyadi-iio numpy matplotlib scipy
```
Then download and run the **libiio v0.25 Windows installer** from the ADI libiio GitHub releases page. Do **not** install libiio v1.0 — the Python bindings on PyPI are built for the 0.x API, and mixing them gives errors like `AttributeError: function 'iio_channel_read' not found`. Version mismatch is the #1 install bug people hit.

Sanity check from the laptop:
```powershell
iio_info -u ip:192.168.1.50
python -c "import adi; sdr = adi.ad9364(uri='ip:192.168.1.50'); print(sdr.rx_lo)"
```

### 1.4 Free tools worth installing now
- **IIO Oscilloscope** (ADI, Windows binaries) — a GUI that talks to the same IIO server. Priceless for debugging: if the GUI sees a signal and your Python doesn't, the bug is in your Python.
- **VS Code + Remote-SSH extension** — lets you edit and run code *on the board* as if it were local. You'll want this in Phase 5.
- **Radioconda / GNU Radio + gr-iio** — optional, an alternative front-end for cross-checking.

Run `01_link_check.py` now. It prints the device's capabilities and grabs one buffer.

---

## Phase 2 — Your first spectrum (1 hour)

A spectrum analyzer is only four ideas:

1. **Tune.** Set `rx_lo` (center frequency) and `sample_rate` (how wide a slice you see).
2. **Capture.** `sdr.rx()` returns `rx_buffer_size` complex I/Q samples.
3. **Window + FFT.** Multiply by a Hann window (stops spectral leakage smearing everything), then `np.fft.fft`, then `np.fft.fftshift` so DC lands in the middle.
4. **Log scale.** `20*log10(|X|)`, normalized so full-scale = 0 dBFS.

The x-axis is `rx_lo ± sample_rate/2`. That's it — the "analyzer" is a plot.

Things that will confuse you the first time:

- **Set gain to manual.** With `slow_attack` AGC the amplitudes wander and comparisons are meaningless. Use `gain_control_mode_chan0 = "manual"`, `rx_hardwaregain_chan0 = 40`.
- **Throw away the first few buffers.** The first `rx()` after a retune contains stale/settling data.
- **There is always a spike at the center.** That's LO leakage + DC offset, not a real signal. Everyone rediscovers this.
- **The mirror image.** A weak copy of your tone appears at `-f` relative to center. That's I/Q imbalance. Normal.
- **The edges roll off.** The analog filter is at ~80% of the sample rate. Don't trust the outer 20%.
- **`sdr.rx()` returns raw ADC counts**, roughly ±2048 (12-bit). Divide by `2**11` to get −1…+1.

Run `02_spectrum_live.py`. Point it at a known transmitter first — FM broadcast at 88–108 MHz with any wire in RX1A is the easiest "it works!" moment. Try `CENTER = 100e6`, `FS = 4e6`.

**Beginner experiments:**
- Change `rx_buffer_size` from 1024 → 65536. Watch the noise floor get *smoother* and the resolution get *finer*. Understand why: RBW ≈ `sample_rate / N`.
- Average 10 FFTs (in power, not dB!). The noise floor drops ~5 dB in appearance; the tone doesn't move.
- Swap Hann for a rectangular window and watch a tone smear into a mess.

---

## Phase 3 — Signal generator (1 hour)

Two ways to make a tone. Both are worth doing, because they teach where work happens.

**3a. FPGA DDS (no samples cross the network).**
```python
sdr.tx_lo = int(100e6)
sdr.tx_hardwaregain_chan0 = -30   # dB, range about -89 .. 0
sdr.dds_single_tone(200e3, 0.5)   # 200 kHz offset from tx_lo, half scale
```
Output appears at 100.2 MHz. Nothing streamed — a hardware DDS *inside the FPGA fabric* is generating it. **You just used the FPGA.**

**3b. Buffer TX (samples come from Python).**
```python
N = 2**14
t = np.arange(N) / FS
iq = 0.5 * np.exp(2j*np.pi*200e3*t) * 2**14   # TX full scale is 2**14
sdr.tx_cyclic_buffer = True                    # loop it forever
sdr.tx(iq)
```
This is how you'd send *arbitrary* waveforms: chirps, QPSK, noise. The cyclic buffer must be seamless — make sure your tone completes a whole number of cycles in `N` samples, or you'll transmit a click every buffer (visible as spectral spurs). Use `f = round(f*N/FS) * FS/N`.

Run `03_siggen.py`.

**Beginner experiments:**
- Transmit a two-tone signal at half amplitude each. Sweep `tx_hardwaregain_chan0` up. Watch **intermodulation products** appear at `2f1−f2`. You've just measured amplifier linearity.
- Transmit a chirp. Watch it sweep across your spectrum plot.
- Set `tx_cyclic_buffer = False` and call `tx()` in a loop. Notice the gaps. Understand why cyclic mode exists.

---

## Phase 4 — Close the loop

**4a. RF loopback.** TX1A →[30 dB attenuator]→ RX1A. Set `tx_lo == rx_lo`. You should see your tone at the right offset. Now you have a complete transmit-and-measure instrument.

**4b. Digital loopback (no cable, no RF).** The AD9364 can route TX digital data straight back to RX inside the chip:
```python
sdr.loopback = 1   # 0 = off, 1 = digital TX->RX, 2 = RF loopback
```
This is the single best debugging tool on this board. If digital loopback shows your tone perfectly, then Python, DMA, FPGA and drivers are all fine, and any problem is in the RF/analog domain. If it *doesn't*, the problem is on the digital side. Learn to reach for this first.

Run `04_loopback_test.py`.

---

## Phase 5 — Use the ARM core properly (the "aha" phase)

Right now your laptop pulls raw I/Q over Ethernet. Do the arithmetic:

```
5 MS/s × 2 channels (I,Q) × 2 bytes = 20 MB/s = 160 Mbit/s
```

That works. **61.44 MS/s does not** — it's ~2 Gbit/s. This is the trap every beginner hits: "why does `rx()` stall / why do I get overflow warnings?" Rule of thumb: **for continuous streaming over the network, stay at or below ~5 MS/s.** For bursts (grab one buffer, stop, think, grab another) any rate is fine.

The professional answer is: **don't move the raw data. Move the answer.**

Move the FFT onto the ARM core. The board captures at full rate over `local:` (no network in the path), computes a 4096-point averaged PSD, and sends 4096 floats (~16 KB) to your laptop. That's a 100× reduction. Your laptop just draws.

- Copy `04_board_psd_server.py` to the board (VS Code Remote-SSH makes this trivial, or `scp`).
- On the board: `python3 04_board_psd_server.py` (it uses `uri="local:"`).
- On the laptop: `python 05_laptop_psd_client.py`.

You now have a genuine **remote instrument**: a headless embedded Linux radio serving processed measurements to a thin client. This is exactly how real network analyzers and SDR appliances are architected.

**Bonus: make DS3 mean something.** Wire your LED into the instrument — LED on while the board is capturing. Now you can see from across the room whether the acquisition is running. `led.py` does this from the laptop over SSH; the board-side server can do it directly by writing to `/sys/class/gpio/gpio963/value`.

Remember the init sequence from your notes must run **once per boot** (unbind `gpio-keys`, export 963, set direction out) before any write to `value` works.

---

## Phase 6 — The FPGA (optional, hard, do it last)

Only start this once Phases 1–5 all work. Rebuilding the FPGA image without a working software baseline means you can't tell whether a failure is your fault or the tool's.

**What's already in the bitstream:**
- `axi_ad9361` — the LVDS/CMOS interface to the transceiver, plus TX DDS and PRBS/pattern generators
- `axi_dmac` ×2 — DMA engines pushing RX samples into DDR and pulling TX samples out
- Zynq PS7 block, AXI interconnect, EMIO GPIO

**Free tools:** Vivado ML Edition, **Standard** (free, no licence) supports the xc7z020. That's the part on your SOM.

**Source:** the ADI `hdl` GitHub repo, project `projects/adrv9364z7020/ccbob_lvds`. **You must check out the `hdl` branch that matches your Kuiper release** (e.g. `hdl_2021_r2`, `hdl_2023_r2`). Mismatched HDL/kernel/device-tree is the source of ~90% of "it built but the board doesn't boot" reports.

**Practical advice on Windows:** the ADI build flow is `make`-based and expects a Unix shell. Install **WSL2 + Ubuntu**, install Vivado for Linux inside it, and build there. Fighting Cygwin is not a good use of your first month.

**A gentle first FPGA task** — don't redesign anything. Instead:
1. Open the block design, find `axi_ad9361`, and add an **ILA (Integrated Logic Analyzer)** on the ADC data bus.
2. Rebuild, program, and trigger. You can now literally *watch* the I/Q samples arrive from the chip, in hardware, before Linux ever sees them.

That teaches you more about the data path than any code change would.

**A second, more interesting task, specific to your board.** Your LED is on GPIO 963. Zynq's PS GPIO controller has 54 MIO pins (0–53) followed by 64 **EMIO** pins (54–117), and EMIO pins are wired *through the FPGA fabric*. Check the base:
```bash
for c in /sys/class/gpio/gpiochip*; do echo "$c base=$(cat $c/base) label=$(cat $c/label) n=$(cat $c/ngpio)"; done
```
If the base is 906 and `ngpio` is 118, then `963 − 906 = 57`, i.e. **EMIO pin 3** — meaning DS3's copper wire runs through the PL. *Verify this before believing it.* If it holds, you can drive that LED from FPGA logic (a counter → blinker) instead of from Linux, which is a lovely, self-contained first HDL modification, and it neatly sidesteps the `gpio-keys` device tree bug entirely.

(You could also fix the bug properly by editing the device tree source to remove the bogus `gpio-keys` "Down" entry and add a `gpio-leds` node — a good, low-risk introduction to device trees. The unbind hack is fine for now.)

---

## 7. Debugging playbook

Work **outside-in**: is the network up → is the driver up → is the FPGA up → is the RF right. Change **one thing at a time** and write down what you changed.

| Symptom | Likely cause | What to try |
|---|---|---|
| **A.** `ping` fails | Laptop not in `192.168.1.x`; Windows firewall; cable/link LED | `ipconfig`, `arp -a`, disable firewall on the Ethernet adapter temporarily |
| **B.** `ping` OK, `iio_info -u ip:...` fails | `iiod` not running; libiio version mismatch; firewall blocking TCP 30431 | On board: `systemctl status iiod`. On laptop: `iio_info -V` (want 0.25, **not** 1.0) |
| **C.** `import adi` → `TypeError` / `function 'iio_...' not found` | Windows libiio DLL missing or wrong version | Reinstall via conda-forge, or install the libiio **v0.25** Windows installer |
| **D.** `adi.ad9364(...)` → device not found | Wrong class, or FPGA/device tree not loaded | Try `adi.ad9361`. On board: `ls /sys/bus/iio/devices/`, `dmesg \| grep -i 9361` |
| **E.** `AttributeError: gain_control_mode_chan0` | pyadi version difference | Use `gain_control_mode`. Generally: `print([a for a in dir(sdr) if not a.startswith('_')])` |
| **F.** Spectrum is flat noise, no signal | Gain too low; wrong port (use **RX1A**); antenna not connected; wrong `rx_lo` | Set `rx_hardwaregain_chan0 = 60`; sanity-check with FM broadcast at 100 MHz |
| **G.** Big spike exactly at center | LO leakage / DC offset | Normal. Ignore that bin, or offset-tune (`rx_lo` 500 kHz away from your target) |
| **H.** Spectrum is a flat-topped mess | Clipping — input too strong or gain too high | Lower `rx_hardwaregain_chan0`. Check `abs(rx()).max()` — near 2048 means clipping |
| **I.** `rx()` hangs or throws overflow | Streaming faster than Ethernet | Drop `sample_rate` ≤ 5 MS/s, or move processing to the board (Phase 5) |
| **J.** TX tone appears with spurs every buffer | Non-seamless cyclic buffer | Snap the tone frequency to an FFT bin: `f = round(f*N/FS)*FS/N` |
| **K.** LED write → `Permission denied` / nothing happens | Init sequence not run this boot; not root | Re-run unbind + export + direction. Use `sudo`/root |
| **L.** Everything worked, now nothing does | Board rebooted → device tree reset → LED init gone; or stale Python object holding a buffer | Re-run init. In Python: `sdr.tx_destroy_buffer()`, `sdr.rx_destroy_buffer()`, restart the interpreter |

**Two habits that will save you weeks:**

1. **Bisect the chain.** Digital loopback (`sdr.loopback = 1`) splits the system in half instantly. IIO Oscilloscope splits "is it my Python?" in half instantly. Learn both.
2. **Restart the Python interpreter** whenever the radio behaves oddly. `pyadi-iio` objects hold DMA buffers; a half-dead one wedges the driver. In VS Code, don't reuse the interactive kernel across crashes.

---

## 8. Suggested schedule

| Session | Goal | Done when |
|---|---|---|
| 1 | Ping, SSH, `iio_info`, LED blinks | You can turn DS3 on from the laptop |
| 2 | Python env, first `rx()` | `01_link_check.py` prints 1024 complex samples |
| 3 | Static spectrum plot | You can see FM broadcast |
| 4 | Live spectrum, averaging, waterfall | `02_spectrum_live.py` runs smoothly |
| 5 | DDS tone + buffer tone | `03_siggen.py` |
| 6 | Digital + RF loopback | Tone appears at the predicted bin |
| 7 | Board-side FFT server | `05_laptop_psd_client.py` plots at full rate |
| 8+ | Vivado, ILA, device tree | Optional |

---

## 9. Using AI (me, or any model) efficiently on this project

Where AI is genuinely strong here, and where it will lie to you.

**Strong:**
- **Explaining concepts on demand.** "Why does a Hann window reduce leakage?" "What is a cyclic DMA buffer?" Ask until it clicks. This is the highest-value use, and there's no downside.
- **Writing the boring code.** Plotting, argparse, waterfall buffers, threading a live display. Say what you want; read the result critically.
- **Decoding errors.** Paste the *entire* traceback plus `iio_info -V`, `pip list | findstr iio`, and your OS. Never paraphrase an error — the exact string is the information.
- **Being a rubber duck for debugging.** "TX loopback shows a tone 200 kHz *low*, not high. Here are my settings. What are the five most likely causes, ranked?" Forcing a ranked hypothesis list is much more useful than asking "what's wrong."
- **Reading datasheets with you.** Paste the paragraph, ask what it implies for your configuration.

**Weak — verify, always:**
- **Exact API names, register names, file paths, IIO attribute names, GPIO numbers.** These change between library versions and board revisions. A model will confidently produce a plausible-looking `sdr.some_attribute` that does not exist. Your PDF's `gpio 963` and the `gpio-keys` bug are *exactly* the kind of board-specific detail no model reliably knows. **Ground truth lives on your board**, not in the model:
  ```python
  print([a for a in dir(sdr) if not a.startswith('_')])
  ```
  ```bash
  iio_info -u ip:192.168.1.50   # every device, channel and attribute, verbatim
  ```
- **Version-specific build instructions.** Vivado/HDL/kernel branch pairings. Check the ADI wiki and the repo's release notes; a model's memory of these is stale by definition.
- **Anything numeric it "remembers."** Ask for the derivation, not the number.

**How to prompt well for embedded work:**
1. **Give the model the ground truth.** Paste the output of `iio_info` (or the first 60 lines) and `dir(sdr)` once at the start of a session. Now it's writing against reality instead of memory.
2. **State your layer.** "This runs on the *board*, Python 3.9, `uri='local:'`" vs "this runs on the *laptop*". Half of all bad answers come from the model guessing wrong here.
3. **Ask for one testable step, not a finished system.** "Give me the smallest script that proves the DMA works." Then run it. Then the next.
4. **Ask it to predict before you run.** "What exactly should I see if this is working? What if the cable is bad?" Now the experiment can actually falsify something.
5. **When it gives you code, ask: 'which lines here are you unsure about, and how would I check them on the board?'** Models are reasonably good at flagging their own soft spots when asked directly.
6. **Keep a lab notebook** (a plain `.md` file). Command, expected, observed. Paste it into the model when stuck. It also stops you from re-doing failed experiments.

**Anti-pattern:** asking for a 300-line "complete spectrum analyzer with GUI" up front. You'll get something that almost works, and you'll have no idea which of the 300 lines is wrong. Build it in 20-line increments where each one prints something you can check.

---

## 10. Where to go after it works

- Add a **waterfall** (scrolling 2D history of the PSD) — 15 lines with `imshow` and a rolling numpy array.
- Add **power calibration**: transmit a known tone through a known attenuator, and turn your dBFS axis into dBm.
- Measure a real thing: the **noise figure** of the receiver, or the **frequency error** of the on-board oscillator against a broadcast station.
- Implement an **FM receiver**: capture at 100 MHz, `np.angle(x[1:] * np.conj(x[:-1]))`, decimate, write a `.wav`. Ten lines, and you'll hear the radio.
- Swap the matplotlib front-end for **PyQtGraph** when matplotlib gets too slow (it will, around 20 fps).
