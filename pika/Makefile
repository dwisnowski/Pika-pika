# BeagleBone Black Data Acquisition System - Top-Level Makefile
#
# This Makefile orchestrates builds across all subprojects using a delegation pattern.
# Each target delegates to the corresponding subproject Makefile using $(MAKE) -C.
#
# Targets:
#   all        - Build all components (PRU firmware, data logger, web application)
#   pru        - Build PRU firmware only
#   datalogger - Build data logger only
#   web        - Build web application only
#   clean      - Clean all build artifacts from all subprojects
#
# Delegation Pattern:
#   $(MAKE) -C <directory> invokes Make in the specified subdirectory,
#   executing the Makefile in that directory. This allows each component
#   to maintain its own build logic while providing a unified interface
#   at the top level.

.PHONY: all pru datalogger web clean test-pru pru-bringup pru-load pru-load-bringup pru-stop pru-overlay run-datalogger run-all stop help setup

# Build all components
all: pru datalogger web

# Install system dependencies
setup:
	@echo "Installing system dependencies..."
	@sudo apt-get update && sudo apt-get install -y libyaml-dev

# Build PRU firmware - delegates to pru/Makefile
pru:
	$(MAKE) -C pru load

# Build PRU bringup firmware
pru-bringup:
	$(MAKE) -C pru bringup

# Build data logger - delegates to datalogger/Makefile
datalogger:
	$(MAKE) -C datalogger

# Build web application - delegates to webapp/Makefile
web:
	$(MAKE) -C webapp

# Test PRU firmware (unit + property tests)
test-pru:
	$(MAKE) -C pru test

# Load PRU firmware to BeagleBone Black
pru-load:
	$(MAKE) -C pru load

# Load PRU bringup firmware to BeagleBone Black
pru-load-bringup:
	$(MAKE) -C pru load-bringup

# Stop PRU
pru-stop:
	$(MAKE) -C pru stop

# Build and install device tree overlay
pru-overlay:
	$(MAKE) -C pru overlay install-overlay

# Web Application
web-setup:
	$(MAKE) -C webapp setup

run-web:
	$(MAKE) -C webapp run

# Run datalogger (builds first). PRU firmware must be installed: run make pru-load once.
run-datalogger: datalogger
	@sudo $(MAKE) -C datalogger run

# Build PRU firmware and datalogger, then run both.
run-all: pru datalogger web
	@echo "Starting Datalogger (C)..."
	@sudo $(MAKE) -C datalogger run &
	@echo "Starting Web Application (FastAPI)..."
	@$(MAKE) -C webapp run

stop:
	@echo "Stopping all Pika components..."
	-@sudo pkill -9 -f datalogger
	-@sudo pkill -9 -f uvicorn
	-@$(MAKE) -C pru stop
	@echo "Stopped."

# Clean all build artifacts - delegates to all subproject Makefiles
clean:
	$(MAKE) -C pru clean
	$(MAKE) -C datalogger clean
# 	$(MAKE) -C webapp clean  #  Not needed most of the time. <-----

# Help
help:
	@echo "Pika - BeagleBone Black Data Acquisition System"
	@echo "================================================"
	@echo ""
	@echo "Build Targets:"
	@echo "  all              - Build all components"
	@echo "  pru              - Build PRU firmware"
	@echo "  pru-bringup      - Build PRU bringup test firmware"
	@echo "  datalogger       - Build data logger"
	@echo "  web              - Build web application (planned)"
	@echo ""
	@echo "Run Targets:"
	@echo "  run-datalogger   - Build and run datalogger (run make pru-load once first)"
	@echo "  run-all          - Build pru + datalogger, then run datalogger"
	@echo "  stop             - Force stop all background components"
	@echo ""
	@echo "PRU Targets:"
	@echo "  test-pru         - Run PRU firmware tests"
	@echo "  pru-load         - Load PRU firmware to BBB"
	@echo "  pru-load-bringup - Load PRU bringup firmware to BBB"
	@echo "  pru-stop         - Stop PRU"
	@echo "  pru-overlay      - Build and install device tree overlay"
	@echo ""
	@echo "Other:"
	@echo "  setup            - Install system dependencies (libyaml-dev)"
	@echo "  clean            - Clean all build artifacts"
	@echo "  help             - Show this help message"
	@echo ""
	@echo "See docs/getting-started.md for hardware setup instructions"
