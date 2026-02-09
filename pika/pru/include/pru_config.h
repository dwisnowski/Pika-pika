#ifndef PRU_CONFIG_H
#define PRU_CONFIG_H

#include <stdint.h>

/**
 * PRU Configuration Constants
 * 
 * This header defines hardware and timing constants for the PRU firmware
 * that performs deterministic data acquisition from an AD7606 ADC.
 * 
 * Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
 */

/* ============================================================================
 * PRU Hardware Constants (Requirement 2.1)
 * ============================================================================ */

/** PRU clock frequency in Hz (200 MHz) */
#define PRU_CLOCK_HZ 200000000

/** Number of PRU cycles per microsecond */
#define CYCLES_PER_US (PRU_CLOCK_HZ / 1000000)  // 200 cycles/µs

/* ============================================================================
 * Timing Constraints (Requirement 2.2)
 * ============================================================================ */

/** Minimum sample period in microseconds (10 µs = 100 kHz max rate) */
#define MIN_SAMPLE_PERIOD_US 10

/** Maximum sample period in microseconds (100 ms = 10 Hz min rate) */
#define MAX_SAMPLE_PERIOD_US 100000

/** Minimum sample period in PRU cycles */
#define MIN_SAMPLE_PERIOD_CYCLES (MIN_SAMPLE_PERIOD_US * CYCLES_PER_US)

/** Maximum sample period in PRU cycles */
#define MAX_SAMPLE_PERIOD_CYCLES (MAX_SAMPLE_PERIOD_US * CYCLES_PER_US)

/* ============================================================================
 * AD7606 Timing Constants (Requirement 2.4)
 * ============================================================================ */

/** CONVST pulse width in cycles (250 ns minimum from datasheet = 50 cycles @ 200 MHz) */
#define CONVST_PULSE_CYCLES 50

/** BUSY signal timeout in cycles (5 µs timeout for conversion) */
#define BUSY_TIMEOUT_CYCLES 1000

/** Typical conversion time in cycles (~4 µs) */
#define CONVERSION_TIME_CYCLES 800

/* ============================================================================
 * PRU Pin Assignments (Requirement 2.4)
 * ============================================================================ */

/** CONVST output pin (PRU0 R30.0) */
#define PIN_CONVST 0

/** BUSY input pin (PRU0 R31.0) */
#define PIN_BUSY 0

/** Base pin for 16-bit parallel data (PRU0 R31.1-16) */
#define PIN_DATA_BASE 1

/* ============================================================================
 * Channel Configuration (Requirement 2.3)
 * ============================================================================ */

/** Number of ADC channels */
#define NUM_ADC_CHANNELS 8

/** ADC resolution in bits */
#define ADC_RESOLUTION_BITS 16

/* ============================================================================
 * Block Size Constants (Requirement 2.5)
 * ============================================================================ */

/** Minimum block size (samples per block) - must be power of 2 */
#define MIN_BLOCK_SIZE 64

/** Maximum block size (samples per block) - must be power of 2 */
#define MAX_BLOCK_SIZE 1024

/** Default block size for typical applications */
#define DEFAULT_BLOCK_SIZE 256

/** Default number of ring buffer blocks */
#define DEFAULT_NUM_BLOCKS 4

/* ============================================================================
 * Error Flag Definitions (Requirement 2.4)
 * ============================================================================ */

/** Error: Invalid magic number in shared memory */
#define ERROR_INVALID_MAGIC    (1 << 0)

/** Error: ADC BUSY signal timeout */
#define ERROR_BUSY_TIMEOUT     (1 << 1)

/** Error: Invalid configuration parameters */
#define ERROR_INVALID_CONFIG   (1 << 2)

/** Error: Ring buffer overrun */
#define ERROR_BUFFER_OVERRUN   (1 << 3)

#endif /* PRU_CONFIG_H */
