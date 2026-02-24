import struct
import os
from typing import List, Dict
from app.core.config import settings

# Header format: uint64, uint32, uint32, uint32
HEADER_FORMAT = "<QIII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

class HistoryService:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def get_decimated_data(self, max_points: int = 1000) -> Dict:
        path = os.path.join(self.data_dir, "decimated.bin")
        if not os.path.exists(path):
            return {"samples": [], "rate": 0}

        samples = []
        sample_rate = 0
        
        try:
            with open(path, "rb") as f:
                # For this POC, we'll just read the last chunk or 
                # scan for a reasonable number of points.
                # A production version would support time-range SEEKING.
                
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                
                # Let's read from the end
                # Each sample is 8 channels * 2 bytes = 16 bytes
                # A chunk header is 24 bytes
                # Assume chunks of 10 samples (from logger main.c)
                # chunk_size = 24 + (10 * 16) = 184 bytes
                
                chunk_total = 24 + (10 * 8 * 2) 
                num_to_read = min(max_points // 10, file_size // chunk_total)
                
                if num_to_read > 0:
                    f.seek(file_size - (num_to_read * chunk_total))
                    
                    for _ in range(num_to_read):
                        hdr_data = f.read(HEADER_SIZE)
                        if not hdr_data: break
                        
                        ts, rate, count, channels = struct.unpack(HEADER_FORMAT, hdr_data)
                        
                        # Safety check: avoid reading corrupt huge sizes
                        if count > 100000 or channels > 32 or count <= 0:
                            print(f"Skipping corrupt chunk: count={count}, channels={channels}")
                            continue
                            
                        sample_rate = rate
                        
                        raw_samples = f.read(count * channels * 2)
                        if len(raw_samples) < count * channels * 2:
                            break
                            
                        # Just grab Channel 0 for the trend graph
                        shorts = struct.unpack(f"<{count * channels}h", raw_samples)
                        ch0 = shorts[0::channels]
                        samples.extend(ch0)
        except Exception as e:
            print(f"Error reading history: {e}")

        return {
            "samples": samples[-max_points:],
            "rate": sample_rate
        }

history_service = HistoryService(settings.data_dir)
