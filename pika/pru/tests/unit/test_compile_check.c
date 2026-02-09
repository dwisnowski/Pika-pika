/**
 * Compilation Check Test
 * 
 * This test verifies that all foundational component headers can be
 * included together without conflicts and that the basic structure
 * is sound.
 */

#include <stdio.h>
#include <stdint.h>
#include <assert.h>

// Mock PRU-specific inline assembly for compilation check
#define __asm__ __volatile__(...)
#define __volatile__(...)

// Include all foundational headers
#include "../../include/pru_config.h"
#include "../../include/shm_layout.h"

// Note: timing.h and adc_parallel.h contain PRU-specific inline assembly
// that cannot be compiled on host, but they are tested via mocks in other tests

int main(void) {
    printf("=== Compilation Check Test ===\n\n");
    
    // Test 1: Verify configuration constants are defined
    printf("Test 1: Configuration constants defined\n");
    assert(PRU_CLOCK_HZ == 200000000);
    assert(NUM_ADC_CHANNELS == 8);
    assert(MIN_SAMPLE_PERIOD_CYCLES > 0);
    assert(MAX_SAMPLE_PERIOD_CYCLES > MIN_SAMPLE_PERIOD_CYCLES);
    printf("  PASS: All configuration constants defined correctly\n\n");
    
    // Test 2: Verify shared memory structure is defined
    printf("Test 2: Shared memory structure defined\n");
    pru_shared_memory_t shm;
    shm.magic = SHM_MAGIC;
    shm.version = SHM_VERSION;
    assert(shm.magic == 0xDEADBEEF);
    assert(shm.version == 1);
    printf("  PASS: Shared memory structure defined correctly\n\n");
    
    // Test 3: Verify block descriptor structure is defined
    printf("Test 3: Block descriptor structure defined\n");
    block_descriptor_t desc;
    desc.timestamp_cycles = 12345;
    desc.num_samples = 256;
    desc.flags = 0;
    assert(desc.timestamp_cycles == 12345);
    assert(desc.num_samples == 256);
    printf("  PASS: Block descriptor structure defined correctly\n\n");
    
    // Test 4: Verify error flags are defined
    printf("Test 4: Error flags defined\n");
    assert(ERROR_INVALID_MAGIC == (1 << 0));
    assert(ERROR_BUSY_TIMEOUT == (1 << 1));
    assert(ERROR_INVALID_CONFIG == (1 << 2));
    assert(ERROR_BUFFER_OVERRUN == (1 << 3));
    printf("  PASS: All error flags defined correctly\n\n");
    
    printf("=== All Compilation Checks Passed ===\n");
    return 0;
}
