# Device Tree Overlay for AD7606 with PRU0

## Overview

The device tree overlay `BB-PRU0-AD7606.dts` configures the BeagleBone Black to interface the PRU0 (Programmable Real-time Unit) with the AD7606 ADC. This overlay:

1. **Disables HDMI** - Frees up pins that conflict with PRU0
2. **Configures PRU0 pins** - Sets up pin multiplexing for the parallel interface
3. **Enables PRU subsystem** - Activates PRU0 for firmware execution

## Pin Mapping

### Control Signals
- **CONVST** (P9.31): PRU0 R30.0 output - Triggers ADC conversion
- **BUSY** (P9.29): PRU0 R31.0 input - Indicates conversion in progress

### 16-bit Parallel Data Bus
| Signal | BBB Pin | PRU Pin     | Description |
|--------|---------|-------------|-------------|
| D0     | P9.27   | PRU0 R31.1  | Data bit 0 (LSB) |
| D1     | P9.25   | PRU0 R31.2  | Data bit 1 |
| D2     | P9.28   | PRU0 R31.3  | Data bit 2 |
| D3     | P9.30   | PRU0 R31.4  | Data bit 3 |
| D4     | P9.92   | PRU0 R31.5  | Data bit 4 |
| D5     | P9.42   | PRU0 R31.6  | Data bit 5 |
| D6     | P9.91   | PRU0 R31.7  | Data bit 6 |
| D7     | P9.41   | PRU0 R31.8  | Data bit 7 |
| D8     | P8.45   | PRU0 R31.9  | Data bit 8 |
| D9     | P8.46   | PRU0 R31.10 | Data bit 9 |
| D10    | P8.43   | PRU0 R31.11 | Data bit 10 |
| D11    | P8.44   | PRU0 R31.12 | Data bit 11 |
| D12    | P8.41   | PRU0 R31.13 | Data bit 12 |
| D13    | P8.42   | PRU0 R31.14 | Data bit 13 |
| D14    | P8.39   | PRU0 R31.15 | Data bit 14 |
| D15    | P8.40   | PRU0 R31.16 | Data bit 15 (MSB) |

## Compilation

The device tree overlay must be compiled into a binary format (.dtbo) before it can be loaded.

### On BeagleBone Black:

```bash
# Compile the device tree overlay
dtc -O dtb -o BB-PRU0-AD7606.dtbo -b 0 -@ BB-PRU0-AD7606.dts

# Copy to overlays directory
sudo cp BB-PRU0-AD7606.dtbo /lib/firmware/
```

### Cross-compilation (on development machine):

```bash
# Using device tree compiler with appropriate includes
dtc -O dtb -o BB-PRU0-AD7606.dtbo -b 0 -@ BB-PRU0-AD7606.dts
```

## Installation

### Method 1: Load at Runtime

```bash
# Load the overlay
sudo sh -c "echo 'BB-PRU0-AD7606' > /sys/devices/platform/bone_capemgr/slots"

# Verify it loaded
cat /sys/devices/platform/bone_capemgr/slots
```

### Method 2: Load at Boot

Edit `/boot/uEnv.txt` and add:

```
cape_enable=bone_capemgr.enable_partno=BB-PRU0-AD7606
```

Or add to the `uboot_overlay_addr4` line:

```
uboot_overlay_addr4=/lib/firmware/BB-PRU0-AD7606.dtbo
```

Reboot for changes to take effect.

## Verification

### Check PRU Subsystem Status

```bash
# Verify PRU subsystem is enabled
cat /sys/devices/platform/ocp/4a300000.pruss/status
# Should show: okay

# Check if PRU0 is available
ls -l /dev/remoteproc/pruss-core0/
```

### Check Pin Configuration

```bash
# View pin configuration for P9.31 (CONVST)
cat /sys/kernel/debug/pinctrl/44e10800.pinmux/pins | grep -A1 "pin 100"

# View pin configuration for P9.29 (BUSY)
cat /sys/kernel/debug/pinctrl/44e10800.pinmux/pins | grep -A1 "pin 101"
```

### Test with Bringup Firmware

After loading the overlay, test with the bringup firmware:

```bash
cd pika/pru
make bringup
make load-bringup

# Use logic analyzer or oscilloscope to verify 1 kHz square wave on P9.31
```

## Troubleshooting

### HDMI Still Active

If HDMI is still active after loading the overlay:

```bash
# Check if HDMI overlay is loaded
cat /sys/devices/platform/bone_capemgr/slots

# Disable HDMI in /boot/uEnv.txt
# Comment out or remove: cape_enable=bone_capemgr.enable_partno=BB-HDMI
```

### Pin Conflicts

If you get "pin already in use" errors:

```bash
# Check what's using the pins
cat /sys/kernel/debug/pinctrl/44e10800.pinmux/pinmux-pins

# Unload conflicting overlays
sudo sh -c "echo '-N' > /sys/devices/platform/bone_capemgr/slots"
# Where N is the slot number of the conflicting overlay
```

### PRU Not Available

If PRU subsystem doesn't appear:

```bash
# Check kernel modules
lsmod | grep pru

# Load PRU remoteproc driver if needed
sudo modprobe pruss
sudo modprobe pru_rproc
```

## Technical Details

### Pin Modes

- **0x05**: Mode 5, output, pull-down disabled (PRU outputs)
- **0x26**: Mode 6, input, pull-down enabled (PRU inputs)

### Register Offsets

Pin configuration register offsets are from AM335x Technical Reference Manual (TRM) Table 9-10. The offsets are relative to the control module base address (0x44E10800).

### PRU Register Access

- **R30**: Output register - Write to control output pins (CONVST)
- **R31**: Input register - Read to sample input pins (BUSY, D0-D15)

## References

- [AM335x Technical Reference Manual](https://www.ti.com/lit/ug/spruh73q/spruh73q.pdf)
- [BeagleBone Black System Reference Manual](https://github.com/beagleboard/beaglebone-black/wiki/System-Reference-Manual)
- [PRU Subsystem Documentation](https://processors.wiki.ti.com/index.php/PRU-ICSS)
- [Device Tree Overlay Guide](https://elinux.org/Beagleboard:BeagleBoneBlack_Debian#U-Boot_Overlays)
