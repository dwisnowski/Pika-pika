import mmap
import ctypes
import os
import time
from typing import Optional, Tuple

# Sensor calibration constants — matching datalogger config/logger.yaml
ADC_VREF          = 5.0      # AD7606 input range (±5V)
ADC_FULL_SCALE    = 32768.0  # 2^15 (signed 16-bit)
TRANSFORMER_RATIO = 120.0    # ZMPT101B: mains / adc_output_amplitude
_CALIBRATION_SCALE = (ADC_VREF / ADC_FULL_SCALE) * TRANSFORMER_RATIO

# Physical address constants for BeagleBone Black PRU SHM
PRU_SHM_PHYS_BASE = 0x4a310000
PRU_SHM_SIZE = 0x3000

class BlockDescriptor(ctypes.Structure):
    _fields_ = [
        ("timestamp_cycles", ctypes.c_uint64),
        ("num_samples", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32),
    ]

class SHMHeader(ctypes.Structure):
    _fields_ = [
        ("magic", ctypes.c_uint32),
        ("version", ctypes.c_uint32),
        ("sample_period_cycles", ctypes.c_uint32),
        ("channel_mask", ctypes.c_uint32),
        ("block_size", ctypes.c_uint32),
        ("num_blocks", ctypes.c_uint32),
        ("write_block_idx", ctypes.c_uint32),
        ("error_flags", ctypes.c_uint32),
        ("sample_count", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 7), # Padding to 64 bytes
    ]

class SHMService:
    def __init__(self):
        self.fd = -1
        self.mm = None
        self.header: Optional[SHMHeader] = None
        self.last_read_idx = 0

    def connect(self):
        try:
            self.fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
            self.mm = mmap.mmap(
                self.fd, 
                PRU_SHM_SIZE, 
                flags=mmap.MAP_SHARED, 
                prot=mmap.PROT_READ | mmap.PROT_WRITE, 
                offset=PRU_SHM_PHYS_BASE
            )
            self.header = SHMHeader.from_buffer(self.mm)
            if self.header.magic != 0xDEADBEEF:
                print(f"Warning: SHM Magic mismatch! Got {hex(self.header.magic)}")
        except Exception as e:
            print(f"Failed to connect to SHM: {e}")
            self.cleanup()
            raise

    def cleanup(self):
        self.header = None
        if self.mm:
            self.mm.close()
            self.mm = None
        if self.fd != -1:
            os.close(self.fd)
            self.fd = -1

    def get_latest_samples(self) -> Optional[Tuple[BlockDescriptor, list]]:
        if not self.header:
            return None

        current_idx = self.header.write_block_idx
        num_blocks = self.header.num_blocks
        
        if num_blocks == 0:
            return None

        # The most recently completed block is at (current_idx - 1)
        ready_idx = (current_idx + num_blocks - 1) % num_blocks
        
        # Calculate offset: Header (64) + (idx * block_total_size)
        # block_total_size = 16 (desc) + (samples * channels * 2)
        # Logger assumes 8 channels hardcoded
        block_total_size = 16 + (self.header.block_size * 8 * 2)
        offset = 64 + (ready_idx * block_total_size)

        # Bounds check
        if offset + block_total_size > PRU_SHM_SIZE:
            return None

        # Map descriptor
        desc = BlockDescriptor.from_buffer(self.mm, offset)
        
        # Map samples
        samples_offset = offset + 16
        # The number of samples per block is 128 * 8 channels
        total_samples = self.header.block_size * 8
        
        # Create a ctypes array type for the samples
        SamplesArray = ctypes.c_int16 * total_samples
        samples_view = SamplesArray.from_buffer(self.mm, samples_offset)
        
        # Convert to a standard Python list and apply calibration:
        # raw → instantaneous mains voltage (VAC)
        raw_list    = list(samples_view)
        # Remove DC bias by subtracting the block mean before scaling —
        # the ZMPT101B resting DC offset is removed per-block.
        if raw_list:
            block_mean = sum(raw_list) / len(raw_list)
        else:
            block_mean = 0.0
        samples = [round((r - block_mean) * _CALIBRATION_SCALE, 2) for r in raw_list]

        return desc, samples

# Global instance
shm = SHMService()
