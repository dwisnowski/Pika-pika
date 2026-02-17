# Pika Wiring Diagrams

This document contains wiring instructions for connecting the AD7606 ADC to the BeagleBone Black (BBB).

## Safety Warning

**CRITICAL:** Ensure the **VIO** (or **VDRIVE**) pin on the AD7606 is connected to **3.3V (P9.3)** and NOT 5V. Connecting VIO to 5V will output 5V logic signals to the BeagleBone Black, which can damage the PRU input pins.

---

## 1-Channel "Safe" Configuration

This configuration uses pins that avoid conflicts with the BeagleBone Black's HDMI and Audio drivers, allowing it to work without modifying `uEnv.txt`.

### Power Connections

| AD7606 Pin      | BBB Pin | Description             |
| :-------------- | :------ | :---------------------- |
| **GND**         | **P9.1**| Common Ground           |
| **+5V / AVCC**  | **P9.5**| Analog Supply Power     |
| **VIO / VDRIVE**| **P9.3**| **Logic Supply (3.3V)** |

### Control & Configuration

| AD7606 Pin      | BBB Pin | Description                                        |
| :-------------- | :------ | :------------------------------------------------- |
| **CVA / CVB**   | **P9.27** | CONVST - Trigger Conversion (Tie CVA & CVB together) |
| **BUSY**        | **P8.15** | Conversion Status Input                            |
| **CS**          | **GND**  | Chip Select (Tie to GND for always active)         |
| **RD**          | **GND**  | Read (Tie to GND for transparent mode)             |
| **RST**         | **GND**  | Reset (Tie to GND for normal operation)            |
| **OS0, OS1, OS2**| **GND** | Oversampling Mode (Tie all to GND for No OS)       |
| **RANGE**       | **GND**  | Input Range (Tie to GND for +/- 5V)                |

### Data Connections

| AD7606 Pin      | BBB Pin | Description             |
| :-------------- | :------ | :---------------------- |
| **DB0 (D0)**    | **P8.16** | Data Bit 0 (LSB)      |

---

## Operating Modes

### Parallel Mode
To use the parallel interface (required by this PRU firmware), ensure the **PAR/SER** (if present on your module) is connected to **GND**.

### Transparent Read
By tying **CS** and **RD** to **GND**, the AD7606 operates in "transparent read" mode. As soon as the conversion is complete and **BUSY** goes low, the 16-bit data is immediately presented on the DB0-DB15 pins for the PRU to read.
