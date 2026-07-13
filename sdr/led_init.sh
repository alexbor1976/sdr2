#!/bin/bash
# led_init.sh -- run ON THE BOARD, as root, ONCE PER BOOT.
#   scp led_init.sh analog@192.168.1.50:~
#   ssh analog@192.168.1.50 'sudo bash led_init.sh'
#
# Why this is needed (from your board notes):
#   DS4/DS5/DS6 are not routed to the processor on the ADRV9364-Z7020 SOM.
#   Only DS3 (red) is. Its pin is raw GPIO 963, but the stock Analog Devices
#   device tree wrongly hands 963 to the gpio-keys driver as a "Down" button.
#   The kernel then locks it as an input with an IRQ, so exporting it gives
#   "Device or resource busy". We unbind the driver to free the pin.
#
# The device tree is restored on every reboot, so this must run every boot.

set -u

echo "[1/3] unbinding gpio-keys ..."
for dir in /sys/bus/platform/drivers/gpio-keys/*; do
    if [ -d "$dir" ]; then
        echo "$(basename "$dir")" > /sys/bus/platform/drivers/gpio-keys/unbind 2>/dev/null
    fi
done

echo "[2/3] exporting GPIO 963 ..."
if [ ! -d /sys/class/gpio/gpio963 ]; then
    echo 963 > /sys/class/gpio/export
fi

echo "[3/3] direction = out ..."
echo out > /sys/class/gpio/gpio963/direction

echo 1 > /sys/class/gpio/gpio963/value; sleep 0.3
echo 0 > /sys/class/gpio/gpio963/value; sleep 0.3
echo 1 > /sys/class/gpio/gpio963/value; sleep 0.3
echo 0 > /sys/class/gpio/gpio963/value

echo "done -- DS3 should have blinked twice."

# ---------------------------------------------------------------------------
# Curiosity: is GPIO 963 actually driven through the FPGA fabric?
# Zynq PS GPIO = 54 MIO pins (0..53) then 64 EMIO pins (54..117).
# EMIO pins are routed through the PL. If base=906 below, then 963-906 = 57,
# i.e. EMIO pin 3 -- which would mean DS3's wire passes through your FPGA.
# Verify, do not assume:
#
#   for c in /sys/class/gpio/gpiochip*; do
#       echo "$c base=$(cat $c/base) label=$(cat $c/label) n=$(cat $c/ngpio)"
#   done
#
# If it holds, you can later drive DS3 from HDL and sidestep the device tree
# bug entirely. That is a very satisfying first FPGA modification.
# ---------------------------------------------------------------------------

echo
echo "gpiochip map:"
for c in /sys/class/gpio/gpiochip*; do
    echo "  $c base=$(cat "$c"/base) label=$(cat "$c"/label) ngpio=$(cat "$c"/ngpio)"
done
