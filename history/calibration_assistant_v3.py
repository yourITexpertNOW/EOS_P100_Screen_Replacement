# ============================================================
# EOS Calibration Assistant v3  -  full run, confirmed coords
#
# Runs the entire 5-point calibration with NO screen swap:
#   - synthetic taps for navigation (proven under genuine cal)
#   - real finger + SAMPLE-AND-HOLD for the 5 calibration points
#     (settles, locks one clean coordinate, discards lift-off)
#   - synthetic tap on the Tick to save
#
# Confirmed synthetic tap map (genuine pointercal, 10-bit):
#   Service 1           (38, 40)
#   Touchscreen cal bar (50, 122)
#   Calibration finger  (51, 97)
#   Tick (save)         (65, 55)
#
# CONTROL: BOOTSEL steps through the sequence. LED blinks the
# step number. In the PHYSICAL step, press BOOTSEL again when
# all 5 points are done to advance to the Tick.
#
# STEPS:
#   press 1 -> tap Service 1
#   press 2 -> tap Touchscreen calibration bar
#   press 3 -> tap Calibration finger (starts the 5-point routine)
#   press 4 -> PHYSICAL sample-and-hold (do the 5 finger points),
#              then press BOOTSEL again to finish
#   press 5 -> tap Tick to save
#
# Decode: byte order high-7/low-7, per-axis auto-range learned.
# Run a 15s panel wipe learn at boot BEFORE the finger points,
# so physical touches map to full 0-1023 for a clean calibration.
#
# Wiring: CH0 (GP0/GP1) <- iiyama ; CH1 (GP4/GP5) -> Charon
# ============================================================

import machine
import utime
import rp2

BAUD = 9600
LEARN_SECONDS = 15
TENBIT_MAX = 1023

uart_in = machine.UART(0, baudrate=BAUD, tx=machine.Pin(0), rx=machine.Pin(1),
                        bits=8, parity=None, stop=1)
uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)
led = machine.Pin(25, machine.Pin.OUT)

# ---- confirmed navigation tap targets (10-bit, genuine cal) ----
SERVICE1   = (38, 40)
CAL_BAR    = (50, 122)
CAL_FINGER = (51, 97)
TICK       = (65, 55)

# ---- per-axis learned ranges (filled by learn phase) ----
X_MIN, X_MAX, Y_MIN, Y_MAX = 167, 1920, 142, 1930   # sane defaults

SMOOTH_SAMPLES = 5
SETTLE_WINDOW  = 6
SETTLE_TOL     = 25
OUTLIER_TOL    = 250

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

def encode_coord(t):
    low = t & 0xFF
    if low == 0xFF or low == 0xFE:
        t -= 1; low = t & 0xFF
    high = ((t >> 8) & 0x03) << 6
    return high, low

def map_axis(raw, lo, hi):
    if hi <= lo: return 0
    v = (raw - lo) * TENBIT_MAX // (hi - lo)
    return max(0, min(TENBIT_MAX, v))

def send_tap(target, holds=6):
    tx, ty = target
    xh,xl = encode_coord(tx); yh,yl = encode_coord(ty)
    pkt = bytes([0xFF,xh,xl,yh,yl])
    for _ in range(holds):
        uart_out.write(pkt); utime.sleep_ms(20)
    uart_out.write(bytes([0xFF,0xFE,0xFE]))

def bootsel():
    return rp2.bootsel_button() == 1

def wait_release():
    utime.sleep_ms(30)
    while bootsel(): utime.sleep_ms(10)
    utime.sleep_ms(30)

def blink(n):
    for _ in range(n):
        led.on(); utime.sleep_ms(120); led.off(); utime.sleep_ms(120)

def learn_ranges():
    global X_MIN,X_MAX,Y_MIN,Y_MAX
    print("LEARN: wipe WHOLE panel for {}s (all edges+corners)".format(LEARN_SECONDS))
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

def physical_mode():
    """Real finger, sample-and-hold. Press BOOTSEL to finish."""
    print("PHYSICAL: touch the 5 points. BOOTSEL when done.")
    was=False; xh=[]; yh=[]; locked=None; pts=0
    led.on()
    while True:
        if bootsel():
            wait_release()
            if was:
                uart_out.write(bytes([0xFF,0xFE,0xFE]))
            print("physical done ({} points locked)".format(pts))
            return
        r=read_raw()
        if r:
            touch,rx,ry=r
            tx=map_axis(rx,X_MIN,X_MAX); ty=map_axis(ry,Y_MIN,Y_MAX)
            if touch:
                if xh:
                    cmx=median(xh); cmy=median(yh)
                    if abs(tx-cmx)>OUTLIER_TOL or abs(ty-cmy)>OUTLIER_TOL:
                        continue
                xh.append(tx); yh.append(ty)
                if len(xh)>SETTLE_WINDOW: xh.pop(0); yh.pop(0)
                if locked is None and len(xh)>=SETTLE_WINDOW:
                    if (max(xh)-min(xh)<=SETTLE_TOL and max(yh)-min(yh)<=SETTLE_TOL):
                        locked=(median(xh),median(yh)); pts+=1
                        print("  LOCK point {} ({},{})".format(pts,locked[0],locked[1]))
                if locked is not None:
                    a,b=encode_coord(locked[0]); c,d=encode_coord(locked[1])
                    uart_out.write(bytes([0xFF,a,b,c,d]))
                was=True
            else:
                if was:
                    uart_out.write(bytes([0xFF,0xFE,0xFE]))
                was=False; xh=[]; yh=[]; locked=None
        utime.sleep_ms(1)

# ---- boot ----
for _ in range(3):
    led.on(); utime.sleep_ms(150); led.off(); utime.sleep_ms(150)

print("="*50)
print("EOS Calibration Assistant v3")
print("Steps: 1 Service1  2 CalBar  3 CalFinger  4 FINGERx5  5 Tick")
print("="*50)
learn_ranges()   # do the wipe now, before calibration

step = 0
while True:
    if bootsel():
        wait_release()
        step += 1
        if step > 5: step = 0
        if step == 1:
            print("Step 1: tap Service 1", SERVICE1); blink(1); send_tap(SERVICE1)
        elif step == 2:
            print("Step 2: tap Cal bar", CAL_BAR); blink(2); send_tap(CAL_BAR)
        elif step == 3:
            print("Step 3: tap Cal finger", CAL_FINGER); blink(3); send_tap(CAL_FINGER)
        elif step == 4:
            print("Step 4: PHYSICAL points"); blink(4); physical_mode()
        elif step == 5:
            print("Step 5: tap Tick", TICK); blink(5); send_tap(TICK)
            print(">>> calibration saved. Back up pointercal now! <<<")
    utime.sleep_ms(15)
