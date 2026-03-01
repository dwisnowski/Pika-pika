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

                # Read all chunks from the beginning to get the most recent data
                f.seek(0)
                all_chunks = []
                chunk_idx = 0
                
                while f.tell() < file_size:
                    hdr_data = f.read(HEADER_SIZE)
                    if not hdr_data or len(hdr_data) < HEADER_SIZE:
                        break

                    ts, rate, count, channels, values_per_sample = struct.unpack(HEADER_FORMAT, hdr_data)

                    # Sanity check - separate checks for each field
                    if count == 0 or count > 100000:
                        print(f"[HistoryService] Skipping corrupt chunk {chunk_idx}: count={count}")
                        if chunk_idx == 0:
                            print(f"[HistoryService] First chunk is corrupt - file may be in old format.")
                            print(f"[HistoryService] Please delete decimated.bin and restart the datalogger:")
                            print(f"[HistoryService]   rm {path}")
                            print(f"[HistoryService]   rm {path}.old")
                            return {"samples": [], "samples_raw": [], "rate": 0}
                        break
                    
                    if channels == 0 or channels > 32:
                        print(f"[HistoryService] Skipping corrupt chunk {chunk_idx}: channels={channels}")
                        if chunk_idx == 0:
                            print(f"[HistoryService] First chunk is corrupt - file may be in old format.")
                            print(f"[HistoryService] Please delete decimated.bin and restart the datalogger:")
                            print(f"[HistoryService]   rm {path}")
                            print(f"[HistoryService]   rm {path}.old")
                            return {"samples": [], "samples_raw": [], "rate": 0}
                        break
                    
                    if values_per_sample == 0 or values_per_sample > 10:
                        print(f"[HistoryService] Skipping corrupt chunk {chunk_idx}: values_per_sample={values_per_sample}")
                        if chunk_idx == 0:
                            print(f"[HistoryService] First chunk is corrupt - file may be in old format.")
                            print(f"[HistoryService] Please delete decimated.bin and restart the datalogger:")
                            print(f"[HistoryService]   rm {path}")
                            print(f"[HistoryService]   rm {path}.old")
                            return {"samples": [], "samples_raw": [], "rate": 0}
                        break

                    sample_rate = rate
                    # Total values = sample_count * channels * values_per_sample
                    total_values = count * channels * values_per_sample
                    raw_bytes   = f.read(total_values * 2)
                    if len(raw_bytes) < total_values * 2:
                        print(f"[HistoryService] Incomplete data at chunk {chunk_idx}: expected {total_values * 2} bytes, got {len(raw_bytes)}")
                        break

                    # Parse the data
                    if total_values > 0:
                        shorts  = struct.unpack(f"<{total_values}h", raw_bytes)
                        # For min/max bucketed data: values_per_sample=2 means [min, max]
                        # Extract the max value (index 1) from each [min, max] pair
                        if values_per_sample == 2:
                            # For each sample, take the max value (index 1 of the pair)
                            ch0 = shorts[1::values_per_sample]
                        else:
                            # Fallback: take first value per sample
                            ch0 = shorts[0::values_per_sample]
                        all_chunks.append(list(ch0))
                    
                    chunk_idx += 1

                # Keep only the most recent max_points samples
                for chunk in all_chunks:
                    samples_raw.extend(chunk)
                
                samples_raw = samples_raw[-max_points:] if len(samples_raw) > max_points else samples_raw
                print(f"[HistoryService] Successfully read {chunk_idx} chunks, using {len(samples_raw)} samples")

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
