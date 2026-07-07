# ============================================================
# EOS Calibration Assistant v1
#
# Combines everything learned today:
#  - 10-bit iRV protocol encoding (the breakthrough)
#  - Synthetic navigation taps (proven reliable, repeatable)
#  - SAMPLE-AND-HOLD physical touch for the 5 calibration points
#    (makes a real finger behave like a clean synthetic tap:
#     settle -> lock -> emit one clean point -> clean release,
#     discarding lift-off spikes)
#
# CONTROL: the Pico's onboard BOOTSEL button steps through modes.
# Press it to advance. The LED pattern shows the current mode.
#
# SEQUENCE (press BOOTSEL to advance each step):
#   Mode 0  IDLE          - nothing sent. (startup)
#   Mode 1  NAV: Service1  - taps Service 1 button (34,68)
#   Mode 2  NAV: StartCal  - taps calibration start button *
#   Mode 3  PHYSICAL       - sample-and-hold passthrough for the
#                            5 calibration points (use your finger)
#   Mode 4  NAV: Tick      - taps the Tick/OK (80,96) as fallback
#   (wraps back to IDLE)
#
# * The calibration start button (hand-pointing icon) coordinate
#   is a placeholder below - update START_CAL_XY once measured.
#
# Wiring unchanged: CH0 (GP0/GP1) <- iiyama; CH1 (GP4/GP5) -> Charon
# ============================================================

import machine
import utime
import rp2

BAUD = 9600

uart_in = machine.UART(0, baudrate=BAUD, tx=machine.Pin(0), rx=machine.Pin(1),
                        bits=8, parity=None, stop=1)
uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)
led = machine.Pin(25, machine.Pin.OUT)

# ---- Navigation tap targets (iRV 10-bit-derived units Brandon mapped) ----
SERVICE1_XY   = (34, 68)
START_CAL_XY  = (210, 80)   # PLACEHOLDER - the hand/finger start button; update!
TICK_XY       = (80, 96)

# ---- 10-bit encoding ----
EGALAX_MAX = 16383
TENBIT_MAX = 1023

def encode_coord(tenbit):
    low = tenbit & 0xFF
    if low == 0xFF or low == 0xFE:
        tenbit -= 1
        low = tenbit & 0xFF
    high = ((tenbit >> 8) & 0x03) << 6
    return high, low

def send_tap(x10, y10, holds=6):
    """Synthetic tap: clean touch-down, brief hold, clean release."""
    xh, xl = encode_coord(x10)
    yh, yl = encode_coord(y10)
    pkt = bytes([0xFF, xh, xl, yh, yl])
    for _ in range(holds):
        uart_out.write(pkt)
        utime.sleep_ms(20)
    uart_out.write(bytes([0xFF, 0xFE, 0xFE]))

def scale_10bit(val):
    s = (val * TENBIT_MAX) // EGALAX_MAX
    if s < 0: s = 0
    if s > TENBIT_MAX: s = TENBIT_MAX
    return s

def median(vals):
    return sorted(vals)[len(vals)//2]

# ---- BOOTSEL button read (no wiring needed on Pico H) ----
def bootsel_pressed():
    return rp2.bootsel_button() == 1

def wait_button_release():
    while bootsel_pressed():
        utime.sleep_ms(10)
    utime.sleep_ms(50)  # debounce

# ---- Sample-and-hold physical touch ----
# Settle detection: collect samples; once a window of them agrees
# within tolerance, lock and emit that single point. Re-emit the
# locked point steadily so EOS sees a stable hold. On release,
# emit clean release, discard the lift-off tail.
SETTLE_WINDOW = 5
SETTLE_TOL    = 25          # 10-bit units; tight = clean lock
OUTLIER_TOL   = 200

def physical_mode():
    """Runs until BOOTSEL pressed. Sample-and-hold per touch."""
    buf = bytearray()
    was_touching = False
    xh_hist = []; yh_hist = []
    locked = None
    led.on()
    while True:
        if bootsel_pressed():
            wait_button_release()
            # ensure a release is sent if mid-touch
            if was_touching:
                uart_out.write(bytes([0xFF, 0xFE, 0xFE]))
            return
        if uart_in.any():
            data = uart_in.read()
            if data:
                buf.extend(data)
                while len(buf) >= 5:
                    b0,b1,b2,b3,b4 = buf[0:5]
                    if not (b0 & 0x80):
                        buf = buf[1:]; continue
                    touch = b0 & 0x01
                    rx = (b1 & 0x7F) | ((b2 & 0x7F) << 7)
                    ry = (b3 & 0x7F) | ((b4 & 0x7F) << 7)
                    tx = scale_10bit(rx); ty = scale_10bit(ry)

                    if touch:
                        # outlier rejection vs current lock/history
                        if xh_hist:
                            cmx = median(xh_hist); cmy = median(yh_hist)
                            if abs(tx-cmx) > OUTLIER_TOL or abs(ty-cmy) > OUTLIER_TOL:
                                buf = buf[5:]; continue
                        xh_hist.append(tx); yh_hist.append(ty)
                        if len(xh_hist) > SETTLE_WINDOW:
                            xh_hist.pop(0); yh_hist.pop(0)

                        if locked is None and len(xh_hist) >= SETTLE_WINDOW:
                            if (max(xh_hist)-min(xh_hist) <= SETTLE_TOL and
                                max(yh_hist)-min(yh_hist) <= SETTLE_TOL):
                                locked = (median(xh_hist), median(yh_hist))
                                print("LOCK ({},{})".format(*locked))

                        # emit the locked point steadily (clean hold)
                        if locked is not None:
                            xh,xl = encode_coord(locked[0])
                            yh,yl = encode_coord(locked[1])
                            uart_out.write(bytes([0xFF,xh,xl,yh,yl]))
                        was_touching = True
                    else:
                        if was_touching:
                            uart_out.write(bytes([0xFF,0xFE,0xFE]))
                            print("RELEASE (locked point held)")
                        was_touching = False
                        xh_hist=[]; yh_hist=[]; locked=None
                    buf = buf[5:]
        utime.sleep_ms(1)

# ---- LED mode indicator ----
def blink(n):
    for _ in range(n):
        led.on(); utime.sleep_ms(120); led.off(); utime.sleep_ms(120)

print("=" * 50)
print("EOS Calibration Assistant v1")
print("Press BOOTSEL to advance through steps:")
print(" 1=Service1  2=StartCal  3=PHYSICAL(finger)  4=Tick")
print("=" * 50)

mode = 0
while True:
    # wait for a button press to advance
    if bootsel_pressed():
        wait_button_release()
        mode += 1
        if mode > 4:
            mode = 0

        if mode == 0:
            print("Mode 0: IDLE")
        elif mode == 1:
            print("Mode 1: tapping Service 1 (34,68)")
            blink(1); send_tap(*SERVICE1_XY)
        elif mode == 2:
            print("Mode 2: tapping calibration START button", START_CAL_XY)
            blink(2); send_tap(*START_CAL_XY)
        elif mode == 3:
            print("Mode 3: PHYSICAL sample-and-hold - touch the 5 points")
            print("        press BOOTSEL again when done to advance")
            blink(3)
            physical_mode()   # blocks until BOOTSEL pressed again
            print("       exited physical mode")
        elif mode == 4:
            print("Mode 4: tapping Tick/OK (80,96) [fallback]")
            blink(4); send_tap(*TICK_XY)

    utime.sleep_ms(20)
