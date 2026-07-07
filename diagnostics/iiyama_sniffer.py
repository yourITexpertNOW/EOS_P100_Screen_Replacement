# ============================================================
# iiyama T1531SR RS232 Touch Sniffer (standalone, no Charon)
# Raspberry Pi Pico + Waveshare 2-CH RS232 Hat
#
# Channel 0: GP0 (TX), GP1 (RX) --> iiyama RS232 touch port
#
# Wiring (cross TX/RX, like a null-modem):
#   iiyama TXD (pin 3) --> hat RX0
#   iiyama RXD (pin 2) --> hat TX0
#   iiyama GND (pin 5) --> hat GND
#
# Starts at 9600 8N1 (common for eGalax/EETI RS232 controllers)
# Prints raw hex AND attempts eGalax 5-byte decode
# ============================================================

import machine
import utime

BAUD = 9600

uart = machine.UART(0, baudrate=BAUD, tx=machine.Pin(0), rx=machine.Pin(1),
                     bits=8, parity=None, stop=1)

led = machine.Pin(25, machine.Pin.OUT)

print("=" * 50)
print("iiyama RS232 Touch Sniffer")
print("Baud: {} 8N1".format(BAUD))
print("Channel 0 (GP0/GP1)")
print("=" * 50)
print("Touch the iiyama screen...")
print()

for _ in range(5):
    led.on()
    utime.sleep_ms(100)
    led.off()
    utime.sleep_ms(100)
led.on()

buf = []
last_time = utime.ticks_ms()

def try_egalax_decode(b):
    # eGalax 5-byte packet: byte0 has bit7 set (>=0x80)
    if len(b) == 5 and (b[0] & 0x80):
        touch = b[0] & 0x01
        x = (b[1] & 0x7F) | ((b[2] & 0x7F) << 7)
        y = (b[3] & 0x7F) | ((b[4] & 0x7F) << 7)
        print("    -> eGalax decode: touch={} X={} Y={}".format(touch, x, y))

while True:
    if uart.any():
        data = uart.read()
        if data:
            now = utime.ticks_ms()
            for byte in data:
                elapsed = utime.ticks_diff(now, last_time)
                if elapsed > 50 and len(buf) > 0:
                    hex_str = ' '.join(['0x{:02X}'.format(x) for x in buf])
                    print("Pkt ({} bytes): {}".format(len(buf), hex_str))
                    try_egalax_decode(buf)
                    led.off()
                    utime.sleep_ms(10)
                    led.on()
                    buf = []
                buf.append(byte)
                last_time = now
    utime.sleep_ms(1)
