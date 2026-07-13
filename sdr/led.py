"""
led.py  --  Run on the LAPTOP. Controls DS3 (red LED) on the ADRV1CRR-BOB over SSH.

    python led.py init     # once per boot: unbind gpio-keys, export 963, set output
    python led.py on
    python led.py off
    python led.py blink 10

Uses the OpenSSH client built into Windows 10/11. It will ask for the password
(default 'analog') each time. To stop that:

    ssh-keygen -t ed25519
    type $env:USERPROFILE\\.ssh\\id_ed25519.pub | ssh analog@192.168.1.50 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"

Once that works, the board-side server (05_board_psd_server.py) can drive the LED
directly, and DS3 becomes a "capture in progress" indicator you can see across
the room.
"""

import subprocess
import sys
import time

HOST = "analog@192.168.1.50"
PASSWORD_HINT = "(default password: analog)"

INIT = r"""
for dir in /sys/bus/platform/drivers/gpio-keys/*; do
  [ -d "$dir" ] && echo $(basename "$dir") > /sys/bus/platform/drivers/gpio-keys/unbind 2>/dev/null
done
[ -d /sys/class/gpio/gpio963 ] || echo 963 > /sys/class/gpio/export
echo out > /sys/class/gpio/gpio963/direction
echo "gpio963 ready"
"""


def run(cmd: str) -> int:
    """Run a command on the board as root."""
    full = f"sudo sh -c {shell_quote(cmd)}"
    return subprocess.run(["ssh", HOST, full]).returncode


def shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def set_led(on: bool) -> int:
    return run(f"echo {1 if on else 0} > /sys/class/gpio/gpio963/value")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd = sys.argv[1]

    print(f"talking to {HOST} {PASSWORD_HINT}")

    if cmd == "init":
        rc = run(INIT)
        if rc != 0:
            print("init failed. Check SSH works: ssh", HOST)
        return

    if cmd == "on":
        set_led(True)
    elif cmd == "off":
        set_led(False)
    elif cmd == "blink":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        # One SSH session for the whole blink -- opening a session per toggle is
        # slow (~0.3 s each) and you would never see a crisp blink.
        script = f"for i in $(seq {n}); do " \
                 f"echo 1 > /sys/class/gpio/gpio963/value; sleep 0.2; " \
                 f"echo 0 > /sys/class/gpio/gpio963/value; sleep 0.2; done"
        run(script)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
