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
// P9.27 is bit 5 of R30 on PRU0
#define PIN_CONVST (1 << 5) // P9.27
#define PIN_RD (1 << 2)     // P9.30
#define PIN_CS (1 << 3)     // P9.28
#define PIN_RESET (1 << 1)  // P9.29

/** PRU0 R31 Input Pins on P9 */
#define PIN_BUSY (1 << 7) // P9.25

/* PRU Special Core Registers (Direct I/O) */
/* These are intrinsic to the PRU and do not have memory addresses */
volatile register uint32_t __R30;
volatile register uint32_t __R31;

// Pin mapping organized by GPIO Bank for optimized assembly
// Bank 0 (GPIO0): P8.13, P8.14, P8.17, P8.19
#define M_GPIO0_DB7 (1 << 23)
#define M_GPIO0_DB6 (1 << 26)
#define M_GPIO0_DB11 (1 << 27)
#define M_GPIO0_DB13 (1 << 22)

// Bank 1 (GPIO1): P9.23, P8.11, P8.12, P8.15, P8.16, P8.26
#define M_GPIO1_DB3 (1 << 17)
#define M_GPIO1_DB5 (1 << 13)
#define M_GPIO1_DB4 (1 << 12)
#define M_GPIO1_DB9 (1 << 15)
#define M_GPIO1_DB8 (1 << 14)
#define M_GPIO1_DB12 (1 << 29)

// Bank 2 (GPIO2): P8.29, P8.30, P8.10, P8.18, P8.27, P8.28
#define M_GPIO2_DB1 (1 << 23)
#define M_GPIO2_DB0 (1 << 25)
#define M_GPIO2_DB2 (1 << 4)
#define M_GPIO2_DB10 (1 << 1)
#define M_GPIO2_DB15 (1 << 22)
#define M_GPIO2_DB14 (1 << 24)

/* GPIO base addresses (AM335x) */
#define GPIO0_BASE 0x44E07000
#define GPIO1_BASE 0x4804C000
#define GPIO2_BASE 0x481AC000

#define GPIO_DATAIN 0x138

/* Volatile register pointers */
#define GPIO0_DATAIN_REG (*(volatile uint32_t *)(GPIO0_BASE + GPIO_DATAIN))
#define GPIO1_DATAIN_REG (*(volatile uint32_t *)(GPIO1_BASE + GPIO_DATAIN))
#define GPIO2_DATAIN_REG (*(volatile uint32_t *)(GPIO2_BASE + GPIO_DATAIN))

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
