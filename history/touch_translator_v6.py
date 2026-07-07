# ============================================================
# EOS P100/P110 Touch Translator - v6
# Adds: rolling-average smoothing on raw X/Y to reduce jitter
#       (resistive panel readings drift several % even when
#        the finger is held perfectly still - this averages
#        that out before scaling/sending)
# ============================================================

import machine
import utime

BAUD = 9600

INVERT_X = True
INVERT_Y = True
SWAP_XY  = False

CLAMP_MIN = 1
CLAMP_MAX = 253

SMOOTH_SAMPLES = 8   # rolling window size - tune if needed

uart_in = machine.UART(0, baudrate=BAUD, tx=machine.Pin(0), rx=machine.Pin(1),
                        bits=8, parity=None, stop=1)

uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)

led = machine.Pin(25, machine.Pin.OUT)

print("=" * 50)
print("EOS Touch Translator v6 - smoothed")
print("INVERT_X={} INVERT_Y={} SWAP_XY={}".format(INVERT_X, INVERT_Y, SWAP_XY))
print("Smoothing window: {} samples".format(SMOOTH_SAMPLES))
print("=" * 50)

for _ in range(3):
    led.on()
    utime.sleep_ms(150)
    led.off()
    utime.sleep_ms(150)
led.on()

EGALAX_MAX = 16383
IRV_MAX = 255

buf = bytearray()
was_touching = False
x_hist = []
y_hist = []

def scale(val, invert):
    scaled = (val * IRV_MAX) // EGALAX_MAX
    if invert:
        scaled = IRV_MAX - scaled
    if scaled < CLAMP_MIN:
        scaled = CLAMP_MIN
    if scaled > CLAMP_MAX:
        scaled = CLAMP_MAX
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
                    # rolling average
                    x_hist.append(raw_x)
                    y_hist.append(raw_y)
                    if len(x_hist) > SMOOTH_SAMPLES:
                        x_hist.pop(0)
                        y_hist.pop(0)
                    avg_x = sum(x_hist) // len(x_hist)
                    avg_y = sum(y_hist) // len(y_hist)

                    irv_x = scale(avg_x, INVERT_X)
                    irv_y = scale(avg_y, INVERT_Y)
                    if SWAP_XY:
                        irv_x, irv_y = irv_y, irv_x

                    out = bytes([0xFF, 0x00, irv_x, 0x00, irv_y])
                    uart_out.write(out)
                    print("TOUCH  raw X={:5d} Y={:5d}  avg X={:5d} Y={:5d}  -> iRV X={:3d} Y={:3d}".format(
                        raw_x, raw_y, avg_x, avg_y, irv_x, irv_y))
                    was_touching = True
                else:
                    if was_touching:
                        uart_out.write(bytes([0xFF, 0xFE, 0xFE]))
                        print("RELEASE")
                        was_touching = False
                    x_hist = []
                    y_hist = []

                led.toggle()
                buf = buf[5:]

    utime.sleep_ms(1)
