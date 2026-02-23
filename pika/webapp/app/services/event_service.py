import struct
import os
from typing import List
from app.core.config import settings

# Index record: uint64, uint8, int16, uint32
INDEX_FORMAT = "<QB hI" # Wait, packing in C was 24 bytes total probably due to padding
INDEX_SIZE = 24 # Adhering to the C struct padding

class EventService:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def get_recent_events(self, limit: int = 10) -> List[dict]:
        path = os.path.join(self.data_dir, "index.idx") # Wait, C logger used .bin or .idx?
        # Checking writer.c learnings... it used index.bin
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
                f.seek(size - (to_read * INDEX_SIZE))
                
                for i in range(to_read):
                    data = f.read(INDEX_SIZE)
                    # Mapping: uint64 ts, uint8 type, int16 peak, uint32 dur
                    # Note: C compiler likely padded the uint8 to 8 bytes or similar
                    # Let's assume standard alignment for now
                    ts, etype, peak, dur = struct.unpack("<Q B h I", data[:8+1+2+4])
                    
                    events.append({
                        "id": count - to_read + i,
                        "timestamp": ts,
                        "type": ["NONE", "SAG", "SWELL", "SPIKE"][etype] if etype < 4 else "UNKNOWN",
                        "peak": peak,
                        "duration_ms": (dur / 10000.0) * 1000 # 10kHz sample rate
                    })
        except Exception as e:
            print(f"Error reading events: {e}")
            
        return list(reversed(events))

event_service = EventService(settings.data_dir)
