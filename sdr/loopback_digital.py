"""
loopback_digital.py  --  Run on the LAPTOP. This is the FIRST test to run.

Digital loopback INSIDE the AD9364. The signal never leaves the chip.

    python loopback_digital.py

WHAT THIS DOES
--------------
Sets the AD9364 debug attribute `loopback = 1`. Per the ADI driver docs, this
routes the digital TX samples back into the digital RX path *inside the chip*,
close to the internal digital interface block. The entire RF section --
mixers, PA, SMA connectors -- is bypassed. Nothing is radiated.

This means you can leave both SMA ports empty (or, better, capped) and still
exercise the whole chain that matters for software:

    Python -> libiio -> Ethernet -> iiod -> kernel driver -> FPGA DMA
           -> AD9364 digital TX -> [loopback] -> AD9364 digital RX
           -> FPGA DMA -> ... -> back to Python

If the tone lands in the predicted FFT bin, every one of those stages works.
Any later failure is then, by elimination, in the analog/RF domain.

DO NOT USE loopback = 2
-----------------------
`loopback = 2` is "RF RX -> RF TX". It loops in the ADI HDL core and the chip
*actively transmits whatever it receives*. It keeps the full RF chain live.
That is the opposite of what you want with open SMA ports. Value 1 only.

WHAT THIS DOES NOT TEST
-----------------------
Because the RF section is bypassed, the following have NO effect here and tell
you nothing: rx_lo, tx_lo, rx_hardwaregain, rx_rf_bandwidth, antennas, cables.
Do not be surprised when changing rx_lo does nothing. That is the point.

Also note: `loopback` is a *debug* attribute (debugfs). It needs root on the
board. If pyadi cannot reach it over the network, see the fallback at the
bottom of this file.
"""

import numpy as np
import matplotlib.pyplot as plt
import adi

URI = "ip:192.168.1.50"

FS = int(4e6)      # sample rate. In digital loopback this sets the tone scale only.
N = 4096           # FFT size
TONE = 200e3       # baseband tone. In digital loopback it appears at exactly +TONE.
TX_AMPLITUDE = 0.25  # fraction of digital full scale. Keep well below 1.0.

TX_FULL_SCALE = 2 ** 14
RX_FULL_SCALE = 2 ** 11


def open_sdr():
    try:
        return adi.ad9364(uri=URI)
    except Exception:
        return adi.ad9361(uri=URI)


def set_loopback(sdr, value):
    """Returns True on success. Debug attrs need root; iiod usually runs as root."""
    try:
        sdr.loopback = value
        readback = sdr.loopback
        print(f"loopback set to {value}, reads back as {readback}")
        return int(readback) == value
    except Exception as e:
        print(f"\n!! Could not set loopback via pyadi: {e}")
        print("   Fallback -- run this ON THE BOARD as root:")
        print('     grep "" /sys/bus/iio/devices/iio:device*/name   # find ad9361-phy')
        print("     echo 1 > /sys/kernel/debug/iio/iio:deviceN/loopback")
        print("   (replace N with the ad9361-phy device number), then re-run this")
        print("   script with SET_LOOPBACK_HERE = False.\n")
        return False


def main():
    sdr = open_sdr()

    sdr.sample_rate = FS
    sdr.rx_enabled_channels = [0]
    sdr.tx_enabled_channels = [0]
    sdr.rx_buffer_size = N

    # Belt and braces. The RF section is bypassed, but there is no harm in
    # slamming the TX attenuator to its minimum so nothing can leave the chip.
    try:
        sdr.tx_hardwaregain_chan0 = -89
    except AttributeError:
        try:
            sdr.tx_hardwaregain = -89
        except Exception:
            pass

    if not set_loopback(sdr, 1):
        print("Continuing anyway -- if the tone is absent, the loopback is off.")

    # Seamless cyclic tone: snap to an exact FFT bin so the buffer wraps without
    # a discontinuity. Otherwise you transmit a click every N samples.
    f = round(TONE * N / FS) * FS / N
    t = np.arange(N) / FS
    iq = TX_AMPLITUDE * np.exp(2j * np.pi * f * t) * TX_FULL_SCALE

    sdr.tx_cyclic_buffer = True
    sdr.tx(iq)

    for _ in range(10):
        sdr.rx()                       # flush settling buffers

    x = np.asarray(sdr.rx()) / RX_FULL_SCALE

    win = np.hanning(N)
    cg = win.sum() / N
    X = np.fft.fftshift(np.fft.fft(x * win))
    p = 20 * np.log10(np.abs(X) / (N * cg) + 1e-20)
    freqs = np.fft.fftshift(np.fft.fftfreq(N, 1 / FS))

    expected_bin = int(np.argmin(np.abs(freqs - f)))
    search = p.copy()
    search[N // 2 - 3: N // 2 + 4] = -999      # mask DC
    found_bin = int(np.argmax(search))

    print()
    print(f"  |peak| of raw samples   {np.abs(x).max()*RX_FULL_SCALE:8.0f}  (full scale {RX_FULL_SCALE})")
    print(f"  expected tone at        {f/1e3:8.3f} kHz   (bin {expected_bin})")
    print(f"  strongest peak at       {freqs[found_bin]/1e3:8.3f} kHz   (bin {found_bin})")
    print(f"  peak level              {p[found_bin]:8.1f} dBFS")
    print(f"  median noise            {np.median(p):8.1f} dBFS")
    print(f"  SNR (rough)             {p[found_bin]-np.median(p):8.1f} dB")
    print()

    if abs(found_bin - expected_bin) <= 2:
        print("PASS -- the entire digital chain works. Move on with confidence.")
    else:
        print("FAIL. Read this carefully before changing anything:")
        print("  * Peak at the MIRROR bin (-f instead of +f)?")
        print("      -> I and Q are swapped, or the spectrum is inverted.")
        print("  * Peak only at DC, nothing else?")
        print("      -> loopback is probably still 0. Check the readback above.")
        print("  * Pure noise, no peak at all?")
        print("      -> the TX buffer is not reaching the chip. Check tx_cyclic_buffer,")
        print("         and restart Python (a wedged DMA buffer survives a rerun).")
        print("  * Peak in the right place but only ~20 dB SNR?")
        print("      -> lower TX_AMPLITUDE; you may be clipping the digital path.")

    sdr.tx_destroy_buffer()
    sdr.rx_destroy_buffer()
    set_loopback(sdr, 0)               # always leave the chip in a normal state

    plt.figure(figsize=(11, 5))
    plt.plot(freqs / 1e3, p, lw=0.8)
    plt.axvline(f / 1e3, color="r", ls="--", lw=0.8, label="expected tone")
    plt.xlabel("Baseband frequency (kHz)")
    plt.ylabel("dBFS")
    plt.title("AD9364 digital loopback (RF section bypassed, nothing radiated)")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()


# --- Experiments, all completely safe with empty SMA ports --------------------
#
# 1. Set TONE = 1e6 while FS = 4e6. The tone moves to +1 MHz. Now set
#    TONE = 3e6. It appears at -1 MHz. You have just seen aliasing: anything
#    above FS/2 folds back. This is the single most important sampling fact.
#
# 2. Set TX_AMPLITUDE = 0.99, then 1.5. Watch harmonics and a raised noise
#    floor appear as the digital path clips. That is what overdrive looks like.
#
# 3. Replace the tone with noise:  iq = (randn(N) + 1j*randn(N)) * 500
#    The spectrum should be flat. Average 16 buffers and watch it flatten.
#
# 4. Break the seamless-wrap rule on purpose: use f = TONE without the snap.
#    Spurs appear every FS/N. Now you know what a discontinuous cyclic buffer
#    looks like, and you will recognise it instantly when it happens by accident.
#
# 5. Send a QPSK burst: iq = choice([1+1j,1-1j,-1+1j,-1-1j], N) * 4000
#    Recover it: plt.plot(rx.real, rx.imag, '.') -- your first constellation.
