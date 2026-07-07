# ============================================================
# EOS P100 Touch Translator
# iiyama T1531SR (eGalax RS232) --> iRV 5W232 protocol --> Charon
#
# Raspberry Pi Pico + Waveshare 2-CH RS232 Hat
#
# Channel 0: GP0 (TX), GP1 (RX) --> iiyama RS232 touch port
#   Wiring (crossed, as confirmed working for sniffing):
#     iiyama TXD (pin3) -> hat RX0
#     iiyama RXD (pin2) -> hat TX0
#     iiyama GND (pin5) -> hat GND
#
# Channel 1: GP4 (TX), GP5 (RX) --> Charon touchscreen port
#   Wiring: use the SAME orientation that made the original
#   iRV controller work correctly with the Charon
#   (labelled "straight through" - TX1->TXD, RX1->RXD on the
#   breakout board, due to the iRV's DCE-style pin convention)
#
# Protocol details:
#   iiyama (eGalax): 5 bytes
#     byte0: 0x80 | touch_state (1=down, 0=up)
#     byte1: X low 7 bits
#     byte2: X high 7 bits  (X = 0-16383)
#     byte3: Y low 7 bits
#     byte4: Y high 7 bits  (Y = 0-16383)
#
#   iRV (target, decoded from real captures):
#     Repeating 5-byte records while touched:
#       [0xFF, status1, X(0-255 inverted), status2, Y(0-255 inverted)]
#     Terminator on release:
#       [0xFF, 0xFE, 0xFE]
# ============================================================

import machine
import utime

BAUD = 9600

# Channel 0 - iiyama touch input
uart_in = machine.UART(0, baudrate=BAUD, tx=machine.Pin(0), rx=machine.Pin(1),
                        bits=8, parity=None, stop=1)

# Channel 1 - Charon touch output
uart_out = machine.UART(1, baudrate=BAUD, tx=machine.Pin(4), rx=machine.Pin(5),
                         bits=8, parity=None, stop=1)

led = machine.Pin(25, machine.Pin.OUT)

print("=" * 50)
print("EOS P100 Touch Translator")
print("iiyama (eGalax) -> iRV 5W232 -> Charon")
print("Baud: {} 8N1".format(BAUD))
print("=" * 50)

for _ in range(3):
    led.on()
    utime.sleep_ms(150)
    led.off()
    utime.sleep_ms(150)
led.on()

EGALAX_MAX = 16383  # 14-bit
IRV_MAX = 255       # 8-bit

buf = bytearray()
was_touching = False

def scale_and_invert(val):
    # Scale 0-16383 -> 0-255, then invert (iRV axes run opposite to eGalax)
    scaled = (val * IRV_MAX) // EGALAX_MAX
    return IRV_MAX - scaled

print("Listening for touch input...")
print()

while True:
    if uart_in.any():
        data = uart_in.read()
        if data:
            buf.extend(data)

            # Process complete 5-byte eGalax packets
            while len(buf) >= 5:
                b0, b1, b2, b3, b4 = buf[0:5]

                # Sanity check: byte0 should have bit7 set
                if not (b0 & 0x80):
                    # Misaligned - drop a byte and resync
                    buf = buf[1:]
                    continue

                touch = b0 & 0x01
                x = (b1 & 0x7F) | ((b2 & 0x7F) << 7)
                y = (b3 & 0x7F) | ((b4 & 0x7F) << 7)

                irv_x = scale_and_invert(x)
                irv_y = scale_and_invert(y)

                if touch:
                    # Send a touch sample
                    out = bytes([0xFF, 0x00, irv_x, 0x00, irv_y])
                    uart_out.write(out)
                    print("TOUCH  iiyama X={:5d} Y={:5d}  -> iRV X={:3d} Y={:3d}".format(
                        x, y, irv_x, irv_y))
                    was_touching = True
                else:
                    if was_touching:
                        # Touch released - send terminator
                        uart_out.write(bytes([0xFF, 0xFE, 0xFE]))
                        print("RELEASE")
                        was_touching = False

                led.toggle()
                buf = buf[5:]

    utime.sleep_ms(1)
