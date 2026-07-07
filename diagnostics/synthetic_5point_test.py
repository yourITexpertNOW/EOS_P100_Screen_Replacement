# ============================================================
# EOS SYNTHETIC 5-POINT + TICK - PLUMBING TEST
#
# Purpose: prove we can drive the WHOLE calibration flow with
# synthetic taps - hit all 5 crosses in EOS's order, then Tick.
#
# *** This produces a calibration mapped to SYNTHETIC values,
# not your finger. It is a FLOW test, not a usable calibration.
# For a real calibration the 5 points must be REAL finger touches. ***
#
# Requires GENUINE pointercal active (tap coords mapped under it).
#
# EOS calibration order: TL, BL, BR, TR, Center.
# BOOTSEL steps through: press once per point, then Tick.
#
# Coordinates are ESTIMATES for the crosses - nudge after seeing
# where they land. Tick (65,55) is confirmed.
#
# Wiring: CH1 (GP4 TX) -> Charon.
# ============================================================

import machine, utime, rp2

BAUD = 9600
uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)
led = machine.Pin(25, machine.Pin.OUT)

# calibration order: TL, BL, BR, TR, Center, then Tick
POINTS = [
    ("1 Top-Left",     36, 36),
    ("2 Bottom-Left",  36, 122),
    ("3 Bottom-Right", 96, 122),
    ("4 Top-Right",    96, 36),
    ("5 Center",       66, 79),
    ("6 TICK",         65, 55),
]

def encode_coord(t):
    low = t & 0xFF
    if low in (0xFF, 0xFE):
        t -= 1; low = t & 0xFF
    high = ((t >> 8) & 0x03) << 6
    return high, low

def send_tap(tx, ty, holds=8):
    xh,xl = encode_coord(tx); yh,yl = encode_coord(ty)
    pkt = bytes([0xFF,xh,xl,yh,yl])
    for _ in range(holds):
        uart_out.write(pkt); utime.sleep_ms(25)
    uart_out.write(bytes([0xFF,0xFE,0xFE]))

def bootsel(): return rp2.bootsel_button() == 1
def wait_release():
    utime.sleep_ms(30)
    while bootsel(): utime.sleep_ms(10)
    utime.sleep_ms(30)

print("="*50)
print("SYNTHETIC 5-POINT + TICK (plumbing test)")
print("Order: TL, BL, BR, TR, Center, Tick")
print("Press BOOTSEL to fire each in turn.")
print("="*50)
for _ in range(3):
    led.on(); utime.sleep_ms(120); led.off(); utime.sleep_ms(120)

idx = 0
while True:
    if bootsel():
        wait_release()
        if idx < len(POINTS):
            name, x, y = POINTS[idx]
            led.on()
            send_tap(x, y)
            led.off()
            print("fired {}  ({}, {})".format(name, x, y))
            idx += 1
            if idx == len(POINTS):
                print(">>> sequence complete. Check pointercal. <<<")
                idx = 0
                print("(loops back to point 1 for another run)")
    utime.sleep_ms(15)
