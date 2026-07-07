# ============================================================
# EOS P100 Touch Protocol Sniffer
# Raspberry Pi Pico + Waveshare 2-CH RS232 Hat
# Channel 1: GP4 (TX), GP5 (RX)
#
# Wiring:
#   RS232 hat Channel 1 DB9 --> iRV controller DB9
#   (use the included DB9 to 3-pin adapter cable)
#   Pin 2 (RX) on iRV side --> hat channel 1
#   Pin 3 (TX) on iRV side --> hat channel 1
#   Pin 5 (GND)            --> hat GND
#
# What this does:
#   Listens on the RS232 line from the iRV controller
#   Prints every byte received in hex format
#   Groups bytes into likely packets based on timing
#   Helps identify the sync byte and packet structure
# ============================================================

import machine
import utime

# Channel 1 UART - GP4=TX, GP5=RX
# Try common baud rates one at a time
# Start with 9600 - most common for industrial touchscreens
BAUD_RATE = 9600

uart = machine.UART(1, baudrate=BAUD_RATE, tx=machine.Pin(4), rx=machine.Pin(5),
                    bits=8, parity=None, stop=1)

led = machine.Pin(25, machine.Pin.OUT)

print("=" * 50)
print("EOS P100 Touch Protocol Sniffer")
print("Baud rate: {}".format(BAUD_RATE))
print("Listening on Channel 1 (GP4/GP5)")
print("=" * 50)
print("Touch the screen to generate data...")
print()

# Flash LED to show we are running
for _ in range(5):
    led.on()
    utime.sleep_ms(100)
    led.off()
    utime.sleep_ms(100)

led.on()

packet = []
last_byte_time = utime.ticks_ms()
packet_count = 0

while True:
    if uart.any():
        byte = uart.read(1)
        if byte:
            now = utime.ticks_ms()
            elapsed = utime.ticks_diff(now, last_byte_time)
            
            # If more than 50ms since last byte, treat as new packet
            if elapsed > 50 and len(packet) > 0:
                # Print the previous packet
                packet_count += 1
                hex_str = ' '.join(['0x{:02X}'.format(b) for b in packet])
                print("Packet {:3d} ({} bytes): {}".format(
                    packet_count, len(packet), hex_str))
                
                # Flash LED on each packet
                led.off()
                utime.sleep_ms(20)
                led.on()
                
                packet = []
            
            packet.append(byte[0])
            last_byte_time = now
    
    # Print incomplete packet if it's been a while
    if len(packet) > 0:
        now = utime.ticks_ms()
        elapsed = utime.ticks_diff(now, last_byte_time)
        if elapsed > 200:
            packet_count += 1
            hex_str = ' '.join(['0x{:02X}'.format(b) for b in packet])
            print("Packet {:3d} ({} bytes): {}".format(
                packet_count, len(packet), hex_str))
            led.off()
            utime.sleep_ms(20)
            led.on()
            packet = []
    
    utime.sleep_ms(1)
