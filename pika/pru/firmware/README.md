# PRU Firmware Binaries

This directory contains compiled PRU firmware binaries:

- `ad7606_sampler.out` - Main sampling firmware for PRU0
- `bringup_test.out` - Bring-up test firmware for PRU0

## Loading Firmware

To load firmware onto PRU0:

```bash
cd ..
make load      # Load main firmware to PRU0
```

Or manually using remoteproc:

```bash
echo 'stop' > /sys/class/remoteproc/remoteproc1/state
cp firmware/ad7606_sampler.out /lib/firmware/am335x-pru0-fw
echo 'start' > /sys/class/remoteproc/remoteproc1/state
```

## Hardware Validation

For initial hardware validation, load the bring-up test firmware:

```bash
cp firmware/bringup_test.out /lib/firmware/am335x-pru0-fw
echo 'start' > /sys/class/remoteproc/remoteproc1/state
```

This will toggle the CONVST pin at 1 kHz, which can be verified with a logic analyzer.
