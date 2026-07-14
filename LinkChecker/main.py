"""
main.py -- run this on the LAPTOP, from inside this LinkChecker/ folder.

Entry point. Settings live in Settings.py at the PROJECT ROOT (one folder
up from here) -- shared by every script in the project, not just this one.
This file bootstraps sys.path so `from Settings import Settings` can find
it regardless of where Python was launched from.

Run with:
    cd LinkChecker
    python main.py

Why "cd LinkChecker" first: results (results/<run_id>_report.json and
_samples.npy) get written to a `results` folder relative to your current
working directory. Running from inside this folder keeps them at
LinkChecker/results/, next to this script, instead of scattered into
whatever folder you happened to launch Python from.
"""

import sys
import os

# --- Make the shared Settings.py (project root, one level up) importable,
#     no matter which folder you launched Python from. ---
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _project_root)     # so the import below can find Settings.py

from Settings import Settings         # shared settings, used directly as a class -- not instantiated
from LinkChecker import LinkChecker   # the class that actually talks to the radio (same folder as this file)


def main():
    # Optional: override any Settings values just for this run, by
    # reassigning the class attribute directly. Leave commented out to use
    # the defaults defined in Settings.py.
    # Settings.rx_lo = int(200e6)
    # Settings.rx_hardwaregain = 30

    checker = LinkChecker()   # no settings object passed in -- LinkChecker reads Settings.* itself
    checker.run()              # connect -> configure -> capture -> analyze -> save -> report


if __name__ == "__main__":   # only runs when this file is executed directly
    main()
