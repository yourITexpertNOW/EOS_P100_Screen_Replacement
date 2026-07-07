# ============================================================
# EOS Touch Translator - v16  *** PER-AXIS SCALING ***
#
# The full chain of fixes, now complete:
#   v14: byte order (high 7 bits first, low 7 bits second)
#   v15: panel is ~11-bit not 14-bit
#   v16: X and Y have DIFFERENT ranges - scale each independently
#
# Measured from clean full-panel drags:
#   X: 185 - 1876   (span 1691)
#   Y: 145 - 1027   (span  882)
# X uses ~2x the numeric range of Y. A single scale factor
# compresses one axis - THE reason calibration never worked.
#
# Each axis is now mapped from its own [min,max] to 0-1023,
# so both axes use the full output range. EOS calibration then
# only has to do fine alignment, not fight a 2x axis mismatch.
#
# NOTE: the MIN/MAX below are from one measurement session.
# If touches don't quite reach screen edges, widen them slightly;
# if they clip/saturate before the edge, narrow them.
#
# Orientation: raw passthrough (EOS calibration handles flips).
# ============================================================

import machine
import utime

BAUD = 9600

# Per-axis calibration range (measured from full-panel drags)
X_MIN, X_MAX = 185, 1876
Y_MIN, Y_MAX = 145, 1027

INVERT_X = False
INVERT_Y = False
SWAP_XY  = False

SMOOTH_SAMPLES = 5
OUTLIER_TOL    = 200

uart_in = machine.UART(0, baudrate=BAUD, tx=machine.Pin(0), rx=machine.Pin(1),
                        bits=8, parity=None, stop=1)
uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)
led = machine.Pin(25, machine.Pin.OUT)

print("=" * 50)
print("EOS Touch Translator v16 - PER-AXIS SCALING")
print("X range {}-{}  Y range {}-{}".format(X_MIN,X_MAX,Y_MIN,Y_MAX))
print("=" * 50)

for _ in range(3):
    led.on(); utime.sleep_ms(150); led.off(); utime.sleep_ms(150)
led.on()

TENBIT_MAX = 1023
buf = bytearray()
was_touching = False
x_hist = []; y_hist = []

def median(vals):
    return sorted(vals)[len(vals)//2]

def map_axis(raw, lo, hi, invert):
    if hi <= lo:
        return 0
    v = (raw - lo) * TENBIT_MAX // (hi - lo)
    if v < 0: v = 0
    if v > TENBIT_MAX: v = TENBIT_MAX
    if invert:
        v = TENBIT_MAX - v
    return v

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
                b0,b1,b2,b3,b4 = buf[0:5]
                if not (b0 & 0x80):
                    buf = buf[1:]; continue
                touch = b0 & 0x01
                raw_x = ((b1 & 0x7F) << 7) | (b2 & 0x7F)
                raw_y = ((b3 & 0x7F) << 7) | (b4 & 0x7F)

                tx = map_axis(raw_x, X_MIN, X_MAX, INVERT_X)
                ty = map_axis(raw_y, Y_MIN, Y_MAX, INVERT_Y)

                if touch:
                    if x_hist:
                        cmx = median(x_hist); cmy = median(y_hist)
                        if abs(tx-cmx) > OUTLIER_TOL or abs(ty-cmy) > OUTLIER_TOL:
                            buf = buf[5:]; continue
                    x_hist.append(tx); y_hist.append(ty)
                    if len(x_hist) > SMOOTH_SAMPLES:
                        x_hist.pop(0); y_hist.pop(0)
                    mx = median(x_hist); my = median(y_hist)
                    if SWAP_XY:
                        mx, my = my, mx
                    xh,xl = encode_coord(mx)
                    yh,yl = encode_coord(my)
                    uart_out.write(bytes([0xFF,xh,xl,yh,yl]))
                    print("raw({:5d},{:5d}) 10bit({:4d},{:4d})  FF {:02X} {:02X} {:02X} {:02X}".format(
                        raw_x, raw_y, mx, my, xh, xl, yh, yl))
                    was_touching = True
                else:
                    if was_touching:
                        uart_out.write(bytes([0xFF,0xFE,0xFE]))
                        print("RELEASE")
                        was_touching = False
                    x_hist=[]; y_hist=[]
                led.toggle()
                buf = buf[5:]
    utime.sleep_ms(1)
