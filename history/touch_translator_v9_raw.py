# ============================================================
# EOS Touch Translator - v9 RAW PASSTHROUGH
# NO inversions, NO swap - sends iiyama coordinates straight
# through (scaled to iRV range only), letting the EOS 5-point
# calibration routine handle ALL orientation/flip/rotation.
#
# This avoids two conflicting layers of axis correction
# (Pico transform + EOS calibration transform fighting).
#
# Median filtering retained (jitter reduction is still good).
# Use SHORT TAPS for calibration, not holds.
# ============================================================

import machine
import utime

BAUD = 9600

# ALL TRANSFORMS OFF - raw passthrough
INVERT_X = False
INVERT_Y = False
SWAP_XY  = False

CLAMP_MIN = 1
CLAMP_MAX = 253
SMOOTH_SAMPLES = 7

uart_in = machine.UART(0, baudrate=BAUD, tx=machine.Pin(0), rx=machine.Pin(1),
                        bits=8, parity=None, stop=1)
uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)

led = machine.Pin(25, machine.Pin.OUT)

print("=" * 50)
print("EOS Touch Translator v9 - RAW PASSTHROUGH")
print("INVERT_X={} INVERT_Y={} SWAP_XY={}".format(INVERT_X, INVERT_Y, SWAP_XY))
print("Median window: {} samples".format(SMOOTH_SAMPLES))
print("(EOS calibration handles all orientation)")
print("=" * 50)

for _ in range(3):
    led.on(); utime.sleep_ms(150); led.off(); utime.sleep_ms(150)
led.on()

EGALAX_MAX = 16383
IRV_MAX = 255

buf = bytearray()
was_touching = False
x_hist = []
y_hist = []

def median(vals):
    return sorted(vals)[len(vals)//2]

def scale(val, invert):
    scaled = (val * IRV_MAX) // EGALAX_MAX
    if invert:
        scaled = IRV_MAX - scaled
    if scaled < CLAMP_MIN: scaled = CLAMP_MIN
    if scaled > CLAMP_MAX: scaled = CLAMP_MAX
    return scaled

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
                    irv_x = scale(mx, INVERT_X)
                    irv_y = scale(my, INVERT_Y)
                    if SWAP_XY:
                        irv_x, irv_y = irv_y, irv_x
                    uart_out.write(bytes([0xFF, 0x00, irv_x, 0x00, irv_y]))
                    print("TOUCH  raw X={:5d} Y={:5d}  med X={:5d} Y={:5d}  -> iRV X={:3d} Y={:3d}".format(
                        raw_x, raw_y, mx, my, irv_x, irv_y))
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
