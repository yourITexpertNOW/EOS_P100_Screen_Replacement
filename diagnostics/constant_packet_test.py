# ============================================================
# EOS Touch - CONSTANT PACKET FRAMING TEST
#
# Diagnostic only. Ignores the iiyama entirely. Sends ONE fixed,
# known 5-byte packet on repeat to a fixed mid-screen coordinate.
#
# PURPOSE: isolate framing/parser determinism from touch data.
#   - Cursor sits STILL  -> our 5-byte framing is parsed
#     deterministically. Encoding is sound; the inconsistency
#     we've been chasing is in the TOUCH DATA / release timing,
#     NOT the protocol. (Evidence AGAINST the 7-byte theory.)
#   - Cursor JUMPS around -> identical bytes are being parsed
#     into different positions => EOS is mis-framing our stream.
#     (Evidence FOR a framing problem / the 7-byte theory.)
#
# Sends at ~50ms intervals, same as a steady touch would.
# Channel 1 (GP4 TX) -> Charon touch DB9, as normal.
# ============================================================

import machine
import utime

BAUD = 9600

uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)

led = machine.Pin(25, machine.Pin.OUT)

# Fixed mid-screen target: 10-bit (512, 512)
# X=512=0x200 -> top2=10 -> high=0x80, low=0x00
# Y=512=0x200 -> high=0x80, low=0x00
# (low byte 0x00 is safe - no 0xFE/0xFF collision)
FIXED_X = 512
FIXED_Y = 512

def encode_coord(tenbit):
    low = tenbit & 0xFF
    if low == 0xFF or low == 0xFE:
        tenbit -= 1
        low = tenbit & 0xFF
    high = ((tenbit >> 8) & 0x03) << 6
    return high, low

xh, xl = encode_coord(FIXED_X)
yh, yl = encode_coord(FIXED_Y)
packet = bytes([0xFF, xh, xl, yh, yl])

print("=" * 50)
print("CONSTANT PACKET FRAMING TEST")
print("Sending fixed packet for 10-bit ({},{}):".format(FIXED_X, FIXED_Y))
print("  bytes: FF {:02X} {:02X} {:02X} {:02X}".format(xh, xl, yh, yl))
print("Watch the cursor: STILL = framing OK, JUMPING = framing bad")
print("=" * 50)

for _ in range(3):
    led.on(); utime.sleep_ms(150); led.off(); utime.sleep_ms(150)
led.on()

# Stream the identical packet repeatedly, like a held touch
count = 0
while True:
    uart_out.write(packet)
    count += 1
    if count % 20 == 0:
        led.toggle()
        print("sent {} identical packets".format(count))
    utime.sleep_ms(50)
