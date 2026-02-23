import mmap
import ctypes
import os
import time
from typing import Optional, Tuple

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
        ("num_blocks", ctypes.c_uint32),
        ("block_size", ctypes.c_uint32),
        ("write_block_idx", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 11), # Padding to 64 bytes
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

        # Map descriptor
        desc = BlockDescriptor.from_buffer(self.mm, offset)
        
        # Map samples
        samples_offset = offset + 16
        samples_size = desc.num_samples * 8 * 2
        
        # Read raw bytes and convert to shorts
        raw_data = self.mm[samples_offset : samples_offset + samples_size]
        samples = list(ctypes.cast(raw_data, ctypes.POINTER(ctypes.c_int16 * (desc.num_samples * 8))).contents)

        return desc, samples

# Global instance
shm = SHMService()
