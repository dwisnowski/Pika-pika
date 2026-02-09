# Design Document: PRU Firmware

## Overview

This design specifies the implementation of deterministic PRU firmware for the BeagleBone Black that performs cycle-accurate data acquisition from an AD7606 ADC. The firmware uses a shared memory interface for configuration and data transfer with Linux userspace, implements a ring buffer for continuous streaming, and provides hard real-time sampling with cycle-level timing precision.

The PRU (Programmable Real-time Unit) is a 200 MHz deterministic processor on the AM335x SoC that provides guaranteed timing without OS interference. This firmware leverages the PRU's capabilities to achieve microsecond-level sampling precision required for high-quality data acquisition.

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Linux Userspace                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Application (reads config, writes to shared memory) │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                      │
└───────────────────────┼──────────────────────────────────────┘
                        │ (mmap)
┌───────────────────────▼──────────────────────────────────────┐
│                  Shared Memory Region                        │
│  ┌────────────┬──────────────┬─────────────────────────┐   │
│  │   Header   │ Configuration│    Ring Buffer          │   │
│  │ (magic,ver)│ (period,mask)│  (blocks + descriptors) │   │
│  └────────────┴──────────────┴─────────────────────────┘   │
└───────────────────────▲──────────────────────────────────────┘
                        │ (direct access)
┌───────────────────────┼──────────────────────────────────────┐
│                    PRU Core 0                                │
│  ┌─────────────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │  Main Loop      │  │ Timing System│  │ ADC Interface  │ │
│  │ - Read config   │  │ - Cycle count│  │ - CONVST ctrl  │ │
│  │ - Sample loop   │  │ - Precise wait│ │ - BUSY monitor │ │
│  │ - Ring buffer   │  │ - No division│  │ - Parallel read│ │
│  └────────┬────────┘  └──────────────┘  └───────┬────────┘ │
│           │                                      │          │
└───────────┼──────────────────────────────────────┼──────────┘
            │                                      │
            │ (R30 outputs, R31 inputs)            │
┌───────────▼──────────────────────────────────────▼──────────┐
│                      AD7606 ADC                              │
│  - 8 channels, 16-bit resolution                            │
│  - Parallel interface                                        │
│  - CONVST trigger, BUSY status                              │
└──────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Determinism First**: No dynamic allocation, no floating point, no division in hot loops
2. **Cycle-Accurate Timing**: Use PRU cycle counter for precise sample intervals
3. **Zero-Copy Data Transfer**: Ring buffer in shared memory eliminates copying
4. **Fail-Fast Error Handling**: Detect errors early and signal to userspace
5. **Hardware Validation**: Separate bring-up firmware for testing without dependencies

## Components and Interfaces

### 1. Shared Memory Layout (`shm_layout.h`)

The shared memory interface is the contract between PRU and Linux userspace.

```c
// Memory layout structure
typedef struct {
    // Header (read-only after init)
    uint32_t magic;              // 0xDEADBEEF - verification
    uint32_t version;            // Layout version (1)
    
    // Configuration (written by Linux, read by PRU)
    uint32_t sample_period_cycles;  // Cycles between samples
    uint32_t channel_mask;          // Bit mask of enabled channels (0-7)
    uint32_t block_size;            // Samples per block (power of 2)
    uint32_t num_blocks;            // Number of ring buffer blocks
    
    // Status (written by PRU, read by Linux)
    volatile uint32_t write_block_idx;  // Current block being written
    volatile uint32_t error_flags;      // Error status bits
    volatile uint32_t sample_count;     // Total samples acquired
    
    // Ring buffer follows this header
    // Layout: [block_descriptor_0][data_0][block_descriptor_1][data_1]...
} pru_shared_memory_t;

typedef struct {
    uint32_t timestamp_cycles;   // Cycle count when block started
    uint16_t num_samples;        // Samples in this block
    uint16_t flags;              // Block status flags
} block_descriptor_t;

// Constants
#define SHM_MAGIC 0xDEADBEEF
#define SHM_VERSION 1
#define MAX_CHANNELS 8
#define DEFAULT_BLOCK_SIZE 256
#define DEFAULT_NUM_BLOCKS 4

// Error flags
#define ERROR_INVALID_MAGIC    (1 << 0)
#define ERROR_BUSY_TIMEOUT     (1 << 1)
#define ERROR_INVALID_CONFIG   (1 << 2)
#define ERROR_BUFFER_OVERRUN   (1 << 3)
```

**Memory Layout Calculation:**
- Header: sizeof(pru_shared_memory_t)
- Per block: sizeof(block_descriptor_t) + (block_size * num_enabled_channels * 2 bytes)
- Total: header + (num_blocks * per_block_size)

**Interface Contract:**
- Linux initializes magic, version, configuration fields
- Linux sets write_block_idx = 0 before starting PRU
- PRU verifies magic number on startup
- PRU reads configuration once at startup
- PRU updates write_block_idx atomically after completing each block
- PRU writes error_flags before halting on error

### 2. PRU Configuration (`pru_config.h`)

Hardware and timing constants for the PRU.

```c
// PRU hardware constants
#define PRU_CLOCK_HZ 200000000   // 200 MHz
#define CYCLES_PER_US (PRU_CLOCK_HZ / 1000000)  // 200 cycles/µs

// Timing constraints
#define MIN_SAMPLE_PERIOD_US 10      // 10 µs minimum (100 kHz max rate)
#define MAX_SAMPLE_PERIOD_US 100000  // 100 ms maximum (10 Hz min rate)
#define MIN_SAMPLE_PERIOD_CYCLES (MIN_SAMPLE_PERIOD_US * CYCLES_PER_US)
#define MAX_SAMPLE_PERIOD_CYCLES (MAX_SAMPLE_PERIOD_US * CYCLES_PER_US)

// AD7606 timing (from datasheet)
#define CONVST_PULSE_CYCLES 50       // 250 ns minimum (50 cycles @ 200 MHz)
#define BUSY_TIMEOUT_CYCLES 1000     // 5 µs timeout for conversion
#define CONVERSION_TIME_CYCLES 800   // ~4 µs typical conversion time

// PRU pin assignments (R30 outputs, R31 inputs)
#define PIN_CONVST 0         // R30.0 - Convert start output
#define PIN_BUSY 0           // R31.0 - Busy input
#define PIN_DATA_BASE 1      // R31.1-16 - 16-bit parallel data

// Channel configuration
#define NUM_ADC_CHANNELS 8
#define ADC_RESOLUTION_BITS 16

// Block constraints
#define MIN_BLOCK_SIZE 64
#define MAX_BLOCK_SIZE 1024
```

### 3. Timing System (`timing.c`)

Provides cycle-accurate timing primitives without division or floating point.

```c
// Read current PRU cycle counter
static inline uint32_t get_cycle_count(void) {
    uint32_t count;
    __asm__ __volatile__ (
        "MVI R0.w0, 0x22000\n"    // CTRL register base
        "LBBO %0, R0, 0x0C, 4\n"  // Read CYCLE register
        : "=r"(count)
        :
        : "r0"
    );
    return count;
}

// Wait for specified number of cycles (busy wait)
static inline void wait_cycles(uint32_t cycles) {
    uint32_t start = get_cycle_count();
    uint32_t target = start + cycles;
    
    // Handle counter wrap-around
    if (target < start) {
        // Wait for wrap
        while (get_cycle_count() >= start);
    }
    
    // Wait until target
    while (get_cycle_count() < target);
}

// Calculate elapsed cycles between two timestamps
static inline uint32_t elapsed_cycles(uint32_t start, uint32_t end) {
    if (end >= start) {
        return end - start;
    } else {
        // Handle wrap-around
        return (0xFFFFFFFF - start) + end + 1;
    }
}

// Validate sample period is within acceptable range
static inline int is_valid_sample_period(uint32_t period_cycles) {
    return (period_cycles >= MIN_SAMPLE_PERIOD_CYCLES &&
            period_cycles <= MAX_SAMPLE_PERIOD_CYCLES);
}
```

**Design Notes:**
- Uses inline assembly to access PRU cycle counter (CTRL.CYCLE register)
- Busy-wait implementation for deterministic timing
- Handles 32-bit counter wrap-around correctly
- No division or modulo operations
- All functions are inline for zero overhead

### 4. ADC Parallel Interface (`adc_parallel.c`)

Low-level hardware interface to AD7606 using PRU GPIO registers.

```c
// PRU register access
#define PRU0_R30 (*((volatile uint32_t *)0x00000000))  // Output register
#define PRU0_R31 (*((volatile uint32_t *)0x00000004))  // Input register

// Assert CONVST signal (start conversion)
static inline void adc_assert_convst(void) {
    PRU0_R30 |= (1 << PIN_CONVST);
}

// Deassert CONVST signal
static inline void adc_deassert_convst(void) {
    PRU0_R30 &= ~(1 << PIN_CONVST);
}

// Read BUSY signal state (returns 1 if busy, 0 if ready)
static inline uint32_t adc_read_busy(void) {
    return (PRU0_R31 >> PIN_BUSY) & 0x1;
}

// Read 16-bit parallel data from specified channel
static inline uint16_t adc_read_channel(uint8_t channel) {
    // Set channel select bits (implementation depends on wiring)
    // For AD7606, channel is selected via CS/RD signals
    // This is a simplified version - actual implementation depends on hardware
    
    // Read 16 bits from data pins
    uint32_t data = (PRU0_R31 >> PIN_DATA_BASE) & 0xFFFF;
    return (uint16_t)data;
}

// Trigger conversion and wait for completion
static inline int adc_trigger_and_wait(void) {
    // Assert CONVST pulse
    adc_assert_convst();
    wait_cycles(CONVST_PULSE_CYCLES);
    adc_deassert_convst();
    
    // Wait for BUSY to go high (conversion started)
    uint32_t timeout = BUSY_TIMEOUT_CYCLES;
    while (!adc_read_busy() && timeout > 0) {
        timeout--;
    }
    if (timeout == 0) return -1;  // Timeout error
    
    // Wait for BUSY to go low (conversion complete)
    timeout = BUSY_TIMEOUT_CYCLES;
    while (adc_read_busy() && timeout > 0) {
        timeout--;
    }
    if (timeout == 0) return -1;  // Timeout error
    
    return 0;  // Success
}
```

**Design Notes:**
- Direct register access for zero overhead
- All functions are inline
- CONVST pulse width meets AD7606 datasheet requirements (>25 ns)
- BUSY timeout prevents infinite loops
- Returns error codes for timeout conditions

### 5. Main Sampling Loop (`pru_main.c`)

Core firmware logic that orchestrates sampling and ring buffer management.

```c
// Main entry point
void main(void) {
    // Map shared memory (PRU can access DDR memory)
    volatile pru_shared_memory_t *shm = 
        (volatile pru_shared_memory_t *)SHM_BASE_ADDRESS;
    
    // Verify magic number
    if (shm->magic != SHM_MAGIC) {
        shm->error_flags = ERROR_INVALID_MAGIC;
        __halt();
    }
    
    // Read configuration
    uint32_t sample_period = shm->sample_period_cycles;
    uint32_t channel_mask = shm->channel_mask;
    uint32_t block_size = shm->block_size;
    uint32_t num_blocks = shm->num_blocks;
    
    // Validate configuration
    if (!is_valid_sample_period(sample_period) ||
        channel_mask == 0 ||
        block_size < MIN_BLOCK_SIZE ||
        block_size > MAX_BLOCK_SIZE) {
        shm->error_flags = ERROR_INVALID_CONFIG;
        __halt();
    }
    
    // Count enabled channels
    uint8_t num_channels = 0;
    for (int i = 0; i < NUM_ADC_CHANNELS; i++) {
        if (channel_mask & (1 << i)) num_channels++;
    }
    
    // Calculate block data size
    uint32_t block_data_size = block_size * num_channels * sizeof(uint16_t);
    uint32_t block_total_size = sizeof(block_descriptor_t) + block_data_size;
    
    // Initialize sampling state
    uint32_t current_block = 0;
    uint32_t sample_in_block = 0;
    uint32_t next_sample_time = get_cycle_count() + sample_period;
    
    // Main sampling loop
    while (1) {
        // Wait for next sample time
        uint32_t now = get_cycle_count();
        if (elapsed_cycles(now, next_sample_time) > sample_period) {
            // We're behind schedule - skip to next interval
            next_sample_time = now + sample_period;
        } else {
            // Wait until sample time
            while (get_cycle_count() < next_sample_time);
        }
        
        // Trigger ADC conversion
        if (adc_trigger_and_wait() != 0) {
            shm->error_flags = ERROR_BUSY_TIMEOUT;
            __halt();
        }
        
        // Calculate pointers to current block
        uint8_t *block_base = ((uint8_t *)shm) + 
                              sizeof(pru_shared_memory_t) +
                              (current_block * block_total_size);
        block_descriptor_t *desc = (block_descriptor_t *)block_base;
        uint16_t *data = (uint16_t *)(block_base + sizeof(block_descriptor_t));
        
        // Read enabled channels
        uint32_t data_idx = sample_in_block * num_channels;
        for (uint8_t ch = 0; ch < NUM_ADC_CHANNELS; ch++) {
            if (channel_mask & (1 << ch)) {
                data[data_idx++] = adc_read_channel(ch);
            }
        }
        
        // Update sample count
        sample_in_block++;
        shm->sample_count++;
        
        // Check if block is complete
        if (sample_in_block >= block_size) {
            // Finalize block descriptor
            desc->num_samples = block_size;
            desc->timestamp_cycles = next_sample_time - (block_size * sample_period);
            desc->flags = 0;
            
            // Move to next block (atomic update)
            current_block = (current_block + 1) % num_blocks;
            shm->write_block_idx = current_block;
            sample_in_block = 0;
        }
        
        // Schedule next sample
        next_sample_time += sample_period;
    }
}
```

**Design Notes:**
- Single-pass initialization with fail-fast validation
- Cycle-accurate timing with drift compensation
- Zero-copy data writes directly to shared memory
- Ring buffer wraps automatically using modulo
- Atomic block completion signaling via write_block_idx
- No dynamic allocation or complex control flow in hot loop

### 6. Bring-up Test Firmware (`pru_bringup.c`)

Minimal firmware for hardware validation without shared memory dependencies.

```c
// Simple bring-up test - toggle GPIO at known frequency
void main(void) {
    uint32_t toggle_period = 200000;  // 1 ms @ 200 MHz = 1 kHz square wave
    
    while (1) {
        // Toggle CONVST pin
        PRU0_R30 ^= (1 << PIN_CONVST);
        
        // Wait
        wait_cycles(toggle_period);
    }
}
```

**Purpose:**
- Verify PRU is running and clock is correct
- Verify pin configuration in device tree
- Measure with logic analyzer to confirm 1 kHz output
- No dependencies on shared memory or complex logic

### 7. Device Tree Overlay (`BB-PRU0-AD7606.dts`)

Configures pin multiplexing for PRU0 interface.

```dts
/dts-v1/;
/plugin/;

/ {
    compatible = "ti,beaglebone", "ti,beaglebone-black";
    
    part-number = "BB-PRU0-AD7606";
    version = "00A0";
    
    exclusive-use =
        "P9.31",  // PRU0 R30.0 - CONVST
        "P9.29",  // PRU0 R31.0 - BUSY
        "P9.27",  // PRU0 R31.1 - D0
        "P9.25",  // PRU0 R31.2 - D1
        // ... (continue for all 16 data lines)
        "pru0";
    
    fragment@0 {
        target = <&am33xx_pinmux>;
        __overlay__ {
            pru0_pins: pinmux_pru0_pins {
                pinctrl-single,pins = <
                    0x190 0x05  /* P9.31: pr1_pru0_pru_r30_0, OUTPUT */
                    0x194 0x26  /* P9.29: pr1_pru0_pru_r31_0, INPUT */
                    0x1a4 0x26  /* P9.27: pr1_pru0_pru_r31_1, INPUT */
                    // ... (continue for all pins)
                >;
            };
        };
    };
    
    fragment@1 {
        target = <&pruss>;
        __overlay__ {
            status = "okay";
            pinctrl-names = "default";
            pinctrl-0 = <&pru0_pins>;
        };
    };
    
    fragment@2 {
        target = <&lcdc>;
        __overlay__ {
            status = "disabled";  // Disable HDMI to free pins
        };
    };
};
```

**Pin Mapping:**
- CONVST: P9.31 (PRU0 R30.0) - Output
- BUSY: P9.29 (PRU0 R31.0) - Input
- D0-D15: P9.27, P9.25, ... (PRU0 R31.1-16) - Inputs
- CS/RD: Additional pins as needed for channel selection

## Data Models

### Ring Buffer Structure

The ring buffer enables continuous streaming without data loss:

```
Shared Memory Layout:
┌─────────────────────────────────────────────────────────┐
│ Header (pru_shared_memory_t)                            │
├─────────────────────────────────────────────────────────┤
│ Block 0:                                                │
│   ┌─────────────────────────────────────────────────┐  │
│   │ Descriptor (timestamp, num_samples, flags)      │  │
│   ├─────────────────────────────────────────────────┤  │
│   │ Data [sample0_ch0, sample0_ch1, ...,           │  │
│   │       sample1_ch0, sample1_ch1, ...,           │  │
│   │       ...                                       │  │
│   │       sampleN_ch0, sampleN_ch1, ...]           │  │
│   └─────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│ Block 1: [Descriptor][Data]                            │
├─────────────────────────────────────────────────────────┤
│ Block 2: [Descriptor][Data]                            │
├─────────────────────────────────────────────────────────┤
│ Block 3: [Descriptor][Data]                            │
└─────────────────────────────────────────────────────────┘
```

**Data Organization:**
- Samples are interleaved by channel within each block
- Only enabled channels (per channel_mask) are stored
- Block size is configurable (typically 256 samples)
- Number of blocks is configurable (typically 4)

**Example:** With channels 0, 2, 4 enabled and block_size=256:
```
[s0_ch0][s0_ch2][s0_ch4][s1_ch0][s1_ch2][s1_ch4]...[s255_ch0][s255_ch2][s255_ch4]
```

### Timing Model

The PRU maintains cycle-accurate timing using this algorithm:

```
next_sample_time = current_time + sample_period
loop:
    wait until current_time >= next_sample_time
    trigger_adc()
    read_samples()
    store_samples()
    next_sample_time += sample_period
```

**Key Properties:**
- Timing is based on cycle counter, not wall-clock time
- Each sample is scheduled relative to previous sample
- Drift is bounded by single sample period
- No accumulation of timing errors over long runs

## Error Handling

### Error Detection

The firmware detects these error conditions:

1. **Invalid Magic Number** (ERROR_INVALID_MAGIC)
   - Detected at startup
   - Indicates shared memory not initialized
   - Action: Set error flag and halt

2. **BUSY Timeout** (ERROR_BUSY_TIMEOUT)
   - Detected during ADC conversion
   - Indicates hardware problem or incorrect timing
   - Action: Set error flag and halt

3. **Invalid Configuration** (ERROR_INVALID_CONFIG)
   - Detected at startup
   - Sample period out of range, invalid channel mask, or bad block size
   - Action: Set error flag and halt

4. **Buffer Overrun** (ERROR_BUFFER_OVERRUN)
   - Detected if Linux doesn't consume blocks fast enough
   - Would require read pointer tracking (future enhancement)
   - Action: Set error flag and halt

### Error Reporting

All errors are reported through the error_flags field in shared memory:

```c
// Error flag definitions
#define ERROR_INVALID_MAGIC    (1 << 0)
#define ERROR_BUSY_TIMEOUT     (1 << 1)
#define ERROR_INVALID_CONFIG   (1 << 2)
#define ERROR_BUFFER_OVERRUN   (1 << 3)
```

Linux userspace can poll error_flags to detect PRU failures.

### Recovery

The PRU firmware uses fail-fast error handling:
- On any error, set appropriate error flag
- Halt execution using __halt()
- Linux must reset and restart PRU to recover

This approach is appropriate for embedded systems where:
- Errors indicate serious hardware or configuration problems
- Continuing with corrupted state is worse than stopping
- Userspace has full control over recovery strategy



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Cycle-accurate wait timing

*For any* positive number of cycles N, calling wait_cycles(N) should result in elapsed time of N ± 1 cycles (allowing for measurement overhead).

**Validates: Requirements 3.2**

### Property 2: Block completion signaling

*For any* completed ring buffer block, the write_block_idx field in shared memory should be atomically updated to point to the next block.

**Validates: Requirements 1.7, 5.7**

### Property 3: Magic number validation

*For any* shared memory initialization, if the magic number does not equal SHM_MAGIC (0xDEADBEEF), the PRU should set ERROR_INVALID_MAGIC flag and halt without starting sampling.

**Validates: Requirements 5.2, 6.1**

### Property 4: Sampling sequence correctness

*For any* sample acquisition, the PRU should: (1) assert CONVST, (2) wait for BUSY to deassert, (3) read only channels enabled in channel_mask, and (4) write samples to the current ring buffer block in the correct order.

**Validates: Requirements 5.3, 5.4, 5.5, 5.6**

### Property 5: Ring buffer wrapping

*For any* ring buffer with N blocks, when the PRU completes block (N-1), the next block written should be block 0, and this wrapping should continue indefinitely without data corruption.

**Validates: Requirements 5.8, 5.9**

### Property 6: Sample timing accuracy

*For any* configured sample_period_cycles value, the time interval between consecutive samples should be sample_period_cycles ± 1 cycle, measured over any sequence of samples.

**Validates: Requirements 5.10, 10.2**

### Property 7: Error handling completeness

*For any* error condition (invalid magic, BUSY timeout, invalid configuration), the PRU should set the appropriate error flag in shared memory before halting, ensuring userspace can determine the failure cause.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4**

### Property 8: Channel mask filtering

*For any* channel_mask configuration, the number of samples written per acquisition should equal the number of bits set in channel_mask, and only those channels should be read from the ADC.

**Validates: Requirements 5.5**

## Testing Strategy

### Dual Testing Approach

This firmware requires both unit testing and property-based testing for comprehensive validation:

**Unit Tests** focus on:
- Specific examples of shared memory layout (magic number at offset 0, version field present)
- Configuration constant definitions (PRU_CLOCK_HZ = 200000000, NUM_ADC_CHANNELS = 8)
- API existence (functions for CONVST control, BUSY reading, cycle counter access)
- Build system targets (build, bringup, load, clean)
- Device tree overlay structure (HDMI disabled, pin configurations)
- Bringup firmware behavior (GPIO toggle at known frequency)
- Edge cases like counter wrap-around in timing functions

**Property-Based Tests** focus on:
- Timing accuracy across random cycle counts
- Block completion signaling across random block sequences
- Magic number validation with random invalid values
- Sampling sequence correctness with random channel masks
- Ring buffer wrapping with random block counts
- Sample timing accuracy over random sample periods
- Error handling with random error conditions
- Channel mask filtering with random mask patterns

### Property-Based Testing Configuration

We will use **C property-based testing with theft library** (https://github.com/silentbicycle/theft) for PRU firmware testing. Theft provides QuickCheck-style property testing for C code.

**Configuration:**
- Minimum 100 iterations per property test
- Each test tagged with: `/* Feature: pru-firmware, Property N: [property text] */`
- Tests run on host system (x86) with mocked PRU registers
- Mock layer simulates PRU R30/R31 registers and cycle counter

**Test Organization:**
```
tests/
├── unit/
│   ├── test_shm_layout.c       # Shared memory structure tests
│   ├── test_timing.c           # Timing function unit tests
│   ├── test_adc_interface.c    # ADC interface unit tests
│   └── test_config.c           # Configuration constant tests
├── property/
│   ├── test_timing_props.c     # Property 1: Cycle-accurate timing
│   ├── test_block_props.c      # Property 2: Block completion
│   ├── test_validation_props.c # Property 3: Magic number validation
│   ├── test_sampling_props.c   # Property 4: Sampling sequence
│   ├── test_ringbuf_props.c    # Property 5: Ring buffer wrapping
│   ├── test_accuracy_props.c   # Property 6: Sample timing accuracy
│   ├── test_error_props.c      # Property 7: Error handling
│   └── test_channel_props.c    # Property 8: Channel mask filtering
└── mocks/
    ├── pru_registers.c         # Mock PRU R30/R31 registers
    └── cycle_counter.c         # Mock cycle counter
```

**Example Property Test Structure:**
```c
/* Feature: pru-firmware, Property 1: Cycle-accurate wait timing */
static enum theft_trial_res prop_wait_cycles_accurate(
    struct theft *t, void *arg1) {
    uint32_t cycles = *(uint32_t *)arg1;
    
    // Test that wait_cycles(N) takes N ± 1 cycles
    uint32_t start = get_cycle_count();
    wait_cycles(cycles);
    uint32_t end = get_cycle_count();
    uint32_t elapsed = elapsed_cycles(start, end);
    
    // Allow ±1 cycle tolerance for measurement overhead
    if (elapsed >= cycles - 1 && elapsed <= cycles + 1) {
        return THEFT_TRIAL_PASS;
    }
    return THEFT_TRIAL_FAIL;
}
```

### Hardware Validation

In addition to software tests, hardware validation is critical:

1. **Logic Analyzer Verification:**
   - Measure CONVST pulse width (should be ≥250 ns)
   - Measure sample intervals (should match configured period ±5 ns)
   - Verify BUSY signal timing during conversions
   - Confirm data line transitions during reads

2. **Bringup Test:**
   - Load bringup firmware first
   - Verify 1 kHz square wave on CONVST pin
   - Confirms PRU clock, pin configuration, and basic operation

3. **Integration Test:**
   - Load main firmware with known configuration
   - Verify data in shared memory matches expected pattern
   - Use test signal generator on ADC inputs
   - Confirm sample rate and data accuracy

### Test Execution

**Host-based tests** (unit + property):
```bash
make test          # Run all tests
make test-unit     # Run unit tests only
make test-property # Run property tests only
```

**Hardware tests:**
```bash
make bringup       # Build and load bringup firmware
make load          # Load main firmware
make test-hw       # Run hardware validation scripts
```

### Coverage Goals

- **Line coverage:** >90% for all C source files
- **Branch coverage:** >85% for control flow
- **Property coverage:** 100% (all 8 properties tested)
- **Hardware validation:** All timing requirements verified with logic analyzer

