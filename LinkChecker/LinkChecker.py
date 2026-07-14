"""
LinkChecker.py -- run this on the LAPTOP (not the board), via main.py.

Class-based rewrite of the original link_check.py from the
spectrumAnalyzerTutorial project (RX-only "does the whole chain work?"
smoke test). Reads its configuration directly from the shared Settings
class (Settings.py, one folder up, at the project root) -- it is never
handed a settings object; it just imports Settings and reads
Settings.whatever wherever it needs a value.

Proves: laptop -> Ethernet -> iiod -> ad9361/ad9364 driver -> FPGA DMA
-> Python. Safe to run with antennas connected: RX-only, never transmits.

Every run also saves its samples + a JSON summary to disk (see
save_report()), so a later script -- or an AI chat -- can be given real
ground truth instead of a re-typed description.
"""

import json               # for writing the small, human-readable summary file
import numpy as np        # numerical arrays -- sdr.rx() hands us samples as a numpy array
import adi                # pyadi-iio: the friendly Python wrapper around libiio

from Settings import Settings   # the shared, class-level settings -- read directly, never passed in
                                  # (main.py adds the project root to sys.path so this import works)


class LinkChecker:
    """
    Wraps the "prove the link works" steps in a class, one method per step.
    Configuration comes from Settings.* directly -- there is no settings
    argument anywhere in this class, by design (see Settings.py's docstring
    for why).
    """

    def __init__(self):
        # Only per-run STATE lives on the instance -- not configuration.
        self.sdr = None            # will hold the connected radio object once connect() runs
        self.last_samples = None   # will hold the most recent capture, used by save_report()
        self.last_peak = None      # will hold the most recent peak value, used by save_report()

    def connect(self):
        """Step 1 -- open a connection to the radio over the network."""
        print(f"Connecting to {Settings.uri} ...")       # read the address straight off Settings
        try:
            # Most ADRV9364-Z7020 boards identify as the 1TX/1RX "ad9364" class.
            self.sdr = adi.ad9364(uri=Settings.uri)
        except Exception as e:                              # class name didn't match this board/driver
            print(f"  ad9364 failed ({e}); trying ad9361 ...")
            self.sdr = adi.ad9361(uri=Settings.uri)            # fall back to the more generic 2x2 base class
        return self.sdr

    def print_properties(self):
        """Step 2 -- ground truth beats memory: ask the object what it really supports."""
        if self.sdr is None:                                  # guard: needs a live connection first
            raise RuntimeError("Call connect() before print_properties().")
        print("\nAvailable properties:")
        props = sorted(p for p in dir(self.sdr) if not p.startswith("_"))   # drop Python-internal names
        for i in range(0, len(props), 4):                      # print 4 per line, just for readability
            row = props[i:i + 4]
            print("  " + " ".join(f"{p:<28}" for p in row))
        return props

    def configure(self):
        """Step 3 & 4 -- apply Settings to the radio, then force manual gain."""
        if self.sdr is None:
            raise RuntimeError("Call connect() before configure().")

        self.sdr.rx_enabled_channels = [0]                          # use RX channel 0 (this board has only one RX)
        self.sdr.sample_rate = Settings.sample_rate                  # ADC samples per second
        self.sdr.rx_rf_bandwidth = int(Settings.sample_rate * 0.8)    # analog filter width; ~80% of sample rate is the safe zone
        self.sdr.rx_lo = Settings.rx_lo                                 # tune the receiver to this center frequency
        self.sdr.rx_buffer_size = Settings.rx_buffer_size                # samples returned per sdr.rx() call

        # AGC (automatic gain control) keeps re-adjusting on its own, which
        # makes "is my signal too big/small" checks meaningless -- so we
        # force a fixed, manual gain instead.
        try:
            self.sdr.gain_control_mode_chan0 = "manual"              # newer pyadi-iio naming
            self.sdr.rx_hardwaregain_chan0 = Settings.rx_hardwaregain
        except AttributeError:
            self.sdr.gain_control_mode = "manual"                     # older/alternate naming
            self.sdr.rx_hardwaregain = Settings.rx_hardwaregain

        # Report what actually got applied -- the device can round/clamp values.
        print("\nConfigured:")
        print(f"  sample_rate      = {self.sdr.sample_rate/1e6:.3f} MS/s")
        print(f"  rx_lo            = {self.sdr.rx_lo/1e6:.3f} MHz")
        print(f"  rx_rf_bandwidth  = {self.sdr.rx_rf_bandwidth/1e6:.3f} MHz")

    def capture(self):
        """Step 5 & 6 -- throw away 'settling' buffers, then grab one real one."""
        if self.sdr is None:
            raise RuntimeError("Call connect() before capture().")
        for _ in range(Settings.discard_buffers):        # discard N buffers right after (re)tuning
            _ = self.sdr.rx()
        x = np.asarray(self.sdr.rx())                       # the buffer we'll actually inspect
        self.last_samples = x                                 # remember it for save_report()
        return x

    def analyze(self, x):
        """Step 6b -- sanity-check the peak amplitude of a captured buffer."""
        peak = np.abs(x).max()                # magnitude of the largest sample (|I + jQ|)
        self.last_peak = float(peak)            # remember it for save_report() (float, so JSON can store it)

        print(f"\nGot {len(x)} complex samples, dtype={x.dtype}")
        print(f"  first 4: {x[:4]}")
        print(f"  |peak| = {peak:.0f} (full scale is about 2048)")

        if peak > 1900:
            print("  !! CLIPPING. Lower rx_hardwaregain_chan0.")
        elif peak < 20:
            print("  !! Almost nothing. Raise the gain, or check the antenna is in RX1A.")
        else:
            print("  Signal level looks sane.")
        return peak

    def cleanup(self):
        """Step 7 -- free the DMA buffer this checker allocated on the board."""
        if self.sdr is not None:
            self.sdr.rx_destroy_buffer()

    def save_report(self):
        """
        Save this run's settings + results to disk, so they can be handed to
        a later script -- or pasted into an AI chat -- as real ground truth
        instead of a re-typed description.

        Writes two files into Settings.results_dir (relative to wherever you
        launched Python from -- run main.py from inside LinkChecker/ to keep
        these next to this script, see LinkChecker.md):
          - <run_id>_samples.npy  -- the full raw complex sample buffer
          - <run_id>_report.json  -- settings used + a small summary (peak,
            first few samples, timestamp): easy to open, read, or paste.
        """
        if self.last_samples is None:                 # guard: nothing captured yet
            raise RuntimeError("Call capture() and analyze() before save_report().")

        Settings.ensure_results_dir()                    # create results/ if it doesn't exist yet
        run_id = Settings.timestamped_run_id()             # e.g. "2026-07-14_193045"

        # --- Save the full raw samples, in case you want to re-analyze them later ---
        samples_path = f"{Settings.results_dir}/{run_id}_samples.npy"
        np.save(samples_path, self.last_samples)             # numpy's native binary format

        # --- Save a small JSON summary: settings used + key results ---
        report = {
            "run_id": run_id,
            "uri": Settings.uri,
            "sample_rate_hz": Settings.sample_rate,
            "rx_lo_hz": Settings.rx_lo,
            "rx_buffer_size": Settings.rx_buffer_size,
            "rx_hardwaregain_db": Settings.rx_hardwaregain,
            "peak": self.last_peak,
            "num_samples": len(self.last_samples),
            "dtype": str(self.last_samples.dtype),
            "first_4_samples": [str(v) for v in self.last_samples[:4]],
            "samples_file": samples_path,
        }
        report_path = f"{Settings.results_dir}/{run_id}_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)                    # indent=2 keeps it readable if opened by hand

        print(f"\nSaved report  -> {report_path}")
        print(f"Saved samples -> {samples_path}")
        return report_path, samples_path

    def run(self):
        """Run every step above, in order, and save a report at the end."""
        self.connect()                  # 1. open the connection
        self.print_properties()         # 2. ground-truth check
        self.configure()                # 3 & 4. apply Settings, force manual gain
        x = self.capture()              # 5 & 6. discard settling buffers, grab one real one
        self.analyze(x)                 # 6b. sanity-check the peak amplitude
        self.cleanup()                  # 7. free the buffer
        self.save_report()              # 8. write results to disk for later reuse
        print("\nOK. The whole chain works.")
        return x


if __name__ == "__main__":
    # Lets you still run `python LinkChecker.py` directly, using whatever
    # values are currently set in Settings.py, without needing main.py.
    # Note: this direct-run path does NOT get main.py's sys.path fix, so it
    # only works if Settings.py happens to be importable already (e.g. you
    # ran it from the project root with the root on PYTHONPATH). Prefer
    # `python main.py` from inside this folder.
    LinkChecker().run()
