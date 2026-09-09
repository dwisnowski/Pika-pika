import mmap
import ctypes
import os
import time
from typing import Optional
from app.services.config_service import config_service

SCOPE_SHM_PATH = "/dev/shm/pika_scope_shm"

class ScopeSHM(ctypes.Structure):
    _fields_ = [
        ("magic", ctypes.c_uint32),
        ("sample_rate", ctypes.c_uint32),
        ("channels", ctypes.c_uint32),
        ("capacity", ctypes.c_uint32),
        ("pru_clock_hz", ctypes.c_uint32),
        ("sample_period_cycles", ctypes.c_uint32),
        ("total_samples", ctypes.c_uint64),
    ]

class SHMService:
    def __init__(self):
        self.fd = -1
        self.mm = None
        self.header: Optional[ScopeSHM] = None
        self.last_raw_range = None
        self._calibration_scale = config_service.get_calibration_scale()
        self._calibration_updated_at = 0.0

    def get_calibration_scale(self) -> float:
        """Convert ADC counts to mains volts using the latest learned ratio."""
        from app.services.calibration_service import calibration_service

        now = time.monotonic()
        if now - self._calibration_updated_at < 2.0:
            return self._calibration_scale

        calibration = calibration_service.get_calibration_values()
        full_scale = float(1 << (config_service.get_adc_bits() - 1))
        self._calibration_scale = (
            config_service.get_adc_vref() / full_scale
        ) * calibration["transformer_ratio"]
        self._calibration_updated_at = now
        return self._calibration_scale

    def connect(self):
        try:
            self.fd = os.open(SCOPE_SHM_PATH, os.O_RDWR)
            self.mm = mmap.mmap(self.fd, 0)
            self.header = ScopeSHM.from_buffer(self.mm)
            if self.header.magic != 0x5C09E000:
                print(f"Warning: Scope magic mismatch! Got {hex(self.header.magic)}")
        except Exception as e:
            print(f"Failed to connect to Scope SHM: {e}")
            self.cleanup()

    def cleanup(self):
        self.header = None
        if self.mm:
            self.mm.close()
            self.mm = None
        if self.fd != -1:
            os.close(self.fd)
            self.fd = -1

    def get_window(self, time_window_s: float, channel: int = 0) -> list:
        if not self.header:
            # Attempt to auto-reconnect
            self.connect()
            if not self.header:
                return []

        rate = self.header.sample_rate
        channels = self.header.channels
        capacity = self.header.capacity
        total = self.header.total_samples

        if total == 0:
            return []

        # Number of samples requested
        req_samples = int(rate * time_window_s)
        if req_samples > capacity:
            req_samples = capacity

        # Can not fetch more than what's arrived
        if req_samples > total:
            req_samples = int(total)

        if req_samples <= 0:
            return []

        head = total % capacity
        start_idx = (head - req_samples + capacity) % capacity

        data_offset = ctypes.sizeof(ScopeSHM)
        DataArray = ctypes.c_int16 * (capacity * channels)
        data_view = DataArray.from_buffer(self.mm, data_offset)

        if start_idx < head:
            raw = data_view[start_idx * channels : head * channels]
        else:
            part1 = data_view[start_idx * channels : capacity * channels]
            part2 = data_view[0 : head * channels]
            raw = part1 + part2

        # Extract desired channel
        ch_raw = raw[channel::channels]

        # Decimate purely for transmission size (approx 2000 points is enough for HD curve)
        max_points = 2000
        stride = 1
        if len(ch_raw) > max_points:
            stride = len(ch_raw) // max_points
            ch_raw = ch_raw[::stride]

        if ch_raw:
            mean = sum(ch_raw) / len(ch_raw)
            self.last_raw_range = (
                int(min(ch_raw) - mean),
                int(max(ch_raw) - mean),
            )
            scale = self.get_calibration_scale()
            return [round((r - mean) * scale, 2) for r in ch_raw]
        else:
            self.last_raw_range = None
            return []

# Global instance replaces the old PRU SHM service
shm = SHMService()
