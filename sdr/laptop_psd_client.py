"""
06_laptop_psd_client.py  --  Run on the LAPTOP, after 05_board_psd_server.py
is running on the board.

Notice what this file does NOT contain: adi, libiio, any radio code at all.
The laptop is now a thin display client. All the DSP happens on the ARM core.
Only ~16 kB of processed spectrum crosses the wire per frame.
"""

import json
import socket
import struct
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

HOST = "192.168.1.50"
PORT = 5001

REQ = {"lo": 100e6, "fs": 4e6, "n": 4096, "avg": 8, "gain": 40}


def recv_exact(f, n):
    buf = f.read(n)
    if buf is None or len(buf) != n:
        raise ConnectionError("short read")
    return buf


def main():
    s = socket.create_connection((HOST, PORT), timeout=10)
    f = s.makefile("rwb")

    def get_psd():
        f.write((json.dumps(REQ) + "\n").encode())
        f.flush()
        (nbytes,) = struct.unpack("<Q", recv_exact(f, 8))
        return np.frombuffer(recv_exact(f, nbytes), dtype=np.float32)

    n, fs, lo = int(REQ["n"]), REQ["fs"], REQ["lo"]
    freqs = (np.fft.fftshift(np.fft.fftfreq(n, 1 / fs)) + lo) / 1e6

    fig, ax = plt.subplots(figsize=(11, 5))
    (line,) = ax.plot(freqs, get_psd(), lw=0.8)
    ax.set_xlim(freqs[0], freqs[-1])
    ax.set_ylim(-110, 0)
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Power (dBFS)")
    ax.set_title(f"Remote spectrum analyzer @ {HOST}  (FFT computed on the ARM core)")
    ax.grid(alpha=0.3)

    def update(_):
        line.set_ydata(get_psd())
        return (line,)

    ani = FuncAnimation(fig, update, interval=100, blit=True, cache_frame_data=False)
    plt.tight_layout()
    plt.show()
    s.close()


if __name__ == "__main__":
    main()
