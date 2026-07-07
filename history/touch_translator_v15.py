# ============================================================
# EOS Touch Translator - v14  *** BYTE ORDER FIX ***
#
# THE ROOT CAUSE, finally found via raw-packet sniffing:
# the iiyama eGalax decode had HIGH and LOW bytes SWAPPED.
#
# Proven by a smooth vertical finger sweep showing a clean
# 7-bit rollover:  b3=0E b4=7F  ->  b3=0F b4=00
#   - wrong decode (b4 high): 16270 -> 15   (impossible jump)
#   - right decode (b3 high):  1919 -> 1920  (smooth +1)
#
# CORRECT eGalax 5-byte frame:
#   byte0 = 0x80 | touch_bit
#   byte1 = X HIGH 7 bits
#   byte2 = X LOW  7 bits
#   byte3 = Y HIGH 7 bits
#   byte4 = Y LOW  7 bits
#   value = (high << 7) | low   -> 14-bit, 0..16383
#
# TWO fixes together (v14 + v15):
#  1. BYTE ORDER: high 7 bits first, low 7 bits second.
#  2. PANEL RANGE: this iiyama reports ~11-bit coordinates
#     (0-~2000), NOT the full 14-bit eGalax range (0-16383).
#     Measured from edge-to-edge drags: X 183-1873, Y 142-1917.
#     Scaling by /16383 crushed everything into the bottom 12%
#     of output - the real reason touches bunched together and
#     calibration could never spread the points. Now /2047.
#
# Output: iRV 10-bit protocol (that part was correct).
# Orientation: raw passthrough (EOS calibration handles it).
# ============================================================

import machine
import utime

BAUD = 9600

INVERT_X = False
INVERT_Y = False
SWAP_XY  = False

SMOOTH_SAMPLES = 5
OUTLIER_TOL    = 200   # should now rarely trigger - kept as light safety

uart_in = machine.UART(0, baudrate=BAUD, tx=machine.Pin(0), rx=machine.Pin(1),
                        bits=8, parity=None, stop=1)
uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)
led = machine.Pin(25, machine.Pin.OUT)

print("=" * 50)
print("EOS Touch Translator v15 - byte order + 11-bit scale FIXED")
print("eGalax: byte1/3 = HIGH 7 bits, byte2/4 = LOW 7 bits")
print("=" * 50)

for _ in range(3):
    led.on(); utime.sleep_ms(150); led.off(); utime.sleep_ms(150)
led.on()

PANEL_MAX = 2047   # iiyama actual range is ~11-bit, NOT 14-bit eGalax max
TENBIT_MAX = 1023

buf = bytearray()
was_touching = False
x_hist = []; y_hist = []

def median(vals):
    return sorted(vals)[len(vals)//2]

def scale_10bit(val, invert):
    s = (val * TENBIT_MAX) // PANEL_MAX
    if invert:
        s = TENBIT_MAX - s
    if s < 0: s = 0
    if s > TENBIT_MAX: s = TENBIT_MAX
    return s

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

                # *** FIXED BYTE ORDER: high 7 bits first, low 7 bits second ***
                raw_x = ((b1 & 0x7F) << 7) | (b2 & 0x7F)
                raw_y = ((b3 & 0x7F) << 7) | (b4 & 0x7F)

                tx = scale_10bit(raw_x, INVERT_X)
                ty = scale_10bit(raw_y, INVERT_Y)

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
                    print("raw14({:5d},{:5d}) 10bit({:4d},{:4d})  FF {:02X} {:02X} {:02X} {:02X}".format(
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
