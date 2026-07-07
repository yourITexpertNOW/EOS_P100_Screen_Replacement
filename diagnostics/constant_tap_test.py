# ============================================================
# EOS Touch - CONSTANT TAP FRAMING TEST  (v2 of diagnostic)
#
# The steady-stream test produced NO cursor response, which
# suggests EOS registers on touch-down/release TRANSITIONS,
# not on a continuous identical stream.
#
# This version sends discrete TAP CYCLES at one fixed point:
#   - touch-down + a few identical position packets
#   - release terminator (FF FE FE)
#   - pause
#   - repeat  (same coordinate every time)
#
# WHAT IT TELLS US:
#  - Cursor now appears and TAPS land in the SAME spot each
#    cycle  -> framing/encoding deterministic. Our protocol is
#    fine; the real problem is that live touch data varies at
#    the moment of release. (Focus shifts to release handling.)
#  - Taps land in DIFFERENT spots despite identical bytes
#    -> EOS is mis-framing -> 7-byte protocol path becomes
#    the priority.
#  - Still nothing -> the packet structure itself is being
#    rejected (deeper protocol mismatch).
#
# Fixed point: 10-bit (512,512) = mid screen.
# 2 second pause between taps so you can watch each one land.
# ============================================================

import machine
import utime

BAUD = 9600
uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)
led = machine.Pin(25, machine.Pin.OUT)

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
touch_packet = bytes([0xFF, xh, xl, yh, yl])
release_packet = bytes([0xFF, 0xFE, 0xFE])

print("=" * 50)
print("CONSTANT TAP TEST - discrete taps at fixed point")
print("Point 10-bit ({},{}): FF {:02X} {:02X} {:02X} {:02X}".format(
    FIXED_X, FIXED_Y, xh, xl, yh, yl))
print("Watch: do all taps land in the SAME place?")
print("=" * 50)

for _ in range(3):
    led.on(); utime.sleep_ms(150); led.off(); utime.sleep_ms(150)

tap = 0
while True:
    tap += 1
    led.on()
    # touch-down: send the position a handful of times (like a brief hold)
    for _ in range(6):
        uart_out.write(touch_packet)
        utime.sleep_ms(20)
    # release
    uart_out.write(release_packet)
    led.off()
    print("TAP {} sent at ({},{})".format(tap, FIXED_X, FIXED_Y))
    utime.sleep_ms(2000)   # pause so you can see where it landed
