# ============================================================
# iiyama RAW PACKET SNIFFER
#
# Shows the COMPLETE raw bytes coming from the iiyama on CH0,
# with NO interpretation. Purpose: verify the actual eGalax
# packet structure and confirm whether our X/Y byte assignment
# is correct - specifically to diagnose why Y barely varies.
#
# Prints every byte in hex as it arrives, groups into lines on
# a likely sync byte, and decodes BOTH possible interpretations
# so we can see which axis is which.
#
# CH0 = GP0/GP1 <- iiyama touch RS232 output.
# Just touch the screen at known spots and watch the bytes.
# ============================================================

import machine
import utime

BAUD = 9600

uart_in = machine.UART(0, baudrate=BAUD, tx=machine.Pin(0), rx=machine.Pin(1),
                        bits=8, parity=None, stop=1)
led = machine.Pin(25, machine.Pin.OUT)

print("=" * 56)
print("iiyama RAW PACKET SNIFFER - no interpretation")
print("Touch KNOWN spots; watch the raw bytes + both decodes")
print("=" * 56)

for _ in range(3):
    led.on(); utime.sleep_ms(120); led.off(); utime.sleep_ms(120)
led.on()

# eGalax 5-byte format is typically:
#   byte0: 1 0 0 0 0 0 0 T   (0x80 set, T=touch bit)
#   byte1: X high 7 bits
#   byte2: X low 7 bits
#   byte3: Y high 7 bits
#   byte4: Y low 7 bits
# We'll show raw, and decode two ways to compare.

buf = bytearray()

def decode_A(b):
    # our current assumption: x=(b1&7F)|((b2&7F)<<7), y=(b3&7F)|((b4&7F)<<7)
    x = (b[1] & 0x7F) | ((b[2] & 0x7F) << 7)
    y = (b[3] & 0x7F) | ((b[4] & 0x7F) << 7)
    return x, y

def decode_B(b):
    # alt: high byte first  x=((b1&7F)<<7)|(b2&7F)
    x = ((b[1] & 0x7F) << 7) | (b[2] & 0x7F)
    y = ((b[3] & 0x7F) << 7) | (b[4] & 0x7F)
    return x, y

print("Listening... (raw hex per 5-byte frame, then decodes)")
print()

count = 0
while True:
    if uart_in.any():
        data = uart_in.read()
        if data:
            buf.extend(data)
            # find frames starting with a byte that has 0x80 set
            while len(buf) >= 5:
                if not (buf[0] & 0x80):
                    buf = buf[1:]
                    continue
                frame = bytes(buf[0:5])
                ax, ay = decode_A(frame)
                bx, by = decode_B(frame)
                touchbit = frame[0] & 0x01
                hexstr = " ".join("{:02X}".format(c) for c in frame)
                count += 1
                # only print every few to avoid flooding
                if count % 3 == 0:
                    print("RAW[{}]  T={}  A:x={:5d} y={:5d}   B:x={:5d} y={:5d}".format(
                        hexstr, touchbit, ax, ay, bx, by))
                led.toggle()
                buf = buf[5:]
    utime.sleep_ms(1)
