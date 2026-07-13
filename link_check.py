"""
link_check.py -- run this on the LAPTOP (not the board).

Class-based rewrite of the original link_check.py from the
spectrumAnalyzerTutorial project (RX-only "does the whole chain work?"
smoke test). Same purpose, same logic, same order of operations --
just organized as a reusable class instead of one big function, and
commented line-by-line for someone new to SDR / IIO / Python.

Proves: laptop -> Ethernet -> iiod -> ad9361/ad9364 driver -> FPGA DMA
-> Python. If this passes, later failures are in YOUR code/math, not
in the underlying plumbing.

Safe to run even with antennas connected: this script only *receives*
(RX). It never transmits, so there is nothing to radiate.
"""

import numpy as np   # numerical arrays -- sdr.rx() hands us samples as a numpy array
import adi           # pyadi-iio: the friendly Python wrapper around libiio


class LinkChecker:
    """
    Wraps the "prove the link works" steps in a class so each step is a
    separate, individually callable method instead of one long function.

    Typical use:
        checker = LinkChecker(uri="ip:192.168.1.50")
        checker.run()          # does everything, in order, and prints results

    Or call the steps yourself, one at a time, e.g. in a Python shell,
    which is a good way to learn what each step actually does:
        checker = LinkChecker()
        checker.connect()
        checker.print_properties()
        checker.configure()
        samples = checker.capture()
        checker.analyze(samples)
        checker.cleanup()
    """

    def __init__(self, uri="ip:192.168.1.50", sample_rate=int(4e6),
                 rx_lo=int(100e6), rx_buffer_size=1024, rx_hardwaregain=40):
        # --- Every setting lives on the instance (self.xxx) instead of ---
        # --- being hardcoded inside a function. This means you can     ---
        # --- create two LinkChecker objects with different settings    ---
        # --- without touching this file at all.                       ---
        self.uri = uri                          # network address of the board's IIO server
        self.sample_rate = sample_rate           # samples per second to capture at (Hz)
        self.rx_lo = rx_lo                       # receive center frequency (Hz)
        self.rx_buffer_size = rx_buffer_size     # how many I/Q samples one sdr.rx() call returns
        self.rx_hardwaregain = rx_hardwaregain   # fixed receive gain in dB, used once we disable AGC
        self.sdr = None                          # will hold the connected radio object; None until connect() runs

    def connect(self):
        """Step 1 -- open a connection to the radio over the network."""
        print(f"Connecting to {self.uri} ...")     # tell the human what's about to happen
        try:
            # Most ADRV9364-Z7020 boards identify as the 1TX/1RX "ad9364" class.
            self.sdr = adi.ad9364(uri=self.uri)      # try the specific chip class first
        except Exception as e:                        # if the class name doesn't match this board/driver...
            # ...don't just crash -- fall back to the more generic 2x2 base class,
            # which often still works because ad9364 is a subset of ad9361 hardware.
            print(f"  ad9364 failed ({e}); trying ad9361 ...")
            self.sdr = adi.ad9361(uri=self.uri)
        return self.sdr                                # return it too, in case the caller wants direct access

    def print_properties(self):
        """Step 2 -- ground truth beats memory: ask the object what it really supports."""
        if self.sdr is None:                           # guard: this needs a live connection first
            raise RuntimeError("Call connect() before print_properties().")

        print("\nAvailable properties:")
        # dir(self.sdr) lists every attribute and method on the object.
        # We drop the ones starting with "_" -- those are Python-internal, not useful here.
        props = sorted(p for p in dir(self.sdr) if not p.startswith("_"))

        # Print 4 names per line instead of one-per-line, purely for readability.
        for i in range(0, len(props), 4):
            row = props[i:i + 4]                                   # take 4 names at a time
            print("  " + " ".join(f"{p:<28}" for p in row))         # left-pad each into a 28-char column
        return props                                                  # handy if you want to search this list later

    def configure(self):
        """Step 3 & 4 -- set receive parameters, then force manual gain."""
        if self.sdr is None:
            raise RuntimeError("Call connect() before configure().")

        # --- Basic RX (receive) configuration ---
        self.sdr.rx_enabled_channels = [0]                          # use RX channel 0 (this board only has one RX anyway)
        self.sdr.sample_rate = self.sample_rate                      # ADC samples per second
        self.sdr.rx_rf_bandwidth = int(self.sample_rate * 0.8)       # analog filter width; ~80% of sample rate is the safe zone
        self.sdr.rx_lo = self.rx_lo                                    # tune the receiver to this center frequency
        self.sdr.rx_buffer_size = self.rx_buffer_size                  # each sdr.rx() call will return this many samples

        # --- Force manual gain ---
        # AGC (automatic gain control) constantly re-adjusts on its own, which
        # makes "is my signal too big / too small" checks meaningless, because
        # the number you're reading keeps moving underneath you.
        try:
            # Newer pyadi-iio versions expose gain settings with a "_chan0" suffix.
            self.sdr.gain_control_mode_chan0 = "manual"
            self.sdr.rx_hardwaregain_chan0 = self.rx_hardwaregain
        except AttributeError:
            # Older / differently-named versions drop the "_chan0" suffix.
            self.sdr.gain_control_mode = "manual"
            self.sdr.rx_hardwaregain = self.rx_hardwaregain

        # --- Report what actually got applied ---
        # (The radio can silently round or clamp requested values, so we read
        #  the values back from the device instead of trusting what we asked for.)
        print("\nConfigured:")
        print(f"  sample_rate      = {self.sdr.sample_rate/1e6:.3f} MS/s")
        print(f"  rx_lo            = {self.sdr.rx_lo/1e6:.3f} MHz")
        print(f"  rx_rf_bandwidth  = {self.sdr.rx_rf_bandwidth/1e6:.3f} MHz")

    def capture(self, discard_count=5):
        """Step 5 & 6 -- throw away 'settling' buffers, then grab one real one."""
        if self.sdr is None:
            raise RuntimeError("Call connect() before capture().")

        # Right after a retune, the first few buffers contain stale/settling
        # data that hasn't stabilized yet, so we deliberately throw them away.
        for _ in range(discard_count):
            _ = self.sdr.rx()                                          # capture and discard

        # Now grab the buffer we'll actually inspect.
        x = np.asarray(self.sdr.rx())                                    # np.asarray just guarantees a numpy array back
        return x                                                           # complex I/Q samples, raw ADC counts

    def analyze(self, x):
        """Step 6b -- sanity-check the peak amplitude of a captured buffer."""
        peak = np.abs(x).max()                                            # magnitude of the largest sample (|I + jQ|)

        print(f"\nGot {len(x)} complex samples, dtype={x.dtype}")
        print(f"  first 4: {x[:4]}")
        print(f"  |peak| = {peak:.0f} (full scale is about 2048)")

        # --- Interpret the peak for a beginner, in plain language ---
        if peak > 1900:
            print("  !! CLIPPING. Lower rx_hardwaregain_chan0.")
        elif peak < 20:
            print("  !! Almost nothing. Raise the gain, or check the antenna is in RX1A.")
        else:
            print("  Signal level looks sane.")

        return peak                                                        # let the caller assert on this if they want

    def cleanup(self):
        """Step 7 -- free the DMA buffer this checker allocated on the board."""
        if self.sdr is not None:
            self.sdr.rx_destroy_buffer()                                   # tells the driver it can release the RX buffer

    def run(self):
        """Run every step above, in order -- the same order as the original script."""
        self.connect()                  # 1. open the connection
        self.print_properties()         # 2. ground-truth check: what does this object really support?
        self.configure()                # 3 & 4. set parameters, force manual gain
        x = self.capture()              # 5 & 6. discard settling buffers, grab one real one
        self.analyze(x)                 # 6b. sanity-check the peak amplitude
        self.cleanup()                  # 7. free the buffer
        print("\nOK. The whole chain works.")
        return x                          # in case the caller wants to inspect the samples themselves


if __name__ == "__main__":
    # This lets you still run `python link_check.py` directly, with default
    # settings, without needing the separate main script.
    LinkChecker().run()
