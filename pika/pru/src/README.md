# PRU Source Files

This directory contains the PRU firmware source code:

- `pru_main.c` - Main sampling loop firmware
- `pru_bringup.c` - Bring-up test firmware
- `timing.c` - Cycle-accurate timing functions
- `adc_parallel.c` - AD7606 parallel interface functions

## Building

Use the Makefile in the parent directory:

```bash
cd ..
make build     # Build main firmware
make bringup   # Build bring-up test firmware
```
