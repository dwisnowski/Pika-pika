import struct
import os
from typing import List
from app.core.config import settings
from app.services.config_service import config_service

def raw_to_mains_volts(raw: int) -> float:
    """Convert a raw signed int16 ADC count to instantaneous mains voltage."""
    adc_vref = config_service.get_adc_vref()
    adc_bits = config_service.get_adc_bits()
    transformer_ratio = config_service.get_transformer_ratio()
    
    full_scale = float(1 << (adc_bits - 1))  # 2^(bits-1)
    v_adc = raw * (adc_vref / full_scale)
    return v_adc * transformer_ratio

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

                # Ensure perfect alignment
                f.seek((count - to_read) * INDEX_SIZE)

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

    def get_event_data(self, event_id: int):
        """Finds event by ID and returns its high-precision samples."""
        index_path = os.path.join(self.data_dir, "index.bin")
        data_path = os.path.join(self.data_dir, "events.bin")

        if not os.path.exists(index_path) or not os.path.exists(data_path):
            return None

        try:
            with open(index_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                count = size // INDEX_SIZE
                
                # Scan backwards for the ID
                for i in range(count - 1, -1, -1):
                    f.seek(i * INDEX_SIZE)
                    record_data = f.read(INDEX_SIZE)
                    eid, ts, etype, peak_raw, dur, file_off = struct.unpack(
                        INDEX_FORMAT, record_data
                    )
                    
                    if eid == event_id:
                        # Find the length of this event's data
                        next_offset = None
                        if i < count - 1:
                            f.seek((i + 1) * INDEX_SIZE)
                            next_data = f.read(INDEX_SIZE)
                            _, _, _, _, _, next_offset = struct.unpack(INDEX_FORMAT, next_data)
                        
                        # Read raw data
                        with open(data_path, "rb") as df:
                            if next_offset is not None:
                                bytes_to_read = next_offset - file_off
                            else:
                                df.seek(0, os.SEEK_END)
                                data_size = df.tell()
                                bytes_to_read = data_size - file_off
                                
                            cap_samps = bytes_to_read // 2
                            
                            df.seek(file_off)
                            raw_samples = df.read(cap_samps * 2)
                            samples = struct.unpack(f"<{cap_samps}h", raw_samples)
                            
                            # Convert to volts
                            volts = [round(raw_to_mains_volts(s), 2) for s in samples]
                            
                            return {
                                "id": event_id,
                                "timestamp": ts,
                                "type": (["NONE", "SAG", "SWELL", "SPIKE", "DIP"] + ["UNKNOWN"])[
                                    etype if etype <= 4 else 5
                                ],
                                "vrms": round(raw_to_mains_volts(peak_raw), 2),
                                "samples": volts,
                                "sample_rate": 10000
                            }
        except Exception as e:
            print(f"[EventService] Error fetching event data: {e}")
            
        return None

event_service = EventService(settings.data_dir)
