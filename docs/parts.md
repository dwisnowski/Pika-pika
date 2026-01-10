# Hardware: Parts list & Wiring

This page lists the hardware used in the Pika‑pika project and provides example shopping links for convenience. These links are **examples only** — verify part specifications and local availability before buying.

> **Safety first:** Do **not** connect to mains without proper isolation and a fuse. If you are unsure, use an isolation transformer or certified commercial sensor modules.

## Parts list

- Raspberry Pi 2 (or newer) — SBC to run the logger and web UI.
  - Example: https://www.amazon.com/s?k=raspberry+pi+2

- ADS1115 I2C ADC breakout (4-channel, 16-bit)
  - Example: https://www.amazon.com/dp/B00STQ4GQ4

- ZMPT101B AC voltage sensor module (with biasing and signal conditioner)
  - Example: https://www.amazon.com/dp/B07G9F2B2X

- Waveshare 2" SPI LCD / ST7789 (optional) — show QR code and status on-device
  - Example: https://www.amazon.com/dp/B07Y8V4M8Y

- 5 V power supply (capable of providing at least 2 A for Pi + peripherals)
  - Example: https://www.amazon.com/dp/B07TYQRX5H

- microSD card (16 GB or larger, class 10 recommended)
  - Example: https://www.amazon.com/dp/B08GYG1YH1

- Jumper wires and breadboard / small prototyping accessories
  - Example: https://www.amazon.com/dp/B01EV70C78

- Enclosure and inline fuse for mains safety (if you are building a mains-connected measurement device)
  - Example inline fuse: https://www.amazon.com/dp/B07QX4Q9G5


## Wiring diagram

Below is an illustrative wiring diagram showing the Raspberry Pi, ADS1115 and ZMPT101B connections. This diagram is **illustrative only** and does not replace proper safety practices.

![Wiring diagram](/wiring.svg)

### Quick wiring summary

- ADS1115 VCC → Pi 3.3 V (Pin 1)
- ADS1115 GND → Pi GND (Pin 6)
- ADS1115 SDA → Pi SDA (Pin 3)
- ADS1115 SCL → Pi SCL (Pin 5)
- ADS1115 A0 → ZMPT101B Vout
- ZMPT101B VCC → 5 V (use board 5 V or external supply, per sensor recommendation)
- ZMPT101B GND → Pi GND

---

If you would like, I can add example Amazon product titles (rather than the generic search / product links), or include alternate parts (e.g., different ADCs or a voltage divider approach) — tell me which you'd prefer.