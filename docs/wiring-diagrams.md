# Pika Wiring Diagrams

This document contains wiring instructions for connecting the AD7606 ADC to the BeagleBone Black (BBB).

## Safety Warning

**CRITICAL:** Ensure the **VIO** (or **VDRIVE**) pin on the AD7606 is connected to **3.3V (P9.3)** and NOT 5V. Connecting VIO to 5V will output 5V logic signals to the BeagleBone Black, which can damage the PRU input pins.

---

## 16-Bit Parallel Configuration

This configuration uses 21 pins (16 data + 5 control) and requires disabling HDMI and Audio on the BeagleBone Black.

### Power Connections

| AD7606 Pin      | BBB Pin | Description             |
| :-------------- | :------ | :---------------------- |
| **GND**         | **P9.1**| Common Ground           | ✅
| **+5V / AVCC**  | **P9.5**| Analog Supply Power     | ✅ 
| **VIO / DRV**   | **P9.3**| **Logic Supply (3.3V)** | ✅ 

### Control Connections

| AD7606 Pin | BBB Pin  | Mode    | Function              |
| :--------- | :------- | :------ | :-------------------- |
| **CONVST** | **P9.27**| pruout  | Trigger Conversion    | ✅ |
| **BUSY**   | **P9.25**| pruin   | Conversion Status     | ✅ |
| **RD**     | **P9.30**| pruout  | Read Strobe (PULSE)   | **REQUIRED** (Advances Channels) |
| **CS**     | **P9.28**| pruout  | Chip Select           | ✅ |
| **RESET**  | **P9.29**| pruout  | Reset Pulse           | P9.29 Preferred (GND works) |
| **FRST**   | -        | -       | First Result Output   | **OPTIONAL** (Leave Floating) |

### Data Connections (16-Bit Bus)

Configure these pins as `gpio` via `config-pin`.

| AD7606 Pin | BBB Pin  | GPIO Register |
| :--------- | :------- | :------------ |
| **DB1 / DB0** | **P8.7 / P8.8** | GPIO2_2 / GPIO2_3 | ✅ ✅
| **DB3 / DB2** | **P8.9 / P8.10** | GPIO2_5 / GPIO2_4 | ✅ ✅
| **DB5 / DB4** | **P8.11 / P8.12** | GPIO1_13 / GPIO1_12 | ✅ ✅
| **DB7 / DB6** | **P8.13 / P8.14** | GPIO0_23 / GPIO0_26 | ✅ ✅
| **DB9 / DB8** | **P8.15 / P8.16** | GPIO1_15 / GPIO1_14 | ✅ ✅
| **DB11 / DB10**| **P8.17 / P8.18** | GPIO0_27 / GPIO2_1 | ✅ ✅
| **DB13 / DB12**| **P8.19 / P8.26** | GPIO0_22 / GPIO1_29 | ✅ ✅
| **DB15 / DB14**| **P8.27 / P8.28** | GPIO2_22 / GPIO2_24 | ✅ ✅

---

## Operating Modes

### Parallel Mode Select
Ensure the **PAR/SER** pin on your module is connected to **GND** to enable parallel mode.

### Hardware Configuration
- **OS[0:2]**: Tie to **GND** for no oversampling (highest speed).
- **RANGE**: Tie to **GND** for +/- 5V range.
- **VIO**: Must be **3.3V**.
