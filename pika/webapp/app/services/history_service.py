import math
import struct
import os
import json
from collections import deque
from typing import List, Dict, Any, Optional, Tuple
from app.core.config import settings
from app.services.calibration_service import calibration_service
from app.services.config_service import config_service

HEADER_FORMAT = "<QIIII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# Decimated payload layouts (values_per_sample)
VPS_LEGACY_MINMAX = 2
VPS_IEC_VRMS = 3
VPS_IEC_VRMS_FREQ = 6  # ADR-0009: + qtr RMS min/max + freq_centihertz

# Writer flushes 10 IEC intervals per chunk.
TYPICAL_CHUNK_INTERVALS = 10
TYPICAL_IEC_CHUNK_BYTES = HEADER_SIZE + TYPICAL_CHUNK_INTERVALS * 1 * VPS_IEC_VRMS * 2
TYPICAL_IEC_CHUNK_BYTES_V3 = (
    HEADER_SIZE + TYPICAL_CHUNK_INTERVALS * 1 * VPS_IEC_VRMS_FREQ * 2
)
DEFAULT_IEC_RATE_HZ = 5


class HistoryService:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def _scale(self) -> float:
        cal = calibration_service.get_calibration_values()
        adc_vref = float(config_service.get_adc_vref())
        return (adc_vref / 32768.0) * float(cal["transformer_ratio"])

    def _empty(self, **extra) -> Dict[str, Any]:
        payload = {
            "samples": [],
            "samples_min": [],
            "samples_max": [],
            "samples_qtr_min": [],
            "samples_qtr_max": [],
            "frequency_hz": [],
            "timestamps": [],
            "rate": 0,
            "format": "none",
            "rollup_10min": self.get_vrms_10min_rollup(limit=24),
            "window_seconds": 0,
            "source_points": 0,
            "display_points": 0,
            "harmonics_note": (
                "IEC-inspired harmonic trends; accuracy limited by sensor front-end."
            ),
        }
        payload.update(extra)
        return payload

    @staticmethod
    def _valid_header(ts: int, rate: int, count: int, channels: int, vps: int) -> bool:
        if count == 0 or count > 100000:
            return False
        if channels == 0 or channels > 8:
            return False
        if vps not in (VPS_LEGACY_MINMAX, VPS_IEC_VRMS, VPS_IEC_VRMS_FREQ):
            return False
        if rate == 0 or rate > 200000:
            return False
        if ts != 0 and ts < 1_000_000_000:
            return False
        return True

    @staticmethod
    def _chunk_bytes(count: int, channels: int, vps: int) -> int:
        return HEADER_SIZE + count * channels * vps * 2

    def _decimated_path(self) -> str:
        return os.path.join(self.data_dir, "decimated.bin")

    def peek_decimated_rate(self) -> int:
        """Read the last chunk header for the stored IEC/trend rate. Defaults to 5 Hz."""
        path = self._decimated_path()
        if not os.path.exists(path):
            return DEFAULT_IEC_RATE_HZ
        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                if file_size < HEADER_SIZE:
                    return DEFAULT_IEC_RATE_HZ
                rate = self._peek_rate_from_file(f, file_size)
                return rate or DEFAULT_IEC_RATE_HZ
        except OSError:
            return DEFAULT_IEC_RATE_HZ

    def _peek_rate_from_file(self, f, file_size: int) -> int:
        if file_size < HEADER_SIZE:
            return 0
        for chunk in (TYPICAL_IEC_CHUNK_BYTES_V3, TYPICAL_IEC_CHUNK_BYTES):
            if file_size >= chunk:
                f.seek(file_size - chunk)
                hdr = f.read(HEADER_SIZE)
                if len(hdr) == HEADER_SIZE:
                    ts, rate, count, channels, vps = struct.unpack(HEADER_FORMAT, hdr)
                    if (
                        self._valid_header(ts, rate, count, channels, vps)
                        and self._chunk_bytes(count, channels, vps) == chunk
                    ):
                        return int(rate)
        probe_start = max(0, file_size - TYPICAL_IEC_CHUNK_BYTES_V3)
        f.seek(probe_start)
        probe = f.read(file_size - probe_start)
        for offset in range(0, max(0, len(probe) - HEADER_SIZE + 1)):
            ts, rate, count, channels, vps = struct.unpack(
                HEADER_FORMAT, probe[offset:offset + HEADER_SIZE]
            )
            if self._valid_header(ts, rate, count, channels, vps):
                return int(rate)
        return 0

    def get_decimated_data(
        self,
        max_points: int = 20000,
        window_minutes: Optional[int] = None,
        max_display_points: Optional[int] = None,
    ) -> Dict[str, Any]:
        path = self._decimated_path()
        if not os.path.exists(path):
            return self._empty()

        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                if file_size == 0:
                    return self._empty()

                rate_hint = self._peek_rate_from_file(f, file_size) or DEFAULT_IEC_RATE_HZ
                if window_minutes is not None:
                    source_cap = max(1, int(window_minutes) * 60 * int(rate_hint))
                else:
                    source_cap = max(1, int(max_points))

                parsed = self._read_tail_intervals(f, file_size, source_cap)
        except Exception as e:
            print(f"[HistoryService] Error reading history: {e}")
            return self._empty()

        if parsed is None:
            return self._empty()

        (
            vrms,
            mins,
            maxs,
            qtr_mins,
            qtr_maxs,
            freqs,
            timestamps,
            sample_rate,
            fmt,
        ) = parsed
        if not vrms:
            return self._empty()

        source_points = len(vrms)
        display_cap = max_display_points if max_display_points is not None else source_points
        vrms, mins, maxs, qtr_mins, qtr_maxs, freqs, timestamps = self._bucket_intervals(
            vrms, mins, maxs, qtr_mins, qtr_maxs, freqs, timestamps, display_cap
        )

        if timestamps:
            window_seconds = max(0.0, (timestamps[-1] - timestamps[0]) / 1e9)
        else:
            window_seconds = source_points / float(sample_rate or DEFAULT_IEC_RATE_HZ)

        return {
            "samples": [round(v, 2) for v in vrms],
            "samples_min": [round(v, 2) for v in mins],
            "samples_max": [round(v, 2) for v in maxs],
            "samples_qtr_min": [round(v, 2) for v in qtr_mins],
            "samples_qtr_max": [round(v, 2) for v in qtr_maxs],
            "frequency_hz": [round(v, 3) for v in freqs],
            "timestamps": timestamps,
            "rate": sample_rate,
            "format": fmt,
            "rollup_10min": self.get_vrms_10min_rollup(limit=24),
            "window_seconds": round(window_seconds, 1),
            "source_points": source_points,
            "display_points": len(vrms),
            "harmonics_note": (
                "IEC-inspired harmonic trends; accuracy limited by sensor front-end."
            ),
        }

    def _read_tail_intervals(
        self, f, file_size: int, source_cap: int
    ):
        """Read the last source_cap intervals (vps=3 or vps=6 chunks)."""
        scale = self._scale()
        chunk = (
            TYPICAL_IEC_CHUNK_BYTES_V3
            if file_size % TYPICAL_IEC_CHUNK_BYTES_V3 == 0
            else TYPICAL_IEC_CHUNK_BYTES
        )
        needed_bytes = (
            math.ceil(source_cap / TYPICAL_CHUNK_INTERVALS) + 2
        ) * max(TYPICAL_IEC_CHUNK_BYTES_V3, TYPICAL_IEC_CHUNK_BYTES)
        start = max(0, file_size - needed_bytes)

        if file_size % chunk == 0:
            start = start - (start % chunk)
            parsed = self._parse_from(f, start, file_size, source_cap, scale)
            if parsed and parsed[0]:
                return parsed

        scanned = self._scan_and_parse(f, start, file_size, source_cap, scale)
        if scanned and scanned[0]:
            return scanned

        return self._walk_all(f, file_size, source_cap, scale)

    def _parse_chunk_payload(
        self,
        shorts,
        count: int,
        vps: int,
        ts: int,
        rate: int,
        scale: float,
        vrms: List[float],
        mins: List[float],
        maxs: List[float],
        timestamps: List[int],
        qtr_mins: Optional[List[float]] = None,
        qtr_maxs: Optional[List[float]] = None,
        freqs: Optional[List[float]] = None,
    ) -> str:
        bucket_ns = int(1_000_000_000 / rate) if rate else 0
        fmt = "legacy"
        if vps == VPS_IEC_VRMS_FREQ:
            fmt = "iec_vrms_freq"
            for i in range(count):
                base = i * vps
                vrms.append(shorts[base] / 100.0)
                mins.append(shorts[base + 1] / 100.0)
                maxs.append(shorts[base + 2] / 100.0)
                if qtr_mins is not None:
                    qtr_mins.append(shorts[base + 3] / 100.0)
                if qtr_maxs is not None:
                    qtr_maxs.append(shorts[base + 4] / 100.0)
                if freqs is not None:
                    freqs.append(shorts[base + 5] / 100.0)
                timestamps.append(ts + i * bucket_ns)
        elif vps == VPS_IEC_VRMS:
            fmt = "iec_vrms"
            for i in range(count):
                base = i * vps
                v = shorts[base] / 100.0
                vrms.append(v)
                mins.append(shorts[base + 1] / 100.0)
                maxs.append(shorts[base + 2] / 100.0)
                if qtr_mins is not None:
                    qtr_mins.append(v)
                if qtr_maxs is not None:
                    qtr_maxs.append(v)
                if freqs is not None:
                    freqs.append(0.0)
                timestamps.append(ts + i * bucket_ns)
        else:
            for i in range(count):
                base = i * vps
                mn = shorts[base] * scale
                mx = shorts[base + 1] * scale
                mins.append(round(mn, 2))
                maxs.append(round(mx, 2))
                v = round(abs(mx) / (2 ** 0.5), 2)
                vrms.append(v)
                if qtr_mins is not None:
                    qtr_mins.append(v)
                if qtr_maxs is not None:
                    qtr_maxs.append(v)
                if freqs is not None:
                    freqs.append(0.0)
                timestamps.append(ts + i * bucket_ns)
        return fmt

    def _parse_from(self, f, start: int, file_size: int, source_cap: int, scale: float):
        vrms: List[float] = []
        mins: List[float] = []
        maxs: List[float] = []
        qtr_mins: List[float] = []
        qtr_maxs: List[float] = []
        freqs: List[float] = []
        timestamps: List[int] = []
        sample_rate = 0
        fmt = "legacy"
        f.seek(start)
        while f.tell() + HEADER_SIZE <= file_size:
            hdr_data = f.read(HEADER_SIZE)
            if len(hdr_data) < HEADER_SIZE:
                break
            ts, rate, count, channels, vps = struct.unpack(HEADER_FORMAT, hdr_data)
            if not self._valid_header(ts, rate, count, channels, vps):
                return None
            total_values = count * channels * vps
            raw_bytes = f.read(total_values * 2)
            if len(raw_bytes) < total_values * 2:
                break
            shorts = struct.unpack(f"<{total_values}h", raw_bytes)
            fmt = self._parse_chunk_payload(
                shorts, count, vps, ts, rate, scale, vrms, mins, maxs, timestamps,
                qtr_mins, qtr_maxs, freqs,
            )
            sample_rate = rate
        if not vrms:
            return None
        if len(vrms) > source_cap:
            vrms = vrms[-source_cap:]
            mins = mins[-source_cap:]
            maxs = maxs[-source_cap:]
            qtr_mins = qtr_mins[-source_cap:]
            qtr_maxs = qtr_maxs[-source_cap:]
            freqs = freqs[-source_cap:]
            timestamps = timestamps[-source_cap:]
        return (
            vrms, mins, maxs, qtr_mins, qtr_maxs, freqs, timestamps, sample_rate, fmt
        )

    def _scan_and_parse(self, f, start: int, file_size: int, source_cap: int, scale: float):
        """Find the first valid header in a tail window, then parse to EOF."""
        window_end = min(
            file_size, start + TYPICAL_IEC_CHUNK_BYTES_V3 + HEADER_SIZE
        )
        f.seek(start)
        probe = f.read(max(0, window_end - start))
        for offset in range(0, max(0, len(probe) - HEADER_SIZE + 1)):
            hdr = probe[offset:offset + HEADER_SIZE]
            ts, rate, count, channels, vps = struct.unpack(HEADER_FORMAT, hdr)
            if not self._valid_header(ts, rate, count, channels, vps):
                continue
            abs_off = start + offset
            if abs_off + self._chunk_bytes(count, channels, vps) > file_size:
                continue
            parsed = self._parse_from(f, abs_off, file_size, source_cap, scale)
            if parsed and parsed[0]:
                return parsed
        return None

    def _walk_all(self, f, file_size: int, source_cap: int, scale: float):
        """Full-file header walk, keeping only the last source_cap intervals."""
        rows: deque = deque(maxlen=source_cap)
        sample_rate = 0
        fmt = "legacy"
        f.seek(0)
        while f.tell() + HEADER_SIZE <= file_size:
            hdr_data = f.read(HEADER_SIZE)
            if len(hdr_data) < HEADER_SIZE:
                break
            ts, rate, count, channels, vps = struct.unpack(HEADER_FORMAT, hdr_data)
            if not self._valid_header(ts, rate, count, channels, vps):
                break
            total_values = count * channels * vps
            raw_bytes = f.read(total_values * 2)
            if len(raw_bytes) < total_values * 2:
                break
            shorts = struct.unpack(f"<{total_values}h", raw_bytes)
            bucket_ns = int(1_000_000_000 / rate) if rate else 0
            if vps == VPS_IEC_VRMS_FREQ:
                fmt = "iec_vrms_freq"
                for i in range(count):
                    base = i * vps
                    rows.append((
                        shorts[base] / 100.0,
                        shorts[base + 1] / 100.0,
                        shorts[base + 2] / 100.0,
                        shorts[base + 3] / 100.0,
                        shorts[base + 4] / 100.0,
                        shorts[base + 5] / 100.0,
                        ts + i * bucket_ns,
                    ))
            elif vps == VPS_IEC_VRMS:
                fmt = "iec_vrms"
                for i in range(count):
                    base = i * vps
                    v = shorts[base] / 100.0
                    rows.append((
                        v,
                        shorts[base + 1] / 100.0,
                        shorts[base + 2] / 100.0,
                        v,
                        v,
                        0.0,
                        ts + i * bucket_ns,
                    ))
            else:
                for i in range(count):
                    base = i * vps
                    mn = shorts[base] * scale
                    mx = shorts[base + 1] * scale
                    v = round(abs(mx) / (2 ** 0.5), 2)
                    rows.append((
                        v,
                        round(mn, 2),
                        round(mx, 2),
                        v,
                        v,
                        0.0,
                        ts + i * bucket_ns,
                    ))
            sample_rate = rate
        if not rows:
            return None
        vrms, mins, maxs, qtr_mins, qtr_maxs, freqs, timestamps = map(list, zip(*rows))
        return (
            vrms, mins, maxs, qtr_mins, qtr_maxs, freqs, timestamps, sample_rate, fmt
        )

    @staticmethod
    def _bucket_intervals(
        vrms: List[float],
        mins: List[float],
        maxs: List[float],
        qtr_mins: List[float],
        qtr_maxs: List[float],
        freqs: List[float],
        timestamps: List[int],
        display_points: int,
    ):
        n = len(vrms)
        if display_points <= 0 or n <= display_points:
            return vrms, mins, maxs, qtr_mins, qtr_maxs, freqs, timestamps
        bucket = math.ceil(n / display_points)
        out_v: List[float] = []
        out_mn: List[float] = []
        out_mx: List[float] = []
        out_qmn: List[float] = []
        out_qmx: List[float] = []
        out_f: List[float] = []
        out_ts: List[int] = []
        for i in range(0, n, bucket):
            end = min(i + bucket, n)
            chunk_v = vrms[i:end]
            out_v.append(sum(chunk_v) / len(chunk_v))
            out_mn.append(min(mins[i:end]))
            out_mx.append(max(maxs[i:end]))
            out_qmn.append(min(qtr_mins[i:end]))
            out_qmx.append(max(qtr_maxs[i:end]))
            chunk_f = freqs[i:end]
            out_f.append(sum(chunk_f) / len(chunk_f))
            out_ts.append(timestamps[end - 1])
        return out_v, out_mn, out_mx, out_qmn, out_qmx, out_f, out_ts

    def intervals_between(self, start_ns: int, end_ns: int) -> Dict[str, Any]:
        """Full-resolution intervals whose timestamps fall in [start_ns, end_ns].

        Reads decimated.bin.old first, then decimated.bin, so a rotation during
        the window still contributes. Min/max are the AC waveform envelope.
        """
        if end_ns < start_ns:
            return self._interval_payload([], [], [], [])

        merged: List[Tuple[float, float, float, int]] = []
        for name in ("decimated.bin.old", "decimated.bin"):
            path = os.path.join(self.data_dir, name)
            merged.extend(self._intervals_in_file(path, start_ns, end_ns))
        merged.sort(key=lambda row: row[3])

        deduped: List[Tuple[float, float, float, int]] = []
        seen = set()
        for row in merged:
            if row[3] in seen:
                continue
            seen.add(row[3])
            deduped.append(row)
        if not deduped:
            return self._interval_payload([], [], [], [])
        vrms, mins, maxs, timestamps = map(list, zip(*deduped))
        return self._interval_payload(vrms, mins, maxs, timestamps)

    @staticmethod
    def _interval_payload(vrms, mins, maxs, timestamps) -> Dict[str, Any]:
        return {
            "samples": [round(float(v), 2) for v in vrms],
            "samples_min": [round(float(v), 2) for v in mins],
            "samples_max": [round(float(v), 2) for v in maxs],
            "timestamps": [int(ts) for ts in timestamps],
        }

    def _intervals_in_file(
        self, path: str, start_ns: int, end_ns: int
    ) -> List[Tuple[float, float, float, int]]:
        if not os.path.exists(path):
            return []
        rows: List[Tuple[float, float, float, int]] = []
        scale = self._scale()
        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                if file_size < HEADER_SIZE:
                    return []
                pos = self._seek_chunk_at_or_before(f, file_size, start_ns)
                while pos + HEADER_SIZE <= file_size:
                    f.seek(pos)
                    hdr_data = f.read(HEADER_SIZE)
                    if len(hdr_data) < HEADER_SIZE:
                        break
                    ts, rate, count, channels, vps = struct.unpack(
                        HEADER_FORMAT, hdr_data
                    )
                    nbytes = count * channels * vps * 2
                    chunk_ok = (
                        self._valid_header(ts, rate, count, channels, vps)
                        and nbytes > 0
                        and pos + HEADER_SIZE + nbytes <= file_size
                    )
                    if not chunk_ok:
                        nxt = self._find_next_valid_chunk(f, file_size, pos + 1)
                        if nxt is None:
                            break
                        pos = nxt
                        continue
                    bucket_ns = int(1_000_000_000 / rate) if rate else 0
                    chunk_end = ts + max(count - 1, 0) * bucket_ns
                    if chunk_end < start_ns:
                        pos += HEADER_SIZE + nbytes
                        continue
                    if ts > end_ns:
                        break
                    raw = f.read(nbytes)
                    if len(raw) < nbytes:
                        break
                    shorts = struct.unpack(f"<{count * channels * vps}h", raw)
                    vrms: List[float] = []
                    mins: List[float] = []
                    maxs: List[float] = []
                    timestamps: List[int] = []
                    self._parse_chunk_payload(
                        shorts, count, vps, ts, rate, scale,
                        vrms, mins, maxs, timestamps,
                    )
                    for v, mn, mx, stamp in zip(vrms, mins, maxs, timestamps):
                        if start_ns <= stamp <= end_ns:
                            rows.append((v, mn, mx, stamp))
                    pos += HEADER_SIZE + nbytes
        except Exception as e:
            print(f"[HistoryService] Error reading {path}: {e}")
        return rows

    def get_harmonics_trend(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Read rotate-capped harmonics.jsonl (+ .old) newest-last."""
        rows: List[Dict[str, Any]] = []
        for name in ("harmonics.jsonl.old", "harmonics.jsonl"):
            path = os.path.join(self.data_dir, name)
            if not os.path.exists(path):
                continue
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
            except OSError as e:
                print(f"[HistoryService] Error reading {path}: {e}")
        if len(rows) > limit:
            rows = rows[-limit:]
        return rows

    def _find_next_valid_chunk(
        self, f, file_size: int, start_pos: int
    ) -> Optional[int]:
        """Resync after corruption: skip holes and find the next parseable chunk."""
        pos = max(0, start_pos)
        chunk = TYPICAL_IEC_CHUNK_BYTES_V3
        while pos + HEADER_SIZE <= file_size:
            f.seek(pos)
            # Fast-skip zero runs common after a torn write / hole.
            probe = f.read(min(4096, file_size - pos))
            if not probe:
                return None
            nonzero = next((i for i, b in enumerate(probe) if b != 0), None)
            if nonzero is None:
                pos += len(probe)
                continue
            pos += nonzero
            f.seek(pos)
            hdr = f.read(HEADER_SIZE)
            if len(hdr) < HEADER_SIZE:
                return None
            ts, rate, count, channels, vps = struct.unpack(HEADER_FORMAT, hdr)
            nbytes = count * channels * vps * 2
            if (
                self._valid_header(ts, rate, count, channels, vps)
                and nbytes > 0
                and pos + HEADER_SIZE + nbytes <= file_size
                # Prefer the standard IEC flush size; still accept other valid sizes.
                and (
                    HEADER_SIZE + nbytes == chunk
                    or self._chunk_bytes(count, channels, vps) == HEADER_SIZE + nbytes
                )
            ):
                return pos
            pos += 1
        return None

    def _seek_chunk_at_or_before(self, f, file_size: int, start_ns: int) -> int:
        """Locate a chunk at or before start_ns (binary search if aligned)."""
        if file_size % TYPICAL_IEC_CHUNK_BYTES_V3 == 0:
            chunk = TYPICAL_IEC_CHUNK_BYTES_V3
        elif file_size % TYPICAL_IEC_CHUNK_BYTES == 0:
            chunk = TYPICAL_IEC_CHUNK_BYTES
        else:
            return self._seek_unaligned_near(f, file_size, start_ns)
        if file_size < chunk:
            return 0
        n = file_size // chunk
        lo, hi = 0, n
        while lo < hi:
            mid = (lo + hi) // 2
            f.seek(mid * chunk)
            hdr = f.read(HEADER_SIZE)
            if len(hdr) < HEADER_SIZE:
                return 0
            ts, rate, count, channels, vps = struct.unpack(HEADER_FORMAT, hdr)
            if not self._valid_header(ts, rate, count, channels, vps):
                return 0
            if self._chunk_bytes(count, channels, vps) != chunk:
                return 0
            bucket_ns = int(1_000_000_000 / rate) if rate else 0
            chunk_end = ts + max(count - 1, 0) * bucket_ns
            if chunk_end < start_ns:
                lo = mid + 1
            else:
                hi = mid
        return max(0, lo - 1) * chunk

    def _seek_unaligned_near(self, f, file_size: int, start_ns: int) -> int:
        """Coarse seek across holey/unaligned files, then resync from that point."""
        step = TYPICAL_IEC_CHUNK_BYTES * 2048
        best = 0
        pos = 0
        while pos < file_size:
            synced = self._find_next_valid_chunk(f, file_size, pos)
            if synced is None:
                break
            f.seek(synced)
            hdr = f.read(HEADER_SIZE)
            if len(hdr) < HEADER_SIZE:
                break
            ts, rate, count, channels, vps = struct.unpack(HEADER_FORMAT, hdr)
            if not self._valid_header(ts, rate, count, channels, vps):
                pos = synced + 1
                continue
            if ts > start_ns:
                return best
            best = synced
            pos = synced + step
        return best

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
