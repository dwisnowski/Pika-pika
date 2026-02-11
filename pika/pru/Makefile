# PRU Firmware Makefile
# Builds PRU firmware for the AD7606 data acquisition system

# =============================================================================
# Toolchain Configuration
# =============================================================================

# TI PRU C Compiler
PRU_CC := clpru
PRU_LD := lnkpru

# PRU Software Support Package paths (adjust as needed)
# These paths may need to be configured based on installation
PRU_SSP ?= /usr/lib/ti/pru-software-support-package
PRU_CGT ?= /usr/share/ti/cgt-pru

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
               --heap_size=0x100

# Linker command file (if needed)
PRU_LINKER_CMD := AM335x_PRU.cmd

# =============================================================================
# Source and Objects
# =============================================================================

# Main sampling firmware sources
MAIN_SOURCES := $(SRC_DIR)/pru_main.c \
                $(SRC_DIR)/timing.c \
                $(SRC_DIR)/adc_parallel.c

# Bringup test firmware sources
BRINGUP_SOURCES := $(SRC_DIR)/pru_bringup.c \
                   $(SRC_DIR)/timing.c

# Header dependencies
HEADERS := $(wildcard $(INC_DIR)/*.h)

# =============================================================================
# Output Files
# =============================================================================

MAIN_FIRMWARE := $(FIRMWARE_DIR)/ad7606_sampler.out
BRINGUP_FIRMWARE := $(FIRMWARE_DIR)/bringup_test.out

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

# =============================================================================
# Linking Rules
# =============================================================================
$(MAIN_FIRMWARE): $(MAIN_OBJECTS) firmware_dir
	@echo "Linking main firmware: $@"
	@$(PRU_LD) $(PRU_LDFLAGS) -o $@ $(MAIN_OBJECTS) \
	    --library=$(PRU_CGT)/lib/libc.a \
	    --cmd_file=$(PRU_LINKER_CMD)
	@echo "Main firmware built successfully: $@"


$(BRINGUP_FIRMWARE): $(BRINGUP_OBJECTS) | firmware_dir
	@echo "Linking bringup firmware: $@"
	@$(PRU_LD) $(PRU_LDFLAGS) -o $@ $(BRINGUP_OBJECTS) \
		--library=$(PRU_CGT)/lib/libc.a \
		$(if $(wildcard $(PRU_LINKER_CMD)),--cmd_file=$(PRU_LINKER_CMD),)
	@echo "Bringup firmware built successfully: $@"

# =============================================================================
# Build Targets
# =============================================================================
build: $(MAIN_FIRMWARE)
bringup: $(BRINGUP_FIRMWARE)

# =============================================================================
# Load Firmware to PRU
# =============================================================================
load: $(MAIN_FIRMWARE)
	@echo "Loading main firmware to PRU0..."
	@if [ ! -d /sys/class/remoteproc/remoteproc1 ]; then \
		echo "Error: PRU remoteproc not found"; exit 1; \
	fi
	@echo "Stopping PRU0..."
	@sudo sh -c "echo 'stop' > $(PRU0_STATE)" || true
	@echo "Copying firmware to /lib/firmware..."
	@sudo cp $(MAIN_FIRMWARE) $(PRU0_FIRMWARE_PATH)
	@echo "Starting PRU0..."
	@sudo sh -c "echo 'start' > $(PRU0_STATE)"
	@echo "PRU0 firmware loaded and started"

# Load bringup test firmware
load-bringup: $(BRINGUP_FIRMWARE)
	@echo "Loading bringup firmware to PRU0..."
	@if [ ! -d /sys/class/remoteproc/remoteproc1 ]; then \
		echo "Error: PRU remoteproc not found. Is PRU enabled in device tree?"; exit 1; \
	fi
	@echo "Stopping PRU0..."
	@sudo sh -c "echo 'stop' > $(PRU0_STATE)" || true
	@echo "Copying firmware to /lib/firmware..."
	@sudo cp $(BRINGUP_FIRMWARE) $(PRU0_FIRMWARE_PATH)
	@echo "Starting PRU0..."
	@sudo sh -c "echo 'start' > $(PRU0_STATE)"
	@echo "PRU0 bringup firmware loaded and started"

# Stop PRU0
stop:
	@echo "Stopping PRU0..."
	@sudo sh -c "echo 'stop' > $(PRU0_STATE)" || true
	@echo "PRU0 stopped"

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

# Run property-based tests
test-property: test-mocks
	@echo "Running property-based tests..."
	@$(MAKE) -C tests/property test
	@echo "Property tests completed"

# Run all tests
test: test-unit test-property
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
# Clean test artifacts
clean-tests:
	@echo "Cleaning test artifacts..."
	@$(MAKE) -C tests/mocks clean
	@$(MAKE) -C tests/unit clean
	@$(MAKE) -C tests/property clean
	@echo "Test artifacts cleaned"

clean: clean-tests
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
	@echo "  test           - Run all tests (unit + property)"
	@echo "  test-unit      - Run unit tests only"
	@echo "  test-property  - Run property-based tests only"
	@echo "  test-mocks     - Build mock library for testing"
	@echo "  overlay        - Compile device tree overlay"
	@echo "  install-overlay- Install device tree overlay to /lib/firmware"
	@echo "  clean          - Remove all build artifacts (including tests)"
	@echo "  clean-tests    - Remove test artifacts only"
	@echo "  help           - Show this help message"
	@echo ""
	@echo "Configuration:"
	@echo "  PRU_SSP        - PRU Software Support Package path (default: $(PRU_SSP))"
	@echo "  PRU_CGT        - PRU Code Generation Tools path (default: $(PRU_CGT))"
	@echo ""
	@echo "Examples:"
	@echo "  make build                    # Build main firmware"
	@echo "  make bringup                  # Build bringup firmware"
	@echo "  make test                     # Run all tests"
	@echo "  make load                     # Load main firmware to PRU0"
	@echo "  make PRU_SSP=/path/to/pru-ssp build  # Build with custom PRU_SSP path"
