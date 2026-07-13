"""
02_spectrum_live.py  --  Run on the LAPTOP.

A live spectrum analyzer in ~60 lines.
Try CENTER=100e6 with a wire in RX1A: you should see FM broadcast stations.

Controls: close the window to stop.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import adi

URI = "ip:192.168.1.50"
CENTER = int(100e6)   # Hz  -- centre of the displayed band
# CENTER = int(433e6)

FS = int(4e6)         # Hz  -- displayed bandwidth (also the sample rate)
N = 4096              # FFT size. RBW = FS/N  ~= 977 Hz here.
GAIN_DB = 40
AVG = 4               # power-average this many FFTs. Smooths the noise floor.

FULL_SCALE = 2 ** 11  # 12-bit ADC


def make_sdr():
    try:
        sdr = adi.ad9364(uri=URI)
    except Exception:
        sdr = adi.ad9361(uri=URI)
    sdr.rx_enabled_channels = [0]
    sdr.sample_rate = FS
    sdr.rx_rf_bandwidth = int(FS * 0.8)
    sdr.rx_lo = CENTER
    sdr.rx_buffer_size = N
    try:
        sdr.gain_control_mode_chan0 = "manual"
        sdr.rx_hardwaregain_chan0 = GAIN_DB
    except AttributeError:
        sdr.gain_control_mode = "manual"
        sdr.rx_hardwaregain = GAIN_DB
    for _ in range(5):
        sdr.rx()          # flush settling buffers
    return sdr


# Hann window. Coherent gain correction keeps a full-scale tone at 0 dBFS.
win = np.hanning(N)
cg = win.sum() / N
freqs = (np.fft.fftshift(np.fft.fftfreq(N, 1 / FS)) + CENTER) / 1e6  # MHz


def psd_dbfs(sdr):
    """Capture AVG buffers, average in POWER (never in dB), return dBFS."""
    acc = np.zeros(N)
    for _ in range(AVG):
        x = np.asarray(sdr.rx()) / FULL_SCALE
        X = np.fft.fftshift(np.fft.fft(x * win))
        acc += np.abs(X) ** 2
    acc /= AVG
    return 10 * np.log10(acc / (N * cg) ** 2 + 1e-20)


def main():
    sdr = make_sdr()

    fig, ax = plt.subplots(figsize=(11, 5))
    (line,) = ax.plot(freqs, psd_dbfs(sdr), lw=0.8)
    ax.set_xlim(freqs[0], freqs[-1])
    ax.set_ylim(-110, 0)
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Power (dBFS)")
    ax.set_title(f"Spectrum  |  centre {CENTER/1e6:g} MHz  span {FS/1e6:g} MHz  RBW {FS/N:.0f} Hz")
    ax.grid(alpha=0.3)

    def update(_):
        line.set_ydata(psd_dbfs(sdr))
        return (line,)

    ani = FuncAnimation(fig, update, interval=50, blit=True, cache_frame_data=False)
    plt.tight_layout()
    plt.show()

    sdr.rx_destroy_buffer()


if __name__ == "__main__":
    main()

# --- Experiments -------------------------------------------------------------
# 1. Set N = 1024, then 65536. Watch RBW change. Why does the noise floor look
#    lower with a bigger N? (Hint: each bin collects less noise bandwidth.)
# 2. Set AVG = 1 vs AVG = 32. The tone stays put; the grass calms down.
# 3. Replace np.hanning(N) with np.ones(N). Transmit a tone (03_siggen.py) and
#    watch it smear across the whole plot. That is spectral leakage.
# 4. The permanent spike at exactly CENTER is LO leakage / DC offset, not a signal.
