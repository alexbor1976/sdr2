"""
01_link_check.py  --  Run this on the LAPTOP first.

Proves: network -> iiod -> driver -> FPGA DMA -> Python.
If this works, everything else is just maths.
"""

import numpy as np
import adi

URI = "ip:192.168.1.50"


def main():
    print(f"Connecting to {URI} ...")
    try:
        sdr = adi.ad9364(uri=URI)
    except Exception as e:
        print(f"  ad9364 failed ({e}); trying ad9361 ...")
        sdr = adi.ad9361(uri=URI)

    # ---- Print what this object ACTUALLY exposes. Ground truth beats memory. ----
    print("\nAvailable properties:")
    props = sorted(p for p in dir(sdr) if not p.startswith("_"))
    for i in range(0, len(props), 4):
        print("   " + "  ".join(f"{p:<28}" for p in props[i:i + 4]))

    # ---- Configure ----
    fs = int(4e6)
    sdr.rx_enabled_channels = [0]
    sdr.sample_rate = fs
    sdr.rx_rf_bandwidth = int(fs * 0.8)
    sdr.rx_lo = int(100e6)
    sdr.rx_buffer_size = 1024

    # Manual gain: AGC makes amplitudes wander and comparisons meaningless.
    try:
        sdr.gain_control_mode_chan0 = "manual"
        sdr.rx_hardwaregain_chan0 = 40
    except AttributeError:
        sdr.gain_control_mode = "manual"
        sdr.rx_hardwaregain = 40

    print("\nConfigured:")
    print(f"  sample_rate      = {sdr.sample_rate/1e6:.3f} MS/s")
    print(f"  rx_lo            = {sdr.rx_lo/1e6:.3f} MHz")
    print(f"  rx_rf_bandwidth  = {sdr.rx_rf_bandwidth/1e6:.3f} MHz")

    # ---- Capture. Discard the first few buffers: they contain settling data. ----
    for _ in range(5):
        x = sdr.rx()

    x = np.asarray(sdr.rx())
    peak = np.abs(x).max()

    print(f"\nGot {len(x)} complex samples, dtype={x.dtype}")
    print(f"  first 4: {x[:4]}")
    print(f"  |peak|  = {peak:.0f}  (full scale is about 2048)")

    if peak > 1900:
        print("  !! CLIPPING. Lower rx_hardwaregain_chan0.")
    elif peak < 20:
        print("  !! Almost nothing. Raise the gain, or check the antenna is in RX1A.")
    else:
        print("  Signal level looks sane.")

    sdr.rx_destroy_buffer()
    print("\nOK. The whole chain works.")


if __name__ == "__main__":
    main()
