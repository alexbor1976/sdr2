"""
03_siggen.py  --  Run on the LAPTOP.

Two ways to generate a tone:
  mode "dds"    -> the FPGA's hardware DDS makes it. Nothing crosses the network.
  mode "buffer" -> Python makes the samples, DMA loops them forever.

SAFETY: do NOT connect an antenna unless you are licensed for the band.
Use a cable + >=30 dB attenuator into RX1A, or a 50-ohm dummy load.
Start with TX_GAIN_DB very low (-40) and work up.

Usage:  python 03_siggen.py dds
        python 03_siggen.py buffer
"""

import sys
import time
import numpy as np
import adi

URI = "ip:192.168.1.50"
TX_LO = int(100e6)
TX_LO = int(433e6)

TONE_OFFSET = 200e3      # tone appears at TX_LO + TONE_OFFSET
TONE_OFFSET = 000e3      # tone appears at TX_LO + TONE_OFFSET
FS = int(4e6)
TX_GAIN_DB = -40         # dB. Range roughly -89.75 .. 0. Less negative = more power.
# TX_GAIN_DB = -50
N = 2 ** 14
TX_FULL_SCALE = 2 ** 14


def make_sdr():
    try:
        sdr = adi.ad9364(uri=URI)
    except Exception:
        sdr = adi.ad9361(uri=URI)
    sdr.tx_enabled_channels = [0]
    sdr.sample_rate = FS
    sdr.tx_rf_bandwidth = int(FS * 0.8)
    sdr.tx_lo = TX_LO
    try:
        sdr.tx_hardwaregain_chan0 = TX_GAIN_DB
    except AttributeError:
        sdr.tx_hardwaregain = TX_GAIN_DB
    return sdr


def run_dds(sdr):
    # scale is 0..1 of full scale
    sdr.dds_single_tone(TONE_OFFSET, 0.5)
    print(f"FPGA DDS running. Tone at {(TX_LO + TONE_OFFSET)/1e6:.4f} MHz.")
    print("No samples are crossing the network -- the FPGA fabric is making this.")


def run_buffer(sdr):
    # Snap the tone to an exact FFT bin so the cyclic buffer wraps seamlessly.
    # Otherwise there is a discontinuity every N samples -> a click -> spurs.
    f = round(TONE_OFFSET * N / FS) * FS / N
    t = np.arange(N) / FS
    iq = 0.5 * np.exp(2j * np.pi * f * t) * TX_FULL_SCALE

    sdr.tx_cyclic_buffer = True
    sdr.tx(iq)
    print(f"Cyclic buffer TX running. Tone at {(TX_LO + f)/1e6:.4f} MHz "
          f"(snapped from {(TX_LO + TONE_OFFSET)/1e6:.4f}).")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "dds"
    sdr = make_sdr()

    if mode == "dds":
        run_dds(sdr)
    elif mode == "buffer":
        run_buffer(sdr)
    else:
        raise SystemExit("mode must be 'dds' or 'buffer'")

    print("Transmitting. Ctrl-C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            sdr.tx_destroy_buffer()
        except Exception:
            pass
        try:
            sdr.tx_hardwaregain_chan0 = -89
        except Exception:
            pass
        print("\nTX stopped and attenuated.")


if __name__ == "__main__":
    main()

# --- Experiments -------------------------------------------------------------
# 1. Two-tone test: iq = 0.25*exp(2j*pi*f1*t) + 0.25*exp(2j*pi*f2*t)
#    Raise TX_GAIN_DB and watch intermodulation products appear at 2*f1-f2.
#    You have just measured the linearity of the transmit chain.
# 2. Chirp: iq = 0.5*exp(2j*pi*(f0*t + 0.5*k*t**2)) * TX_FULL_SCALE
# 3. Set tx_cyclic_buffer = False and call sdr.tx(iq) in a loop. Look at the
#    spectrum: the gaps between buffers spread energy everywhere.
