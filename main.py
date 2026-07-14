"""
main.py -- run this on the LAPTOP.

Entry point. Settings live in Settings.py as class attributes shared by
every script in this project. This file does NOT build or pass around a
settings object -- it just imports Settings, optionally overrides a value
or two for this particular run, then runs LinkChecker.

All files must sit in the same folder:
    Settings.py
    LinkChecker.py
    main.py

Run with:
    python main.py
"""

from Settings import Settings         # shared settings, used directly as a class -- not instantiated
from LinkChecker import LinkChecker   # the class that actually talks to the radio


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
