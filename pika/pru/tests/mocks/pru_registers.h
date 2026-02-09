/**
 * Mock PRU Registers Header
 * 
 * Provides mock implementations of PRU R30/R31 registers for host testing.
 */

#ifndef MOCK_PRU_REGISTERS_H
#define MOCK_PRU_REGISTERS_H

#include <stdint.h>

/* Mock PRU register storage (defined in pru_registers.c) */
extern volatile uint32_t mock_pru_r30;  /* Output register */
extern volatile uint32_t mock_pru_r31;  /* Input register */

/* Mock register access macros - override PRU definitions */
#define PRU0_R30 mock_pru_r30
#define PRU0_R31 mock_pru_r31

/* Mock control functions */
void mock_pru_registers_reset(void);
void mock_pru_r31_set_bit(uint8_t bit_position);
void mock_pru_r31_clear_bit(uint8_t bit_position);
void mock_pru_r31_set_value(uint32_t value);
uint32_t mock_pru_r30_get_value(void);
int mock_pru_r30_is_bit_set(uint8_t bit_position);

#endif /* MOCK_PRU_REGISTERS_H */
