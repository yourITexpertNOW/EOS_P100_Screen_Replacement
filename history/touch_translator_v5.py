# ============================================================
# EOS P100 Touch Translator - v3
# Fixes: clamp X/Y away from 0xFF/0xFE (sync/terminator bytes)
#        to avoid parser desync mid-stream
# ============================================================

import machine
import utime

BAUD = 9600

INVERT_X = True
INVERT_Y = True
SWAP_XY  = False

# Clamp range - avoid 0x00, 0xFE, 0xFF which have special meaning
# in the protocol (sync=0xFF, terminator=FF FE FE)
CLAMP_MIN = 1
CLAMP_MAX = 253

uart_in = machine.UART(0, baudrate=BAUD, tx=machine.Pin(0), rx=machine.Pin(1),
                        bits=8, parity=None, stop=1)

uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)

led = machine.Pin(25, machine.Pin.OUT)

print("=" * 50)
print("EOS P100 Touch Translator v5")
print("INVERT_X={} INVERT_Y={} SWAP_XY={}".format(INVERT_X, INVERT_Y, SWAP_XY))
print("Clamping output to {}-{}".format(CLAMP_MIN, CLAMP_MAX))
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

                irv_x = scale(raw_x, INVERT_X)
                irv_y = scale(raw_y, INVERT_Y)

                if SWAP_XY:
                    irv_x, irv_y = irv_y, irv_x

                if touch:
                    out = bytes([0xFF, 0x00, irv_x, 0x00, irv_y])
                    uart_out.write(out)
                    print("TOUCH  iiyama X={:5d} Y={:5d}  -> iRV X={:3d} Y={:3d}".format(
                        raw_x, raw_y, irv_x, irv_y))
                    was_touching = True
                else:
                    if was_touching:
                        uart_out.write(bytes([0xFF, 0xFE, 0xFE]))
                        print("RELEASE")
                        was_touching = False

                led.toggle()
                buf = buf[5:]

    utime.sleep_ms(1)
