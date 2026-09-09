import struct
import os
import math
from typing import List, Optional, Tuple
from app.core.config import settings
from app.services.calibration_service import calibration_service
from app.services.config_service import config_service
from app.services.review_policy import evaluate_event_review


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
INDEX_FORMAT_V2 = "<QQQQ B h I Q"
INDEX_SIZE_V2 = struct.calcsize(INDEX_FORMAT_V2)

# v3 adds extreme_rms_v before file_offset
INDEX_FORMAT_V3 = "<QQQQ B h I f Q"
INDEX_SIZE_V3 = struct.calcsize(INDEX_FORMAT_V3)


def _detect_index_format(size: int) -> Tuple[str, int, bool]:
    """Return (format, record_size, has_extreme_rms). Prefer v3 when unambiguous."""
    if size == 0:
        return INDEX_FORMAT_V3, INDEX_SIZE_V3, True
    if size % INDEX_SIZE_V3 == 0:
        return INDEX_FORMAT_V3, INDEX_SIZE_V3, True
    if size % INDEX_SIZE_V2 == 0:
        return INDEX_FORMAT_V2, INDEX_SIZE_V2, False
    # Partial/corrupt: try v3 first for new writers
    return INDEX_FORMAT_V3, INDEX_SIZE_V3, True


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

    def _type_name(self, etype: int) -> str:
        names = ["NONE", "SAG", "SWELL", "SPIKE", "DIP"]
        return names[etype] if 0 <= etype < len(names) else "UNKNOWN"

    def _annotate_review(
        self, event: dict, extreme_rms_v: float, duration_ms: float
    ) -> dict:
        nominal = float(config_service.get_target_mains_vrms())
        review = evaluate_event_review(
            event_type=event.get("type", ""),
            extreme_rms_v=extreme_rms_v,
            duration_ms=duration_ms,
            nominal_vrms=nominal,
            config=config_service.config,
        )
        event.update(review)
        return event

    def _unpack_record(
        self, data: bytes, fmt: str, has_extreme: bool, scale: float
    ) -> Optional[dict]:
        if has_extreme:
            (
                event_id,
                ts,
                wf_start,
                ns_per_sample,
                etype,
                peak_raw,
                dur,
                extreme_rms_v,
                file_off,
            ) = struct.unpack(fmt, data)
        else:
            (
                event_id,
                ts,
                wf_start,
                ns_per_sample,
                etype,
                peak_raw,
                dur,
                file_off,
            ) = struct.unpack(fmt, data)
            extreme_rms_v = None

        duration_ms = round(self._duration_ms(dur, ns_per_sample), 2)
        type_name = self._type_name(etype)

        if extreme_rms_v is not None and math.isfinite(extreme_rms_v):
            peak_rms = round(float(extreme_rms_v), 1)
        else:
            peak_ac = self._legacy_peak_without_dc(peak_raw, file_off)
            # Legacy: instantaneous crest → approximate RMS for display only
            peak_rms = round(abs(peak_ac) * scale / math.sqrt(2.0), 1)

        event = {
            "id": event_id,
            "timestamp": ts,
            "waveform_start_ns": wf_start,
            "ns_per_sample": ns_per_sample,
            "type": type_name,
            "peak_volts": peak_rms,  # extreme RMS (kept key for UI compat)
            "peak_rms_v": peak_rms,
            "duration_ms": duration_ms,
            "duration_samples": dur,
            "file_offset": file_off,
        }
        return self._annotate_review(event, peak_rms, duration_ms)

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
                fmt, rec_size, has_extreme = _detect_index_format(size)
                count = size // rec_size
                to_read = min(limit, count)
                if to_read == 0:
                    return []
                f.seek((count - to_read) * rec_size)
                for _ in range(to_read):
                    data = f.read(rec_size)
                    if len(data) < rec_size:
                        break
                    event = self._unpack_record(data, fmt, has_extreme, scale)
                    if event:
                        events.append(event)
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
                fmt, rec_size, has_extreme = _detect_index_format(size)
                count = size // rec_size
                scale = mains_volts_per_count()
                for i in range(count - 1, -1, -1):
                    f.seek(i * rec_size)
                    record_data = f.read(rec_size)
                    if len(record_data) < rec_size:
                        continue
                    meta = self._unpack_record(
                        record_data, fmt, has_extreme, scale
                    )
                    if not meta or meta["id"] != event_id:
                        continue

                    file_off = meta["file_offset"]
                    next_offset = None
                    if i < count - 1:
                        f.seek((i + 1) * rec_size)
                        next_data = f.read(rec_size)
                        if has_extreme:
                            next_offset = struct.unpack(fmt, next_data)[8]
                        else:
                            next_offset = struct.unpack(fmt, next_data)[7]

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
                        volts = [
                            round((sample - baseline) * scale, 2)
                            for sample in samples
                        ]
                        rms = (
                            math.sqrt(sum(v * v for v in volts) / len(volts))
                            if volts
                            else 0.0
                        )
                        sample_rate = (
                            int(1_000_000_000 / meta["ns_per_sample"])
                            if meta["ns_per_sample"]
                            else config_service.get_nominal_rate_hz()
                        )

                        return {
                            **meta,
                            "vrms": round(rms, 2),
                            "instantaneous_peak_v": round(
                                max((abs(v) for v in volts), default=0.0), 2
                            ),
                            "samples": volts,
                            "sample_rate": sample_rate,
                        }
        except Exception as e:
            print(f"[EventService] Error fetching event data: {e}")
        return None


event_service = EventService(settings.data_dir)
