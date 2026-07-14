"""
Settings.py -- a single, shared source of truth for every tunable value
used across this project's scripts.

This class is NOT meant to be instantiated (never write "Settings()").
Every value below is a CLASS attribute, so any file can just do:

    from Settings import Settings
    print(Settings.uri)

...and read a value straight off the class itself. No object to create,
no settings object to thread through every function call.

Why this matters as the project grows: if this project ends up with
dozens or hundreds of settings across many scripts (LinkChecker.py today,
maybe spectrum_live.py / siggen.py / etc. later), a single shared class
that everything imports keeps them in ONE place, instead of each script
hardcoding (and slowly drifting from) its own copy of the same values.

Want a different value for a specific run? Reassign it before running,
e.g. in main.py:
    Settings.rx_lo = int(200e6)
That changes it for every file that reads Settings after that point,
for the rest of that program's run.
"""

import os
from datetime import datetime


class Settings:
    # --- Connection ----------------------------------------------------
    uri = "ip:192.168.1.50"
    # Network address of the board's IIO server. "ip:<address>" means
    # "reach the radio over Ethernet"; on the board itself you'd use
    # "local:" instead (see CONTEXT.md's "Architecture" section).

    # --- Capture configuration --------------------------------------------
    sample_rate = int(4e6)
    # Samples per second the ADC produces (Hz). 4 MS/s stays comfortably
    # under the ~5 MS/s Ethernet ceiling noted in HARDWARE_NOTES.md.

    rx_lo = int(100e6)
    # Receive center frequency (Hz). Default 100 MHz sits inside the FM
    # broadcast band (88-108 MHz) -- a free, real signal to test against.
    # Unrelated to the project's 433 MHz TX default in CONTEXT.md, since
    # this checker never transmits.

    rx_buffer_size = 1024
    # How many complex I/Q samples one sdr.rx() call returns.

    rx_hardwaregain = 40
    # Fixed (manual) receive gain, in dB. Per HARDWARE_NOTES.md, this
    # board's usable RX gain range is roughly -3 .. 71 dB (band-dependent).

    discard_buffers = 5
    # How many rx() calls to throw away right after (re)tuning, before
    # trusting a buffer. The first few contain "settling" data.

    # --- Where to save results ----------------------------------------------
    results_dir = "results"
    # Folder where each run's captured samples + a JSON summary get saved.
    # See LinkChecker.save_report() and LinkChecker.md for details.

    # --- Helpers ---------------------------------------------------------
    # These use @classmethod (not @staticmethod) so they can read/use
    # `cls.results_dir` etc. -- i.e. the class's own current values --
    # without needing an instance either.

    @classmethod
    def timestamped_run_id(cls):
        """Build a filename-safe timestamp, e.g. '2026-07-14_193045'."""
        return datetime.now().strftime("%Y-%m-%d_%H%M%S")

    @classmethod
    def ensure_results_dir(cls):
        """Create the results folder if it doesn't already exist."""
        os.makedirs(cls.results_dir, exist_ok=True)   # no error if it's already there
        return cls.results_dir
