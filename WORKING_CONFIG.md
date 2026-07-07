# Working Configuration

The final, verified working setup for the EOS P100 touchscreen replacement.

Security sensitive values (controller credentials, network addresses, hostnames) are redacted. Anyone reproducing this on their own machine will use their own.

## Firmware

`touch_translator_v20_standalone.py`

- Output coordinate range matched to the original screen's native resolution (this was the key fix)
- Input decode: high 7 bits first, low 7 bits second (byte order corrected)
- Per axis scaling with hardcoded panel range, measured on this panel
- Runs standalone on power up, no host computer, no boot time calibration
- Optional re-learn available by holding the onboard button, only needed if the physical panel is ever swapped

Panel range values are stored in the firmware and can be re-measured with the built in learn routine if a different panel is fitted.

## Controller calibration

The controller stores touch calibration as a standard 7 value tslib `pointercal` matrix. A normal on device 5 point calibration, run once the output range was correct, produces a matrix that maps the translated touches accurately across the whole screen.

Note for anyone reproducing this: the calibration matrix is specific to your panel and mounting. Run the controller's own 5 point calibration once the translator output range is correct, rather than copying a matrix from elsewhere.

## Access

Controller access for setup was via its serial console and over the network. Method is documented in the main write up. Specific credentials, addresses, and identifiers are intentionally omitted from this public repository.

## Recovery note

The controller's calibration file occasionally reset during development. Keeping a known good copy of the working calibration matrix, stored off the machine, is strongly recommended so it can be restored quickly if needed.
