# ============================================================
# EOS P100 Charon - Touch Protocol Translator
# Raspberry Pi Pico (MicroPython)
#
# Reads eGalax USB HID touch data from iiyama T1531SR
# Translates to Gunze AP-920 RS-232 protocol
# Outputs to Charon /dev/ttyS2 at 9600 baud
#
# Wiring:
#   iiyama USB touch cable -> Pico USB (via OTG adapter)
#   Pico GP0 (TX) -> RS-232 level shifter TX in
#   Pico GP1 (RX) -> RS-232 level shifter RX out (not used)
#   RS-232 level shifter out -> Charon DB9 ttyS2
#   GND -> GND (common ground between Pico and level shifter)
#
# AP-920 Packet Format (from Linux kernel gunze.c):
#   Touch:   "T" + 4-digit-X + "," + 4-digit-Y + "\r"
#   Release: "R" + 4-digit-X + "," + 4-digit-Y + "\r"
#   Example: "T0512,0384\r"
#   Baud:    9600, 8N1
#
# eGalax USB HID Report Format (vendor 0x0eef, product 0x0001):
#   Byte 0: Report ID (0x01)
#   Byte 1: Touch status (0x01 = touch, 0x00 = release)
#   Byte 2: X high byte
#   Byte 3: X low byte
#   Byte 4: Y high byte
#   Byte 5: Y low byte
#   Raw range: 0-4095 (12-bit)
#
# Screen resolution: 640x480 (Charon framebuffer)
# ============================================================

import machine
import utime
import struct

# --- UART setup (GP0=TX, GP1=RX, 9600 baud, 8N1) ---
uart = machine.UART(0, baudrate=9600, tx=machine.Pin(0), rx=machine.Pin(1),
                    bits=8, parity=None, stop=1)

# --- USB HID constants ---
EGALAX_VID = 0x0EEF
EGALAX_PID = 0x0001

# --- Coordinate scaling ---
# eGalax raw range: 0-4095 (12-bit ADC)
# AP-920 coordinate range: 0-1023
EGALAX_MAX = 4095
AP920_MAX = 1023

# --- Status LED on Pico board pin 25 ---
led = machine.Pin(25, machine.Pin.OUT)

# --- State tracking ---
last_touch_state = False


def scale_coordinate(raw, raw_max, out_max):
    """Scale a raw coordinate to the output range."""
    return int((raw / raw_max) * out_max)


def send_ap920(touch_down, x, y):
    """
    Send a Gunze AP-920 formatted packet over UART.
    Format: T/R + XXXX + , + YYYY + \r
    Coordinates are zero-padded to 4 digits.
    """
    status = 'T' if touch_down else 'R'
    packet = "{}{:04d},{:04d}\r".format(status, x, y)
    uart.write(packet.encode('ascii'))


def parse_egalax_report(data):
    """
    Parse a raw eGalax HID report.
    Returns (touch_down, x, y) or None if invalid.
    
    Report layout (8 bytes):
    [0] Report ID = 0x01
    [1] Touch flag: bit0=1 touch, bit0=0 release
    [2] X high
    [3] X low
    [4] Y high  
    [5] Y low
    [6] Reserved
    [7] Reserved
    """
    if len(data) < 6:
        return None
    
    if data[0] != 0x01:
        return None

    touch_down = bool(data[1] & 0x01)
    
    # 12-bit X and Y from two bytes each
    x_raw = ((data[2] & 0x1F) << 7) | (data[3] & 0x7F)
    y_raw = ((data[4] & 0x1F) << 7) | (data[5] & 0x7F)

    # Scale to AP-920 range (0-1023)
    x = scale_coordinate(x_raw, EGALAX_MAX, AP920_MAX)
    y = scale_coordinate(y_raw, EGALAX_MAX, AP920_MAX)

    # Clamp to valid range
    x = max(0, min(AP920_MAX, x))
    y = max(0, min(AP920_MAX, y))

    return (touch_down, x, y)


def main():
    global last_touch_state

    print("EOS P100 Touch Translator starting...")
    print("Waiting for eGalax USB touch device...")

    # Flash LED 3 times on startup
    for _ in range(3):
        led.on()
        utime.sleep_ms(100)
        led.off()
        utime.sleep_ms(100)

    # Import USB host support
    # NOTE: Requires Pico W or Pico with USB host support
    # Uses the 'usb' module available in MicroPython 1.20+
    try:
        import usb.host
        import usb.host.hid
    except ImportError:
        print("ERROR: USB host module not available.")
        print("Please flash MicroPython with USB host support.")
        # Flash LED rapidly to indicate error
        while True:
            led.on()
            utime.sleep_ms(50)
            led.off()
            utime.sleep_ms(50)

    # Initialise USB host
    host = usb.host.USBHost()

    print("USB host initialised. Waiting for device...")
    led.on()

    egalax_device = None

    while True:
        # Poll for device connection
        if egalax_device is None:
            devices = host.devices()
            for dev in devices:
                if dev.vid == EGALAX_VID and dev.pid == EGALAX_PID:
                    egalax_device = dev
                    print("eGalax touch device found! VID={:04x} PID={:04x}".format(
                        EGALAX_VID, EGALAX_PID))
                    # Flash LED twice to confirm device found
                    for _ in range(2):
                        led.off()
                        utime.sleep_ms(200)
                        led.on()
                        utime.sleep_ms(200)
                    break

        if egalax_device is not None:
            try:
                # Read HID report (8 bytes, 10ms timeout)
                report = egalax_device.read(8, timeout=10)

                if report and len(report) >= 6:
                    result = parse_egalax_report(report)

                    if result is not None:
                        touch_down, x, y = result

                        # Only send if state changed or position changed while touching
                        if touch_down != last_touch_state or touch_down:
                            send_ap920(touch_down, x, y)
                            last_touch_state = touch_down

                            # Brief LED flash on each touch event
                            led.off()
                            utime.sleep_ms(5)
                            led.on()

            except Exception as e:
                print("Device error: {}. Reconnecting...".format(e))
                egalax_device = None
                last_touch_state = False
                led.off()

        utime.sleep_ms(5)


if __name__ == "__main__":
    main()
