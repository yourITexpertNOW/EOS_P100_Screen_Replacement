# ============================================================
# EOS Touch Translator - v17  *** AUTO-RANGE LEARNING ***
#
# Full fix stack:
#   byte order (v14) + ~11-bit panel (v15) + per-axis (v16)
#   + v17: LEARN each axis's true min/max instead of hardcoding.
#
# Hardcoded ranges from a single drag caused saturation (a later
# touch exceeded the assumed max -> clamped to 1023). This version
# has a CALIBRATION PHASE: wipe the whole panel (all edges +
# corners) for ~15s; it records true min/max per axis, then uses
# them for clean full-range per-axis mapping.
#
# FLOW:
#   1. On boot: 15-second LEARN phase (LED fast-blinks).
#      Wipe finger over the ENTIRE panel - all 4 edges, 4 corners,
#      press right to the bezel on every side.
#   2. After 15s: prints learned ranges, switches to RUN mode,
#      outputs translated 10-bit packets normally.
#
# Press BOOTSEL during RUN to re-learn (re-enter calibration).
#
# Orientation: raw passthrough. EOS calibration handles flips.
# ============================================================

import machine
import utime
import rp2

BAUD = 9600
LEARN_SECONDS = 15

uart_in = machine.UART(0, baudrate=BAUD, tx=machine.Pin(0), rx=machine.Pin(1),
                        bits=8, parity=None, stop=1)
uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)
led = machine.Pin(25, machine.Pin.OUT)

INVERT_X = False
INVERT_Y = False
SWAP_XY  = False
SMOOTH_SAMPLES = 5
TENBIT_MAX = 1023

_rxbuf = bytearray()

def read_raw():
    """Return (touch, raw_x, raw_y) for next complete frame, or None."""
    global _rxbuf
    if uart_in.any():
        data = uart_in.read()
        if data:
            _rxbuf.extend(data)
    out = None
    while len(_rxbuf) >= 5:
        if not (_rxbuf[0] & 0x80):
            _rxbuf = _rxbuf[1:]; continue
        b0,b1,b2,b3,b4 = _rxbuf[0:5]
        touch = b0 & 0x01
        rx = ((b1 & 0x7F) << 7) | (b2 & 0x7F)
        ry = ((b3 & 0x7F) << 7) | (b4 & 0x7F)
        out = (touch, rx, ry)
        _rxbuf = _rxbuf[5:]
    return out

def median(vals):
    return sorted(vals)[len(vals)//2]

def encode_coord(tenbit):
    low = tenbit & 0xFF
    if low == 0xFF or low == 0xFE:
        tenbit -= 1
        low = tenbit & 0xFF
    high = ((tenbit >> 8) & 0x03) << 6
    return high, low

def bootsel():
    return rp2.bootsel_button() == 1

def learn_ranges():
    print("=" * 50)
    print("LEARN PHASE - wipe the WHOLE panel for {}s".format(LEARN_SECONDS))
    print("Cover every edge and corner, press to the bezel!")
    print("=" * 50)
    xmin = ymin = 99999
    xmax = ymax = -1
    start = utime.ticks_ms()
    last_blink = start
    while utime.ticks_diff(utime.ticks_ms(), start) < LEARN_SECONDS*1000:
        r = read_raw()
        if r:
            touch, rx, ry = r
            if touch:
                if rx < xmin: xmin = rx
                if rx > xmax: xmax = rx
                if ry < ymin: ymin = ry
                if ry > ymax: ymax = ry
        now = utime.ticks_ms()
        if utime.ticks_diff(now, last_blink) > 150:
            led.toggle(); last_blink = now
        utime.sleep_ms(1)
    # safety margins in case bezel not fully reached
    if xmax <= xmin: xmin, xmax = 0, 2047
    if ymax <= ymin: ymin, ymax = 0, 2047
    led.on()
    print("LEARNED:  X {}-{}   Y {}-{}".format(xmin,xmax,ymin,ymax))
    print("Switching to RUN mode.")
    print()
    return xmin, xmax, ymin, ymax

def map_axis(raw, lo, hi, invert):
    if hi <= lo: return 0
    v = (raw - lo) * TENBIT_MAX // (hi - lo)
    if v < 0: v = 0
    if v > TENBIT_MAX: v = TENBIT_MAX
    if invert: v = TENBIT_MAX - v
    return v

# startup blink
for _ in range(3):
    led.on(); utime.sleep_ms(150); led.off(); utime.sleep_ms(150)

print("EOS Touch Translator v17 - AUTO-RANGE")
X_MIN, X_MAX, Y_MIN, Y_MAX = learn_ranges()

was_touching = False
x_hist = []; y_hist = []

while True:
    if bootsel():
        while bootsel(): utime.sleep_ms(10)
        X_MIN, X_MAX, Y_MIN, Y_MAX = learn_ranges()
        x_hist=[]; y_hist=[]; was_touching=False

    r = read_raw()
    if r:
        touch, rx, ry = r
        if touch:
            tx = map_axis(rx, X_MIN, X_MAX, INVERT_X)
            ty = map_axis(ry, Y_MIN, Y_MAX, INVERT_Y)
            x_hist.append(tx); y_hist.append(ty)
            if len(x_hist) > SMOOTH_SAMPLES:
                x_hist.pop(0); y_hist.pop(0)
            mx = median(x_hist); my = median(y_hist)
            if SWAP_XY: mx, my = my, mx
            xh,xl = encode_coord(mx); yh,yl = encode_coord(my)
            uart_out.write(bytes([0xFF,xh,xl,yh,yl]))
            print("raw({:5d},{:5d}) 10bit({:4d},{:4d})".format(rx,ry,mx,my))
            was_touching = True
        else:
            if was_touching:
                uart_out.write(bytes([0xFF,0xFE,0xFE]))
                print("RELEASE")
                was_touching = False
            x_hist=[]; y_hist=[]
        led.toggle()
    utime.sleep_ms(1)
