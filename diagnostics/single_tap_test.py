# ============================================================
# EOS SINGLE SYNTHETIC TAP - BOOTSEL triggered
#
# Purpose: verify calculated tap coordinates under the
# DIAGNOSTIC calibration (800 0 0 0 600 0 1023).
#
# With that calibration active:
#   screen_x = 800 * tenbit_x / 1023
#   screen_y = 600 * tenbit_y / 1023
# So to hit a screen position (X, Y):
#   tenbit_x = X * 1023 // 800
#   tenbit_y = Y * 1023 // 600
#
# Set TARGET_SCREEN below to the on-screen position you want.
# Press BOOTSEL -> fires ONE clean tap (touch, brief hold,
# release). LED blinks once per tap fired.
#
# Default target: screen center (400, 300).
# Wiring: CH1 (GP4 TX) -> Charon touch port, as usual.
# ============================================================

import machine
import utime
import rp2

BAUD = 9600

# ---- set your target screen position here ----
TARGET_SCREEN = (400, 300)   # (X, Y) in screen pixels, 800x600

uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)
led = machine.Pin(25, machine.Pin.OUT)

def screen_to_tenbit(sx, sy):
    tx = sx * 1023 // 800
    ty = sy * 1023 // 600
    tx = max(0, min(1023, tx))
    ty = max(0, min(1023, ty))
    return tx, ty

def encode_coord(tenbit):
    low = tenbit & 0xFF
    if low == 0xFF or low == 0xFE:
        tenbit -= 1
        low = tenbit & 0xFF
    high = ((tenbit >> 8) & 0x03) << 6
    return high, low

def send_tap(tx, ty, holds=6):
    xh, xl = encode_coord(tx)
    yh, yl = encode_coord(ty)
    pkt = bytes([0xFF, xh, xl, yh, yl])
    for _ in range(holds):
        uart_out.write(pkt)
        utime.sleep_ms(20)
    uart_out.write(bytes([0xFF, 0xFE, 0xFE]))

tx, ty = screen_to_tenbit(*TARGET_SCREEN)

print("=" * 50)
print("SINGLE TAP TEST (diagnostic calibration must be active)")
print("Target screen ({}, {}) -> 10bit ({}, {})".format(
    TARGET_SCREEN[0], TARGET_SCREEN[1], tx, ty))
print("Press BOOTSEL to fire one tap.")
print("=" * 50)

for _ in range(3):
    led.on(); utime.sleep_ms(120); led.off(); utime.sleep_ms(120)

count = 0
while True:
    if rp2.bootsel_button() == 1:
        # debounce + wait for release so one press = one tap
        utime.sleep_ms(30)
        while rp2.bootsel_button() == 1:
            utime.sleep_ms(10)
        count += 1
        led.on()
        send_tap(tx, ty)
        led.off()
        print("TAP {} fired at screen ({}, {})".format(
            count, TARGET_SCREEN[0], TARGET_SCREEN[1]))
    utime.sleep_ms(15)
