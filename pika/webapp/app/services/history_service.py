import struct
import os
from typing import List, Dict
from app.core.config import settings
from app.services.calibration_service import calibration_service

HEADER_FORMAT = "<QIIII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)


class HistoryService:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.config_file = "../pika.yaml"

    def _get_adc_vref(self) -> float:
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    import yaml
                    config = yaml.safe_load(f)
                    if config and "sensor" in config:
                        return float(config["sensor"].get("adc_vref", 5.0))
        except Exception as e:
            print(f"[HistoryService] Error reading adc_vref: {e}")
        return 5.0

    def get_decimated_data(self, max_points: int = 1000) -> Dict:
        path = os.path.join(self.data_dir, "decimated.bin")
        if not os.path.exists(path):
            return {"samples": [], "samples_raw": [], "timestamps": [], "rate": 0}

        samples_raw: List[int] = []
        timestamps: List[int] = []
        sample_rate = 0

        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                if file_size == 0:
                    return {"samples": [], "samples_raw": [], "timestamps": [], "rate": 0}

                parsed_chunks = []
                f.seek(0)
                while f.tell() < file_size:
                    hdr_data = f.read(HEADER_SIZE)
                    if len(hdr_data) < HEADER_SIZE:
                        break
                    ts, rate, count, channels, vps = struct.unpack(
                        HEADER_FORMAT, hdr_data
                    )
                    if count == 0 or count > 100000 or channels == 0 or vps == 0:
                        break
                    total_values = count * channels * vps
                    raw_bytes = f.read(total_values * 2)
                    if len(raw_bytes) < total_values * 2:
                        break
                    shorts = struct.unpack(f"<{total_values}h", raw_bytes)
                    if vps == 2:
                        ch0 = shorts[1::vps]
                    else:
                        ch0 = shorts[0::vps]
                    bucket_ns = int(1_000_000_000 / rate) if rate else 0
                    chunk_ts = [
                        ts + i * bucket_ns for i in range(len(ch0))
                    ]
                    parsed_chunks.append(
                        {"values": list(ch0), "timestamps": chunk_ts, "rate": rate}
                    )
                    sample_rate = rate

                if not parsed_chunks:
                    return {"samples": [], "samples_raw": [], "timestamps": [], "rate": 0}

                for chunk in parsed_chunks:
                    samples_raw.extend(chunk["values"])
                    timestamps.extend(chunk["timestamps"])

                if len(samples_raw) > max_points:
                    samples_raw = samples_raw[-max_points:]
                    timestamps = timestamps[-max_points:]

        except Exception as e:
            print(f"[HistoryService] Error reading history: {e}")
            return {"samples": [], "samples_raw": [], "timestamps": [], "rate": 0}

        cal = calibration_service.get_calibration_values()
        adc_vref = self._get_adc_vref()
        scale = (adc_vref / 32768.0) * cal["transformer_ratio"]
        samples_volts = [raw * scale for raw in samples_raw]
        if samples_volts:
            dc_offset = sum(samples_volts) / len(samples_volts)
            samples_volts = [v - dc_offset for v in samples_volts]

        return {
            "samples": [round(v, 2) for v in samples_volts],
            "samples_raw": samples_raw,
            "timestamps": timestamps,
            "rate": sample_rate,
        }


history_service = HistoryService(settings.data_dir)
