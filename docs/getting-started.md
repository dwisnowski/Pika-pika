# Getting Started with Pika on BeagleBone Black

This guide walks you through setting up a brand new BeagleBone Black (BBB) to run the Pika data acquisition system with PRU firmware.

## Prerequisites

### Hardware
- BeagleBone Black (Rev C or later recommended)
- 5V 2A power supply
- MicroSD card (8GB+ recommended)
- USB cable for serial console (optional but recommended)
- Logic analyzer (for validation)
- AD7606 ADC board (for full system operation)

### Host Computer
- Linux, macOS, or Windows with SSH client
- SD card reader/writer
- Internet connection

## Step 1: Flash BeagleBone Black with Debian

### Download Image

1. Download the latest Debian IoT image from [beagleboard.org](https://beagleboard.org/latest-images)
   - Recommended: Debian 11 (Bullseye) IoT image
   - Look for: `bone-debian-X.X-iot-armhf-YYYY-MM-DD-4gb.img.xz`

2. Verify the download checksum (optional but recommended)

### Flash to SD Card

**Linux/macOS:**
```bash
# Extract image
xz -d bone-debian-*.img.xz

# Find SD card device (be careful!)
lsblk

# Flash image (replace /dev/sdX with your SD card)
sudo dd if=bone-debian-*.img of=/dev/sdX bs=4M status=progress
sync
```

**Windows:**
- Use [Balena Etcher](https://www.balena.io/etcher/) or [Win32DiskImager](https://sourceforge.net/projects/win32diskimager/)

### Boot from SD Card

1. Insert SD card into BBB
2. Hold down the boot button (near SD card slot)
3. Apply power while holding button
4. Wait for LEDs to start flashing (release button after 5 seconds)
5. Wait 2-3 minutes for first boot

## Step 2: Connect to BeagleBone Black

### Via USB (Easiest)

1. Connect BBB to computer via USB cable
2. BBB will appear as a network device with IP `192.168.7.2`

```bash
ssh debian@192.168.7.2
# Default password: temppwd
```

### Via Ethernet

1. Connect BBB to your network via Ethernet
2. Find IP address from your router or use:
```bash
# From serial console or USB connection
ip addr show eth0
```

3. SSH to the IP address:
```bash
ssh debian@<ip-address>
```

### Via Serial Console (Optional)

Connect a USB-to-serial adapter to BBB's debug header (J1):
- Pin 1: Ground
- Pin 4: RX
- Pin 5: TX

```bash
# Linux/macOS
screen /dev/ttyUSB0 115200

# Windows: Use PuTTY
```

## Step 3: Initial System Setup

### Update System

```bash
# Change default password
passwd

# Update package lists
sudo apt update
sudo apt upgrade -y

# Install essential tools
sudo apt install -y build-essential git device-tree-compiler
```

### Configure Timezone and Locale (Optional)

```bash
sudo dpkg-reconfigure tzdata
sudo dpkg-reconfigure locales
```

## Step 4: Install PRU Development Tools

### Install PRU Compiler and Support Package

```bash
# Install PRU compiler
sudo apt install -y ti-pru-cgt-installer

# Install PRU software support package
sudo apt install -y ti-pru-software-support-package

# Verify installation
ls /usr/share/ti/cgt-pru
ls /usr/lib/ti/pru-software-support-package
```

### Enable PRU Subsystem

Check if PRU is enabled:
```bash
ls /sys/class/remoteproc/
# Should see remoteproc1 and remoteproc2 (PRU0 and PRU1)
```

If not present, enable PRU in `/boot/uEnv.txt`:
```bash
sudo nano /boot/uEnv.txt

# Uncomment or add:
uboot_overlay_pru=/lib/firmware/AM335X-PRU-RPROC-4-19-TI-00A0.dtbo

# Save and reboot
sudo reboot
```

## Step 5: Clone and Build Pika

### Clone Repository

```bash
cd ~
git clone <repository-url> pika
cd pika
```

### Build PRU Firmware

```bash
cd pika

# Build main firmware
make pru

# Build bringup test firmware
make pru-bringup

# Run tests (on development machine with mocks)
make test-pru
```

## Step 6: Deploy Device Tree Overlay

The device tree overlay configures BBB pins for PRU use and disables HDMI.

### Build and Install Overlay

```bash
cd ~/pika/pika

# Build and install device tree overlay
make pru-overlay
```

### Load Overlay at Boot

Modern BeagleBone images load overlays via `/boot/uEnv.txt`:

```bash
sudo nano /boot/uEnv.txt

# Find the line with uboot_overlay_addr4 (or similar unused overlay slot)
# Uncomment and set it to:
uboot_overlay_addr4=/lib/firmware/BB-PRU0-AD7606.dtbo

# Or add to the dtb_overlay line:
# dtb_overlay=/lib/firmware/BB-PRU0-AD7606.dtbo

# Save and reboot
sudo reboot
```

### Verify Overlay Loaded

After reboot, check if the overlay is active:

```bash
# Check loaded overlays
sudo cat /proc/device-tree/chosen/overlays/name

# Or check for PRU pins in pinmux
cat /sys/kernel/debug/pinctrl/44e10800.pinmux/pins | grep -i pru

# Verify PRU is available
ls /sys/class/remoteproc/
# Should see remoteproc1 and remoteproc2
```

## Step 7: Load and Run PRU Firmware

### Load Bringup Test Firmware

Start with the bringup firmware to verify basic PRU operation:

```bash
cd ~/pika/pika

# Load bringup firmware
make pru-load-bringup

# Check PRU status
cat /sys/class/remoteproc/remoteproc1/state
# Should show "running"
```

### Verify PRU is Running

```bash
# Check PRU firmware name
cat /sys/class/remoteproc/remoteproc1/firmware

# Check for errors in kernel log
sudo dmesg | tail -20
```

## Step 8: Validate with Logic Analyzer

### Pin Connections

Connect your logic analyzer to the following BBB pins:

| Signal | BBB Pin | PRU Pin | Description |
|--------|---------|---------|-------------|
| CONVST | P9.31   | PRU0 R30.0 | Convert start pulse (output) |
| BUSY   | P9.29   | PRU0 R31.0 | ADC busy signal (input) |
| D0-D7  | P9.27, P9.25, P9.28, P9.30, P9.92, P9.42, P9.91, P9.41 | PRU0 R31.1-8 | Data bits 0-7 |
| D8-D15 | P8.45, P8.46, P8.43, P8.44, P8.41, P8.42, P8.39, P8.40 | PRU0 R31.9-16 | Data bits 8-15 |

**Note:** Pin P9.92, P9.42, P9.91, P9.41 are on the inner row of the P9 header.

### Bringup Test Validation

The bringup firmware toggles CONVST at a known rate. With a logic analyzer:

1. **Connect to CONVST (P9.31)**
2. **Set trigger on rising edge**
3. **Capture waveform**

Expected behavior:
- CONVST should toggle at configured rate (e.g., 1 kHz for bringup)
- Pulse width should be consistent
- Timing should be deterministic (no jitter)

### Main Firmware Validation

Once bringup is verified, load the main firmware:

```bash
# Stop PRU
make pru-stop

# Load main firmware
make pru-load

# Verify running
cat /sys/class/remoteproc/remoteproc1/state
```

With AD7606 connected and logic analyzer:

1. **Monitor CONVST, BUSY, and data lines**
2. **Trigger on CONVST rising edge**
3. **Verify timing sequence:**
   - CONVST pulse (min 25ns)
   - BUSY goes high (conversion in progress)
   - BUSY goes low (conversion complete)
   - Data read sequence begins

Expected timing (for 10 kHz sampling):
- Sample period: 100 µs
- CONVST pulse: ~50 ns
- BUSY duration: ~4 µs (depends on AD7606 configuration)
- Data read: ~1 µs per channel (8 channels = 8 µs total)

### Common Issues

**PRU won't start:**
- Check device tree overlay is loaded: `cat /sys/devices/platform/bone_capemgr/slots`
- Check for HDMI conflicts: HDMI must be disabled
- Check kernel log: `sudo dmesg | grep pru`

**No signal on CONVST:**
- Verify pin mux configuration: `cat /sys/kernel/debug/pinctrl/44e10800.pinmux/pins | grep 190`
- Check PRU is actually running: `cat /sys/class/remoteproc/remoteproc1/state`
- Verify firmware loaded correctly: `ls -l /lib/firmware/am335x-pru0-fw`

**Timing issues:**
- PRU runs at 200 MHz (5 ns per cycle)
- Check cycle counter implementation in firmware
- Verify no interrupts or delays in critical sections

## Step 9: Monitor PRU Operation

### Check Shared Memory

The PRU writes status and data to shared memory:

```bash
# View PRU shared memory (requires root)
sudo hexdump -C /dev/mem -s 0x4A310000 -n 256

# Look for magic number 0xADC7606 at offset 0x00
```

### Read PRU Logs (if implemented)

```bash
# Check for PRU debug output in kernel log
sudo dmesg | grep -i pru

# Monitor in real-time
sudo dmesg -w
```

## Step 10: Next Steps

### With Hardware Connected

1. Connect AD7606 to BBB according to pin mapping
2. Apply test signals to ADC inputs
3. Verify data capture in shared memory
4. Implement data logger application to read from shared memory

### Development Workflow

```bash
# Edit firmware
nano ~/pika/pika/pru/src/pru_main.c

# Rebuild
cd ~/pika/pika
make pru

# Stop PRU
make pru-stop

# Load new firmware
make pru-load

# Validate with logic analyzer
```

### Performance Tuning

- Adjust sampling rate in `pru_config.h`
- Optimize timing loops in `timing.c`
- Tune buffer sizes in `shm_layout.h`
- Monitor CPU usage: `top` or `htop`

## Troubleshooting

### PRU Remoteproc Not Found

```bash
# Check if PRU overlay is loaded
ls /sys/class/remoteproc/

# If empty, check uEnv.txt
cat /boot/uEnv.txt | grep pru

# Reload PRU overlay
sudo reboot
```

### Permission Denied Errors

```bash
# Add user to necessary groups
sudo usermod -a -G kmem,gpio,i2c,spi debian

# Logout and login again
```

### HDMI Interference

The device tree overlay disables HDMI, but if you need HDMI:
- Use PRU1 instead of PRU0 (requires firmware changes)
- Use different pins that don't conflict with HDMI

### Compilation Errors

```bash
# Verify PRU compiler installation
which clpru
clpru --version

# Check PRU_SSP path
ls /usr/lib/ti/pru-software-support-package

# Set paths explicitly
export PRU_SSP=/usr/lib/ti/pru-software-support-package
export PRU_CGT=/usr/share/ti/cgt-pru
```

## Additional Resources

- [BeagleBone PRU Documentation](https://beagleboard.org/pru)
- [TI PRU Training](https://training.ti.com/pru-training-hands-lab-1)
- [AM335x PRU-ICSS Reference Guide](https://www.ti.com/lit/ug/spruh73q/spruh73q.pdf)
- [AD7606 Datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ad7606.pdf)
- [Project Architecture](architecture.md)
- [PRU Memory Map](memory-map.md)

## Support

For issues or questions:
- Check existing documentation in `docs/`
- Review PRU firmware README: `pika/pru/README.md`
- Check kernel logs: `sudo dmesg`
- Verify hardware connections with logic analyzer
