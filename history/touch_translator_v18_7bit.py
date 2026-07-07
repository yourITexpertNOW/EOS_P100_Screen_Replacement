# ============================================================
# EOS Touch Translator - v18  *** 7-BIT OUTPUT (0-127) ***
#
# THE OCCAM FIX. Every on-screen coordinate Brandon ever
# measured falls in 0-127:
#   Service1 (38,40) CalBar (50,122) CalFinger (51,97)
#   Tick (65,55) Nx-corner (25,100)  -- none exceed 127.
#
# The original iRV screen was effectively 7-BIT per axis (0-127).
# We were outputting 0-1023 (10-bit) = 8x too large, so all but
# the bottom sliver flew off-screen. This one scaling change
# should make the GENUINE pointercal work as-is, because it was
# solved for this 7-bit range.
#
# Keeps: correct byte order, per-axis auto-range learning.
# Changes: output scaled to 0-127, packed into the iRV low byte
#          (no high 2-bit field needed at this range).
#
# RUN WITH GENUINE POINTERCAL ACTIVE:
#   54720 0 14235840 -80 42560 10958800 60720
#
# Transforms all False (proven correct orientation).
# Wiring: CH0 (GP0/GP1) <- iiyama ; CH1 (GP4/GP5) -> Charon
# ============================================================

import machine
import utime
import rp2

BAUD = 9600
LEARN_SECONDS = 15
OUT_MAX = 127            # 7-bit output range

uart_in = machine.UART(0, baudrate=BAUD, tx=machine.Pin(0), rx=machine.Pin(1),
                        bits=8, parity=None, stop=1)
uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)
led = machine.Pin(25, machine.Pin.OUT)

INVERT_X = False
INVERT_Y = False
SWAP_XY  = False
SMOOTH_SAMPLES = 5

X_MIN, X_MAX, Y_MIN, Y_MAX = 159, 1917, 139, 1932   # defaults, learned at boot

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

# --- iRV encode for a 0-127 coordinate ---
# At this range the value fits in the low byte directly; the
# 2-bit "high" field stays 0. Avoid low byte hitting FE/FF.
def encode_coord(v):
    low = v & 0xFF
    if low == 0xFF or low == 0xFE:
        v -= 1; low = v & 0xFF
    high = ((v >> 8) & 0x03) << 6
    return high, low

def bootsel():
    return rp2.bootsel_button() == 1

def learn_ranges():
    global X_MIN,X_MAX,Y_MIN,Y_MAX
    print("LEARN: wipe WHOLE panel {}s (all edges+corners)".format(LEARN_SECONDS))
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
    print("LEARNED: X {}-{}  Y {}-{}".format(X_MIN,X_MAX,Y_MIN,Y_MAX))

for _ in range(3):
    led.on(); utime.sleep_ms(150); led.off(); utime.sleep_ms(150)

print("EOS Touch Translator v18 - 7-BIT OUTPUT (0-127)")
print("Run with GENUINE pointercal active.")
learn_ranges()

was_touching = False
x_hist = []; y_hist = []

while True:
    if bootsel():
        while bootsel(): utime.sleep_ms(10)
        learn_ranges()
        x_hist=[]; y_hist=[]; was_touching=False

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
            print("raw({:5d},{:5d}) 7bit({:3d},{:3d})".format(rx,ry,mx,my))
            was_touching = True
        else:
            if was_touching:
                uart_out.write(bytes([0xFF,0xFE,0xFE]))
                print("RELEASE")
                was_touching = False
            x_hist=[]; y_hist=[]
        led.toggle()
    utime.sleep_ms(1)
