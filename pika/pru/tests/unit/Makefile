# Makefile for PRU firmware unit tests

CC = gcc
CFLAGS = -Wall -Wextra -std=c99 -I../../include
LDFLAGS =

# Test executables
TESTS = test_shm_layout test_pru_config test_timing test_adc_interface test_config_validation test_bringup test_device_tree

# Default target: build all tests
all: $(TESTS)

# Build test_shm_layout
test_shm_layout: test_shm_layout.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Build test_pru_config
test_pru_config: test_pru_config.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Build test_timing
test_timing: test_timing.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Build test_adc_interface
test_adc_interface: test_adc_interface.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Build test_config_validation
test_config_validation: test_config_validation.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Build test_bringup
test_bringup: test_bringup.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Build test_device_tree
test_device_tree: test_device_tree.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Run all tests
test: all
	@echo "Running unit tests..."
	@for test in $(TESTS); do \
		echo ""; \
		./$$test || exit 1; \
	done
	@echo ""
	@echo "All unit tests passed!"

# Clean build artifacts
clean:
	rm -f $(TESTS) *.o

.PHONY: all test clean
