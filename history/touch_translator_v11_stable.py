# ============================================================
# EOS Touch Translator - v11  (10-bit + stability gating)
#
# Builds on v10's correct 10-bit protocol, adding suppression
# of the touch-down / lift-off transient glitches that swing
# the raw reading to extremes (e.g. X jumping 0 <-> 1007 in
# consecutive samples). At full 10-bit resolution these
# glitches fling the cursor across the whole screen.
#
# Strategy:
#  - WARMUP: ignore the first N samples of every new touch
#    (touch-down is unstable)
#  - STABILITY GATE: only emit when the median window is
#    "settled" - i.e. recent samples agree within a tolerance
#  - Discard outlier samples that differ wildly from the
#    running median (rejects lift-off spikes)
#
# Orientation: RAW passthrough; EOS calibration handles it.
# Use SHORT, DELIBERATE taps - but hold ~0.5s so warmup can pass.
# ============================================================

import machine
import utime

BAUD = 9600

INVERT_X = False
INVERT_Y = False
SWAP_XY  = False

SMOOTH_SAMPLES = 7
WARMUP_SAMPLES = 3        # ignore first N samples of each touch
OUTLIER_TOL    = 150      # reject samples >this far from running median (10-bit units)
STABLE_TOL     = 40       # window must agree within this to emit

uart_in = machine.UART(0, baudrate=BAUD, tx=machine.Pin(0), rx=machine.Pin(1),
                        bits=8, parity=None, stop=1)
uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)

led = machine.Pin(25, machine.Pin.OUT)

print("=" * 50)
print("EOS Touch Translator v11 - 10bit + stability gating")
print("warmup={} outlier_tol={} stable_tol={}".format(
    WARMUP_SAMPLES, OUTLIER_TOL, STABLE_TOL))
print("=" * 50)

for _ in range(3):
    led.on(); utime.sleep_ms(150); led.off(); utime.sleep_ms(150)
led.on()

EGALAX_MAX = 16383
TENBIT_MAX = 1023

buf = bytearray()
was_touching = False
sample_count = 0
x_hist = []
y_hist = []
last_emit = None

def median(vals):
    return sorted(vals)[len(vals)//2]

def scale_10bit(val, invert):
    scaled = (val * TENBIT_MAX) // EGALAX_MAX
    if invert:
        scaled = TENBIT_MAX - scaled
    if scaled < 0: scaled = 0
    if scaled > TENBIT_MAX: scaled = TENBIT_MAX
    return scaled

def encode_coord(tenbit):
    low = tenbit & 0xFF
    if low == 0xFF or low == 0xFE:
        tenbit -= 1
        low = tenbit & 0xFF
    high = ((tenbit >> 8) & 0x03) << 6
    return high, low

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
                tx_raw = scale_10bit(raw_x, INVERT_X)
                ty_raw = scale_10bit(raw_y, INVERT_Y)

                if touch:
                    sample_count += 1

                    # WARMUP: skip unstable touch-down samples
                    if sample_count <= WARMUP_SAMPLES:
                        buf = buf[5:]
                        continue

                    # OUTLIER REJECTION against running median
                    if x_hist:
                        cur_mx = median(x_hist)
                        cur_my = median(y_hist)
                        if abs(tx_raw - cur_mx) > OUTLIER_TOL or abs(ty_raw - cur_my) > OUTLIER_TOL:
                            buf = buf[5:]
                            continue

                    x_hist.append(tx_raw); y_hist.append(ty_raw)
                    if len(x_hist) > SMOOTH_SAMPLES:
                        x_hist.pop(0); y_hist.pop(0)

                    # STABILITY GATE: only emit if window is settled
                    if len(x_hist) >= 3:
                        if (max(x_hist) - min(x_hist) <= STABLE_TOL and
                            max(y_hist) - min(y_hist) <= STABLE_TOL):
                            tx = median(x_hist); ty = median(y_hist)
                            if SWAP_XY:
                                tx, ty = ty, tx
                            xh, xl = encode_coord(tx)
                            yh, yl = encode_coord(ty)
                            uart_out.write(bytes([0xFF, xh, xl, yh, yl]))
                            last_emit = (tx, ty)
                            print("EMIT 10bit({:4d},{:4d})  FF {:02X} {:02X} {:02X} {:02X}".format(
                                tx, ty, xh, xl, yh, yl))
                    was_touching = True
                else:
                    if was_touching:
                        uart_out.write(bytes([0xFF, 0xFE, 0xFE]))
                        print("RELEASE")
                        was_touching = False
                    sample_count = 0
                    x_hist = []; y_hist = []
                    last_emit = None
                led.toggle()
                buf = buf[5:]
    utime.sleep_ms(1)
