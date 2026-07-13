"""
05_board_psd_server.py  --  Run this ON THE BOARD (the ARM core), not the laptop.

    scp 05_board_psd_server.py analog@192.168.1.50:~
    ssh analog@192.168.1.50
    sudo python3 05_board_psd_server.py

Why: raw I/Q at 5 MS/s is ~160 Mbit/s over Ethernet. At 30 MS/s it is impossible.
So we capture at full rate LOCALLY (uri="local:", no network in the data path),
compute the FFT on the ARM, and send back 4096 floats -- about 16 kB.
That is a ~100x reduction. This is how real networked instruments are built.

Bonus: DS3 (the red LED) is lit while a capture is in progress.
Run the once-per-boot GPIO init first (see led_init.sh).

Protocol (deliberately dumb, easy to debug):
  client sends one line of JSON:  {"lo": 100e6, "fs": 4e6, "n": 4096, "avg": 8, "gain": 40}
  server replies with 8 bytes of little-endian length, then that many bytes of
  float32 PSD in dBFS, fftshifted.
"""

import json
import socket
import struct
import numpy as np
import adi

PORT = 5001
LED_VALUE = "/sys/class/gpio/gpio963/value"
FULL_SCALE = 2 ** 11


def led(on: bool):
    """Fails silently if the once-per-boot init has not been run."""
    try:
        with open(LED_VALUE, "w") as f:
            f.write("1" if on else "0")
    except OSError:
        pass


def make_sdr():
    try:
        return adi.ad9364(uri="local:")
    except Exception:
        return adi.ad9361(uri="local:")


def configure(sdr, lo, fs, n, gain):
    sdr.rx_enabled_channels = [0]
    sdr.sample_rate = int(fs)
    sdr.rx_rf_bandwidth = int(fs * 0.8)
    sdr.rx_lo = int(lo)
    sdr.rx_buffer_size = int(n)
    try:
        sdr.gain_control_mode_chan0 = "manual"
        sdr.rx_hardwaregain_chan0 = int(gain)
    except AttributeError:
        sdr.gain_control_mode = "manual"
        sdr.rx_hardwaregain = int(gain)


def measure(sdr, n, avg):
    win = np.hanning(n)
    cg = win.sum() / n
    for _ in range(3):
        sdr.rx()                       # flush settling buffers
    acc = np.zeros(n)
    for _ in range(avg):
        x = np.asarray(sdr.rx()) / FULL_SCALE
        acc += np.abs(np.fft.fftshift(np.fft.fft(x * win))) ** 2
    acc /= avg
    return (10 * np.log10(acc / (n * cg) ** 2 + 1e-20)).astype(np.float32)


def main():
    sdr = make_sdr()
    last_cfg = None

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(1)
    print(f"PSD server listening on :{PORT}. Ctrl-C to stop.")

    try:
        while True:
            conn, addr = srv.accept()
            print(f"client {addr[0]}")
            f = conn.makefile("rwb")
            try:
                while True:
                    line = f.readline()
                    if not line:
                        break
                    req = json.loads(line)
                    cfg = (req["lo"], req["fs"], req["n"], req["gain"])
                    if cfg != last_cfg:
                        configure(sdr, *cfg)
                        last_cfg = cfg

                    led(True)
                    psd = measure(sdr, int(req["n"]), int(req.get("avg", 8)))
                    led(False)

                    payload = psd.tobytes()
                    f.write(struct.pack("<Q", len(payload)))
                    f.write(payload)
                    f.flush()
            except (ConnectionResetError, json.JSONDecodeError, KeyError) as e:
                print(f"  client gone / bad request: {e}")
            finally:
                led(False)
                conn.close()
                sdr.rx_destroy_buffer()
    except KeyboardInterrupt:
        pass
    finally:
        led(False)
        srv.close()
        print("\nserver stopped")


if __name__ == "__main__":
    main()
