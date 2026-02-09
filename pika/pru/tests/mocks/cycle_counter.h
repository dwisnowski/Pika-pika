/**
 * Mock PRU Cycle Counter Header
 * 
 * Provides mock implementation of PRU cycle counter for host testing.
 */

#ifndef MOCK_CYCLE_COUNTER_H
#define MOCK_CYCLE_COUNTER_H

#include <stdint.h>

/* Mock cycle counter control functions */
void mock_cycle_counter_reset(void);
void mock_cycle_counter_set(uint32_t value);
uint32_t mock_cycle_counter_get(void);
void mock_cycle_counter_advance(uint32_t cycles);
void mock_cycle_counter_enable_auto_advance(uint32_t increment);
void mock_cycle_counter_disable_auto_advance(void);

/* Mock implementation of get_cycle_count() */
uint32_t get_cycle_count(void);

#endif /* MOCK_CYCLE_COUNTER_H */
