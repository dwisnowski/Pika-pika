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
 * ============================================================================
 */

/** PRU clock frequency in Hz (200 MHz) */
#define PRU_CLOCK_HZ 200000000

/** Number of PRU cycles per microsecond */
#define CYCLES_PER_US (PRU_CLOCK_HZ / 1000000) // 200 cycles/µs

/* ============================================================================
 * Timing Constraints (Requirement 2.2)
 * ============================================================================
 */

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
 * ============================================================================
 */

/** CONVST pulse width in cycles (250 ns minimum from datasheet = 50 cycles @
 * 200 MHz) */
/** CONVST pulse width in cycles (250 ns minimum from datasheet = 50 cycles @
 * 200 MHz). set to 200 (1us) for robust operation. */
#define CONVST_PULSE_CYCLES 200

/** BUSY signal timeout in cycles (unused with fixed delay, but kept for
 * reference) */
#define BUSY_TIMEOUT_CYCLES 200000

/** Typical conversion time in cycles (~4 µs) */
#define CONVERSION_TIME_CYCLES 800

/* ============================================================================
 * PRU Pin Assignments (Requirement 2.4 - 16-bit Parallel)
 * ============================================================================
 */

/** PRU0 R30 Output Pins on P9 */
#define PIN_CONVST 5 // P9.27
#define PIN_RD 2     // P9.30
#define PIN_CS 3     // P9.28
#define PIN_RESET 1  // P9.29

/** PRU0 R31 Input Pins on P9 */
#define PIN_BUSY 7 // P9.25

/**
 * GPIO Bank Definitions for 16-bit Parallel Data (P8 Header)
 *
 * DB1 / DB0   : P8.7 / P8.8   -> GPIO2_2 / GPIO2_3
 * DB3 / DB2   : P8.9 / P8.10  -> GPIO2_5 / GPIO2_4
 * DB5 / DB4   : P8.11 / P8.12 -> GPIO1_13 / GPIO1_12
 * DB7 / DB6   : P8.13 / P8.14 -> GPIO0_23 / GPIO0_26
 * DB9 / DB8   : P8.15 / P8.16 -> GPIO1_15 / GPIO1_14
 * DB11 / DB10 : P8.17 / P8.18 -> GPIO0_27 / GPIO2_1
 * DB13 / DB12 : P8.19 / P8.26 -> GPIO0_22 / GPIO1_29
 * DB15 / DB14 : P8.27 / P8.28 -> GPIO2_22 / GPIO2_24
 */

#define GPIO0_BASE 0x44E07000
#define GPIO1_BASE 0x4804C000
#define GPIO2_BASE 0x481AC000
#define GPIO_DATAIN 0x138

// Bank 0 Mask: DB7(23), DB6(26), DB11(27), DB13(22)
#define BANK0_MASK ((1 << 23) | (1 << 26) | (1 << 27) | (1 << 22))
// Bank 1 Mask: DB5(13), DB4(12), DB9(15), DB8(14), DB12(29)
#define BANK1_MASK ((1 << 13) | (1 << 12) | (1 << 15) | (1 << 14) | (1 << 29))
// Bank 2 Mask: DB1(2), DB0(3), DB3(5), DB2(4), DB10(1), DB15(22), DB14(24)
#define BANK2_MASK                                                             \
  ((1 << 2) | (1 << 3) | (1 << 5) | (1 << 4) | (1 << 1) | (1 << 22) | (1 << 24))

/* ============================================================================
 * Channel Configuration (Requirement 2.3)
 * ============================================================================
 */

/** Number of ADC channels */
#define NUM_ADC_CHANNELS 8

/** ADC resolution in bits */
#define ADC_RESOLUTION_BITS 16

/* ============================================================================
 * Block Size Constants (Requirement 2.5)
 * ============================================================================
 */

/** Minimum block size (samples per block) - must be power of 2 */
#define MIN_BLOCK_SIZE 64

/** Maximum block size (samples per block) - must be power of 2 */
#define MAX_BLOCK_SIZE 1024

/** Default block size for typical applications */
#define DEFAULT_BLOCK_SIZE 256

/** Default number of ring buffer blocks */
#define DEFAULT_NUM_BLOCKS 4

#endif /* PRU_CONFIG_H */
