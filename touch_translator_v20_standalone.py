# ============================================================
# EOS Touch Translator - v20  *** STANDALONE / PERMANENT ***
#
# Final production firmware. Powers up and works with NO setup:
#   - hardcoded panel range (no boot-time learn phase)
#   - 0-255 output (the range the genuine screen used - THE fix)
#   - correct byte order (high 7 bits first, low 7 bits second)
#   - per-axis scaling, transforms all False
#
# Save as main.py on the Pico. On power-up it runs immediately.
#
# HARDCODED PANEL RANGE (measured on this iiyama panel):
#   X 161-1907   Y 144-1926
#
# Works with the solved pointercal:
#   0 32800 -23009200 25080 0 -17543460 -42845
#
# OPTIONAL re-learn: hold BOOTSEL at any time to enter a 15s
# panel-wipe learn (only if the panel is ever swapped/changed).
# Normal operation never needs it.
#
# Wiring: CH0 (GP0/GP1) <- iiyama ; CH1 (GP4/GP5) -> Charon
# ============================================================

import machine
import utime
import rp2

BAUD = 9600
OUT_MAX = 255                 # 0-255 output range (the working range)
LEARN_SECONDS = 15

# --- HARDCODED panel range - no learn needed on boot ---
X_MIN, X_MAX = 161, 1907
Y_MIN, Y_MAX = 144, 1926

INVERT_X = False
INVERT_Y = False
SWAP_XY  = False
SMOOTH_SAMPLES = 5

uart_in = machine.UART(0, baudrate=BAUD, tx=machine.Pin(0), rx=machine.Pin(1),
                        bits=8, parity=None, stop=1)
uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)
led = machine.Pin(25, machine.Pin.OUT)

_rxbuf = bytearray()

def read_raw():
    global _rxbuf
    if uart_in.any():
        d = uart_in.read()
        if d:
            _rxbuf.extend(d)
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

def median(v):
    return sorted(v)[len(v)//2]

def map_axis(raw, lo, hi, invert):
    if hi <= lo: return 0
    v = (raw - lo) * OUT_MAX // (hi - lo)
    if v < 0: v = 0
    if v > OUT_MAX: v = OUT_MAX
    if invert: v = OUT_MAX - v
    return v

def encode_coord(v):
    low = v & 0xFF
    if low == 0xFF or low == 0xFE:
        v -= 1; low = v & 0xFF
    high = ((v >> 8) & 0x03) << 6
    return high, low

def bootsel():
    return rp2.bootsel_button() == 1

def learn_ranges():
    """Optional re-learn, only if BOOTSEL held. Normally unused."""
    global X_MIN,X_MAX,Y_MIN,Y_MAX
    print("RE-LEARN: wipe whole panel {}s...".format(LEARN_SECONDS))
    xmn=ymn=99999; xmx=ymx=-1
    start=utime.ticks_ms(); lastb=start
    while utime.ticks_diff(utime.ticks_ms(),start) < LEARN_SECONDS*1000:
        r=read_raw()
        if r and r[0]:
            _,rx,ry=r
            if rx<xmn:xmn=rx
            if rx>xmx:xmx=rx
            if ry<ymn:ymn=ry
            if ry>ymx:ymx=ry
        now=utime.ticks_ms()
        if utime.ticks_diff(now,lastb)>150:
            led.toggle(); lastb=now
        utime.sleep_ms(1)
    if xmx>xmn and ymx>ymn:
        X_MIN,X_MAX,Y_MIN,Y_MAX = xmn,xmx,ymn,ymx
    led.on()
    print("RE-LEARNED: X {}-{}  Y {}-{}".format(X_MIN,X_MAX,Y_MIN,Y_MAX))
    print("(NOTE: reverts to hardcoded values on next power cycle;")
    print(" update the file's X_MIN/X_MAX/Y_MIN/Y_MAX to keep it.)")

# brief startup blink then straight to work - no learn phase
for _ in range(3):
    led.on(); utime.sleep_ms(120); led.off(); utime.sleep_ms(120)
led.on()

print("EOS Touch Translator v20 - STANDALONE")
print("Panel range X {}-{}  Y {}-{}  out 0-{}".format(
    X_MIN,X_MAX,Y_MIN,Y_MAX,OUT_MAX))
print("Ready. (hold BOOTSEL only if re-learning a new panel)")

was_touching = False
x_hist = []; y_hist = []

while True:
    if bootsel():
        # require a deliberate ~1s hold to avoid accidental re-learn
        t0 = utime.ticks_ms()
        while bootsel():
            if utime.ticks_diff(utime.ticks_ms(), t0) > 1000:
                learn_ranges()
                x_hist=[]; y_hist=[]; was_touching=False
                break
            utime.sleep_ms(10)

    r = read_raw()
    if r:
        touch, rx, ry = r
        if touch:
            tx = map_axis(rx, X_MIN, X_MAX, INVERT_X)
            ty = map_axis(ry, Y_MIN, Y_MAX, INVERT_Y)
            if SWAP_XY: tx, ty = ty, tx
            x_hist.append(tx); y_hist.append(ty)
            if len(x_hist) > SMOOTH_SAMPLES:
                x_hist.pop(0); y_hist.pop(0)
            mx = median(x_hist); my = median(y_hist)
            xh,xl = encode_coord(mx); yh,yl = encode_coord(my)
            uart_out.write(bytes([0xFF,xh,xl,yh,yl]))
            was_touching = True
        else:
            if was_touching:
                uart_out.write(bytes([0xFF,0xFE,0xFE]))
                was_touching = False
            x_hist=[]; y_hist=[]
        led.toggle()
    utime.sleep_ms(1)
