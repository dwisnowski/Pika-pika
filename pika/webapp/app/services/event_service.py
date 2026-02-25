import struct
import os
from typing import List
from app.core.config import settings

# Sensor calibration constants — matching datalogger config/logger.yaml
ADC_VREF          = 5.0      # AD7606 input range (±5V)
ADC_FULL_SCALE    = 32768.0  # 2^15 (signed 16-bit)
TRANSFORMER_RATIO = 120.0    # ZMPT101B: mains / adc_output_amplitude

def raw_to_mains_volts(raw: int) -> float:
    """Convert a raw signed int16 ADC count to instantaneous mains voltage."""
    v_adc = raw * (ADC_VREF / ADC_FULL_SCALE)
    return v_adc * TRANSFORMER_RATIO

# Index record binary layout (packed, matches storage_format.h):
#   uint64 event_id   (8)
#   uint64 timestamp  (8)
#   uint8  event_type (1)
#   int16  peak_value (2)
#   uint32 duration   (4)
#   uint64 file_offset(8)
# Total = 31 bytes packed.  C struct with __attribute__((packed)) = 31 bytes.
INDEX_FORMAT = "<QQ B h I Q"
INDEX_SIZE   = struct.calcsize(INDEX_FORMAT)   # 31 bytes

class EventService:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def get_recent_events(self, limit: int = 10) -> List[dict]:
        path = os.path.join(self.data_dir, "index.bin")

        if not os.path.exists(path):
            return []

        events = []
        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                count = size // INDEX_SIZE

                to_read = min(limit, count)
                if to_read == 0:
                    return []

                f.seek(size - (to_read * INDEX_SIZE))

                for i in range(to_read):
                    data = f.read(INDEX_SIZE)
                    if len(data) < INDEX_SIZE:
                        break
                    event_id, ts, etype, peak_raw, dur, file_off = struct.unpack(
                        INDEX_FORMAT, data
                    )

                    # Calibrate peak to mains volts
                    peak_volts = raw_to_mains_volts(peak_raw)

                    events.append({
                        "id":          event_id,
                        "timestamp":   ts,
                        "type":        (["NONE", "SAG", "SWELL", "SPIKE", "DIP"] + ["UNKNOWN"])[
                                           etype if etype <= 4 else 5
                                       ],
                        "peak_volts":  round(peak_volts, 1),
                        "duration_ms": round((dur / 10000.0) * 1000, 2),  # 10kHz default
                    })
        except Exception as e:
            print(f"[EventService] Error reading events: {e}")

        return list(reversed(events))

event_service = EventService(settings.data_dir)
