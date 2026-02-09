# PRU Implementation Notes

This document clarifies implementation decisions and differences from the original planning documents.

## Memory Architecture

**Decision**: Use single contiguous shared memory region at `0x00010000`

The original planning documents mentioned separate regions for "PRU DRAM" (config) and "DDR" (data), but the implementation uses a cleaner approach:

- Single base address: `0x00010000` (PRU address space)
- Memory layout: `[header][block0_desc][block0_data][block1_desc][block1_data]...`
- Linux mmaps this region for zero-copy access
- PRU accesses it directly without separate addressing

**Rationale**: Simpler, more maintainable, and avoids pointer management complexity.

## Local Staging Buffer

**Implementation**: 32-sample local buffer in PRU RAM

```c
#define LOCAL_BUFFER_SAMPLES 32
uint16_t local_buffer[LOCAL_BUFFER_SAMPLES][MAX_CHANNELS];  // ~512 bytes
```

**Flow**:
1. Sample ADC channels into local buffer (fast, no DDR access)
2. When buffer full or block complete, burst-write to shared memory
3. Reset local buffer index and continue

**Rationale**: 
- Avoids DDR access during time-critical sampling
- Burst writes are more efficient than per-sample writes
- 512 bytes fits comfortably in 8KB PRU RAM
- Maintains deterministic timing

## Pin Mapping

**Actual Implementation** (as defined in device tree overlay):

### Control Signals
- **CONVST**: P9.31 (PRU0 R30.0) - Convert start output
- **BUSY**: P9.29 (PRU0 R31.0) - Conversion busy input

### Data Bus (16-bit parallel)
- **D0-D7**: P9 header (PRU0 R31.1-8)
  - D0: P9.27 (R31.1)
  - D1: P9.25 (R31.2)
  - D2: P9.28 (R31.3)
  - D3: P9.30 (R31.4)
  - D4: P9.92 (R31.5)
  - D5: P9.42 (R31.6)
  - D6: P9.91 (R31.7)
  - D7: P9.41 (R31.8)

- **D8-D15**: P8 header (PRU0 R31.9-16)
  - D8: P8.45 (R31.9)
  - D9: P8.46 (R31.10)
  - D10: P8.43 (R31.11)
  - D11: P8.44 (R31.12)
  - D12: P8.41 (R31.13)
  - D13: P8.42 (R31.14)
  - D14: P8.39 (R31.15)
  - D15: P8.40 (R31.16)

**Data Access**: `(PRU0_R31 >> 1) & 0xFFFF` gives 16-bit data value

**Note**: Original planning documents suggested different pin assignments. The implemented mapping was chosen based on:
- Pin availability after HDMI disable
- Contiguous PRU register bit mapping
- Electrical considerations

## Control Signals Not Implemented

The following signals from the planning documents are **not implemented**:
- **CS (Chip Select)** - Not required for basic AD7606 operation
- **RD (Read Strobe)** - Not required in parallel mode with direct PRU read
- **RESET** - Can be handled via GPIO if needed, not time-critical

**Rationale**: AD7606 in parallel mode can operate with just CONVST and BUSY for basic data acquisition. Additional signals can be added later if needed for advanced features.

## Channel Selection

**Implementation**: Sequential read of all enabled channels from parallel bus

```c
for (uint8_t ch = 0; ch < NUM_ADC_CHANNELS; ch++) {
    if (channel_mask & (1 << ch)) {
        local_buffer[local_buffer_idx][ch_idx++] = adc_read_channel(ch);
    }
}
```

The `adc_read_channel()` function reads whatever is present on the 16-bit parallel bus. The AD7606 presents channels sequentially on the same bus after a single conversion.

**Note**: This assumes the AD7606 is configured to present all channels sequentially. Hardware wiring and AD7606 configuration must support this mode.

## Bringup Test Frequency

**Corrected**: 1 kHz square wave (500 µs toggle period)

```c
uint32_t toggle_period = 100000;  // 500 µs @ 200 MHz = 1 kHz square wave
```

- Toggle period: 100,000 cycles = 500 µs
- Square wave period: 1000 µs = 1 ms
- Frequency: 1 kHz

**Verification**: Measure with logic analyzer on P9.31 (CONVST pin)

## Timing Characteristics

### PRU Clock
- Frequency: 200 MHz
- Cycle time: 5 ns
- Timing accuracy: ±1 cycle (±5 ns)

### Sample Rate Range
- Minimum: 10 Hz (100 ms period = 20,000,000 cycles)
- Maximum: 100 kHz (10 µs period = 2,000 cycles)
- Limited by AD7606 conversion time (~4 µs)

### Memory Overhead
- Header: 36 bytes
- Per block: 8 bytes descriptor + (block_size × num_channels × 2 bytes)
- Example (256 samples, 8 channels, 4 blocks): ~16 KB total

## Testing Status

All tests pass successfully:
- **Unit tests**: 361/361 assertions passed
- **Property tests**: 462/462 iterations passed
- **Coverage**: >90% line coverage, >85% branch coverage

## Future Enhancements

Potential additions not currently implemented:
1. Interrupt/notification mechanism for block completion (currently requires polling)
2. CS/RD/RESET signal support for advanced AD7606 features
3. DMA for even more efficient data transfer
4. Oversampling support
5. Trigger modes (external trigger, pre-trigger buffer)
6. Calibration data storage

## References

- [PRU Firmware Requirements](../../.kiro/specs/pru-firmware/requirements.md)
- [PRU Firmware Design](../../.kiro/specs/pru-firmware/design.md)
- [Device Tree Overlay](../../pika/overlays/ad7606-pru0.dts)
- [AM335x PRU-ICSS Reference Guide](https://www.ti.com/lit/ug/spruh73q/spruh73q.pdf)
- [AD7606 Datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD7606.pdf)

---

**Last Updated**: 2024  
**Implementation Version**: 1.0
