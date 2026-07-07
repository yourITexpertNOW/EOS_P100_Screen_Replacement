# EOS P100 Touchscreen Restoration

Replacing a failed resistive touchscreen on an EOS P100 industrial SLS 3D printer with a modern panel, using a Raspberry Pi Pico as a real-time serial protocol translator. No original parts, no vendor support, no documentation.

The original 12.1 inch touchscreen had a working display but completely dead touch input. Replacement panels for this controller are effectively unobtainable. Rather than scrap a working industrial machine, I reverse engineered the proprietary touch protocol and built a translator that lets a standard modern touchscreen speak to the printer's controller as if it were the original part.

This write up documents the whole process, including the wrong turns, because the debugging path is the interesting part.

---

## The result

A Raspberry Pi Pico sits between a modern iiyama touchscreen and the printer's controller. It reads touch data from the new screen in one protocol, translates it in real time, and outputs it in the format the printer's original controller expects. The printer runs its unmodified factory software and behaves exactly as it did with the original screen.

The final firmware runs standalone. Power on, and it works. No calibration ritual, no host computer.

Final firmware: `touch_translator_v20_standalone.py`

---

## The hardware

| Component | Role |
|---|---|
| EOS P100 SLS printer | The machine being repaired |
| Original controller (PowerPC, embedded Linux, kernel 2.4.x) | Runs the factory print software, expects a specific serial touch protocol |
| iiyama ProLite T1531SR | Modern replacement touchscreen, outputs a different serial protocol |
| Raspberry Pi Pico (RP2040, MicroPython) | The translator sitting between the two |
| RS232 level adapters | Interfacing the serial links |

The Pico uses two UART channels: one reading the new screen, one writing to the controller.

---

## The problem in one line

Two touchscreens, two completely different and partly undocumented serial protocols, and a controller that only understands one of them.

To make the translator I had to fully understand both:

- **The input protocol** the modern iiyama screen speaks
- **The output protocol** the printer's original screen used to speak

Neither was documented. Both had to be recovered from captured serial data.

---

## Reverse engineering the protocols

### Gaining access

Root access to the controller was obtained through its serial console. From there I could inspect the touch input device, the calibration files, and the Qt based touch driver the factory software uses. Access details and credentials are redacted in this public write up.

Key discovery: the controller reads touch input from a serial port using a proprietary parser, and stores calibration as a 7 value transformation matrix (the standard tslib `pointercal` format) that maps raw touch coordinates onto screen pixels.

### Capturing the original protocol

By capturing the serial output of a working original screen on an identical machine, I recovered the output protocol: a repeating fixed length binary packet per touch, with a distinct release sequence. Early analysis suggested the coordinates were encoded across multiple bytes, and this is where the first long detour began.

### The input protocol

The iiyama screen outputs a 5 byte binary frame per touch sample. Recovering the exact bit layout took several attempts and produced two of the most important lessons in the whole project (below).

---

## The trial and error, honestly

This project took many firmware iterations. Almost every assumption I made about the protocols was wrong at least once. The versions below trace the actual path.

### Diagnostic tooling

Before the translator could be trusted, I wrote a set of throwaway diagnostic scripts. These turned out to be the most valuable code in the project:

- **Raw packet sniffers** that printed the actual bytes coming off each screen, with no interpretation. Every real breakthrough came from staring at raw bytes rather than decoded values. I should have reached for these far earlier than I did.
- **Constant packet and constant tap tests** that sent a single fixed synthetic touch repeatedly, to prove whether the controller framed and parsed our output deterministically, separate from any touch noise.
- **A diagnostic calibration** (a simple known linear `pointercal`) that let me read back exactly where the controller thought a touch had landed, giving ground truth to check the translator against.

### Screen and button mapping

Because the controller's on screen cursor is only intermittently visible on the normal menus (this is normal behaviour for this hardware), I could not judge accuracy by eye reliably. So I mapped it empirically instead: sending fixed synthetic touches and recording which on screen buttons they activated, building up a coordinate map of the interface. This mapping later drove a synthetic navigation system that could press menu buttons programmatically.

A key insight from this stage: synthetic fixed touches are perfect for navigating menus, but the actual calibration points must be captured from a real finger, otherwise you calibrate the screen to invented numbers rather than to the physical panel.

### The wrong turns worth documenting

**The multi byte coordinate theory.** I spent a long time convinced the output coordinates used a wide numeric range packed across status bytes. It partly fit the evidence, so it survived far longer than it should have.

**The byte order bug.** The single deepest bug in the project. The input decode had the high and low bytes of each coordinate swapped. The proof came from a slow finger drag: at a 7 bit boundary the values jumped discontinuously (for example 16270 straight to 15) under the wrong decode, but incremented smoothly by one under the correct decode. A finger moving smoothly cannot produce a discontinuous jump, so the smooth version had to be right. This one bug had been generating what looked like random cursor glitches, and every noise filter I had written was treating the symptom rather than the cause.

**The range assumption.** Even with the bytes correct, calibration would not land. Measuring full panel drags showed the two axes covered very different numeric ranges, so a single scale factor distorted one of them. I moved to independent per axis scaling, and then to a firmware routine that learns each axis range automatically from a panel wipe, which removed the guesswork.

### The breakthrough

After all of that, calibration still would not settle. The touches were decoded correctly, smooth, and full range, yet the calibration never matched the screen.

The answer was hiding in my own mapping data. Every on screen coordinate I had ever recorded, every button, every calibration target, fell within a small numeric range. The original screen had effectively used a much smaller coordinate resolution than I had been outputting. I had been scaling touches to a range many times larger than the controller's calibration expected, so all but a sliver of the output landed off screen.

Rescaling the translator output to match the original screen's native coordinate range was the fix. The controller's calibration maths, unchanged, suddenly worked. From there a normal 5 point calibration completed cleanly and the screen tracked accurately across its whole surface.

The lesson: the simplest explanation, that the numbers were simply the wrong size, was sitting in the data the whole time.

---

## Firmware progression

| Version | Change |
|---|---|
| Early versions | Initial translator, multi byte coordinate theory, heavy noise filtering |
| Byte order fix | Corrected the swapped high/low bytes in the input decode |
| Per axis scaling | Independent X and Y ranges instead of one shared scale |
| Auto range learning | Firmware learns each axis range from a panel wipe |
| Output range fix | Rescaled output to the original screen's native range. This is what made calibration work |
| `touch_translator_v20_standalone.py` | Final. Hardcoded panel range, no boot time setup, runs standalone |

---

## What I learned

- Reverse engineering two undocumented binary serial protocols from packet captures
- Embedded Linux work on old, constrained hardware (PowerPC, kernel 2.4.x)
- MicroPython firmware development on the RP2040, including dual UART real time translation
- Applying signal processing ideas (outlier rejection, median smoothing, sample and hold) to noisy resistive touch data
- Reading raw bytes instead of trusting decoded values, and reaching for that far sooner
- That the obvious, simplest explanation deserves testing first, not last

---

## Repository contents

- `touch_translator_v20_standalone.py` — final production firmware
- `diagnostics/` — the raw sniffers and constant tap tests used to recover the protocols
- `history/` — earlier firmware versions, kept to show the debugging progression
- `WORKING_CONFIG.md` — the working configuration, with security sensitive values redacted

---

*Industrial repair project. All controller access credentials, network addresses, and machine identifiers have been redacted from this public write up.*
