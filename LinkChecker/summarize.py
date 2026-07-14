"""
summarize.py -- run this on the LAPTOP, from anywhere.

Scans every *_report.json file saved by LinkChecker.save_report() and
prints a one-line-per-run summary table, so you can eyeball a trend (is
`peak` drifting up or down over the last N runs? did rx_lo change between
two runs you're comparing?) without opening each JSON file by hand.

Usage:
    python summarize.py                    # looks in the folder this file is in (results/)
    python summarize.py ./results     # looks in a specific folder instead
"""

import glob   # for finding files matching a pattern, e.g. "*_report.json"
import json   # for reading each report file
import os     # for building file paths and reading command-line-independent defaults
import sys    # for reading an optional folder argument off the command line


def find_reports(folder):
    """Return every *_report.json path in `folder`, oldest first."""
    # glob.glob() finds every file matching a wildcard pattern.
    pattern = os.path.join(folder, "*_report.json")
    # sorted() puts them in filename order, which is also chronological,
    # because run_id is a timestamp like "2026-07-14_111211".
    return sorted(glob.glob(pattern))


def load_report(path):
    """Read one report.json file and return it as a Python dict."""
    with open(path) as f:
        return json.load(f)


def print_table(reports):
    """Print one line per report, in a simple fixed-width table."""
    if not reports:
        print("No *_report.json files found.")
        return

    # --- Header row ---
    header = f"{'run_id':<20} {'rx_lo_hz':>12} {'gain_db':>8} {'peak':>10} {'samples':>8}"
    print(header)
    print("-" * len(header))

    # --- One row per report ---
    for r in reports:
        # .get(key, "?") is used everywhere so a report saved by an older
        # version of LinkChecker.py (missing a newer field) still prints
        # something instead of crashing this whole script.
        run_id = r.get("run_id", "?")
        rx_lo = r.get("rx_lo_hz", "?")
        gain = r.get("rx_hardwaregain_db", "?")
        peak = r.get("peak", "?")
        n = r.get("num_samples", "?")

        # Format the peak to 2 decimal places if it's really a number;
        # otherwise just print whatever's there (e.g. "?") without crashing.
        peak_str = f"{peak:.2f}" if isinstance(peak, (int, float)) else str(peak)

        print(f"{run_id:<20} {rx_lo:>12} {gain:>8} {peak_str:>10} {n:>8}")


def main():
    # If a folder was given on the command line (sys.argv[1]), use that;
    # otherwise default to the folder this script itself lives in, which is
    # normally LinkChecker/results/ -- so `python summarize.py` with no
    # arguments just works when run from inside results/.
    default_folder = os.path.dirname(os.path.abspath(__file__))
    folder = sys.argv[1] if len(sys.argv) > 1 else default_folder

    print(f"Scanning: {folder}\n")
    paths = find_reports(folder)
    reports = [load_report(p) for p in paths]
    print_table(reports)


if __name__ == "__main__":
    main()
