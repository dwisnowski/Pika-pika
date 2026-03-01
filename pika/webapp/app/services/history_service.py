import struct
import os
import yaml
from typing import List, Dict
from app.core.config import settings
from app.services.calibration_service import calibration_service

# Header format matches storage_format.h decimated_chunk_header_t (packed):
#   uint64 start_time_ns (8)
#   uint32 sample_rate   (4)
#   uint32 sample_count  (4)
#   uint32 channels      (4)
#   uint32 values_per_sample (4)
HEADER_FORMAT = "<QIIII"
HEADER_SIZE   = struct.calcsize(HEADER_FORMAT)  # 24 bytes

class HistoryService:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.config_file = "../pika.yaml"  # Path to shared config

    def _get_active_channels(self) -> int:
        """Read active_channels from pika.yaml"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    config = yaml.safe_load(f)
                    if config and "sensor" in config:
                        return int(config["sensor"].get("active_channels", 1))
        except Exception as e:
            print(f"[HistoryService] Error reading active_channels from config: {e}")
        return 1

    def _get_adc_vref(self) -> float:
        """Read adc_vref from pika.yaml"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    config = yaml.safe_load(f)
                    if config and "sensor" in config:
                        return float(config["sensor"].get("adc_vref", 5.0))
        except Exception as e:
            print(f"[HistoryService] Error reading adc_vref from config: {e}")
        return 5.0

    def get_decimated_data(self, max_points: int = 1000) -> Dict:
        path = os.path.join(self.data_dir, "decimated.bin")
        if not os.path.exists(path):
            print(f"[HistoryService] decimated.bin not found at {path}")
            return {"samples": [], "samples_raw": [], "rate": 0}

        samples_raw: List[int] = []
        sample_rate = 0

        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                
                if file_size == 0:
                    print(f"[HistoryService] decimated.bin is empty (0 bytes)")
                    return {"samples": [], "samples_raw": [], "rate": 0}

                # Strategy: Read file backwards in chunks to find the most recent data
                # This is much faster than reading the entire file
                all_chunks = []
                chunk_idx = 0
                bytes_remaining = file_size
                
                # Read backwards in 64KB blocks
                while bytes_remaining > 0 and len(all_chunks) < 100:  # Limit to 100 chunks max
                    block_size = min(65536, bytes_remaining)
                    read_pos = bytes_remaining - block_size
                    
                    f.seek(read_pos)
                    block_data = f.read(block_size)
                    bytes_remaining -= block_size
                    
                    # Parse chunks from this block (forward order within block)
                    offset = 0
                    block_chunks = []
                    
                    while offset + HEADER_SIZE <= len(block_data):
                        hdr_data = block_data[offset:offset + HEADER_SIZE]
                        try:
                            ts, rate, count, channels, values_per_sample = struct.unpack(HEADER_FORMAT, hdr_data)
                        except:
                            break
                        
                        offset += HEADER_SIZE
                        
                        # Sanity checks
                        if count == 0 or count > 100000 or channels == 0 or channels > 32 or values_per_sample == 0 or values_per_sample > 10:
                            break
                        
                        sample_rate = rate
                        total_values = count * channels * values_per_sample
                        data_size = total_values * 2
                        
                        if offset + data_size > len(block_data):
                            break
                        
                        raw_bytes = block_data[offset:offset + data_size]
                        offset += data_size
                        
                        if len(raw_bytes) < data_size:
                            break
                        
                        # Parse the data
                        if total_values > 0:
                            shorts = struct.unpack(f"<{total_values}h", raw_bytes)
                            if values_per_sample == 2:
                                ch0 = shorts[1::values_per_sample]
                            else:
                                ch0 = shorts[0::values_per_sample]
                            block_chunks.append(list(ch0))
                            chunk_idx += 1
                    
                    # Add chunks from this block (in reverse order since we're reading backwards)
                    block_chunks.reverse()
                    all_chunks.extend(block_chunks)
                    
                    # Check if we have enough samples
                    total_samples = sum(len(chunk) for chunk in all_chunks)
                    if total_samples >= max_points:
                        break

                # Reverse all chunks to get chronological order
                all_chunks.reverse()
                
                # Flatten and keep only the most recent max_points
                for chunk in all_chunks:
                    samples_raw.extend(chunk)
                
                samples_raw = samples_raw[-max_points:] if len(samples_raw) > max_points else samples_raw
                print(f"[HistoryService] Successfully read {chunk_idx} chunks, using {len(samples_raw)} samples (file_size={file_size})")

        except Exception as e:
            print(f"[HistoryService] Error reading history: {e}")
            import traceback
            traceback.print_exc()
            return {"samples": [], "samples_raw": [], "rate": 0}

        print(f"[HistoryService] Read {len(samples_raw)} raw samples from decimated.bin")

        # Get calibration values (learned from datalogger or config defaults)
        cal = calibration_service.get_calibration_values()
        adc_vref = self._get_adc_vref()
        adc_full_scale = 32768.0  # 2^15 (signed 16-bit)
        transformer_ratio = cal["transformer_ratio"]

        print(f"[HistoryService] Calibration: vref={adc_vref}, transformer_ratio={transformer_ratio}")
        print(f"[HistoryService] First 10 raw samples: {samples_raw[:10]}")

        # Calibrate: raw ADC count → instantaneous mains voltage
        # v_adc = raw * (vref / 32768)
        # v_mains = v_adc * transformer_ratio
        scale = (adc_vref / adc_full_scale) * transformer_ratio
        samples_volts = [raw * scale for raw in samples_raw[-max_points:]]
        samples_raw_sliced = samples_raw[-max_points:]

        print(f"[HistoryService] Scale factor: {scale}")
        print(f"[HistoryService] First 10 scaled samples: {samples_volts[:10]}")

        # Remove DC bias for display: subtract the mean of this window.
        # The resting ZMPT101B DC offset (scaled up by transformer_ratio)
        # appears as a large constant — the mean subtraction removes it,
        # centering the AC waveform around 0 V for chart display.
        if samples_volts:
            dc_offset = sum(samples_volts) / len(samples_volts)
            samples_volts = [v - dc_offset for v in samples_volts]

        return {
            "samples": [round(v, 2) for v in samples_volts],
            "samples_raw": samples_raw_sliced,
            "rate":    sample_rate,
        }

history_service = HistoryService(settings.data_dir)
