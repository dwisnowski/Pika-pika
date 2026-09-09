import struct
import os
import math
from typing import List
from app.core.config import settings
from app.services.calibration_service import calibration_service
from app.services.config_service import config_service


def mains_volts_per_count() -> float:
    adc_vref = config_service.get_adc_vref()
    adc_bits = config_service.get_adc_bits()
    transformer_ratio = calibration_service.get_calibration_values()[
        "transformer_ratio"
    ]
    full_scale = float(1 << (adc_bits - 1))
    return (adc_vref / full_scale) * transformer_ratio

# v2 index: event_id, timestamp_ns, waveform_start_ns, ns_per_sample,
#           event_type, peak_value, duration_samples, file_offset
INDEX_FORMAT = "<QQQQ B h I Q"
INDEX_SIZE = struct.calcsize(INDEX_FORMAT)


class EventService:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def _duration_ms(self, dur_samples: int, ns_per_sample: int) -> float:
        if ns_per_sample <= 0:
            rate = config_service.get_nominal_rate_hz()
            ns_per_sample = int(1_000_000_000 / rate) if rate else 100000
        return (dur_samples * ns_per_sample) / 1_000_000.0

    def _legacy_peak_without_dc(self, peak_raw: int, file_offset: int) -> int:
        """Remove the ADC bias from peaks written before AC-centered storage."""
        if abs(peak_raw) < 1000:
            return peak_raw

        path = os.path.join(self.data_dir, "events.bin")
        try:
            with open(path, "rb") as f:
                f.seek(file_offset)
                raw = f.read(5000 * 2)
            count = len(raw) // 2
            if count:
                samples = struct.unpack(f"<{count}h", raw[: count * 2])
                baseline = sum(samples) / count
                return int(round(peak_raw - baseline))
        except Exception as e:
            print(f"[EventService] Could not remove legacy event bias: {e}")
        return peak_raw

    def get_recent_events(self, limit: int = 10) -> List[dict]:
        path = os.path.join(self.data_dir, "index.bin")
        if not os.path.exists(path):
            return []

        events = []
        scale = mains_volts_per_count()
        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                count = size // INDEX_SIZE
                to_read = min(limit, count)
                if to_read == 0:
                    return []
                f.seek((count - to_read) * INDEX_SIZE)
                for _ in range(to_read):
                    data = f.read(INDEX_SIZE)
                    if len(data) < INDEX_SIZE:
                        break
                    (
                        event_id,
                        ts,
                        wf_start,
                        ns_per_sample,
                        etype,
                        peak_raw,
                        dur,
                        file_off,
                    ) = struct.unpack(INDEX_FORMAT, data)
                    peak_ac = self._legacy_peak_without_dc(peak_raw, file_off)
                    events.append({
                        "id": event_id,
                        "timestamp": ts,
                        "waveform_start_ns": wf_start,
                        "ns_per_sample": ns_per_sample,
                        "type": (
                            ["NONE", "SAG", "SWELL", "SPIKE", "DIP"] + ["UNKNOWN"]
                        )[etype if etype <= 4 else 5],
                        "peak_volts": round(abs(peak_ac) * scale, 1),
                        "duration_ms": round(
                            self._duration_ms(dur, ns_per_sample), 2
                        ),
                    })
        except Exception as e:
            print(f"[EventService] Error reading events: {e}")
        return list(reversed(events))

    def get_event_data(self, event_id: int):
        index_path = os.path.join(self.data_dir, "index.bin")
        data_path = os.path.join(self.data_dir, "events.bin")
        if not os.path.exists(index_path) or not os.path.exists(data_path):
            return None

        try:
            with open(index_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                count = size // INDEX_SIZE
                for i in range(count - 1, -1, -1):
                    f.seek(i * INDEX_SIZE)
                    record_data = f.read(INDEX_SIZE)
                    (
                        eid,
                        ts,
                        wf_start,
                        ns_per_sample,
                        etype,
                        peak_raw,
                        dur,
                        file_off,
                    ) = struct.unpack(INDEX_FORMAT, record_data)
                    if eid != event_id:
                        continue

                    next_offset = None
                    if i < count - 1:
                        f.seek((i + 1) * INDEX_SIZE)
                        next_data = f.read(INDEX_SIZE)
                        next_offset = struct.unpack(INDEX_FORMAT, next_data)[7]

                    with open(data_path, "rb") as df:
                        if next_offset is not None:
                            bytes_to_read = next_offset - file_off
                        else:
                            df.seek(0, os.SEEK_END)
                            bytes_to_read = df.tell() - file_off
                        cap_samps = bytes_to_read // 2
                        df.seek(file_off)
                        raw_samples = df.read(cap_samps * 2)
                        samples = struct.unpack(f"<{cap_samps}h", raw_samples)
                        baseline = sum(samples) / len(samples) if samples else 0
                        scale = mains_volts_per_count()
                        volts = [
                            round((sample - baseline) * scale, 2)
                            for sample in samples
                        ]
                        rms = (
                            math.sqrt(sum(v * v for v in volts) / len(volts))
                            if volts
                            else 0.0
                        )
                        sample_rate = int(
                            1_000_000_000 / ns_per_sample
                        ) if ns_per_sample else config_service.get_nominal_rate_hz()

                        return {
                            "id": event_id,
                            "timestamp": ts,
                            "waveform_start_ns": wf_start,
                            "ns_per_sample": ns_per_sample,
                            "type": (
                                ["NONE", "SAG", "SWELL", "SPIKE", "DIP"]
                                + ["UNKNOWN"]
                            )[etype if etype <= 4 else 5],
                            "vrms": round(rms, 2),
                            "peak_volts": round(
                                max((abs(v) for v in volts), default=0.0), 2
                            ),
                            "samples": volts,
                            "sample_rate": sample_rate,
                            "duration_samples": dur,
                        }
        except Exception as e:
            print(f"[EventService] Error fetching event data: {e}")
        return None


event_service = EventService(settings.data_dir)
