/**
 * Timing System Implementation for PRU Firmware
 * 
 * This file provides cycle-accurate timing primitives for deterministic
 * data acquisition on the BeagleBone Black PRU.
 * 
 * All timing functions are implemented as static inline functions in
 * timing.h for zero overhead. This source file exists for documentation
 * and potential future non-inline implementations.
 * 
 * Key Features:
 * - Cycle-accurate timing using PRU CTRL.CYCLE register
 * - Busy-wait implementation for deterministic delays
 * - Correct handling of 32-bit counter wrap-around
 * - No floating-point arithmetic (Requirement 3.4)
 * - No division operations in hot loops (Requirement 3.5)
 * 
 * Requirements: 3.1, 3.2, 3.3
 * 
 * Design Notes:
 * -------------
 * The PRU cycle counter is a free-running 32-bit counter that increments
 * at the PRU clock rate (200 MHz). It wraps around to 0 after reaching
 * 0xFFFFFFFF, which occurs approximately every 21.5 seconds.
 * 
 * All timing functions handle wrap-around correctly by:
 * 1. Detecting when target < start (indicates wrap will occur)
 * 2. Waiting for wrap to complete before checking target
 * 3. Using unsigned arithmetic which naturally handles modulo 2^32
 * 
 * Performance Characteristics:
 * ---------------------------
 * - get_cycle_count(): ~5 cycles (inline assembly)
 * - wait_cycles(N): N + ~10 cycles overhead
 * - elapsed_cycles(): ~3 cycles (simple arithmetic)
 * - is_valid_sample_period(): ~5 cycles (two comparisons)
 * 
 * All functions are marked static inline, so they have zero function
 * call overhead when used in the main sampling loop.
 */

#include "timing.h"

/* All implementations are in timing.h as static inline functions */
