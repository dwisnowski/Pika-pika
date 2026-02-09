# Makefile for PRU firmware property-based tests

CC = gcc
CFLAGS = -Wall -Wextra -std=c99 -I../../include
LDFLAGS = -lm

# Property test executables
TESTS = test_timing_props test_sampling_props test_magic_validation_props test_block_completion_props test_ringbuf_wrapping_props test_timing_accuracy_props test_channel_mask_props test_error_handling_props

# Default target: build all tests
all: $(TESTS)

# Build test_timing_props
test_timing_props: test_timing_props.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Build test_sampling_props
test_sampling_props: test_sampling_props.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Build test_magic_validation_props
test_magic_validation_props: test_magic_validation_props.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Build test_block_completion_props
test_block_completion_props: test_block_completion_props.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Build test_ringbuf_wrapping_props
test_ringbuf_wrapping_props: test_ringbuf_wrapping_props.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Build test_timing_accuracy_props
test_timing_accuracy_props: test_timing_accuracy_props.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Build test_channel_mask_props
test_channel_mask_props: test_channel_mask_props.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Build test_error_handling_props
test_error_handling_props: test_error_handling_props.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Run all property tests
test: all
	@echo "Running property-based tests..."
	@for t in $(TESTS); do \
		echo ""; \
		./$$t || exit 1; \
	done
	@echo ""
	@echo "All property tests passed!"

# Clean build artifacts
clean:
	rm -f $(TESTS) *.o

.PHONY: all test clean
