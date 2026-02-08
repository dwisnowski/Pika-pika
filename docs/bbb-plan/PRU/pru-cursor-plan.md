
⸻

⚙️ Plan 2 — PRU-Specific Implementation Plan

Purpose: implement deterministic PRU firmware for AD7606 sampling
This plan assumes Plan 1 is complete.

⸻

Plan 2: PRU Firmware Implementation

Goals
	•	Implement PRU firmware for:
	•	Continuous sampling
	•	Parallel AD7606 interface
	•	Cycle-count timing
	•	Provide build and run targets via make
	•	Keep PRU logic isolated from Linux complexity

⸻

PRU Subproject Structure (Detailed)

pru/
├── Makefile
├── include/
│   ├── pru_config.h        # Constants, limits, error flags
│   ├── shm_layout.h        # Shared memory contract (authoritative)
│
├── src/
│   ├── pru_main.c          # Main sampling loop
│   ├── timing.c            # Cycle counter helpers
│   ├── adc_parallel.c      # AD7606 signal-level interface
│   └── pru_bringup.c       # Minimal test firmware
│
└── firmware/
    ├── ad7606_sampler.out
    └── bringup_test.out


⸻

PRU Makefile (Initial Targets)

📄 pru/Makefile

PRU_CC ?= clpru
PRU_CFLAGS = --include_path=include

FIRMWARE_DIR = firmware

.PHONY: all build bringup load clean

all: build

build: $(FIRMWARE_DIR)/ad7606_sampler.out

bringup: $(FIRMWARE_DIR)/bringup_test.out

$(FIRMWARE_DIR)/ad7606_sampler.out:
	@echo "Building PRU sampler firmware"
	# compile command placeholder

$(FIRMWARE_DIR)/bringup_test.out:
	@echo "Building PRU bring-up firmware"
	# compile command placeholder

load:
	@echo "Loading PRU firmware (not yet implemented)"

clean:
	rm -f $(FIRMWARE_DIR)/*.out

⚠️ Compile and load commands will be added later
This Makefile establishes control points, not behavior.

⸻

Plan 2 Tasks (Cursor-Ready)

Task 2.1 — Define Shared Memory Layout

📄 pru/include/shm_layout.h

Cursor Prompt

Create a C header defining the shared DDR memory layout between PRU and Linux.

Requirements:
- Magic number and version
- Configuration fields (sample rate, block size, channel mask)
- Ring buffer configuration
- Volatile write_block_idx and error_flags
- Block descriptor struct
- No implementation code


⸻

Task 2.2 — Define PRU Configuration Constants

📄 pru/include/pru_config.h

Cursor Prompt

Create a PRU configuration header.

Include:
- PRU clock frequency
- Minimum safe sample period cycles
- Channel limits
- Error flag bitmasks

No pin definitions yet.


⸻

Task 2.3 — Timing Utilities

📄 pru/src/timing.c

Cursor Prompt

Write PRU C timing utilities.

Requirements:
- Enable cycle counter
- Inline get_cycle_count()
- Inline wait_until(target_cycles)
- No division or floating point


⸻

Task 2.4 — AD7606 Parallel Interface

📄 pru/src/adc_parallel.c

Cursor Prompt

Write PRU C code for AD7606 parallel interface.

Requirements:
- Inline functions for CONVST, BUSY wait, and parallel data read
- Assume data bus on R31[15:0]
- No pin numbers yet
- No loops


⸻

Task 2.5 — Main PRU Sampling Loop

📄 pru/src/pru_main.c

Cursor Prompt

Write the main PRU firmware loop.

Requirements:
- Read configuration from shared memory
- Wait for run flag
- Continuous block-based sampling
- Cycle-count timing
- Channel mask support
- Write to DDR ring buffer
- Update write_block_idx only after block completion


⸻

Task 2.6 — Bring-Up Test Firmware

📄 pru/src/pru_bringup.c

Cursor Prompt

Create a minimal PRU bring-up firmware.

Requirements:
- Toggle CONVST periodically
- Read data bus
- Toggle a GPIO on successful read
- No shared memory


⸻

Task 2.7 — PRU Device Tree Overlay

📄 overlays/ad7606-pru0.dts

Cursor Prompt

Create a BeagleBone Black device tree overlay.

Requirements:
- Disable HDMI
- Configure PRU0 R30 outputs and R31 inputs
- Comment each pin with AD7606 signal mapping
- No Linux drivers


⸻

Validation Gates (Do Not Skip)
	•	Logic analyzer verifies:
	•	CONVST timing
	•	BUSY behavior
	•	Data bus stability
	•	PRU code:
	•	No printf
	•	No malloc
	•	No division in hot loops
	•	Shared memory layout unchanged without explicit revision
