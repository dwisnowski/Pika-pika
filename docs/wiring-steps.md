# Wiring steps (photos)

This page provides step-by-step wiring photos and guidance so you can assemble the project safely. If you have real photos you'd like to include, replace the SVG placeholders in `docs/images/` with your own images (e.g., `wiring-step-1.jpg`).

## Step 1 — Connect ADS1115

![Step 1 — Connect ADS1115](/images/wiring-step-1.svg)

- Connect ADS1115 VCC → Pi 3.3 V (Pin 1)
- Connect ADS1115 GND → Pi GND (Pin 6)
- Connect ADS1115 SDA → Pi SDA (Pin 3)
- Connect ADS1115 SCL → Pi SCL (Pin 5)

## Step 2 — Connect ZMPT101B output to A0

![Step 2 — Connect ZMPT101B](/images/wiring-step-2.svg)

- Connect ZMPT101B Vout → ADS1115 A0
- Connect ZMPT101B GND → Pi GND
- Connect ZMPT101B VCC → 5 V (if the board requires it)

> Note: ZMPT101B boards often include a bias circuit — read the board notes and do not apply mains directly without correct isolation and a fuse.

## Step 3 — Verify and test

![Step 3 — Verify and test](/images/wiring-step-3.svg)

- Power the Pi and run a low-rate read script to confirm values on A0.
- Use the demo page (`/demo`) to confirm the UI and highlight detection before applying mains voltages.
- For initial testing prefer a safe, low-voltage source or an isolation transformer.

## Measure & adjust sensor output (multimeter)

Before connecting the ADS1115 to the Raspberry Pi, validate that the ZMPT101B output stays within the ADC input range (0–3.3 V) to avoid damaging the Pi. The steps below assume the sensor board is powered and common ground is connected; do NOT connect mains directly for these checks — use an isolation transformer or a low-voltage test source if possible.

Steps

1. Power up the ZMPT101B (and the Pi/ADS1115) but leave the sensor input unconnected or use a safe low-voltage source.
2. Set your multimeter to DC volts and measure the DC level at the sensor output (Vout measured to GND). With a 3.3 V supply, the midpoint bias should be roughly 1.5 V. If it is far from this value, adjust the board trim pot slowly until the DC reading is near 1.5 V.
3. With a small, **isolated** AC test signal (or the real sensor input if you have an isolation transformer), measure the AC RMS voltage at Vout using the multimeter AC mode. Many bench multimeters show VRMS; if you only have RMS, estimate peak amplitude as: Vpk ≈ Vrms × √2.
4. Verify the peak values will not exceed ADC rails: ensure (Voffset + Vpk) < 3.3 V and (Voffset − Vpk) > 0.1 V (leave a small safety margin, e.g. 0.1–0.2 V).
   - Example: Voffset ≈ 1.5 V and Vrms ≈ 0.7 V → Vpk ≈ 0.99 V, so 1.5 ± 0.99 → stays within 0.51 … 2.49 V (safe).
5. If the peak would exceed the allowable range, reduce the sensor gain using the trim pot (turn slowly while watching the multimeter) or add attenuation between the sensor and ADS1115. Repeat the measurement after every change.
6. If you have an oscilloscope, inspect the waveform for clipping or DC offset changes while the sensor is under expected load — an oscilloscope gives a definitive peak-to-peak reading.
7. Once the output is within safe limits, connect the ADS1115 to the Pi, start the logger at a low sample rate, and verify readings in the `/demo` or the live UI. Watch for saturated (flat) readings which indicate clipping.

Safety notes

- If you do not have an isolation transformer or a low-voltage source, do not attempt to adjust the trim pot while connected to mains. Contact a qualified technician if you are unsure.
- Small adjustments can produce large changes — always adjust slowly and re-check after each small turn.
- Use protective equipment and follow local regulations when measuring mains voltages.

---

If you have real photos you'd like added, upload them to `docs/images/` and update the markdown to reference the new filenames; I can also add a small gallery plugin to MkDocs if you'd like.