# PRU Shared Memory Map

## Overview

This document describes the shared memory layout used for communication between the PRU firmware and Linux userspace applications. The shared memory interface provides a zero-copy mechanism for configuration, status reporting, and high-speed data transfer from the AD7606 ADC.

**Key Characteristics:**
- Zero-copy data transfer (PRU writes directly to shared memory)
- Ring buffer design for continuous streaming
- Atomic synchronization via block index updates
- Configuration and status in single memory region
- Typical size: ~16 KB (configurable based on block size and count)

## Memory Regions

### AM335x Memory Architecture

The BeagleBone Black AM335x SoC provides several memory regions accessible by the PRU:

**PRU Local Memory:**
- **PRU0 Data RAM**: 8 KB at 0x00000000 (PRU0 local view)
- **PRU1 Data RAM**: 8 KB at 0x00002000 (PRU0 local view)
- **Shared RAM**: 12 KB at 0x00010000 (shared between PRU0 and PRU1)

**External Memory:**
- **DDR RAM**: Accessible via L3 interconnect (used for large data buffers)
- **PRU remoteproc**: Linux kernel manages PRU memory mapping

### Shared Memory Region

For this implementation, we use **PRU Shared RAM** at address `0x00010000` (PRU local view):

**Base Address:** `0x00010000` (PRU view) / `0x4A310000` (ARM view)  
**Size:** 12 KB total, ~6-16 KB used depending on configuration  
**Access:** Both PRU and Linux can read/write (via `/dev/mem` mmap)

**Why Shared RAM:**
- Fast access from both PRU and ARM
- No cache coherency issues (uncached region)
- Sufficient size for ring buffer with multiple blocks
- Direct addressing from PRU (no MMU translation)

## Data Structures

### Header Structure (`pru_shared_memory_t`)

Located at the base of shared memory (offset 0x00000000):

```c
typedef struct {
    /* Header - read-only after initialization */
    uint32_t magic;              // Offset 0x00: 0xDEADBEEF
    uint32_t version;            // Offset 0x04: 1
    
    /* Configuration - written by Linux, read by PRU */
    uint32_t sample_period_cycles;  // Offset 0x08: Cycles between samples
    uint32_t channel_mask;          // Offset 0x0C: Enabled channels (bits 0-7)
    uint32_t block_size;            // Offset 0x10: Samples per block
    uint32_t num_blocks;            // Offset 0x14: Number of ring buffer blocks
    
    /* Status - written by PRU, read by Linux */
    volatile uint32_t write_block_idx;  // Offset 0x18: Current block index
    volatile uint32_t error_flags;      // Offset 0x1C: Error status bits
    volatile uint32_t sample_count;     // Offset 0x20: Total samples acquired
    
    /* Ring buffer follows at offset 0x24 */
} pru_shared_memory_t;
```

**Size:** 36 bytes (0x24)

**Field Descriptions:**

| Offset | Field | Type | Access | Description |
|--------|-------|------|--------|-------------|
| 0x00 | magic | uint32_t | R/W | Magic number (0xDEADBEEF) for validation |
| 0x04 | version | uint32_t | R/W | Layout version (1) |
| 0x08 | sample_period_cycles | uint32_t | R/W | PRU cycles between samples (200 MHz clock) |
| 0x0C | channel_mask | uint32_t | R/W | Bit mask of enabled channels (bit 0 = ch0, etc.) |
| 0x10 | block_size | uint32_t | R/W | Number of samples per ring buffer block |
| 0x14 | num_blocks | uint32_t | R/W | Number of blocks in ring buffer |
| 0x18 | write_block_idx | uint32_t | R (volatile) | Current block being written by PRU |
| 0x1C | error_flags | uint32_t | R (volatile) | Error status bits (see Error Flags) |
| 0x20 | sample_count | uint32_t | R (volatile) | Total samples acquired since start |

### Block Descriptor Structure (`block_descriptor_t`)

Each ring buffer block begins with a descriptor:

```c
typedef struct {
    uint32_t timestamp_cycles;   // Cycle count when block started
    uint16_t num_samples;        // Number of samples in this block
    uint16_t flags;              // Block status flags (reserved)
} block_descriptor_t;
```

**Size:** 8 bytes

**Field Descriptions:**

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0x00 | timestamp_cycles | uint32_t | PRU cycle counter value at first sample in block |
| 0x04 | num_samples | uint16_t | Number of samples in this block (typically = block_size) |
| 0x06 | flags | uint16_t | Block status flags (reserved for future use) |

### Ring Buffer Layout

The ring buffer consists of multiple blocks, each containing a descriptor followed by sample data:

```
Memory Layout:
┌─────────────────────────────────────────────────────────────┐
│ Offset 0x00000000: pru_shared_memory_t (36 bytes)          │
├─────────────────────────────────────────────────────────────┤
│ Offset 0x00000024: Block 0                                  │
│   ├─ block_descriptor_t (8 bytes)                           │
│   └─ Sample data (block_size × num_channels × 2 bytes)      │
├─────────────────────────────────────────────────────────────┤
│ Offset 0x00000024 + block_total_size: Block 1               │
│   ├─ block_descriptor_t (8 bytes)                           │
│   └─ Sample data (block_size × num_channels × 2 bytes)      │
├─────────────────────────────────────────────────────────────┤
│ ... (additional blocks)                                      │
├─────────────────────────────────────────────────────────────┤
│ Offset 0x00000024 + (N-1) × block_total_size: Block N-1     │
│   ├─ block_descriptor_t (8 bytes)                           │
│   └─ Sample data (block_size × num_channels × 2 bytes)      │
└─────────────────────────────────────────────────────────────┘
```

**Block Size Calculation:**
```c
num_enabled_channels = popcount(channel_mask);
block_data_size = block_size × num_enabled_channels × sizeof(uint16_t);
block_total_size = sizeof(block_descriptor_t) + block_data_size;
```

**Example:** With default configuration (256 samples, 8 channels, 4 blocks):
```
Header: 36 bytes
Block 0: 8 + (256 × 8 × 2) = 4104 bytes
Block 1: 4104 bytes
Block 2: 4104 bytes
Block 3: 4104 bytes
Total: 36 + (4 × 4104) = 16,452 bytes (~16 KB)
```

### Sample Data Organization

Within each block, samples are interleaved by channel:

```
[sample0_ch0][sample0_ch1]...[sample0_chN]
[sample1_ch0][sample1_ch1]...[sample1_chN]
...
[sampleM_ch0][sampleM_ch1]...[sampleM_chN]
```

**Example:** With channels 0, 2, 4 enabled (channel_mask = 0x15):
```
Offset 0: sample0_ch0 (16-bit)
Offset 2: sample0_ch2 (16-bit)
Offset 4: sample0_ch4 (16-bit)
Offset 6: sample1_ch0 (16-bit)
Offset 8: sample1_ch2 (16-bit)
...
```

**Key Points:**
- Only enabled channels are stored (sparse storage)
- Samples are 16-bit unsigned integers (AD7606 native format)
- Little-endian byte order (ARM/PRU native)
- No padding between samples

## Configuration Constants

### Magic Number and Version

**Magic Number:** `0xDEADBEEF`
- Used to verify shared memory is properly initialized
- PRU checks this value on startup
- If mismatch, PRU sets ERROR_INVALID_MAGIC and halts

**Version:** `1`
- Allows future layout changes with backward compatibility
- PRU can check version and adapt behavior

### Error Flags

Error flags are bit fields in the `error_flags` field:

| Bit | Flag | Value | Description |
|-----|------|-------|-------------|
| 0 | ERROR_INVALID_MAGIC | 0x01 | Magic number mismatch at startup |
| 1 | ERROR_BUSY_TIMEOUT | 0x02 | ADC BUSY signal timeout during conversion |
| 2 | ERROR_INVALID_CONFIG | 0x04 | Invalid configuration parameters |
| 3 | ERROR_BUFFER_OVERRUN | 0x08 | Ring buffer overrun (future) |
| 4-31 | Reserved | - | Reserved for future error types |

**Error Handling:**
- PRU sets appropriate bit(s) before halting
- Linux can read error_flags to determine failure cause
- Multiple errors can be set simultaneously (bitwise OR)

### Default Configuration

**Recommended defaults:**
```c
sample_period_cycles = 20000;    // 100 µs @ 200 MHz = 10 kHz
channel_mask = 0xFF;             // All 8 channels enabled
block_size = 256;                // 256 samples per block
num_blocks = 4;                  // 4 blocks in ring buffer
```

**Constraints:**
- `sample_period_cycles`: 2000 to 20,000,000 (10 µs to 100 ms)
- `channel_mask`: At least one bit set (0x01 to 0xFF)
- `block_size`: 64 to 1024 (power of 2 recommended)
- `num_blocks`: 2 to 16 (must fit in shared RAM)

## Memory Access Patterns

### Initialization Sequence (Linux)

1. **Open /dev/mem:**
   ```c
   int fd = open("/dev/mem", O_RDWR | O_SYNC);
   ```

2. **Map shared memory:**
   ```c
   void *mem = mmap(NULL, 0x3000, PROT_READ | PROT_WRITE,
                    MAP_SHARED, fd, 0x4A310000);
   pru_shared_memory_t *shm = (pru_shared_memory_t *)mem;
   ```

3. **Initialize header:**
   ```c
   shm->magic = SHM_MAGIC;
   shm->version = SHM_VERSION;
   ```

4. **Configure sampling:**
   ```c
   shm->sample_period_cycles = 20000;  // 10 kHz
   shm->channel_mask = 0xFF;           // All channels
   shm->block_size = 256;
   shm->num_blocks = 4;
   ```

5. **Initialize status:**
   ```c
   shm->write_block_idx = 0;
   shm->error_flags = 0;
   shm->sample_count = 0;
   ```

6. **Load PRU firmware:**
   ```bash
   echo 'start' > /sys/class/remoteproc/remoteproc1/state
   ```

### PRU Write Operations

**Startup:**
1. Read and verify magic number
2. Read configuration fields
3. Validate configuration
4. Initialize block pointers

**Sampling Loop:**
1. Wait for next sample time (cycle-accurate)
2. Trigger ADC conversion
3. Wait for BUSY signal to deassert
4. Read enabled channels from ADC
5. Write samples to current block in shared memory
6. Increment sample counter
7. If block complete:
   - Update block descriptor (timestamp, num_samples)
   - Atomically update write_block_idx
   - Move to next block (wrap if needed)

**Memory Write Pattern:**
```c
// Calculate block base address
uint8_t *block_base = ((uint8_t *)shm) + 
                      sizeof(pru_shared_memory_t) +
                      (current_block * block_total_size);

// Get descriptor and data pointers
block_descriptor_t *desc = (block_descriptor_t *)block_base;
uint16_t *data = (uint16_t *)(block_base + sizeof(block_descriptor_t));

// Write samples (interleaved by channel)
uint32_t data_idx = sample_in_block * num_enabled_channels;
for (uint8_t ch = 0; ch < 8; ch++) {
    if (channel_mask & (1 << ch)) {
        data[data_idx++] = adc_read_channel(ch);
    }
}
```

### Linux Read Operations

**Polling for New Blocks:**
```c
uint32_t last_block = 0;

while (running) {
    uint32_t current_block = shm->write_block_idx;
    
    if (current_block != last_block) {
        // New block available
        process_block(last_block);
        last_block = (last_block + 1) % shm->num_blocks;
    }
    
    usleep(1000);  // Poll every 1 ms
}
```

**Reading Block Data:**
```c
void process_block(uint32_t block_idx) {
    // Calculate block address
    uint8_t *block_base = ((uint8_t *)shm) + 
                          sizeof(pru_shared_memory_t) +
                          (block_idx * block_total_size);
    
    // Read descriptor
    block_descriptor_t *desc = (block_descriptor_t *)block_base;
    uint32_t timestamp = desc->timestamp_cycles;
    uint16_t num_samples = desc->num_samples;
    
    // Read sample data
    uint16_t *data = (uint16_t *)(block_base + sizeof(block_descriptor_t));
    
    // Process samples
    for (uint16_t i = 0; i < num_samples; i++) {
        for (uint8_t ch = 0; ch < num_enabled_channels; ch++) {
            uint16_t sample = data[i * num_enabled_channels + ch];
            // Process sample...
        }
    }
}
```

## Synchronization Mechanisms

### Producer-Consumer Model

**Producer (PRU):**
- Writes samples to current block
- Updates write_block_idx when block complete
- Never reads write_block_idx (write-only)

**Consumer (Linux):**
- Reads write_block_idx to detect new blocks
- Processes completed blocks
- Never writes to sample data (read-only)

### Atomic Operations

**Block Completion:**
```c
// PRU atomically updates block index
shm->write_block_idx = next_block;
```

This single 32-bit write is atomic on ARM architecture, ensuring Linux never sees partial updates.

### Lock-Free Design

The ring buffer uses a lock-free design:
- No mutexes or semaphores required
- PRU always writes to current block
- Linux reads from completed blocks
- Sufficient blocks prevent overrun (typically 4 blocks)

**Overrun Prevention:**
- Linux must consume blocks faster than PRU produces them
- With 4 blocks and 256 samples/block at 10 kHz:
  - Block completion time: 25.6 ms
  - Linux has ~75 ms to process each block
  - Typical processing: <1 ms (plenty of margin)

## Performance Considerations

### Memory Access Timing

**PRU Write Performance:**
- Shared RAM access: 1 cycle (5 ns @ 200 MHz)
- Sample write: 2 cycles (load address, store data)
- Block completion: <10 cycles (update descriptor and index)

**Linux Read Performance:**
- Shared RAM access: ~100 ns (via L3 interconnect)
- Block read: ~1 ms for 256 samples × 8 channels
- Negligible compared to sample period (100 µs)

### Cache Coherency

**No Cache Issues:**
- Shared RAM is uncached region
- No cache flush/invalidate required
- Guaranteed memory consistency
- Volatile qualifiers ensure compiler doesn't optimize away reads

### Memory Bandwidth

**PRU Write Bandwidth:**
- 10 kHz × 8 channels × 2 bytes = 160 KB/s (typical)
- 100 kHz × 8 channels × 2 bytes = 1.6 MB/s (maximum)
- Well within shared RAM bandwidth (~400 MB/s)

**Linux Read Bandwidth:**
- Same as write bandwidth (zero-copy)
- No additional memory traffic

## Address Calculation Reference

### Block Address Calculation

```c
// Calculate total size of one block
uint32_t num_enabled_channels = popcount(channel_mask);
uint32_t block_data_size = block_size * num_enabled_channels * sizeof(uint16_t);
uint32_t block_total_size = sizeof(block_descriptor_t) + block_data_size;

// Calculate address of block N
uint8_t *block_N_addr = ((uint8_t *)shm) + 
                        sizeof(pru_shared_memory_t) +
                        (N * block_total_size);

// Get descriptor and data pointers
block_descriptor_t *desc = (block_descriptor_t *)block_N_addr;
uint16_t *data = (uint16_t *)(block_N_addr + sizeof(block_descriptor_t));
```

### Sample Address Calculation

```c
// Calculate address of sample S, channel C in block N
uint32_t sample_offset = (S * num_enabled_channels + C) * sizeof(uint16_t);
uint16_t *sample_addr = data + (S * num_enabled_channels + C);
```

## Memory Map Summary

**Complete memory layout with default configuration:**

```
Address Range          | Size    | Description
-----------------------|---------|----------------------------------
0x00000000 - 0x00000023| 36 B    | Header (pru_shared_memory_t)
0x00000024 - 0x00001027| 4104 B  | Block 0 (descriptor + 256×8×2)
0x00001028 - 0x0000202B| 4104 B  | Block 1 (descriptor + 256×8×2)
0x0000202C - 0x0000302F| 4104 B  | Block 2 (descriptor + 256×8×2)
0x00003030 - 0x00004033| 4104 B  | Block 3 (descriptor + 256×8×2)
-----------------------|---------|----------------------------------
Total:                 | 16452 B | ~16 KB
```

## References

- **Header Definition**: `pika/pru/include/shm_layout.h`
- **PRU Implementation**: `pika/pru/src/pru_main.c`
- **Design Document**: `.kiro/specs/pru-firmware/design.md`
- **Architecture Overview**: `docs/architecture.md`
- **AM335x TRM**: Section 4.4 (PRU-ICSS Memory Map)
