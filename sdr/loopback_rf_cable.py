"""
loopback_rf_cable.py  --  Run on the LAPTOP. Run this AFTER loopback_digital.py passes.

Real RF: TX1A --[ >= 30 dB attenuator ]--> RX1A, via coax.

    python loopback_rf_cable.py

SAFETY
------
  * You need a physical attenuator. The AD9364 TX can put out around +7 dBm;
    the RX input is happy well below that. Direct TX->RX coax with no pad is
    how people kill receivers.
  * Do not substitute an antenna for the cable unless you are licensed for the
    band. If you have no attenuator, stop and use loopback_digital.py instead.
  * This script explicitly sets `loopback = 0`. It never uses `loopback = 2`
    ("RF RX -> RF TX"), which makes the chip retransmit whatever it hears and
    keeps the full RF chain live -- unsafe with open ports.

WHY THIS IS THE SECOND TEST, NOT THE FIRST
------------------------------------------
loopback_digital.py already proved Python / libiio / iiod / driver / DMA / FPGA
all work. So if THIS script fails, the fault is in the RF domain and nowhere
else: cable, attenuator, port choice, LO settings, gain. You have halved the
search space before touching a screwdriver. That is the whole point of
bisecting a system.
"""

import numpy as np
import matplotlib.pyplot as plt
import adi

URI = "ip:192.168.1.50"
LO = int(1000e6)     # 1 GHz. Both TX and RX tune here.
FS = int(4e6)
N = 4096
TONE = 200e3
TX_GAIN_DB = -30     # dB attenuation. Start low (more negative). Raise carefully.
RX_GAIN_DB = 30      # dB. Manual, so amplitudes are comparable between runs.

RX_FULL_SCALE = 2 ** 11
TX_FULL_SCALE = 2 ** 14


def main():
    try:
        sdr = adi.ad9364(uri=URI)
    except Exception:
        sdr = adi.ad9361(uri=URI)

    sdr.sample_rate = FS
    sdr.rx_lo = LO
    sdr.tx_lo = LO
    sdr.rx_rf_bandwidth = int(FS * 0.8)
    sdr.tx_rf_bandwidth = int(FS * 0.8)
    sdr.rx_buffer_size = N
    sdr.rx_enabled_channels = [0]
    sdr.tx_enabled_channels = [0]

    try:
        sdr.gain_control_mode_chan0 = "manual"
        sdr.rx_hardwaregain_chan0 = RX_GAIN_DB
        sdr.tx_hardwaregain_chan0 = TX_GAIN_DB
    except AttributeError:
        sdr.gain_control_mode = "manual"
        sdr.rx_hardwaregain = RX_GAIN_DB
        sdr.tx_hardwaregain = TX_GAIN_DB

    # Full RF chain, no internal loopback of any kind.
    try:
        sdr.loopback = 0
    except Exception:
        pass

    f = round(TONE * N / FS) * FS / N          # snap to an FFT bin: seamless wrap
    t = np.arange(N) / FS
    sdr.tx_cyclic_buffer = True
    sdr.tx(0.5 * np.exp(2j * np.pi * f * t) * TX_FULL_SCALE)

    for _ in range(10):
        sdr.rx()

    x = np.asarray(sdr.rx()) / RX_FULL_SCALE
    win = np.hanning(N)
    cg = win.sum() / N
    p = 20 * np.log10(np.abs(np.fft.fftshift(np.fft.fft(x * win))) / (N * cg) + 1e-20)
    freqs = np.fft.fftshift(np.fft.fftfreq(N, 1 / FS))

    expected_bin = int(np.argmin(np.abs(freqs - f)))
    search = p.copy()
    search[N // 2 - 3: N // 2 + 4] = -999       # mask LO leakage / DC offset
    found_bin = int(np.argmax(search))

    print(f"\n  expected tone at   {f/1e3:8.3f} kHz offset (bin {expected_bin})")
    print(f"  strongest peak at  {freqs[found_bin]/1e3:8.3f} kHz offset (bin {found_bin})")
    print(f"  peak level         {p[found_bin]:8.1f} dBFS")
    print(f"  median noise       {np.median(p):8.1f} dBFS")
    print(f"  SNR (rough)        {p[found_bin]-np.median(p):8.1f} dB")
    print(f"  |peak| raw         {np.abs(x).max()*RX_FULL_SCALE:8.0f} / {RX_FULL_SCALE}")

    if abs(found_bin - expected_bin) <= 2:
        print("\nPASS -- the RF chain works end to end.")
    else:
        print("\nFAIL. Digital loopback already passed, so look only at RF:")
        print("  * Nothing but the DC/LO spike -> cable in the wrong SMA, or")
        print("    TX_GAIN_DB too low. Raise it 10 dB at a time.")
        print("  * Flat-topped, wide, ugly peak -> clipping. Lower RX_GAIN_DB.")
        print("  * Tone present but 40 dB down -> too much attenuation in the pad.")

    sdr.tx_destroy_buffer()
    sdr.rx_destroy_buffer()
    try:
        sdr.tx_hardwaregain_chan0 = -89       # leave the TX quiet
    except Exception:
        pass

    plt.figure(figsize=(11, 5))
    plt.plot(freqs / 1e3, p, lw=0.8)
    plt.axvline(f / 1e3, color="r", ls="--", lw=0.8, label="expected tone")
    plt.axvline(0, color="grey", ls=":", lw=0.8, label="LO leakage (not a signal)")
    plt.xlabel(f"Offset from LO = {LO/1e6:g} MHz (kHz)")
    plt.ylabel("dBFS")
    plt.title("RF cable loopback, TX1A -> attenuator -> RX1A")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
