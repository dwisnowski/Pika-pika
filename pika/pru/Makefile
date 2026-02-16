# PRU Firmware Makefile
# Builds PRU firmware for the AD7606 data acquisition system

# =============================================================================
# Toolchain Configuration
# =============================================================================

# TI PRU C Compiler
PRU_CC := clpru
PRU_LD := clpru

# PRU Software Support Package paths (adjust as needed)
# These paths may need to be configured based on installation
PRU_SSP ?= /usr/lib/ti/pru-software-support-package
PRU_CGT ?= /usr/share/ti/cgt-pru
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

# Compiler flags
PRU_CFLAGS := -v3 \
              -O2 \
              --display_error_number \
              --endian=little \
              --hardware_mac=on \
              --include_path=$(INC_DIR) \
              --include_path=$(PRU_CGT)/include \
              --include_path=$(PRU_SSP)/include \
              --include_path=$(PRU_SSP)/include/am335x \
			  --obj_directory=$(BUILD_DIR)

# Linker flags
PRU_LDFLAGS := --reread_libs \
               --warn_sections \
               --stack_size=0x100 \
               --heap_size=0x100 \
               --entry_point main

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

MAIN_FIRMWARE := $(FIRMWARE_DIR)/ad7606_sampler.fw
BRINGUP_FIRMWARE := $(FIRMWARE_DIR)/bringup_test.fw


# Assembly sources (main firmware only: runtime cycle delay)
MAIN_ASM_SOURCES := $(SRC_DIR)/delay_cycles.asm

# Object files
MAIN_OBJECTS := $(patsubst $(SRC_DIR)/%.c,$(BUILD_DIR)/%.obj,$(MAIN_SOURCES)) \
                $(BUILD_DIR)/delay_cycles.obj
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
.PHONY: all build bringup load load-bringup clean clean-tests overlay install-overlay help build_dir firmware_dir

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
	@$(PRU_CC) $(PRU_CFLAGS) -c $< -o $@ --define=PRU0

$(BUILD_DIR)/delay_cycles.obj: $(SRC_DIR)/delay_cycles.asm | build_dir
	@echo "Assembling: $<"
	@$(PRU_CC) -v3 --endian=little --obj_directory=$(BUILD_DIR) -c $< -o $@ --define=PRU0

# =============================================================================
# Linking Rules
# =============================================================================

# Main firmware
$(FIRMWARE_DIR)/ad7606_sampler.out: $(MAIN_OBJECTS) firmware_dir
	@echo "Linking main firmware: $@"
	@$(PRU_LD) -z --entry_point=main \
	-u pru_remoteproc_ResourceTable \
	$(MAIN_OBJECTS) \
	AM335x_PRU.cmd \
	$(PRU_LIBS) \
	-o $@
	@echo "Main firmware linked successfully: $@"

$(FIRMWARE_DIR)/ad7606_sampler.fw: $(FIRMWARE_DIR)/ad7606_sampler.out
	@echo "Converting main firmware to raw .fw: $@"
	@hexpru -o $@ $<
	@echo "Main firmware .fw created successfully: $@"

# Bringup firmware
$(FIRMWARE_DIR)/bringup_test.out: $(BRINGUP_OBJECTS) firmware_dir
	@echo "Linking bringup firmware: $@"
	@$(PRU_LD) -z --entry_point=main \
	-u pru_remoteproc_ResourceTable \
	$(BRINGUP_OBJECTS) \
	AM335x_PRU.cmd \
	$(PRU_LIBS) \
	-o $@
	@echo "Bringup firmware linked successfully: $@"

$(FIRMWARE_DIR)/bringup_test.fw: $(FIRMWARE_DIR)/bringup_test.out
	@echo "Converting bringup firmware to raw .fw: $@"
	@hexpru -o $@ $<
	@echo "Bringup firmware .fw created successfully: $@"





# =============================================================================
# Build Targets
# =============================================================================
build: $(MAIN_FIRMWARE)
bringup: $(BRINGUP_FIRMWARE)

# =============================================================================
# Load Firmware to PRU
# =============================================================================
# Dynamically discover the index for PRU0 (4a334000)
PRU0_ID := $(shell grep -l "4a334000.pru" /sys/class/remoteproc/remoteproc*/name | cut -d '/' -f 5)


# Load main sampling firmware
load: $(MAIN_FIRMWARE)
	@config-pin P9.27 pruout
	@echo "Loading to $(PRU0_ID) (PRU0)..."
	@if [ "$$(cat /sys/class/remoteproc/$(PRU0_ID)/state)" != "offline" ]; then \
		echo stop | sudo tee /sys/class/remoteproc/$(PRU0_ID)/state; \
	fi
	@sudo cp $(FIRMWARE_DIR)/ad7606_sampler.out /lib/firmware/am335x-pru0-fw
	@echo am335x-pru0-fw | sudo tee /sys/class/remoteproc/$(PRU0_ID)/firmware
	@echo start | sudo tee /sys/class/remoteproc/$(PRU0_ID)/state


load-bringup: $(BRINGUP_FIRMWARE)
	@config-pin P9.27 pruout
	@echo "Loading to $(PRU0_ID) (PRU0)..."
	@if [ "$$(cat /sys/class/remoteproc/$(PRU0_ID)/state)" != "offline" ]; then \
		echo stop | sudo tee /sys/class/remoteproc/$(PRU0_ID)/state; \
	fi
	@sudo cp firmware/bringup_test.out /lib/firmware/am335x-pru0-fw
	@echo am335x-pru0-fw | sudo tee /sys/class/remoteproc/$(PRU0_ID)/firmware
	@echo start | sudo tee /sys/class/remoteproc/$(PRU0_ID)/state


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

# Variables for P9.27 (Chip 3, Line 19)
CHIP = 3
LINE = 19
ITERATIONS = 10
# Duration in milliseconds (2000ms = 2s)
MS_DELAY = 250
# Duration in seconds for the "off" period
SEC_DELAY = .2

pin-test:
	@echo "Configuring P9.27 as GPIO..."
	@config-pin P9.27 gpio
	@echo "Toggling P9.27 $(ITERATIONS) times..."
	@for i in $$(seq 1 $(ITERATIONS)); do \
		echo "Iteration $$i: HIGH (Holding for $(MS_DELAY)ms)"; \
		gpioset --mode time --sec 0 --usec $$(($(MS_DELAY) * 1000)) $(CHIP) $(LINE)=1; \
		echo "Iteration $$i: LOW (Holding for $(MS_DELAY)ms)"; \
		gpioset --mode time --sec 0 --usec $$(($(MS_DELAY) * 1000)) $(CHIP) $(LINE)=0; \
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
	@rm -rf $(FIRMWARE_DIR)/*.out
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
