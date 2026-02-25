import struct
import os
from typing import List, Dict
from app.core.config import settings

# Sensor calibration constants — matching datalogger config/logger.yaml
ADC_VREF          = 5.0      # AD7606 input range (±5V)
ADC_FULL_SCALE    = 32768.0  # 2^15 (signed 16-bit)
TRANSFORMER_RATIO = 120.0    # ZMPT101B: mains / adc_output_amplitude

# Header format matches storage_format.h  decimated_chunk_header_t (packed):
#   uint64 start_time_ns (8)
#   uint32 sample_rate   (4)
#   uint32 sample_count  (4)
#   uint32 channels      (4)
HEADER_FORMAT = "<QIII"
HEADER_SIZE   = struct.calcsize(HEADER_FORMAT)  # 20 bytes

class HistoryService:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def get_decimated_data(self, max_points: int = 1000) -> Dict:
        path = os.path.join(self.data_dir, "decimated.bin")
        if not os.path.exists(path):
            return {"samples": [], "rate": 0}

        samples_raw: List[int] = []
        sample_rate = 0

        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()

                # Each chunk: header (HEADER_SIZE) + (sample_count * channels * 2)
                # Logger batches 10 samples per chunk with 8 channels:
                # chunk_total = 20 + (10 * 8 * 2) = 180 bytes
                # Use a safe heuristic: we'll scan backwards, chunk by chunk.
                # Since chunk size varies, seek to a reasonable start point.
                typical_chunk = HEADER_SIZE + (10 * 8 * 2)
                num_to_read   = min(max_points // 10, file_size // typical_chunk)

                if num_to_read > 0:
                    f.seek(file_size - num_to_read * typical_chunk)

                    for _ in range(num_to_read):
                        hdr_data = f.read(HEADER_SIZE)
                        if not hdr_data or len(hdr_data) < HEADER_SIZE:
                            break

                        ts, rate, count, channels = struct.unpack(HEADER_FORMAT, hdr_data)

                        # Sanity check
                        if count == 0 or count > 100000 or channels == 0 or channels > 32:
                            print(f"[HistoryService] Skipping corrupt chunk count={count} ch={channels}")
                            break

                        sample_rate = rate
                        raw_bytes   = f.read(count * channels * 2)
                        if len(raw_bytes) < count * channels * 2:
                            break

                        shorts  = struct.unpack(f"<{count * channels}h", raw_bytes)
                        ch0     = shorts[0::channels]  # channel 0 interleaved
                        samples_raw.extend(ch0)

        except Exception as e:
            print(f"[HistoryService] Error reading history: {e}")

        # Calibrate: raw ADC count → instantaneous mains voltage
        # v_adc = raw * (vref / 32768)
        # v_mains = v_adc * transformer_ratio
        scale = (ADC_VREF / ADC_FULL_SCALE) * TRANSFORMER_RATIO
        samples_volts = [raw * scale for raw in samples_raw[-max_points:]]

        # Remove DC bias for display: subtract the mean of this window.
        # The resting ZMPT101B DC offset (scaled up by TRANSFORMER_RATIO)
        # appears as a large constant — the mean subtraction removes it,
        # centering the AC waveform around 0 V for chart display.
        if samples_volts:
            dc_offset = sum(samples_volts) / len(samples_volts)
            samples_volts = [v - dc_offset for v in samples_volts]

        return {
            "samples": [round(v, 2) for v in samples_volts],
            "rate":    sample_rate,
        }

history_service = HistoryService(settings.data_dir)
