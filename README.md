# EOS P100 Touchscreen Replacement

**Reverse engineering a proprietary RS232 touch protocol to replace a broken resistive touchscreen on an industrial SLS 3D printer**

---

## Overview

The EOS P100 is an industrial selective laser sintering (SLS) 3D printer running a proprietary embedded controller called **Charon**, a TQM5200/MPC5200 PowerPC board running Linux kernel 2.4.25 with Xenomai real-time extensions. The machine uses a resistive touchscreen as its primary interface.

When the original touchscreen failed, there was no direct replacement available. This project replaces it with a modern **iiyama ProLite T1531SR** resistive touchscreen by translating between its USB HID touch protocol (eGalax) and the proprietary serial touch protocol expected by the Charon controller (iRV 5-wire RS232).

A **Raspberry Pi Pico** sits in the middle, reading touch data from the iiyama screen and retransmitting it in the format the Charon controller expects, in real time.

---

## The problem

| Component | Detail |
|---|---|
| Machine | EOS P100 SLS printer |
| Controller | Charon (TQM5200/MPC5200 PowerPC) |
| Kernel | Linux 2.4.25 with Xenomai |
| Original touchscreen | Resistive, RS232 (iRV protocol) |
| Replacement screen | iiyama ProLite T1531SR (USB HID, eGalax controller) |
| Translator | Raspberry Pi Pico (MicroPython) |

The Charon controller reads touch data from a serial port expecting the iRV protocol. The replacement screen outputs USB HID. These are fundamentally incompatible, and the Pico bridges them.

---

## Protocol discovery

The key challenge was that the iRV protocol was undocumented. Protocol analysis was done by sniffing traffic from a working EOS P110 (which uses the same controller family) and comparing byte patterns from different touch positions.

### The 10-bit breakthrough

Early firmware versions (v1 through v9) could only reach the central third of the 800x600 screen. The root cause was a wrong assumption about coordinate bit depth.

The iRV protocol uses 5-byte packets. The status bytes (byte 1 and byte 3) were initially assumed to be pure status flags since they only ever held four values: `0x00`, `0x40`, `0x80`, `0xC0`. In reality, they carry the **top 2 bits** of each coordinate:

```
Full X = ((byte1 >> 6) << 8) | byte2   -> 0 to 1023 range
Full Y = ((byte3 >> 6) << 8) | byte4   -> 0 to 1023 range
```

This gives a 10-bit coordinate space (0 to 1023) rather than the 8-bit range (0 to 255) previously assumed. The Charon calibration system (`/etc/pointercal`) expects raw values spanning approximately -260 to +628 across the screen, a range that only the full 10-bit space can satisfy.

Implementing 10-bit encoding in `touch_translator_v10_10bit.py` immediately opened up the full screen.

---

## Calibration system

The Charon controller uses tslib for touchscreen calibration. Calibration data is stored in a 7-parameter file:

```
a b c d e f s
```

Where the coordinate transform is: `X_screen = (a * X_raw + b * Y_raw + c) / s`

### P100-specific findings

- `/etc/pointercal` is a **symlink** to `/home/eos/config/pointercal2` (not `pointercal` as assumed from P110 behaviour)
- The P100 only writes calibration data when the on-screen OK button is explicitly pressed, unlike the P110 which writes live during the 5-point sequence
- Factory default backup at `/etc/defaultconfig/pointercal`:
  ```
  54720 0 14235840 -80 42560 10958800 60720
  ```
- Sanity check for valid calibration: compute `a/s` (should be around 0.88) and `e/s` (should be around 0.70). A ratio of 7.69 or `s=0` indicates a corrupted result, restore from factory default

### Orientation

The P100 requires:
```python
INVERT_X = True
INVERT_Y = True
SWAP_XY  = False
```

---

## Firmware versions

| Version | Key change |
|---|---|
| v1 to v9 | 8-bit coordinate encoding, could only reach central third of screen |
| v10 | 10-bit encoding implemented, full screen coverage achieved |
| v11 to v12 | Warmup/stability gating added, over-filtered centre touches |
| **v13** | **Current stable.** `warmup=1`, `outlier_tol=200`, `smooth_window=5` |

The current translator firmware is `touch_translator_v13.py`.

---

## Calibration assistant

Because the 5-point calibration sequence involves pressing a small moving OK button that is difficult to hit reliably with a translated touch, a dedicated calibration assistant was written.

`calibration_assistant_v2.py` combines synthetic taps (sent programmatically) for menu navigation with a sample-and-hold physical touch mode for the 5 calibration points.

The sequence is BOOTSEL-button driven:
1. Press to synthetic tap: Service menu (34, 68)
2. Press to synthetic tap: Touchscreen calibration entry (148, 203)
3. Press to synthetic tap: Calibration start (~210, 80) - **requires field verification**
4. Press to enter sample-and-hold mode: physically touch each of the 5 calibration points, BOOTSEL to confirm each
5. Press to synthetic tap: OK button (80, 96) as a fallback once calibration is confirmed good

---

## Current status

| Stage | Status |
|---|---|
| Protocol analysis (iRV 10-bit) | Complete |
| Screen mapping (button coordinates) | Complete |
| Stable translator firmware (v13) | Complete |
| Calibration assistant v2 | Written |
| START_CAL_XY field verification (~210,80) | Pending, needs in-person test on P100 |
| Full calibration achieved and verified | Pending |

---

## Tools and hardware

- Raspberry Pi Pico (MicroPython)
- iiyama ProLite T1531SR resistive touchscreen
- RS232 serial adapter
- SSH access to EOS P100 Charon controller
- Python scripts for log analysis and coordinate mapping

---

## What I learned

- Reverse engineering an undocumented binary serial protocol from packet captures
- Embedded Linux debugging on old constrained hardware (PowerPC, kernel 2.4)
- MicroPython firmware development for the RP2040
- Signal processing concepts applied to noisy resistive touch data including outlier rejection, smoothing windows, and sample-and-hold input
- The importance of empirical testing, as every assumption about the protocol turned out to be wrong at least once

---

*Project is ongoing. Updates added as calibration work progresses.*
