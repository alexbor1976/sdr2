"""
main_link_check.py -- run this on the LAPTOP.

Thin entry point that imports the LinkChecker class from link_check.py
and runs it. Kept as a separate file so that:
  - link_check.py can be imported and reused by other scripts later
    (e.g. a future spectrum_live.py) without re-running the whole check
    every time it's imported.
  - all your "which settings do I want today" choices live in ONE place,
    at the top of this file, instead of buried inside the class.

Run it with:
    python main_link_check.py
"""

from link_check import LinkChecker   # import the class defined in link_check.py
                                       # (link_check.py must be in the same folder, or on your PYTHONPATH)

# --- Settings you're likely to want to change -----------------------------
# Edit these values here instead of editing link_check.py itself.
URI = "ip:192.168.1.50"     # network address of the board's IIO server (laptop -> board, over Ethernet)
SAMPLE_RATE = int(4e6)      # 4,000,000 samples/second
RX_LO = int(100e6)          # receive center frequency: 100 MHz.
                             # RX-only test -- nothing is transmitted, so this
                             # is safe to run even with antennas connected.
RX_BUFFER_SIZE = 1024       # number of I/Q samples per capture
RX_GAIN = 40                # fixed (manual) receive gain, in dB


def main():
    # Build one LinkChecker with the settings above ...
    checker = LinkChecker(
        uri=URI,
        sample_rate=SAMPLE_RATE,
        rx_lo=RX_LO,
        rx_buffer_size=RX_BUFFER_SIZE,
        rx_hardwaregain=RX_GAIN,
    )
    # ... and run the full end-to-end check (connect, configure, capture, report).
    checker.run()


if __name__ == "__main__":   # only true when you run this file directly,
    main()                    # e.g. `python main_link_check.py` -- not when it's imported
