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
/** CONVST pulse width in cycles (debug: 50us = 10000 cycles) */
#define CONVST_PULSE_CYCLES 10000

/** BUSY signal timeout in cycles (debug: 1ms timeout) */
#define BUSY_TIMEOUT_CYCLES 200000

/** Typical conversion time in cycles (~4 µs) */
#define CONVERSION_TIME_CYCLES 800

/* ============================================================================
 * PRU Pin Assignments (Requirement 2.4)


This mapping avoids the eMMC (P9.42) and HDMI Video/Audio pins.

Signal	BBB Pin	PRU Register	Mode
---------------------------------------
CONVST	P9.27	R30.5	pruout
BUSY	P8.40	R31.7	pruin
Data 0	P8.45	R31.0	pruin
Data 1	P8.46	R31.1	pruin
Data 2	P8.43	R31.2	pruin
Data 3	P8.44	R31.3	pruin
Data 4	P8.41	R31.4	pruin
Data 5	P8.42	R31.5	pruin
Data 6	P8.39	R31.6	pruin
...to Data 15	(See P8 R31 Map)	R31.8-15	pruin
---------------------------------------
 * ============================================================================
*/

/** CONVST output pin (PRU0 R30.5) -> Physical P9.27 */
#define PIN_CONVST 5

/** BUSY input pin (PRU0 R31.15) -> Physical P8.15 */
#define PIN_BUSY 15

/**
 * Base bit for parallel data (1 channel = R31.14)
 * Using P8 cluster: P8.16
 */
#define PIN_DATA_BASE 14

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
