# ============================================================
# EOS P100 Touch Protocol Sniffer with Passthrough
# Raspberry Pi Pico + Waveshare 2-CH RS232 Hat
#
# Channel 0: GP0 (TX), GP1 (RX) --> iRV controller (screen)
# Channel 1: GP4 (TX), GP5 (RX) --> Charon touchscreen port
#
# Passes data in both directions AND prints what it sees
# ============================================================

import machine
import utime

# Channel 0 - connected to iRV controller (screen)
uart0 = machine.UART(0, baudrate=115200, tx=machine.Pin(0), rx=machine.Pin(1),
                     bits=8, parity=None, stop=1)

# Channel 1 - connected to Charon
uart1 = machine.UART(1, baudrate=115200, tx=machine.Pin(4), rx=machine.Pin(5),
                     bits=8, parity=None, stop=1)

led = machine.Pin(25, machine.Pin.OUT)

print("=" * 50)
print("EOS P100 Touch Sniffer + Passthrough")
print("Channel 0 (GP0/GP1) --> iRV Screen")
print("Channel 1 (GP4/GP5) --> Charon")
print("=" * 50)

# Flash LED to confirm running
for _ in range(5):
    led.on()
    utime.sleep_ms(100)
    led.off()
    utime.sleep_ms(100)
led.on()

packet_from_screen = []
packet_from_charon = []
last_screen_time = utime.ticks_ms()
last_charon_time = utime.ticks_ms()
packet_count = 0

while True:
    # Data from iRV screen (channel 0) --> forward to Charon (channel 1)
    if uart0.any():
        data = uart0.read()
        if data:
            uart1.write(data)  # Pass through to Charon
            now = utime.ticks_ms()
            for b in data:
                elapsed = utime.ticks_diff(now, last_screen_time)
                if elapsed > 50 and len(packet_from_screen) > 0:
                    packet_count += 1
                    hex_str = ' '.join(['0x{:02X}'.format(x) for x in packet_from_screen])
                    print("SCREEN->CHARON Pkt {:3d} ({} bytes): {}".format(
                        packet_count, len(packet_from_screen), hex_str))
                    led.off()
                    utime.sleep_ms(10)
                    led.on()
                    packet_from_screen = []
                packet_from_screen.append(b)
                last_screen_time = now

    # Data from Charon (channel 1) --> forward to iRV screen (channel 0)
    if uart1.any():
        data = uart1.read()
        if data:
            uart0.write(data)  # Pass through to screen
            now = utime.ticks_ms()
            for b in data:
                elapsed = utime.ticks_diff(now, last_charon_time)
                if elapsed > 50 and len(packet_from_charon) > 0:
                    packet_count += 1
                    hex_str = ' '.join(['0x{:02X}'.format(x) for x in packet_from_charon])
                    print("CHARON->SCREEN Pkt {:3d} ({} bytes): {}".format(
                        packet_count, len(packet_from_charon), hex_str))
                    led.off()
                    utime.sleep_ms(10)
                    led.on()
                    packet_from_charon = []
                packet_from_charon.append(b)
                last_charon_time = now

    utime.sleep_ms(1)
