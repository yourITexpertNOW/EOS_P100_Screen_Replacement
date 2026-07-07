# ============================================================
# EOS Touch Translator - v10  *** 10-BIT PROTOCOL ***
#
# MAJOR FIX: The iRV protocol is 10-BIT, not 8-bit.
# The "status" bytes we originally dismissed as noise actually
# carry the TOP 2 BITS of each coordinate.
#
# Genuine packet format (5 bytes per sample):
#   [0xFF]
#   [ (Xhigh2 << 6) ]   <- top 2 bits of 10-bit X, in bits 6-7
#   [ Xlow8 ]           <- low 8 bits of X
#   [ (Yhigh2 << 6) ]   <- top 2 bits of 10-bit Y
#   [ Ylow8 ]           <- low 8 bits of Y
#   ... repeating while touched ...
#   [0xFF 0xFE 0xFE]    <- release terminator
#
# Coordinate range: 0-1023 (10-bit), matching what the genuine
# EOS /etc/pointercal calibration actually expects. This is why
# 8-bit output could only ever reach the centre ~1/3 of the screen.
#
# Collision handling: the low byte can equal 0xFE/0xFF at some
# values (e.g. 511 -> 0x40 0xFF). We nudge the 10-bit value by 1
# to avoid emitting 0xFE/0xFF in the low byte mid-stream.
#
# Orientation: RAW passthrough (no invert/swap) - let the EOS
# 5-point calibration handle all orientation. Use SHORT TAPS.
# ============================================================

import machine
import utime

BAUD = 9600

INVERT_X = False
INVERT_Y = False
SWAP_XY  = False

SMOOTH_SAMPLES = 7

uart_in = machine.UART(0, baudrate=BAUD, tx=machine.Pin(0), rx=machine.Pin(1),
                        bits=8, parity=None, stop=1)
uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)

led = machine.Pin(25, machine.Pin.OUT)

print("=" * 50)
print("EOS Touch Translator v10 - 10-BIT PROTOCOL")
print("INVERT_X={} INVERT_Y={} SWAP_XY={}".format(INVERT_X, INVERT_Y, SWAP_XY))
print("Coordinate range 0-1023, median window {}".format(SMOOTH_SAMPLES))
print("=" * 50)

for _ in range(3):
    led.on(); utime.sleep_ms(150); led.off(); utime.sleep_ms(150)
led.on()

EGALAX_MAX = 16383
TENBIT_MAX = 1023

buf = bytearray()
was_touching = False
x_hist = []
y_hist = []

def median(vals):
    return sorted(vals)[len(vals)//2]

def scale_10bit(val, invert):
    scaled = (val * TENBIT_MAX) // EGALAX_MAX
    if invert:
        scaled = TENBIT_MAX - scaled
    if scaled < 0: scaled = 0
    if scaled > TENBIT_MAX: scaled = TENBIT_MAX
    return scaled

def encode_coord(tenbit):
    # returns (high_byte, low_byte); avoid low byte 0xFE/0xFF
    low = tenbit & 0xFF
    if low == 0xFF or low == 0xFE:
        tenbit -= 1            # nudge down by 1 to dodge collision
        low = tenbit & 0xFF
    high = ((tenbit >> 8) & 0x03) << 6
    return high, low

print("Listening for touch input...")
print()

while True:
    if uart_in.any():
        data = uart_in.read()
        if data:
            buf.extend(data)
            while len(buf) >= 5:
                b0, b1, b2, b3, b4 = buf[0:5]
                if not (b0 & 0x80):
                    buf = buf[1:]
                    continue
                touch = b0 & 0x01
                raw_x = (b1 & 0x7F) | ((b2 & 0x7F) << 7)
                raw_y = (b3 & 0x7F) | ((b4 & 0x7F) << 7)

                if touch:
                    x_hist.append(raw_x); y_hist.append(raw_y)
                    if len(x_hist) > SMOOTH_SAMPLES:
                        x_hist.pop(0); y_hist.pop(0)
                    mx = median(x_hist); my = median(y_hist)

                    tx = scale_10bit(mx, INVERT_X)
                    ty = scale_10bit(my, INVERT_Y)
                    if SWAP_XY:
                        tx, ty = ty, tx

                    xh, xl = encode_coord(tx)
                    yh, yl = encode_coord(ty)
                    uart_out.write(bytes([0xFF, xh, xl, yh, yl]))

                    print("TOUCH raw({:5d},{:5d}) -> 10bit({:4d},{:4d}) -> bytes FF {:02X} {:02X} {:02X} {:02X}".format(
                        mx, my, tx, ty, xh, xl, yh, yl))
                    was_touching = True
                else:
                    if was_touching:
                        uart_out.write(bytes([0xFF, 0xFE, 0xFE]))
                        print("RELEASE")
                        was_touching = False
                    x_hist = []; y_hist = []
                led.toggle()
                buf = buf[5:]
    utime.sleep_ms(1)
