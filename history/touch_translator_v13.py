# ============================================================
# EOS Touch Translator - v13  (10-bit, balanced filtering)
#
# v11/v12 over-filtered: marginal-contact touches (esp. screen
# centre on a resistive panel) failed to register. v13 keeps the
# part that matters - OUTLIER REJECTION of the touch-down/lift-off
# extreme spikes (0 <-> 1023) - but drops the aggressive
# stability-gate and long warmup that were swallowing valid taps.
#
# - WARMUP 1 sample (just skip the very first touch-down sample)
# - OUTLIER rejection kept (rejects samples that jump > tol from
#   the running median) -> kills the dangerous spikes
# - Median-of-window smoothing, emit every sample after warmup
#   (responsive, like v10) but spike-protected
#
# 10-bit protocol. Raw passthrough orientation.
# ============================================================

import machine
import utime

BAUD = 9600

INVERT_X = False
INVERT_Y = False
SWAP_XY  = False

SMOOTH_SAMPLES = 5
WARMUP_SAMPLES = 1
OUTLIER_TOL    = 200    # reject only big jumps (the 0<->1023 spikes)

uart_in = machine.UART(0, baudrate=BAUD, tx=machine.Pin(0), rx=machine.Pin(1),
                        bits=8, parity=None, stop=1)
uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)

led = machine.Pin(25, machine.Pin.OUT)

print("=" * 50)
print("EOS Touch Translator v13 - 10bit balanced")
print("warmup={} outlier_tol={} smooth={}".format(
    WARMUP_SAMPLES, OUTLIER_TOL, SMOOTH_SAMPLES))
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
                    if sample_count <= WARMUP_SAMPLES:
                        buf = buf[5:]
                        continue

                    # Outlier rejection - only the big spikes
                    if x_hist:
                        cmx = median(x_hist); cmy = median(y_hist)
                        if abs(tx_raw - cmx) > OUTLIER_TOL or abs(ty_raw - cmy) > OUTLIER_TOL:
                            buf = buf[5:]
                            continue

                    x_hist.append(tx_raw); y_hist.append(ty_raw)
                    if len(x_hist) > SMOOTH_SAMPLES:
                        x_hist.pop(0); y_hist.pop(0)

                    tx = median(x_hist); ty = median(y_hist)
                    if SWAP_XY:
                        tx, ty = ty, tx
                    xh, xl = encode_coord(tx)
                    yh, yl = encode_coord(ty)
                    uart_out.write(bytes([0xFF, xh, xl, yh, yl]))
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
                led.toggle()
                buf = buf[5:]
    utime.sleep_ms(1)
