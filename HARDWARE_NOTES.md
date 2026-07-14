# Hardware notes — ADRV9364-Z7020 on ADRV1CRR-BOB

> Based on `https://github.com/alexbor1976/spectrumAnalyzerTutorial` (original project). See its README for the phase-by-phase build log this one grew out of.
>
> See also: `CONTEXT.md` for current project status and repo layout,
> `LAB.md` for the full experiment log these findings are drawn from.

Board-specific truths that are not in any generic tutorial, and that no AI
model reliably knows. Keep this file updated; it is the most valuable thing
in the repo.

---

## Current RF configuration (read this before anything else)

**This is no longer an empty-SMA-ports setup.** Earlier notes below (and any
old chat history) that assume "both ports empty, digital loopback only" are
**stale** — antennas are now physically connected:

| Port | Antenna |
|---|---|
| RXA | Molex 105263 Series Flexible Cellular 6-Band Antenna |
| TXA | Siretta Delta 2 Series Right-Angle Stubby Antenna |

**Confirmed, not just theoretical:** a 2026-07-14 `LinkChecker` run at
`rx_lo = 100 MHz` captured a real signal — an FFT of the saved buffer shows
a strong, narrow tone ≈99.0 MHz (~24× the noise floor), consistent with an
FM broadcast station coming in on the Molex antenna. See `LAB.md` for the
full row. This is direct evidence the antenna is live and receiving, not
just physically present.

Consequences:

- `loopback_rf_cable.py`-style tests now radiate for real — this is **not** a
  bench-safe digital-only setup anymore. Treat every TX buffer as a real
  transmission.
- `siggen.py` generator frequency has been changed from the tutorial's
  100 MHz to **433 MHz** (checked for legal use in this band/region). If you
  copy code from the original project, check every hardcoded `TX_LO` /
  `CENTER` — the old files default to 100 MHz.
- Keep `tx_hardwaregain_chan0` conservative (large negative = more
  attenuation) until you've measured actual radiated power. The "-89, always
  attenuate on exit" habit from the original scripts still applies here — if
  anything, it matters *more* now that there's a real antenna to radiate
  from, and now that RX has confirmed the antenna genuinely couples to the
  outside world in the first place.

---

## The user LEDs (DS3–DS6)

### Quirk 1 — three of the four LEDs are not connected

DS4, DS5 and DS6 (labelled LED1–LED3) are **not physically routed to the
processor** on the ADRV9364-Z7020 module. No amount of software will light them.

Only **DS3 (LED0)** is controllable. It is red.

### Quirk 2 — the pin is stolen by a device-tree bug

DS3's copper trace goes to **raw GPIO 963**.

The default Analog Devices Linux device tree mistakenly assigns pin 963 to the
`gpio-keys` driver, labelling it a "Down" button. The kernel therefore claims
the pin as an **input with an active IRQ listener**.

Consequences:

- `/sys/class/leds/` shows LED entries, but writing to them does nothing.
- `echo 963 > /sys/class/gpio/export` fails with **`Device or resource busy`**.

### The workaround

Forcefully unbind `gpio-keys` to release the pin, then export it and drive it
manually. **The device tree is restored on every reboot, so this must run once
per boot cycle.**

```bash
# 1. Unbind the rogue button driver to release pin 963
for dir in /sys/bus/platform/drivers/gpio-keys/*; do
    if [ -d "$dir" ]; then
        echo $(basename "$dir") > /sys/bus/platform/drivers/gpio-keys/unbind 2>/dev/null
    fi
done

# 2. Export the raw LED0 pin
echo 963 > /sys/class/gpio/export

# 3. Set direction to output
echo out > /sys/class/gpio/gpio963/direction
```

Then:

```bash
echo 1 > /sys/class/gpio/gpio963/value    # ON
echo 0 > /sys/class/gpio/gpio963/value    # OFF
```

All of the above requires root.

Packaged as [`scripts/led_init.sh`](scripts/led_init.sh) (run on the board)
and [`scripts/led.py`](scripts/led.py) (drive it from the laptop over SSH).
*(Paths updated for the current flat repo layout — see `CONTEXT.md`'s Repo
Layout section. Not yet created as of 2026-07-14.)*

### To make it survive reboots

Either drop `led_init.sh` into a systemd unit, or fix the cause: edit the device
tree source to remove the bogus `gpio-keys` "Down" entry and add a proper
`gpio-leds` node. The latter is a good, low-risk first encounter with device
trees. The unbind hack is fine until then.

---

## Open question: does GPIO 963 pass through the FPGA?

**Hypothesis, not yet verified.**

Zynq-7000 PS GPIO is laid out as:

| Index | Bank |
|---|---|
| 0 – 53 | MIO — hard pins on the PS |
| 54 – 117 | **EMIO — routed through the PL (FPGA fabric)** |

If the `gpiochip` base for the PS controller is 906 and `ngpio` is 118, then:

```
963 − 906 = 57  →  EMIO pin 3
```

…which would mean DS3's signal **crosses the FPGA fabric** on its way to the
carrier board.

Check it:

```bash
for c in /sys/class/gpio/gpiochip*; do
    echo "$c base=$(cat $c/base) label=$(cat $c/label) ngpio=$(cat $c/ngpio)"
done
```

If it holds, two things follow:

1. You can drive DS3 **directly from HDL** (a counter → a blinker), which
   sidesteps the `gpio-keys` bug entirely rather than working around it. This is
   an excellent, self-contained first FPGA modification: small, visible, and it
   forces you through the whole Vivado → bitstream → boot loop.
2. The LED becomes a legitimate FPGA debug output — a hardware "heartbeat" you
   can see without a UART.

**Record the result of the check here when you run it:**

```
base=            label=            ngpio=
→ 963 is MIO / EMIO pin ___
```

*(Still unverified as of 2026-07-14 — not run yet. Tracked as an open
question in `LAB.md` too.)*

---

## AD9364 loopback modes

Debug attribute `loopback` on `ad9361-phy` (debugfs; needs root).

| Value | Meaning | Radiates? |
|---|---|---|
| `0` | Disabled, normal operation | Yes, when TX is active |
| `1` | Digital TX → Digital RX, **inside the AD9364**, near the internal digital interface block. Entire RF section bypassed. | **No** |
| `2` | RF RX → RF TX. Loops in the ADI HDL core; the chip retransmits whatever it receives. Full RF chain live. | **Yes** |

Use `1`. Never `2` with open SMA ports.

In mode `1`, `rx_lo`, `tx_lo`, `rx_hardwaregain` and `rx_rf_bandwidth` have **no
effect** — the RF section they configure is bypassed. This confuses everyone once.

Fallback if pyadi can't reach the debug attribute over the network:

```bash
grep "" /sys/bus/iio/devices/iio:device*/name    # find which one is ad9361-phy
echo 1 > /sys/kernel/debug/iio/iio:deviceN/loopback
```

---

## IIO device names on this board

```bash
grep "" /sys/bus/iio/devices/iio:device*/name
```

Expect roughly:

| Name | Role |
|---|---|
| `ad9361-phy` | The transceiver control device. All the RF attributes live here. |
| `cf-ad9361-lpc` | RX data device (the DMA stream into DDR) |
| `cf-ad9361-dds-core-lpc` | TX data device, and the FPGA's hardware DDS |
| `xadc` | Zynq's internal voltage/temperature ADC |

If `ad9361-phy` is missing, the FPGA bitstream or device tree did not load.
Stop and fix that; nothing else will work.

---

## Numbers worth remembering

| | |
|---|---|
| AD9364 tuning range | 70 MHz – 6 GHz |
| Sample rate | up to 61.44 MS/s (complex) |
| RX ADC full scale | ≈ ±2048 (12-bit) → divide by `2**11` |
| TX DAC full scale | `2**14` in pyadi convention |
| `tx_hardwaregain_chan0` | attenuation in dB, roughly −89.75 … 0 |
| `rx_hardwaregain_chan0` | gain in dB, roughly −3 … 71 (depends on band) |
| Analog filter corner | ~80 % of the sample rate — distrust the outer 20 % of the span |
| Ethernet ceiling | ~5 MS/s continuous (`5e6 × 2 × 2 B` ≈ 160 Mbit/s) |
| IIO network port | TCP 30431 |
| Kuiper default login | `analog` / `analog` |
| RX sample dtype (observed) | `complex128` in practice on this board/library combo — **do not assume `complex64`**, see log below |

---

## Log of things that bit us

Append here. Date, symptom, cause, fix. Future-you will be grateful, and it is
the single most useful thing to paste into an AI chat when stuck.

| Date | Symptom | Cause | Fix |
|---|---|---|---|
| 2026-07-14 | Captured buffer's `dtype` was `complex128`, not the `complex64` assumed in early draft docs/scripts | Not actually investigated — just observed on this pyadi-iio/libiio 0.25 combo. Possibly a version/library default, not a hardware fact. | No fix needed — code that hardcodes `complex64` (e.g. for FFT sizing or memory pre-allocation) will misbehave. Always read `x.dtype` off the actual captured array instead of assuming. |
| | | | |
