import struct
import os
import json
from typing import List, Dict, Any
from app.core.config import settings
from app.services.calibration_service import calibration_service
from app.services.config_service import config_service

HEADER_FORMAT = "<QIIII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# Decimated payload layouts (values_per_sample)
VPS_LEGACY_MINMAX = 2
VPS_IEC_VRMS = 3


class HistoryService:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def _scale(self) -> float:
        cal = calibration_service.get_calibration_values()
        adc_vref = float(config_service.get_adc_vref())
        return (adc_vref / 32768.0) * float(cal["transformer_ratio"])

    def get_decimated_data(self, max_points: int = 20000) -> Dict[str, Any]:
        path = os.path.join(self.data_dir, "decimated.bin")
        empty = {
            "samples": [],
            "samples_min": [],
            "samples_max": [],
            "samples_raw": [],
            "timestamps": [],
            "rate": 0,
            "format": "none",
            "rollup_10min": self.get_vrms_10min_rollup(limit=24),
        }
        if not os.path.exists(path):
            return empty

        vrms: List[float] = []
        mins: List[float] = []
        maxs: List[float] = []
        samples_raw: List[int] = []
        timestamps: List[int] = []
        sample_rate = 0
        fmt = "legacy"

        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                if file_size == 0:
                    return empty

                f.seek(0)
                scale = self._scale()
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
                    bucket_ns = int(1_000_000_000 / rate) if rate else 0

                    if vps == VPS_IEC_VRMS:
                        fmt = "iec_vrms"
                        for i in range(count):
                            base = i * vps
                            vrms.append(shorts[base] / 100.0)
                            mins.append(shorts[base + 1] / 100.0)
                            maxs.append(shorts[base + 2] / 100.0)
                            samples_raw.append(shorts[base])
                            timestamps.append(ts + i * bucket_ns)
                    elif vps == VPS_LEGACY_MINMAX:
                        # Legacy: max envelope only (ADC counts → AC-ish volts)
                        for i in range(count):
                            base = i * vps
                            mn = shorts[base] * scale
                            mx = shorts[base + 1] * scale
                            mins.append(round(mn, 2))
                            maxs.append(round(mx, 2))
                            # Approximate RMS from crest for old files
                            vrms.append(round(abs(mx) / (2 ** 0.5), 2))
                            samples_raw.append(shorts[base + 1])
                            timestamps.append(ts + i * bucket_ns)
                    else:
                        break
                    sample_rate = rate

                if not vrms:
                    return empty

                if len(vrms) > max_points:
                    vrms = vrms[-max_points:]
                    mins = mins[-max_points:]
                    maxs = maxs[-max_points:]
                    samples_raw = samples_raw[-max_points:]
                    timestamps = timestamps[-max_points:]

        except Exception as e:
            print(f"[HistoryService] Error reading history: {e}")
            return empty

        return {
            "samples": [round(v, 2) for v in vrms],
            "samples_min": [round(v, 2) for v in mins],
            "samples_max": [round(v, 2) for v in maxs],
            "samples_raw": samples_raw,
            "timestamps": timestamps,
            "rate": sample_rate,
            "format": fmt,
            "rollup_10min": self.get_vrms_10min_rollup(limit=24),
        }

    def get_vrms_10min_rollup(self, limit: int = 24) -> List[Dict[str, Any]]:
        path = os.path.join(self.data_dir, "vrms_10min.jsonl")
        if not os.path.exists(path):
            return []
        rows: List[Dict[str, Any]] = []
        try:
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return rows[-limit:]
        except Exception as e:
            print(f"[HistoryService] Error reading 10-min rollup: {e}")
            return []


history_service = HistoryService(settings.data_dir)
