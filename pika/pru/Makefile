# PRU Firmware Makefile
# Builds PRU firmware for the AD7606 data acquisition system

# =============================================================================
# Toolchain Configuration
# =============================================================================

# TI PRU C Compiler
PRU_CC := clpru
PRU_LD := clpru

# Host paths (BBB Debian defaults). Override with env or make PRU_CGT=...
# On macOS after scripts/install-pru-toolchain-macos.sh:
#   ~/ti/cgt-pru-2.3.3/ti-cgt-pru_2.3.3 and ~/ti/pru-software-support-package
PRU_SSP ?= /usr/lib/ti/pru-software-support-package
PRU_CGT ?= /usr/share/ti/cgt-pru

# Auto-detect local TI installs (Mac / Linux host cross-build)
ifeq ($(wildcard $(PRU_CGT)/bin/clpru),)
  ifneq ($(wildcard $(HOME)/ti/cgt-pru-2.3.3/ti-cgt-pru_2.3.3/bin/clpru),)
    PRU_CGT := $(HOME)/ti/cgt-pru-2.3.3/ti-cgt-pru_2.3.3
  else ifneq ($(wildcard $(HOME)/ti/ti-cgt-pru_2.3.3/bin/clpru),)
    PRU_CGT := $(HOME)/ti/ti-cgt-pru_2.3.3
  endif
endif
ifeq ($(wildcard $(PRU_SSP)/include/pru_cfg.h)$(wildcard $(PRU_SSP)/include/am335x/pru_cfg.h),)
  ifneq ($(wildcard $(HOME)/ti/pru-software-support-package/include),)
    PRU_SSP := $(HOME)/ti/pru-software-support-package
  endif
endif

# Prefer toolchain bin on PATH for this make invocation
export PATH := $(PRU_CGT)/bin:$(PATH)

PRU_LIBS := --library=$(PRU_CGT)/lib/libc.a

# =============================================================================
# Directories
# =============================================================================
SRC_DIR := src
INC_DIR := include
BUILD_DIR := build
FIRMWARE_DIR := firmware

# =============================================================================
# Compiler and Linker Flags
# =============================================================================

# Include Paths (--include_path is the portable clpru form; -I alone misses CGT headers on macOS)
INCLUDE := --include_path=$(INC_DIR) \
           --include_path=$(PRU_CGT)/include \
           --include_path=$(PRU_SSP)/include \
           --include_path=$(PRU_SSP)/include/am335x

# Common Flags (Shared between C and Assembly)
COMMON_FLAGS := -v3 \
                --endian=little \
                --obj_directory=$(BUILD_DIR) \
                --define=PRU0

# PRU Compiler Flags for CGT 2.3.3
# --mem_model:data=far is required for absolute DDR pointers (0x8xxxxxxx+)
PRU_CFLAGS := $(COMMON_FLAGS) \
              -O2 \
              --hardware_mac=on \
              --display_error_number \
              --mem_model:data=far \
              $(INCLUDE)

# Linker flags
PRU_LDFLAGS := -z \
               --entry_point=main \
               --stack_size=0x100 \
               --heap_size=0x100 \
               --reread_libs \
               --warn_sections \
               -u pru_remoteproc_ResourceTable

# Linker command file (if needed)
PRU_LINKER_CMD := AM335x_PRU.cmd

# =============================================================================
# Source and Objects
# =============================================================================

# Main sampling firmware sources
MAIN_SOURCES := $(SRC_DIR)/pru_main.c \
                $(SRC_DIR)/resource_table.c \
                $(SRC_DIR)/adc_parallel.c

# Bringup test firmware sources
BRINGUP_SOURCES := $(SRC_DIR)/pru_bringup.c \
                   $(SRC_DIR)/resource_table.c

# Header dependencies
HEADERS := $(wildcard $(INC_DIR)/*.h)

# =============================================================================
# Output Files
# =============================================================================
MAIN_OUT := $(FIRMWARE_DIR)/ad7606_sampler.out
BRINGUP_OUT := $(FIRMWARE_DIR)/bringup_test.out


# Assembly sources (main firmware only: runtime cycle delay)
MAIN_ASM_SOURCES := $(SRC_DIR)/delay_cycles.asm

# Object files
MAIN_OBJECTS := $(patsubst $(SRC_DIR)/%.c,$(BUILD_DIR)/%.obj,$(MAIN_SOURCES))
BRINGUP_OBJECTS := $(patsubst $(SRC_DIR)/%.c,$(BUILD_DIR)/%.obj,$(BRINGUP_SOURCES))


# =============================================================================
# Device Tree Overlay
# =============================================================================
DTC := dtc
DTS_FILE := ../overlays/ad7606-pru0.dts
DTBO_FILE := BB-PRU0-AD7606.dtbo

# =============================================================================
# PRU remoteproc paths
# =============================================================================
PRU0_FIRMWARE_PATH := /lib/firmware/am335x-pru0-fw
PRU0_STATE := /sys/class/remoteproc/remoteproc1/state
PRU0_FIRMWARE := /sys/class/remoteproc/remoteproc1/firmware

# =============================================================================
# Phony Targets
# =============================================================================
.PHONY: all build bringup load load-bringup clean clean-tests overlay install-overlay help build_dir firmware_dir run check-toolchain

# =============================================================================
# Default Target
# =============================================================================
all: build

# =============================================================================
# Directory Creation
# =============================================================================
build_dir:
	@mkdir -p $(BUILD_DIR)

firmware_dir:
	@mkdir -p $(FIRMWARE_DIR)

# =============================================================================
# Compilation Rules
# =============================================================================
$(BUILD_DIR)/%.obj: $(SRC_DIR)/%.c $(HEADERS) | build_dir
	@echo "Compiling: $<"
	@$(PRU_CC) $(PRU_CFLAGS) -c $< -o $@

$(BUILD_DIR)/%.obj: $(SRC_DIR)/%.asm | build_dir
	@echo "Assembling: $<"
	@$(PRU_CC) $(COMMON_FLAGS) -c $< -o $@

# =============================================================================
# Linking Rules
# =============================================================================

# Main firmware
$(FIRMWARE_DIR)/ad7606_sampler.out: $(MAIN_OBJECTS) $(BUILD_DIR)/delay_cycles.obj | firmware_dir
	@echo "Linking main firmware: $@"
	@$(PRU_LD) $(PRU_LDFLAGS) $^ $(PRU_LINKER_CMD) $(PRU_LIBS) -o $@
	@echo "Main firmware linked successfully: $@"

# =============================================================================
# Build Targets
# =============================================================================
info:
	$(info PRU_CGT=$(PRU_CGT))
	$(info PRU_SSP=$(PRU_SSP))
	$(info PRU_CC=$(shell which $(PRU_CC) 2>/dev/null || echo missing))

# Fail fast on host if clpru / headers are missing (run before syncing to BBB)
check-toolchain:
	@command -v $(PRU_CC) >/dev/null || { \
	  echo "error: clpru not found on PATH (PRU_CGT=$(PRU_CGT))"; \
	  echo "  macOS: ./scripts/install-pru-toolchain-macos.sh"; \
	  echo "  BBB:   sudo apt install ti-pru-cgt-v2.3"; \
	  exit 1; \
	}
	@test -f $(PRU_CGT)/include/stdint.h || { \
	  echo "error: missing $(PRU_CGT)/include/stdint.h"; exit 1; \
	}
	@test -f $(PRU_SSP)/include/am335x/pru_cfg.h -o -f $(PRU_SSP)/include/pru_cfg.h || { \
	  echo "error: missing PRU SSP headers under $(PRU_SSP)"; exit 1; \
	}
	@$(PRU_CC) -version | head -2
	@echo "Toolchain OK: PRU_CGT=$(PRU_CGT)"
	@echo "              PRU_SSP=$(PRU_SSP)"

build: check-toolchain $(FIRMWARE_DIR)/ad7606_sampler.out
bringup: check-toolchain $(FIRMWARE_DIR)/bringup_test.out

# =============================================================================
# Load Firmware to PRU
# =============================================================================
# Robust PRU0 Discovery
PRU_PATH := /sys/class/remoteproc
# Discover which remoteproc is PRU0 (4a334000)
PRU0_ID := $(shell grep -l "4a334000.pru" $(PRU_PATH)/remoteproc*/name 2>/dev/null | cut -d '/' -f 5)

pru-status:
	@echo "Checking PRU status..."
	@for r in $(PRU_PATH)/remoteproc*; do \
		echo "$$(basename $$r): $$(cat $$r/name) -> $$(cat $$r/state)"; \
	done

run: load

# Load main sampling firmware
load: $(MAIN_OUT)
	@if [ -z "$(PRU0_ID)" ]; then echo "ERROR: PRU0 not found in $(PRU_PATH). Is the overlay loaded?"; exit 1; fi
	@echo "Detected PRU0 at $(PRU_PATH)/$(PRU0_ID)"
	@config-pin P9.27 pruout
	@config-pin P9.30 pruout
	@config-pin P9.28 pruout
	@config-pin P9.29 pruout
	@config-pin P9.25 pruin
	
	@echo "Configuring Data Pins..."
# 	@config-pin P9.23 gpio had to move because of other pins not available.
	@config-pin P9.23 gpio
	@for i in 10 11 12 13 14 15 16 17 18 19 26 27 28 29 30; do \
		config-pin P8.$$i gpio; \
	done

	@echo "Stopping $(PRU0_ID)..."
	@echo stop | sudo tee $(PRU_PATH)/$(PRU0_ID)/state 2>/dev/null || true
	@echo "Loading firmware..."
	@echo "MD5 of firmware before loading:"
	@md5sum $(FIRMWARE_DIR)/ad7606_sampler.out /lib/firmware/am335x-pru0-fw
# 	@sudo rm /lib/firmware/am335x-pru0-fw  2>/dev/null || true
	@sudo cp $(FIRMWARE_DIR)/ad7606_sampler.out /lib/firmware/am335x-pru0-fw
	@echo "MD5 of firmware after loading:"
	@md5sum $(FIRMWARE_DIR)/ad7606_sampler.out /lib/firmware/am335x-pru0-fw
	@echo am335x-pru0-fw | sudo tee $(PRU_PATH)/$(PRU0_ID)/firmware
	@echo "Starting $(PRU0_ID)..."
	@echo start | sudo tee $(PRU_PATH)/$(PRU0_ID)/state
	@echo "Current State: $$(cat $(PRU_PATH)/$(PRU0_ID)/state)"


load-bringup: $(BRINGUP_OUT)
	@if [ -z "$(PRU0_ID)" ]; then echo "ERROR: PRU0 not found in $(PRU_PATH). Is the overlay loaded?"; exit 1; fi
	@config-pin P9.27 pruout
	@echo "Loading to $(PRU0_ID) (PRU0)..."
	@echo stop | sudo tee $(PRU_PATH)/$(PRU0_ID)/state 2>/dev/null || true
	@sudo cp $(FIRMWARE_DIR)/bringup_test.out /lib/firmware/am335x-pru0-fw
	@echo am335x-pru0-fw | sudo tee $(PRU_PATH)/$(PRU0_ID)/firmware
	@echo start | sudo tee $(PRU_PATH)/$(PRU0_ID)/state


# Isolated Debug Target
DEBUG_OBJECTS := $(BUILD_DIR)/pru_test_io.obj $(BUILD_DIR)/resource_table.obj

debug-pru: $(DEBUG_OBJECTS) firmware_dir
	@echo "Linking Debug firmware..."
	@$(PRU_LD) -z --entry_point=main -u pru_remoteproc_ResourceTable $(DEBUG_OBJECTS) AM335x_PRU.cmd $(PRU_LIBS) -o $(FIRMWARE_DIR)/debug.out
	@config-pin P9.27 pruout
	@echo "Loading Debug Firmware to $(PRU0_ID)..."
	@if [ "$$(cat /sys/class/remoteproc/$(PRU0_ID)/state)" != "offline" ]; then echo stop | sudo tee /sys/class/remoteproc/$(PRU0_ID)/state; fi
	@sudo cp $(FIRMWARE_DIR)/debug.out /lib/firmware/am335x-pru0-fw
	@echo am335x-pru0-fw | sudo tee /sys/class/remoteproc/$(PRU0_ID)/firmware
	@echo start | sudo tee /sys/class/remoteproc/$(PRU0_ID)/state

$(BUILD_DIR)/pru_test_io.obj: $(SRC_DIR)/pru_test_io.c | build_dir
	@$(PRU_CC) $(PRU_CFLAGS) -c $< -o $@

wakeup-pru:
	@ls /sys/class/remoteproc/
	@echo "Waking up PRU0 ($(PRU0_ID))..."
	@sudo modprobe pru_rproc
	@echo "PRU0 waked up"
	@ls /sys/class/remoteproc/

pru-info:
	@echo "PRU0 ($(PRU0_ID)): $$(cat /sys/class/remoteproc/$(PRU0_ID)/state 2>/dev/null || echo 'not found')"
	@grep -H . /sys/class/remoteproc/remoteproc*/state 2>/dev/null || true

uart-pulse:
	@echo "Logic Analyzer Sanity Check" | sudo tee /dev/ttyS0

# Parameterized Pin Testing (Usage: make pin-test H=P9 P=27 C=3 L=19)
# Common Mappings:
# P9.27: C=3 L=19 (CONVST) | P9.30: C=3 L=16 (RD) | P9.28: C=3 L=17 (CS)
# P9.29: C=3 L=15 (RST)    | P9.25: C=3 L=21 (BUSY)
# P8.29: C=2 L=23 (DB1)    | P8.30: C=2 L=25 (DB0) | P9.23: C=1 L=17 (DB3)
H ?= P9
P ?= 27
C ?= 3
L ?= 19
ITERATIONS ?= 5
MS_DELAY ?= 250

pin-test:
	@echo "Configuring $(H).$(P) as GPIO..."
	@config-pin $(H).$(P) gpio
	@echo "Toggling $(H).$(P) (Chip $(C), Line $(L)) $(ITERATIONS) times..."
	@for i in $$(seq 1 $(ITERATIONS)); do \
		echo "Iteration $$i: HIGH"; \
		gpioset --mode time --sec 0 --usec $$(($(MS_DELAY) * 1000)) $(C) $(L)=1; \
		echo "Iteration $$i: LOW"; \
		gpioset --mode time --sec 0 --usec $$(($(MS_DELAY) * 1000)) $(C) $(L)=0; \
	done
	@echo "Done."
	

# Stop PRU0 safely
stop:
	@echo "Stopping PRU0 ($(PRU0_ID))..."
	@if [ -d /sys/class/remoteproc/$(PRU0_ID) ]; then \
		STATE=$$(cat /sys/class/remoteproc/$(PRU0_ID)/state); \
		if [ "$$STATE" != "offline" ]; then \
			echo stop | sudo tee /sys/class/remoteproc/$(PRU0_ID)/state; \
			echo "PRU0 stopped"; \
		else \
			echo "PRU0 is already stopped"; \
		fi \
	else \
		echo "PRU remoteproc not found. Is PRU enabled in device tree?"; \
	fi

# Start PRU0 safely
start:
	@echo "Starting PRU0 ($(PRU0_ID))..."
	@if [ -d /sys/class/remoteproc/$(PRU0_ID) ]; then \
		STATE=$$(cat /sys/class/remoteproc/$(PRU0_ID)/state); \
		if [ "$$STATE" = "offline" ]; then \
			echo start | sudo tee /sys/class/remoteproc/$(PRU0_ID)/state; \
			echo "PRU0 started"; \
		else \
			echo "PRU0 is already started"; \
		fi \
	else \
		echo "PRU remoteproc not found. Is PRU enabled in device tree?"; \
	fi

# =============================================================================
# Test Targets
# =============================================================================
test-mocks:
	@$(MAKE) -C tests/mocks

# Run unit tests
test-unit: test-mocks
	@echo "Running unit tests..."
	@$(MAKE) -C tests/unit test
	@echo "Unit tests completed"

# Run all tests
test: test-unit
	@echo ""
	@echo "=========================================="
	@echo "All tests passed successfully!"
	@echo "=========================================="

# =============================================================================
# Device Tree
# =============================================================================
# Compile device tree overlay
overlay: $(DTBO_FILE)

$(DTBO_FILE): $(DTS_FILE)
	@echo "Compiling device tree overlay: $< -> $@"
	@$(DTC) -O dtb -o $@ -b 0 -@ $<
	@echo "Device tree overlay compiled successfully"

# Install device tree overlay to /lib/firmware
install-overlay: $(DTBO_FILE)
	@echo "Installing device tree overlay to /lib/firmware/"
	@sudo cp $(DTBO_FILE) /lib/firmware/
	@echo "Overlay installed. Load with:"
	@echo "  sudo sh -c \"echo 'BB-PRU0-AD7606' > /sys/devices/platform/bone_capemgr/slots\""


# =============================================================================
# Clean
# =============================================================================
clean:
	@rm -rf $(BUILD_DIR)
	@rm -f $(FIRMWARE_DIR)/*.out
	@rm -f $(DTBO_FILE)
	@echo "Clean complete"

# =============================================================================
# Help
# =============================================================================
help:
	@echo "PRU Firmware Build System"
	@echo "========================="
	@echo ""
	@echo "Targets:"
	@echo "  build          - Build main sampling firmware (ad7606_sampler.out)"
	@echo "  check-toolchain- Verify clpru + CGT/SSP paths (host or BBB)"
	@echo "  bringup        - Build bringup test firmware (bringup_test.out)"
	@echo "  load           - Load main firmware to PRU0 via remoteproc"
	@echo "  load-bringup   - Load bringup firmware to PRU0 via remoteproc"
	@echo "  stop           - Stop PRU0"
	@echo "  overlay        - Compile device tree overlay"
	@echo "  install-overlay- Install device tree overlay to /lib/firmware"
	@echo "  clean          - Remove all build artifacts (including tests)"
	@echo "  help           - Show this help message"
	@echo ""
	@echo "Configuration:"
	@echo "  PRU_SSP        - PRU Software Support Package path (default: $(PRU_SSP))"
	@echo "  PRU_CGT        - PRU Code Generation Tools path (default: $(PRU_CGT))"
	@echo ""
